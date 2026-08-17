"""
Complete is_relevant and targets_india for ALL Creators
=========================================================
Ensures 100% of creators in creator_intel.db have:
1. is_relevant (Financial / Stock Market relevance)
2. relevance_confidence
3. targets_india (Indian audience targeting)
4. india_confidence

Also purges any non-stockmarket creators or general talk shows / podcasts.
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
from app.models.database import Creator, PlatformProfile
from app.schemas.creator import RawProfile
from app.llm.client import LLMClient
from app.llm.preprocessor import TextPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("complete_relevance_india.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

INDIA_SIGNALS = {
    "languages": ["hindi", "hinglish", "tamil", "telugu", "kannada", "malayalam",
                   "bengali", "marathi", "gujarati", "punjabi", "odia", "assamese",
                   "urdu", "mixed"],
    "currency_keywords": ["inr", "rupee", "rs.", "rs ", "₹", "lakh", "crore", "lakhs", "crores"],
    "india_keywords": ["india", "indian", "bharat", "bharatiya", "desi",
                       "nse", "bse", "nifty", "sensex", "sebi",
                       "demat", "zerodha", "groww", "angel one", "upstox", "motilal oswal",
                       "icici direct", "hdfc securities", "sharekhan", "5paisa",
                       "kotak securities", "sbi", "lic", "mutual fund india",
                       "smallcase", "kite", "coin by zerodha"],
    "excluded_markets": ["nasdaq", "nyse", "s&p 500", "dow jones", "wall street",
                         "forex usd", "ftse", "dax", "shanghai", "hang seng"],
}

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


def rule_based_relevance_check(text: str, category: str | None) -> tuple[bool | None, float]:
    """Rule check for stock market relevance."""
    text_lower = text.lower()
    fin_hits = sum(1 for kw in FINANCE_KEYWORDS if kw in text_lower)
    non_fin_hits = sum(1 for kw in NON_FINANCE_KEYWORDS if kw in text_lower)
    
    if category and category not in ("", "Equity"):
        fin_hits += 2
        
    if fin_hits >= 2 and non_fin_hits == 0:
        return True, min(0.95, 0.7 + fin_hits * 0.05)
    elif non_fin_hits >= 1 and fin_hits == 0:
        return False, min(0.9, 0.6 + non_fin_hits * 0.1)
    elif non_fin_hits >= 2 and fin_hits < 2:
        return False, 0.85
    return None, 0.0


def rule_based_india_check(text: str, language: str | None) -> tuple[bool | None, float]:
    """Rule check for Indian audience targeting."""
    text_lower = text.lower()
    india_score = 0
    for kw in INDIA_SIGNALS["india_keywords"]:
        if kw in text_lower:
            india_score += 2
    for kw in INDIA_SIGNALS["currency_keywords"]:
        if kw in text_lower:
            india_score += 3
    if language and language.lower() in INDIA_SIGNALS["languages"]:
        india_score += 5

    anti_score = sum(2 for kw in INDIA_SIGNALS["excluded_markets"] if kw in text_lower)
    net = india_score - anti_score

    if net >= 4:
        return True, min(0.95, 0.65 + net * 0.05)
    elif net <= -3:
        return False, min(0.9, 0.5 + abs(net) * 0.05)
    return None, 0.0


async def complete_relevance_and_india():
    logger.info("Starting complete is_relevant and targets_india pass across all creators...")
    llm = LLMClient()
    preprocessor = TextPreprocessor()

    async with async_session_factory() as db:
        res = await db.execute(select(Creator).order_by(Creator.id))
        creators = res.scalars().all()
        total = len(creators)
        logger.info("Total creators in database: %d", total)

        processed = 0
        purge_list = []
        india_true_count = 0
        india_false_count = 0

        for i, creator in enumerate(creators, 1):
            pp_res = await db.execute(
                select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
            )
            pps = pp_res.scalars().all()
            pp = pps[0] if pps else None

            if not pp:
                continue

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

            # 1. Relevance check
            is_rel, rel_conf = rule_based_relevance_check(combined_text, creator.primary_category)
            
            # 2. India check
            is_ind, ind_conf = rule_based_india_check(combined_text, creator.primary_language)

            # If either is uncertain, call LLM
            if is_rel is None or is_ind is None:
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
                        from scripts.enrich_creators import build_relevance_and_india_prompt
                        resp = await llm.classify(
                            system_prompt=build_relevance_and_india_prompt(),
                            user_input=llm_input,
                        )
                        if resp.success and resp.parsed_result:
                            res_data = resp.parsed_result
                            if is_rel is None:
                                is_rel = res_data.get("is_relevant", True)
                                rel_conf = res_data.get("relevance_confidence", 0.5)
                            if is_ind is None:
                                is_ind = res_data.get("targets_india", True)
                                ind_conf = res_data.get("india_confidence", 0.5)
                    except Exception as e:
                        logger.warning("LLM error for #%d: %s", creator.id, e)
                        if is_rel is None:
                            is_rel = True
                            rel_conf = 0.5
                        if is_ind is None:
                            is_ind = True
                            ind_conf = 0.5
                else:
                    if is_rel is None:
                        is_rel = True
                        rel_conf = 0.5
                    if is_ind is None:
                        is_ind = True
                        ind_conf = 0.5

            # Set fields on creator
            creator.is_relevant = is_rel
            creator.relevance_confidence = rel_conf
            creator.targets_india = is_ind
            creator.india_confidence = ind_conf

            if is_rel is False:
                purge_list.append((creator.id, creator.name, creator.primary_category))
            
            if is_ind:
                india_true_count += 1
            else:
                india_false_count += 1

            processed += 1
            if processed % 50 == 0:
                await db.commit()
                logger.info("Processed %d/%d creators...", processed, total)

        await db.commit()
        logger.info("==========================================")
        logger.info("RELEVANCE & INDIA AUDIENCE CHECK COMPLETE")
        logger.info("Total Evaluated: %d", total)
        logger.info("Relevant Stock Market Creators: %d", total - len(purge_list))
        logger.info("Non-Stockmarket / Podcast Channels Flagged for Purge: %d", len(purge_list))
        logger.info("Targets India: %d | Does Not Target India: %d", india_true_count, india_false_count)
        logger.info("==========================================")

        if purge_list:
            logger.info("Purging %d non-stockmarket / podcast creators...", len(purge_list))
            for item in purge_list:
                cid = item[0]
                await db.execute(delete(Creator).where(Creator.id == cid))
            await db.commit()
            logger.info("Purged %d non-stockmarket / podcast creators successfully!", len(purge_list))

        final_res = await db.execute(select(Creator))
        final_total = len(final_res.scalars().all())
        logger.info("FINAL CLEAN DATABASE COUNT: %d Relevant Stock Market Creators", final_total)


if __name__ == "__main__":
    asyncio.run(complete_relevance_and_india())
