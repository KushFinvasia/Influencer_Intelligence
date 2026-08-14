"""Run YouTube discovery and verify persistence to creator_intel.db."""

import asyncio
import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath("."))

from app.database.session import async_session_factory, init_db
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService

async def main():
    print("1. Initializing DB...")
    await init_db()
    
    pipeline = DiscoveryPipeline()
    keywords = ["options trading india", "stock market investing india"]
    
    print("2. Starting discovery pipeline for keywords:", keywords)
    async with async_session_factory() as db:
        service = CreatorService(db)
        job_id = await service.create_scrape_job(job_type="youtube", keywords=keywords, depth=1)
        print(f"   Created Job ID: {job_id}")
        
        stats = await pipeline.run_youtube(db, keywords=keywords, max_depth=1, job_id=job_id)
        print(f"   Pipeline finished stats: {stats}")
        
        await db.commit()
        print("3. Committed async session!")

    # Verify directly with raw sqlite3
    db_file = r"C:\Finvasia\Influencer_Scraper\creator_intel.db"
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    cnt = c.execute("SELECT COUNT(*) FROM creators").fetchone()[0]
    print(f"\n4. Direct SQLite verification: {cnt} creators in '{db_file}'")
    for row in c.execute("SELECT id, name, influencer_score, primary_category FROM creators LIMIT 10"):
        print("   ->", row)

if __name__ == "__main__":
    asyncio.run(main())
