"""Classify and populate categories for all creators in the database."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete
from app.database.session import async_session_factory
from app.extractors.category import CategoryExtractor
from app.models.database import Creator, PlatformProfile, Category, CreatorCategory
from app.schemas.creator import RawProfile
from scripts.view_creators import export_csv, export_html, fetch_creators_table_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reclassify")


async def main():
    print("=" * 60)
    print("RECLASSIFYING CATEGORIES FOR ALL CREATORS")
    print("=" * 60)

    category_extractor = CategoryExtractor()
    session_factory = async_session_factory

    async with session_factory() as db:
        creators_res = await db.execute(select(Creator))
        creators = creators_res.scalars().all()
        print(f"Found {len(creators)} creators to categorize...")

        updated_count = 0
        cat_counts = {}

        for creator in creators:
            pp_res = await db.execute(
                select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
            )
            profiles = pp_res.scalars().all()

            combined_bio = []
            combined_desc = []
            titles = []
            descs = []
            display_name = creator.name

            for pp in profiles:
                if pp.display_name:
                    display_name = pp.display_name
                if pp.bio:
                    combined_bio.append(pp.bio)
                if pp.description:
                    combined_desc.append(pp.description)

                raw_data = pp.raw_data if pp.raw_data else {}
                if isinstance(raw_data, dict):
                    recent_vids = raw_data.get("recentVideos", []) or raw_data.get("videos", []) or []
                    if isinstance(recent_vids, list):
                        for v in recent_vids:
                            if isinstance(v, dict):
                                t = v.get("title") or v.get("caption")
                                if t:
                                    titles.append(t)
                                d = v.get("description")
                                if d:
                                    descs.append(d)

            raw_profile = RawProfile(
                platform=profiles[0].platform if profiles else "youtube",
                platform_user_id=profiles[0].platform_user_id if profiles else "",
                username=profiles[0].username if profiles else creator.name,
                display_name=display_name,
                bio=" ".join(combined_bio),
                description=" ".join(combined_desc),
                recent_video_titles=titles,
                recent_video_descriptions=descs,
            )

            primary_cat, categories = category_extractor.extract_categories(raw_profile)
            creator.primary_category = primary_cat
            cat_counts[primary_cat] = cat_counts.get(primary_cat, 0) + 1
            updated_count += 1

            # Update CreatorCategory associations
            await db.execute(
                delete(CreatorCategory).where(CreatorCategory.creator_id == creator.id)
            )
            for cat_res in categories:
                # Find or create Category
                c_res = await db.execute(
                    select(Category).where(Category.name == cat_res.name)
                )
                cat_obj = c_res.scalar_one_or_none()
                if not cat_obj:
                    cat_obj = Category(name=cat_res.name)
                    db.add(cat_obj)
                    await db.flush()

                db.add(
                    CreatorCategory(
                        creator_id=creator.id,
                        category_id=cat_obj.id,
                        confidence=cat_res.confidence,
                        is_primary=(cat_res.name == primary_cat),
                    )
                )

        await db.commit()
        print(f"[OK] Successfully categorized all {updated_count} creators!")
        print("\nCategory Breakdown:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
            print(f" - {cat:<25}: {count} creators")

    # Re-export table
    print("\nUpdating exports/creators_table.csv and exports/creators_table.html...")
    data = fetch_creators_table_data()
    export_csv(data)
    export_html(data)
    print(f"[OK] Table re-exported with categories populated!")


if __name__ == "__main__":
    asyncio.run(main())
