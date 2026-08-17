"""
Discover & Enrich Remaining YouTube Creators
===========================================
Executes Phase 2, 3, and 4 for all remaining YouTube channels:
- Fetches channel metadata (Phase 2)
- Fetches recent videos & engagement metrics (Phase 3)
- Performs LLM classification, category extraction, language detection,
  broker detection, contact extraction, relevance evaluation, and Indian audience check (Phase 4)
- Upserts enriched creators into creator_intel.db
- Commits progress every 10 creators and supports resumption
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

from sqlalchemy import select, text
from app.config.settings import get_settings, get_keywords_config
from app.database.session import async_session_factory
from app.pipelines.discovery import DiscoveryPipeline
from app.utils.keyword_parser import parse_keywords
from app.models.database import Creator, PlatformProfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("remaining_discovery.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def process_remaining():
    logger.info("Starting discovery and enrichment for remaining creators...")
    
    # Load keywords configuration
    keywords_config = get_keywords_config()
    youtube_keywords = parse_keywords(keywords_config.get("youtube", {}))
    logger.info("Loaded %d search keywords from config", len(youtube_keywords))

    pipeline = DiscoveryPipeline()

    async with async_session_factory() as db:
        # Check starting count
        c_res = await db.execute(select(Creator))
        start_count = len(c_res.scalars().all())
        logger.info("Current creators in DB: %d", start_count)

        try:
            stats = await pipeline.run_youtube(
                db=db,
                keywords=youtube_keywords,
                max_depth=3,
                job_id=None,
            )
            logger.info("Pipeline execution finished: %s", stats)
        except Exception as e:
            logger.error("Pipeline encountered an issue: %s", e, exc_info=True)

        # Check ending count
        c_res_end = await db.execute(select(Creator))
        end_count = len(c_res_end.scalars().all())
        logger.info("==========================================")
        logger.info("DISCOVERY & ENRICHMENT STEP COMPLETED")
        logger.info("Initial count: %d | Final count: %d | New added: %d",
                    start_count, end_count, end_count - start_count)
        logger.info("==========================================")


if __name__ == "__main__":
    asyncio.run(process_remaining())
