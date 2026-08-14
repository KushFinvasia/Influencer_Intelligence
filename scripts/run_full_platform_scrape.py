"""Master discovery script to scrape and enrich creators across BOTH YouTube and Instagram.

Uses all latest pipeline improvements:
- YouTube video transcript-based spoken language detection.
- Deep multi-broker and contact extraction from bio + last 5 video descriptions.
- 2-stage Instagram hashtag discovery & profile follower hydration.
- Re-generation of consolidated CSV and HTML tables.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_keywords_config
from app.database.session import async_session_factory, init_db
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService
from scripts.view_creators import export_csv, export_html, fetch_creators_table_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("full_scrape")


async def main():
    print("=" * 70)
    print("STARTING FULL MULTI-PLATFORM SCRAPE & ENRICHMENT (YOUTUBE + INSTAGRAM)")
    print("=" * 70)

    await init_db()
    pipeline = DiscoveryPipeline()
    keywords_config = get_keywords_config()

    yt_keywords = keywords_config.get("youtube", {}).get("search_keywords", [
        "options trading india",
        "stock market trading hindi",
        "share market investing india",
        "nifty banknifty analysis",
        "intraday trading setup",
    ])[:4]

    insta_hashtags = keywords_config.get("instagram", {}).get("hashtags", [
        "#stockmarketindia",
        "#optionstrading",
        "#finfluencer",
        "#investingindia",
        "#banknifty",
    ])[:4]
    insta_seeds = keywords_config.get("instagram", {}).get("seed_usernames", [])

    total_yt_new = 0
    total_insta_new = 0

    # -------------------------------------------------------------
    # 1. YOUTUBE SCRAPING & TRANSCRIPT LANGUAGE DETECTION
    # -------------------------------------------------------------
    print(f"\n[PHASE 1] YouTube Discovery on {len(yt_keywords)} keywords:")
    for kw in yt_keywords:
        print(f"  - Query: '{kw}'")

    async with async_session_factory() as db:
        service = CreatorService(db)
        yt_job_id = await service.create_scrape_job(
            job_type="youtube",
            keywords=yt_keywords,
            depth=1,
        )
        print(f"\n[1.1] Created YouTube Job ID #{yt_job_id}. Running crawler...")
        yt_stats = await pipeline.run_youtube(
            db,
            keywords=yt_keywords,
            max_depth=1,
            job_id=yt_job_id,
        )
        total_yt_new = yt_stats.get("new", 0)
        await db.commit()
        print(f"[1.2] YouTube Complete: {yt_stats.get('discovered', 0)} discovered, {total_yt_new} saved/updated.")

    # -------------------------------------------------------------
    # 2. INSTAGRAM 2-STAGE AUTONOMOUS DISCOVERY & HYDRATION
    # -------------------------------------------------------------
    print(f"\n[PHASE 2] Instagram 2-Stage Discovery on {len(insta_hashtags)} hashtags:")
    for tag in insta_hashtags:
        print(f"  - Tag: '{tag}'")

    async with async_session_factory() as db:
        service = CreatorService(db)
        insta_job_id = await service.create_scrape_job(
            job_type="instagram",
            keywords=insta_hashtags,
            depth=1,
        )
        print(f"\n[2.1] Created Instagram Job ID #{insta_job_id}. Running crawler & hydration...")
        insta_stats = await pipeline.run_instagram(
            db,
            hashtags=insta_hashtags,
            usernames=insta_seeds,
            max_depth=1,
            job_id=insta_job_id,
        )
        total_insta_new = insta_stats.get("new", 0)
        await db.commit()
        print(f"[2.2] Instagram Complete: {insta_stats.get('discovered', 0)} discovered, {total_insta_new} saved/updated.")

    # -------------------------------------------------------------
    # 3. EXPORT CONSOLIDATED TABLE & DASHBOARD
    # -------------------------------------------------------------
    print("\n[PHASE 3] Generating Consolidated Intelligence Table & Dashboard...")
    data = fetch_creators_table_data()
    csv_file = export_csv(data)
    html_file = export_html(data)
    print(f"\n[+] CSV exported: {csv_file}")
    print(f"[+] HTML Table exported: {html_file}")
    print(f"\n[SUCCESS] ALL PLATFORMS SCRAPED & UPDATED! Total Creators in Platform: {len(data)}")


if __name__ == "__main__":
    asyncio.run(main())
