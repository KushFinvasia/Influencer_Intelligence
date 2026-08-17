"""
Process Previous Discovered Candidates Only
===========================================
Skips Phase 1 keyword search completely.
Loads candidate channel IDs from previous discovery runs / youtube_resume_state.json
and executes Phase 2 (metadata fetch), Phase 3 (video metrics), and Phase 4 (enrichment + DB upsert).
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
from app.crawlers.youtube import YouTubeCrawler
from app.database.session import async_session_factory
from app.models.database import Creator, PlatformProfile
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("previous_candidates_processing.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def process_previous_candidates():
    logger.info("Starting direct Phase 2, 3, and 4 processing for PREVIOUS candidate channels...")

    # Load candidate channel IDs from resume state if present
    candidate_ids = set()
    state_file = "youtube_resume_state.json"

    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                candidate_ids.update(state.get("channels_to_process", []))
            logger.info("Loaded %d candidate channel IDs from %s", len(candidate_ids), state_file)
        except Exception as e:
            logger.error("Failed reading %s: %s", state_file, e)

    if not candidate_ids:
        logger.warning("No candidate channel IDs found in %s! Nothing to process.", state_file)
        return

    async with async_session_factory() as db:
        service = CreatorService(db)
        yt_crawler = YouTubeCrawler()
        pipeline = DiscoveryPipeline()

        # Get existing YouTube channel IDs in DB to prevent duplicate work
        existing_res = await db.execute(
            select(PlatformProfile.platform_user_id).where(PlatformProfile.platform == "youtube")
        )
        existing_db_ids = set(existing_res.scalars().all())
        logger.info("Existing YouTube channels in DB: %d", len(existing_db_ids))

        # Filter out already existing channels
        pending_ids = [cid for cid in candidate_ids if cid not in existing_db_ids]
        logger.info("New candidate channels to process through Phase 2, 3 & 4: %d", len(pending_ids))

        if not pending_ids:
            logger.info("All candidate channels are already in the database!")
            return

        # Phase 2: Batch fetch channel metadata
        logger.info("--- Phase 2: Batch fetching metadata for %d channels ---", len(pending_ids))
        raw_profiles = await yt_crawler._batch_fetch_channels(pending_ids)
        logger.info("Successfully fetched %d RawProfile objects", len(raw_profiles))

        # Phase 3 & 4: Fetch videos & run full enrichment pipeline for each profile
        processed_count = 0
        enriched_count = 0

        for i, profile in enumerate(raw_profiles, 1):
            logger.info("[%d/%d] Processing channel '%s' (%s)", i, len(raw_profiles), profile.display_name or profile.username, profile.platform_user_id)
            try:
                # Fetch recent video payloads (Phase 3)
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

                # Run full enrichment (Phase 4)
                enriched = await pipeline._process_profile(profile, db, service)
                if enriched:
                    enriched_count += 1
                    logger.info("  -> Enriched & Saved creator: %s", profile.display_name or profile.username)
                else:
                    logger.info("  -> Filtered out non-matching channel: %s", profile.display_name or profile.username)

                processed_count += 1

                # Commit every 10 creators
                if processed_count % 10 == 0:
                    await db.commit()
                    logger.info("Committed batch: %d processed, %d added to DB", processed_count, enriched_count)

            except Exception as e:
                logger.error("Error processing channel %s: %s", profile.platform_user_id, e)

        await db.commit()
        logger.info("==========================================")
        logger.info("PHASE 2, 3 & 4 COMPLETION SUMMARY")
        logger.info("Total Channels Processed: %d", processed_count)
        logger.info("Total Enriched Creators Added: %d", enriched_count)
        logger.info("==========================================")


if __name__ == "__main__":
    asyncio.run(process_previous_candidates())
