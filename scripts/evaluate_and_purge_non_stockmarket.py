"""
Evaluate and Purge Non-Stockmarket Creators
===========================================
1. Evaluates financial/stockmarket relevance (is_relevant) for all creators in creator_intel.db.
2. Identifies all non-relevant creators (channels focusing on tech reviews, gaming, comedy, daily vlogs, general non-financial apps/deals).
3. Deletes non-stockmarket creators from creator_intel.db to ensure 100% database purity.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete, text
from app.database.session import async_session_factory
from app.models.database import Creator, PlatformProfile, SocialLink, BrokerAssociation, CreatorCategory, Video, Post
from app.schemas.creator import RawProfile
from app.services.enrichment import EnrichmentEngine
from app.llm.client import LLMClient
from app.llm.preprocessor import TextPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("purge_non_stockmarket.log", encoding="utf-8"),
    ],
)
logger = logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r"https?://[^\s<>\"'\\)]+", re.IGNORECASE)

FINANCE_KEYWORDS = [
    "stock market", "share market", "trading", "investing", "mutual fund",
    "nifty", "sensex", "f&o", "options trading", "intraday", "swing trade",
    "portfolio", "demat", "ipo", "equity", "fundamental analysis",
    "technical analysis", "candlestick", "chart pattern", "price action",
    "sip", "dividend", "stock pick", "multibagger", "penny stock",
    "crypto", "bitcoin", "forex", "algo trading", "smallcase",
    "zerodha", "groww", "angel one", "upstox", "financial planning",
    "tax saving", "insurance", "personal finance", "wealth management",
    "finance", "trader", "investor", "bull", "bear", "market news",
]

NON_FINANCE_KEYWORDS = [
    "gaming", "gameplay", "pubg", "free fire", "bgmi", "gta", "minecraft",
    "tech review", "unboxing", "smartphone", "mobile review", "gadget",
    "comedy", "roast", "funny", "memes", "prank",
    "vlog", "daily vlog", "travel vlog", "family vlog",
    "movie review", "bollywood", "song", "dance", "entertainment",
    "cooking", "recipe", "kitchen", "food vlog",
    "beauty", "makeup", "fashion", "haircare",
    "looting", "earn money app", "refer and earn app", "paytm cash",
    "podcast", "talks", "josh talks", "raj shamani", "figuring out",
    "beerbiceps", "ranveer allahbadia", "the ranveer show", "realhit",
    "untold stories", "trippy story", "interview show", "talk show",
]


def check_rule_relevance(text: str, category: str | None) -> tuple[bool | None, float]:
    """Fast rule check for stock market relevance."""
    text_lower = text.lower()
    fin_hits = sum(1 for kw in FINANCE_KEYWORDS if kw in text_lower)
    non_fin_hits = sum(1 for kw in NON_FINANCE_KEYWORDS if kw in text_lower)
    
    if category and category not in ("", "Equity"):
        fin_hits += 2
        
    if fin_hits >= 2 and non_fin_hits == 0:
        return True, min(0.95, 0.7 + fin_hits * 0.05)
    elif non_fin_hits >= 2 and fin_hits == 0:
        return False, min(0.9, 0.6 + non_fin_hits * 0.1)
    return None, 0.0


async def evaluate_and_purge():
    logger.info("Starting stock market relevance evaluation and cleanup...")
    llm = LLMClient()
    preprocessor = TextPreprocessor()

    async with async_session_factory() as db:
        # Fetch all creators
        res = await db.execute(select(Creator).order_by(Creator.id))
        creators = res.scalars().all()
        total = len(creators)
        logger.info("Total creators in database: %d", total)

        evaluated_count = 0
        purge_list = []

        for i, creator in enumerate(creators, 1):
            # Check platform profile
            pp_res = await db.execute(
                select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
            )
            pps = pp_res.scalars().all()
            pp = pps[0] if pps else None

            if not pp:
                continue

            # Build text for checking
            bio_text = pp.bio or ""
            desc_text = pp.description or ""
            raw_data = pp.raw_data or {}
            video_titles = []

            if isinstance(raw_data, dict):
                videos = raw_data.get("videos", [])
                if isinstance(videos, list):
                    for v in videos[:10]:
                        if isinstance(v, dict) and v.get("title"):
                            video_titles.append(v.get("title"))

            combined_text = f"{creator.name} {bio_text} {desc_text} {' '.join(video_titles)}"

            # Rule check first
            is_rel, conf = check_rule_relevance(combined_text, creator.primary_category)

            if is_rel is None:
                # Need LLM check for ambiguous cases
                raw_profile = RawProfile(
                    platform=pp.platform,
                    platform_user_id=pp.platform_user_id or "",
                    username=pp.username or creator.name,
                    display_name=pp.display_name or creator.name,
                    bio=bio_text,
                    description=desc_text,
                    followers=pp.followers,
                    recent_video_titles=video_titles,
                )
                llm_input = preprocessor.prepare_llm_input(raw_profile)
                if llm_input.strip():
                    try:
                        from app.llm.prompts import build_relevance_prompt
                        resp = await llm.classify(
                            system_prompt=build_relevance_prompt(),
                            user_input=llm_input,
                        )
                        if resp.success and resp.parsed_result:
                            is_rel = resp.parsed_result.get("is_financial_creator", True)
                            conf = resp.parsed_result.get("relevance_score", 0.5)
                        else:
                            is_rel = True
                            conf = 0.5
                    except Exception as e:
                        logger.warning("LLM call failed for #%d: %s", creator.id, e)
                        is_rel = True
                        conf = 0.4

            # Update creator flags
            creator.is_relevant = is_rel
            creator.relevance_confidence = conf

            if is_rel is False:
                purge_list.append((creator.id, creator.name, creator.primary_category))
                logger.info(" Marked Non-Stockmarket Creator #%d: '%s' (Category: %s)", creator.id, creator.name, creator.primary_category)

            evaluated_count += 1
            if evaluated_count % 50 == 0:
                await db.commit()
                logger.info("Evaluated %d/%d creators...", evaluated_count, total)

        await db.commit()
        logger.info("==========================================")
        logger.info("RELEVANCE EVALUATION SUMMARY")
        logger.info("Total Evaluated: %d", total)
        logger.info("Relevant Stock Market Creators: %d", total - len(purge_list))
        logger.info("Non-Stockmarket Creators Identified: %d", len(purge_list))
        logger.info("==========================================")

        if purge_list:
            logger.info("Purging %d non-stockmarket creators from database...", len(purge_list))
            purge_ids = [item[0] for item in purge_list]
            for cid in purge_ids:
                await db.execute(delete(Creator).where(Creator.id == cid))
            await db.commit()
            logger.info("Successfully purged %d non-stockmarket creators!", len(purge_ids))

        # Final count check
        final_res = await db.execute(select(Creator))
        final_creators = len(final_res.scalars().all())
        logger.info("Final Clean Database Count: %d Relevant Stock Market Creators", final_creators)


if __name__ == "__main__":
    asyncio.run(evaluate_and_purge())
