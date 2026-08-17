"""
Comprehensive Creator Enrichment Script
========================================
Enriches all creators in the database with:
1. Financial relevance check (is_relevant) - are they genuinely stock market / finance creators?
2. Indian audience targeting check (targets_india) - do they target Indian audiences?
3. Language detection for creators missing it (136 currently)
4. Contact extraction & broker detection refresh

Resumable: tracks progress via a JSON checkpoint file.
Rate-limit aware: sleeps on 429 errors, commits every 10 creators.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete, text
from app.config.settings import get_settings
from app.extractors.contact import ContactExtractor
from app.extractors.category import CategoryExtractor
from app.database.session import async_session_factory
from app.models.database import (
    Creator,
    PlatformProfile,
    SocialLink,
    BrokerAssociation,
)
from app.schemas.creator import RawProfile, ContactInfo
from app.services.enrichment import EnrichmentEngine
from app.llm.client import LLMClient
from app.llm.preprocessor import TextPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("enrichment_log.txt", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "enrichment_checkpoint.json"
URL_REGEX = re.compile(r"https?://[^\s<>\"'\\)]+", re.IGNORECASE)

# Indian audience detection signals
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


def build_relevance_and_india_prompt() -> str:
    """Combined prompt for financial relevance + Indian audience check."""
    return """You are a strict auditor for an Indian Financial Influencer & Stock Market Creator database.

You have TWO tasks:

## TASK 1: Financial Relevance Check
Determine if this creator is GENUINELY dedicated to Financial / Stock Market / Trading / Investing / Personal Finance content.

RELEVANT (is_relevant = true):
- Stock market trading (F&O, Intraday, Options, Swing Trading)
- Long-term investing, Equity research, Multibaggers, IPO analysis
- Personal finance, Mutual funds, SIP, Tax saving, Insurance, Budgeting
- Crypto / Forex trading education
- Financial education, Demat tutorials, Broker reviews
- Market news and analysis (if primarily financial)

NOT RELEVANT (is_relevant = false):
- General mainstream news (Aaj Tak, NDTV, ABP, Zee News)
- Political commentary / socio-economic debates  
- General motivation / life coaching (unless specifically financial)
- Tech reviews, coding tutorials, gadgets
- Entertainment, comedy, Bollywood, cricket, gaming, vlogs
- Channels that only occasionally mention economy/budget among 90% non-financial content
- Real estate agents (unless also covering financial instruments)
- MLM / network marketing schemes

## TASK 2: Indian Audience Check
Determine if this creator primarily targets INDIAN audiences.

TARGETS INDIA (targets_india = true):
- Content is in Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, or Hinglish
- References Indian markets (NSE, BSE, NIFTY, SENSEX, SEBI)
- Mentions Indian brokers (Zerodha, Groww, Angel One, Upstox, ICICI Direct, etc.)
- Uses Indian currency (INR, ₹, Rs., lakhs, crores)
- Discusses Indian regulations, Indian mutual funds, Indian stocks
- Bio/description explicitly mentions India

DOES NOT TARGET INDIA (targets_india = false):
- Content primarily about US/global markets (NYSE, NASDAQ, S&P 500)
- Uses USD, EUR, GBP exclusively
- No Indian market references whatsoever
- Language is exclusively non-Indian (pure English with US market focus)

Note: English content about Indian markets should still be targets_india = true.

Return ONLY valid JSON:
{
  "is_relevant": true,
  "relevance_confidence": 0.92,
  "targets_india": true,
  "india_confidence": 0.88,
  "reasoning": "Brief explanation covering both decisions"
}"""


def load_checkpoint() -> dict:
    """Load enrichment checkpoint."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"processed_ids": [], "stats": {"relevant": 0, "not_relevant": 0, "india": 0, "not_india": 0, "language_filled": 0, "errors": 0}}


