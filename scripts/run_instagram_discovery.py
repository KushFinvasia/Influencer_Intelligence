"""Script to run live Instagram discovery pipeline via Apify and enrich into SQLite DB."""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.config.settings import get_keywords_config
from app.database.session import async_session_factory, init_db
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("instagram_discovery")


async def main():
    print("=" * 60)
    print("STARTING INSTAGRAM FINFLUENCER DISCOVERY")
    print("=" * 60)

    await init_db()

    pipeline = DiscoveryPipeline()
    keywords_config = get_keywords_config()
    hashtags = keywords_config.get("instagram", {}).get("hashtags", [
        "#stockmarketindia",
        "#optionstrading",
        "#nifty50",
        "#banknifty",
        "#finfluencer"
    ])
    seed_usernames = keywords_config.get("instagram", {}).get("seed_usernames", [])

    print(f"Target Hashtags ({len(hashtags)}): {hashtags[:5]}...")

    async with async_session_factory() as db:
        service = CreatorService(db)
        job_id = await service.create_scrape_job(
            job_type="instagram",
            keywords=hashtags[:5],
            depth=1,
        )
        print(f"\n[1] Created Instagram Scrape Job ID: {job_id}")

        print("\n[2] Triggering Apify Instagram Crawler...")
        stats = await pipeline.run_instagram(
            db,
            hashtags=hashtags[:3],  # Start with top 3 hashtags
            usernames=seed_usernames,
            max_depth=1,
            job_id=job_id,
        )

        print("\n[3] Instagram Discovery Completed!")
        print(f"    - Profiles Discovered: {stats['discovered']}")
        print(f"    - Enriched & Saved: {stats['new']}")

        await db.commit()
        print("\n[4] Re-generating consolidated table and dashboard...")
        from scripts.view_creators import export_csv, export_html, fetch_creators_table_data
        data = fetch_creators_table_data()
        export_csv(data)
        export_html(data)
        print(f"[OK] Table updated with {len(data)} total creators!")


if __name__ == "__main__":
    asyncio.run(main())

