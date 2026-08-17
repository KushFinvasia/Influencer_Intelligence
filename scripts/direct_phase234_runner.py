"""
Fast Candidate Channel Discovery & Phase 2, 3, 4 Enrichment
============================================================
1. Collects candidate channel IDs across stock market keywords.
2. Saves all candidate channel IDs to candidates_pool.json.
3. Immediately runs Phase 2 (metadata fetch), Phase 3 (video metrics), and Phase 4 (LLM classification, contact extraction, broker detection, relevance, and Indian audience check).
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from app.config.settings import get_keywords_config
from app.crawlers.youtube import YouTubeCrawler
from app.database.session import async_session_factory
from app.models.database import Creator, PlatformProfile
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService
from app.utils.keyword_parser import parse_keywords

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("direct_phase234.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def run_direct_pipeline():
    logger.info("Starting candidate collection and direct Phase 2, 3, 4 processing...")

    yt_crawler = YouTubeCrawler()
    pipeline = DiscoveryPipeline()

    pool_file = "candidates_pool.json"
    candidate_ids = set()

    if os.path.exists(pool_file):
        with open(pool_file, "r") as f:
            candidate_ids = set(json.load(f))
        logger.info("Loaded %d existing candidate channel IDs from %s", len(candidate_ids), pool_file)
    else:
        # Perform candidate channel ID collection across keywords
        keywords_config = get_keywords_config()
        youtube_keywords = parse_keywords(keywords_config.get("youtube", {}))
        logger.info("Collecting candidate channel IDs across %d keywords...", len(youtube_keywords))

        new_cids, _, _, _ = await yt_crawler._search_keywords(youtube_keywords)
        candidate_ids.update(new_cids)
        logger.info("Collected %d candidate channel IDs!", len(candidate_ids))

        with open(pool_file, "w") as f:
            json.dump(list(candidate_ids), f, indent=2)

    async with async_session_factory() as db:
        service = CreatorService(db)

        # Get existing YouTube channel IDs in DB
        existing_res = await db.execute(
            select(PlatformProfile.platform_user_id).where(PlatformProfile.platform == "youtube")
        )
        existing_db_ids = set(existing_res.scalars().all())
        logger.info("Existing YouTube channels in DB: %d", len(existing_db_ids))

        # Filter out existing
        pending_ids = [cid for cid in candidate_ids if cid not in existing_db_ids]
        logger.info("New candidate channels remaining to process: %d", len(pending_ids))

        if not pending_ids:
            logger.info("All candidates already processed in DB!")
            return

        # Phase 2: Batch fetch channel metadata
        logger.info("Phase 2: Fetching metadata for %d channels...", len(pending_ids))
        raw_profiles = await yt_crawler._batch_fetch_channels(pending_ids)
        logger.info("Phase 2 Complete: Got %d channel profile objects", len(raw_profiles))

        # Phase 3 & 4: Fetch video metrics & run full enrichment pipeline
        processed = 0
        added = 0

        for i, profile in enumerate(raw_profiles, 1):
            logger.info("[%d/%d] Processing %s (%s)", i, len(raw_profiles), profile.display_name or profile.username, profile.platform_user_id)
            success = False
            for attempt in range(2):
                try:
                    # Phase 3: Video payload & metrics
                    videos = await yt_crawler.fetch_content(profile.platform_user_id, max_items=15)
                    profile.recent_video_titles = [v.title for v in videos if v.title]
                    profile.recent_video_descriptions = [v.description for v in videos[:5] if v.description]
                    profile.recent_video_ids = [v.video_id for v in videos]
                    if not isinstance(profile.raw_data, dict):
                        profile.raw_data = {}
                    profile.raw_data["videos"] = [
                        v.raw_payload if (hasattr(v, "raw_payload") and v.raw_payload)
                        else (v.model_dump() if hasattr(v, "model_dump") else getattr(v, "__dict__", {}))
                        for v in videos
                    ]

                    # Phase 4: Enrichment & DB Upsert
                    enriched = await pipeline._process_profile(profile, db, service)
                    if enriched:
                        added += 1
                    processed += 1
                    success = True

                    if processed % 10 == 0:
                        await db.commit()
                        logger.info("Progress commit: %d/%d processed (%d added)", processed, len(raw_profiles), added)
                    break

                except Exception as e:
                    err_str = str(e)
                    logger.warning("Attempt %d error processing channel %s: %s", attempt + 1, profile.platform_user_id, err_str[:150])
                    if "429" in err_str or "rate" in err_str.lower():
                        logger.info("Rate limit encountered. Sleeping 10s before retry...")
                        await asyncio.sleep(10)
                    else:
                        break

            # Small delay to keep LLM rate limits healthy
            await asyncio.sleep(0.3)

        await db.commit()
        logger.info("ALL PHASES COMPLETED! Processed: %d | Added: %d", processed, added)


if __name__ == "__main__":
    asyncio.run(run_direct_pipeline())