def save_checkpoint(data: dict):
    """Save enrichment checkpoint."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def rule_based_india_check(profile_text: str, language: str | None) -> tuple[bool | None, float]:
    """Quick rule-based pre-check for Indian audience targeting.
    
    Returns (is_india, confidence) or (None, 0) if uncertain.
    """
    text_lower = profile_text.lower()
    
    # Strong Indian signals
    india_score = 0
    for kw in INDIA_SIGNALS["india_keywords"]:
        if kw in text_lower:
            india_score += 2
    for kw in INDIA_SIGNALS["currency_keywords"]:
        if kw in text_lower:
            india_score += 3
    
    # Language signal
    if language and language.lower() in INDIA_SIGNALS["languages"]:
        india_score += 5
    
    # Anti-signals (non-Indian markets)
    anti_score = 0
    for kw in INDIA_SIGNALS["excluded_markets"]:
        if kw in text_lower:
            anti_score += 2
    
    net = india_score - anti_score
    if net >= 5:
        return True, min(0.95, 0.6 + net * 0.05)
    elif net <= -3:
        return False, min(0.9, 0.5 + abs(net) * 0.05)
    
    return None, 0  # Uncertain, need LLM


def rule_based_relevance_check(profile_text: str, category: str | None) -> tuple[bool | None, float]:
    """Quick rule-based pre-check for financial relevance.
    
    Returns (is_relevant, confidence) or (None, 0) if uncertain.
    """
    FINANCE_KEYWORDS = [
        "stock market", "share market", "trading", "investing", "mutual fund",
        "nifty", "sensex", "f&o", "options trading", "intraday", "swing trade",
        "portfolio", "demat", "ipo", "equity", "fundamental analysis",
        "technical analysis", "candlestick", "chart pattern", "price action",
        "sip", "dividend", "stock pick", "multibagger", "penny stock",
        "crypto", "bitcoin", "forex", "algo trading", "smallcase",
        "zerodha", "groww", "angel one", "upstox", "financial planning",
        "tax saving", "insurance", "personal finance", "wealth management",
    ]
    
    NON_FINANCE_KEYWORDS = [
        "comedy", "vlog", "entertainment", "gaming", "cricket", "bollywood",
        "cooking", "recipe", "fashion", "beauty", "makeup", "fitness",
        "travel", "photography", "music video", "lyrics", "movie review",
        "tech review", "unboxing", "smartphone", "laptop review",
        "political debate", "general knowledge", "upsc", "ssc", "government exam",
    ]
    
    text_lower = profile_text.lower()
    
    fin_count = sum(1 for kw in FINANCE_KEYWORDS if kw in text_lower)
    non_fin_count = sum(1 for kw in NON_FINANCE_KEYWORDS if kw in text_lower)
    
    # If strong finance category already assigned
    if category and category not in ("", "Equity"):
        fin_count += 3
    
    if fin_count >= 3 and non_fin_count == 0:
        return True, min(0.95, 0.7 + fin_count * 0.03)
    elif non_fin_count >= 2 and fin_count == 0:
        return False, min(0.9, 0.6 + non_fin_count * 0.05)
    
    return None, 0  # Uncertain


async def enrich_all():
    """Main enrichment loop."""
    settings = get_settings()
    llm = LLMClient()
    preprocessor = TextPreprocessor()
    contact_extractor = ContactExtractor()
    enricher = EnrichmentEngine()
    
    checkpoint = load_checkpoint()
    processed_ids = set(checkpoint["processed_ids"])
    stats = checkpoint["stats"]
    
    logger.info("Starting enrichment. Already processed: %d creators", len(processed_ids))
    
    async with async_session_factory() as db:
        # 1. Add new columns if they don't exist
        try:
            await db.execute(text("ALTER TABLE creators ADD COLUMN is_relevant BOOLEAN DEFAULT NULL"))
            await db.commit()
            logger.info("Added 'is_relevant' column to creators table")
        except Exception:
            await db.rollback()
            logger.info("'is_relevant' column already exists")
        
        try:
            await db.execute(text("ALTER TABLE creators ADD COLUMN relevance_confidence REAL DEFAULT NULL"))
            await db.commit()
            logger.info("Added 'relevance_confidence' column to creators table")
        except Exception:
            await db.rollback()
            logger.info("'relevance_confidence' column already exists")
        
        try:
            await db.execute(text("ALTER TABLE creators ADD COLUMN targets_india BOOLEAN DEFAULT NULL"))
            await db.commit()
            logger.info("Added 'targets_india' column to creators table")
        except Exception:
            await db.rollback()
            logger.info("'targets_india' column already exists")
        
        try:
            await db.execute(text("ALTER TABLE creators ADD COLUMN india_confidence REAL DEFAULT NULL"))
            await db.commit()
            logger.info("Added 'india_confidence' column to creators table")
        except Exception:
            await db.rollback()
            logger.info("'india_confidence' column already exists")
        
        # 2. Fetch all creators
        result = await db.execute(select(Creator).order_by(Creator.id))
        creators = result.scalars().all()
        total = len(creators)
        logger.info("Total creators to process: %d (skipping %d already done)", total, len(processed_ids))
        
        batch_count = 0
        
        for i, creator in enumerate(creators):
            if creator.id in processed_ids:
                continue
            
            logger.info("[%d/%d] Processing creator #%d: %s", i + 1, total, creator.id, creator.name)
            
            try:
                # Get platform profiles
                pp_res = await db.execute(
                    select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
                )
                profiles = pp_res.scalars().all()
                pp = profiles[0] if profiles else None
                
                if not pp:
                    logger.warning("  No platform profile for creator #%d, skipping", creator.id)
                    processed_ids.add(creator.id)
                    continue
                
                # Build combined text for analysis
                bio_text = pp.bio or ""
                desc_text = pp.description or ""
                
                # Get video titles from raw_data
                video_titles = []
                video_descs = []
                links = []
                raw_data = pp.raw_data or {}
                
                if isinstance(raw_data, dict):
                    videos = raw_data.get("videos", [])
                    if isinstance(videos, list):
                        for v in videos[:10]:
                            if isinstance(v, dict):
                                title = v.get("title", "")
                                if title:
                                    video_titles.append(title)
                                vdesc = v.get("description", "")
                                if vdesc:
                                    video_descs.append(vdesc)
                                    for url in URL_REGEX.findall(vdesc):
                                        clean_u = url.rstrip(".,;)\"'>")
                                        if clean_u not in links:
                                            links.append(clean_u)
                
                # Build RawProfile for preprocessor
                raw_profile = RawProfile(
                    platform=pp.platform,
                    platform_user_id=pp.platform_user_id or "",
                    username=pp.username or creator.name,
                    display_name=pp.display_name or creator.name,
                    bio=bio_text,
                    description=desc_text + ("\n" + "\n".join(video_descs[:3]) if video_descs else ""),
                    followers=pp.followers,
                    recent_video_titles=video_titles,
                    recent_video_descriptions=video_descs[:5],
                    links=links,
                )
                
                combined_text = f"{creator.name} {bio_text} {desc_text} {' '.join(video_titles)}"
                
                # ============================================
                # STEP A: Relevance + India Check
                # ============================================
                
                # Try rule-based first
                rule_relevant, rule_rel_conf = rule_based_relevance_check(combined_text, creator.primary_category)
                rule_india, rule_india_conf = rule_based_india_check(combined_text, creator.primary_language)
                
                need_llm = (rule_relevant is None) or (rule_india is None)
                
                if need_llm:
                    # Use LLM for uncertain cases
                    llm_input = preprocessor.prepare_llm_input(raw_profile)
                    
                    if llm_input.strip():
                        try:
                            response = await llm.classify(
                                system_prompt=build_relevance_and_india_prompt(),
                                user_input=llm_input,
                            )
                            
                            if response.success and response.parsed_result:
                                result_data = response.parsed_result
                                
                                is_relevant = result_data.get("is_relevant", True)
                                rel_conf = result_data.get("relevance_confidence", 0.5)
                                targets_india = result_data.get("targets_india", True)
                                india_conf = result_data.get("india_confidence", 0.5)
                                reasoning = result_data.get("reasoning", "")
                                
                                # Override only uncertain rule results
                                if rule_relevant is None:
                                    rule_relevant = is_relevant
                                    rule_rel_conf = rel_conf
                                if rule_india is None:
                                    rule_india = targets_india
                                    rule_india_conf = india_conf
                                
                                logger.info("  LLM: relevant=%s (%.2f), india=%s (%.2f) | %s",
                                           is_relevant, rel_conf, targets_india, india_conf, reasoning[:100])
                            else:
                                logger.warning("  LLM call unsuccessful, using rule-based defaults")
                                if rule_relevant is None:
                                    rule_relevant = True  # Assume relevant since they were discovered via finance keywords
                                    rule_rel_conf = 0.5
                                if rule_india is None:
                                    rule_india = True  # Assume India since pipeline focuses on India
                                    rule_india_conf = 0.5
                                    
                        except Exception as e:
                            error_str = str(e)
                            if "429" in error_str or "rate" in error_str.lower():
                                logger.warning("  Rate limited, waiting 60s...")
                                await asyncio.sleep(60)
                                # Retry once
                                try:
                                    response = await llm.classify(
                                        system_prompt=build_relevance_and_india_prompt(),
                                        user_input=llm_input,
                                    )
                                    if response.success and response.parsed_result:
                                        result_data = response.parsed_result
                                        if rule_relevant is None:
                                            rule_relevant = result_data.get("is_relevant", True)
                                            rule_rel_conf = result_data.get("relevance_confidence", 0.5)
                                        if rule_india is None:
                                            rule_india = result_data.get("targets_india", True)
                                            rule_india_conf = result_data.get("india_confidence", 0.5)
                                except Exception as e2:
                                    logger.error("  Retry also failed: %s", e2)
                            else:
                                logger.error("  LLM error: %s", e)
                            
                            # Fallback defaults
                            if rule_relevant is None:
                                rule_relevant = True
                                rule_rel_conf = 0.4
                            if rule_india is None:
                                rule_india = True
                                rule_india_conf = 0.4
                else:
                    logger.info("  Rule-based: relevant=%s (%.2f), india=%s (%.2f)",
                               rule_relevant, rule_rel_conf, rule_india, rule_india_conf)
                
                # Update creator
                await db.execute(
                    text("UPDATE creators SET is_relevant = :rel, relevance_confidence = :rc, "
                         "targets_india = :ti, india_confidence = :ic WHERE id = :cid"),
                    {"rel": rule_relevant, "rc": rule_rel_conf,
                     "ti": rule_india, "ic": rule_india_conf, "cid": creator.id}
                )
                
                if rule_relevant:
                    stats["relevant"] = stats.get("relevant", 0) + 1
                else:
                    stats["not_relevant"] = stats.get("not_relevant", 0) + 1
                
                if rule_india:
                    stats["india"] = stats.get("india", 0) + 1
                else:
                    stats["not_india"] = stats.get("not_india", 0) + 1
                
                # ============================================
                # STEP B: Fill missing language
                # ============================================
                if not creator.primary_language:
                    llm_input = preprocessor.prepare_llm_input(raw_profile)
                    if llm_input.strip():
                        try:
                            from app.llm.prompts import build_language_prompt
                            lang_response = await llm.classify(
                                system_prompt=build_language_prompt(),
                                user_input=llm_input,
                            )
                            if lang_response.success and lang_response.parsed_result:
                                lang = lang_response.parsed_result.get("primary_language")
                                lang_conf = lang_response.parsed_result.get("confidence", 0.5)
                                if lang:
                                    creator.primary_language = lang
                                    creator.language_confidence = lang_conf
                                    stats["language_filled"] = stats.get("language_filled", 0) + 1
                                    logger.info("  Language detected: %s (%.2f)", lang, lang_conf)
                        except Exception as e:
                            logger.warning("  Language detection failed: %s", str(e)[:100])
                
                # ============================================
                # STEP C: Refresh contacts & broker detection
                # ============================================
                contacts = contact_extractor.extract(
                    bio=raw_profile.bio or "",
                    description=raw_profile.description or "",
                    video_descriptions=raw_profile.recent_video_descriptions[:5],
                    links=raw_profile.links,
                )
                
                # Update creator contact info if missing
                if contacts.emails and not creator.email:
                    creator.email = contacts.emails[0]
                if contacts.phones and not creator.phone:
                    creator.phone = contacts.phones[0]
                if contacts.website and not creator.website:
                    creator.website = contacts.website[0]
                
                # Refresh broker associations
                brokers = enricher.detect_brokers(raw_profile, contacts)
                await db.execute(
                    delete(BrokerAssociation).where(BrokerAssociation.creator_id == creator.id)
                )
                for b in brokers:
                    db.add(BrokerAssociation(
                        creator_id=creator.id,
                        broker_name=b.broker_name,
                        relationship_type=b.relationship_type.value if b.relationship_type else "mention_only",
                        confidence=b.confidence,
                        detection_method=b.detection_method.value,
                        evidence=b.evidence,
                        evidence_urls=b.evidence_urls,
                    ))
                
                # Refresh social links
                await db.execute(
                    delete(SocialLink).where(SocialLink.creator_id == creator.id)
                )
                link_map = {
                    "email": [(e, e) for e in contacts.emails],
                    "phone": [(p, p) for p in contacts.phones],
                    "telegram": [(u, u) for u in contacts.telegram],
                    "whatsapp": [(u, u) for u in contacts.whatsapp],
                    "linkedin": [(u, u) for u in contacts.linkedin],
                    "twitter": [(u, u) for u in contacts.twitter],
                    "facebook": [(u, u) for u in contacts.facebook],
                    "discord": [(u, u) for u in contacts.discord],
                    "website": [(u, u) for u in contacts.website],
                    "linktree": [(u, u) for u in contacts.linktree],
                    "beacons": [(u, u) for u in contacts.beacons],
                }
                for platform_key, entries in link_map.items():
                    for url, val in entries:
                        db.add(SocialLink(
                            creator_id=creator.id,
                            platform=platform_key,
                            url=url,
                            value=val,
                        ))
                
                # Track progress
                processed_ids.add(creator.id)
                batch_count += 1
                
                # Commit every 10 creators
                if batch_count % 10 == 0:
                    await db.commit()
                    checkpoint["processed_ids"] = list(processed_ids)
                    checkpoint["stats"] = stats
                    save_checkpoint(checkpoint)
                    logger.info("  Checkpoint saved: %d/%d processed", len(processed_ids), total)
                
                # Small delay to avoid rate limits
                if need_llm:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error("  Error processing creator #%d: %s", creator.id, str(e)[:200])
                stats["errors"] = stats.get("errors", 0) + 1
                processed_ids.add(creator.id)  # Skip on error to avoid infinite loops
        
        # Final commit
        await db.commit()
        checkpoint["processed_ids"] = list(processed_ids)
        checkpoint["stats"] = stats
        save_checkpoint(checkpoint)
    
    # Print summary
    logger.info("=" * 60)
    logger.info("ENRICHMENT COMPLETE")
    logger.info("=" * 60)
    logger.info("Total processed: %d", len(processed_ids))
    logger.info("Relevant:        %d", stats.get("relevant", 0))
    logger.info("Not relevant:    %d", stats.get("not_relevant", 0))
    logger.info("Targets India:   %d", stats.get("india", 0))
    logger.info("Not India:       %d", stats.get("not_india", 0))
    logger.info("Language filled:  %d", stats.get("language_filled", 0))
    logger.info("Errors:          %d", stats.get("errors", 0))


if __name__ == "__main__":
    asyncio.run(enrich_all())
