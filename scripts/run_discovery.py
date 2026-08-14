"""Script to run live discovery pipeline and fetch creators into SQLite database."""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.database.session import async_session_factory, init_db
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("live_discovery")

async def main():
    print("=" * 60)
    print("STARTING CREATOR INTELLIGENCE DISCOVERY PIPELINE")
    print("=" * 60)
    
    await init_db()
    
    pipeline = DiscoveryPipeline()
    keywords = ["options trading india", "stock market investing india"]
    
    async with async_session_factory() as db:
        service = CreatorService(db)
        # Create scrape job
        job_id = await service.create_scrape_job(
            job_type="youtube",
            keywords=keywords,
            depth=1
        )
        print(f"\n[1] Created Scrape Job ID: {job_id}")
        
        print(f"\n[2] Crawling YouTube for keywords: {keywords} (depth=1)...")
        stats = await pipeline.run_youtube(db, keywords=keywords, max_depth=1, job_id=job_id)
        print(f"\n[3] Discovery & Enrichment Completed!")
        print(f"    - Discovered: {stats['discovered']} profiles")
        print(f"    - Newly Inserted / Updated: {stats['new']} creators")
        
        # Query saved creators
        resp = await service.list_creators(page=1, page_size=50)
        print(f"\n[4] Database Summary ({resp.total} Total Creators in Database):")
        print("-" * 100)
        for i, c in enumerate(resp.results, 1):
            followers = c.followers or 0
            score = c.influencer_score or 0.0
            cat = c.primary_category or "N/A"
            lang = c.primary_language or "N/A"
            ctype = c.creator_type or "N/A"
            platforms = ",".join(c.platforms) if c.platforms else "youtube"
            print(f"{i:2d}. {c.name:<32} | Score: {score:5.1f} | Followers: {followers:>10,d} | Category: {cat:<18} | Type: {ctype:<12} | Lang: {lang}")
        
        await db.commit()
        print("-" * 100)
        print("ALL CREATORS COMMITTED SUCCESSFULLY TO DATABASE.")

if __name__ == "__main__":
    asyncio.run(main())
