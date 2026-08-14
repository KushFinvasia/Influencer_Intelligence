"""Backfill script: populate post-level metrics and calculate creator performance analytics.

Reads all Instagram platform profiles from SQLite, normalizes each post defensively,
persists individual post records into the 'posts' table, deterministically calculates
creator-level performance metrics (mean & median views, likes, comments, engagement rate,
sample sizes), and stores timestamped historical snapshots in 'instagram_metrics'.
"""

import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from app.config.settings import get_settings
from app.models.database import Base, Creator, PlatformProfile, Post, InstagramMetric
from app.analytics import InstagramMetricsCalculator, normalize_apify_instagram_post
from app.database import async_session_factory, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("instagram_analytics")


async def backfill_instagram_analytics():
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        # Create any missing tables (e.g. instagram_metrics)
        await conn.run_sync(Base.metadata.create_all)

        # Handle column additions defensively for SQLite if existing table was created before
        try:
            await conn.execute(text("ALTER TABLE posts ADD COLUMN creator_username VARCHAR(500)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE posts ADD COLUMN media_type VARCHAR(50)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE posts ADD COLUMN views INTEGER"))
        except Exception:
            pass

    async with async_session_factory() as db:
        # Fetch all Instagram platform profiles
        stmt = select(PlatformProfile).where(PlatformProfile.platform == "instagram")
        res = await db.execute(stmt)
        profiles = res.scalars().all()

        logger.info("Found %d Instagram platform profiles to process.", len(profiles))

        total_posts_saved = 0
        total_video_posts = 0
        total_snapshots = 0
        creators_with_analytics = 0

        for pp in profiles:
            raw_data = pp.raw_data or {}
            raw_items = []
            if isinstance(raw_data, dict):
                if "latestPosts" in raw_data and isinstance(raw_data["latestPosts"], list):
                    raw_items.extend(raw_data["latestPosts"])
                if "data" in raw_data and isinstance(raw_data["data"], dict):
                    hashtag_items = raw_data["data"].get("raw_items", [])
                    if isinstance(hashtag_items, list):
                        raw_items.extend(hashtag_items)

            normalized_posts = []
            for item in raw_items:
                norm = normalize_apify_instagram_post(item, default_username=pp.username)
                if not norm:
                    continue
                normalized_posts.append(norm)

                # Upsert post-level record
                existing_p = await db.execute(
                    select(Post).where(
                        Post.platform_profile_id == pp.id,
                        Post.post_id == norm.post_id,
                    )
                )
                p_rec = existing_p.scalar_one_or_none()
                if p_rec:
                    p_rec.creator_username = norm.creator_username
                    p_rec.caption = norm.caption
                    p_rec.media_type = norm.media_type
                    p_rec.likes = norm.likes
                    p_rec.comments_count = norm.comments
                    p_rec.views = norm.views
                    p_rec.published_at = norm.posted_at
                    p_rec.url = norm.url
                    p_rec.raw_payload = norm.raw_payload
                else:
                    db.add(
                        Post(
                            platform_profile_id=pp.id,
                            post_id=norm.post_id,
                            creator_username=norm.creator_username,
                            caption=norm.caption,
                            media_type=norm.media_type,
                            likes=norm.likes,
                            comments_count=norm.comments,
                            views=norm.views,
                            published_at=norm.posted_at,
                            url=norm.url,
                            raw_payload=norm.raw_payload,
                        )
                    )
                    total_posts_saved += 1
                    if norm.views is not None:
                        total_video_posts += 1

            await db.flush()

            # Query all stored posts for this profile
            all_posts_res = await db.execute(
                select(Post)
                .where(Post.platform_profile_id == pp.id)
                .order_by(Post.published_at.desc().nullslast())
            )
            stored_posts = all_posts_res.scalars().all()

            # Calculate metrics
            metrics = InstagramMetricsCalculator.calculate_metrics(
                posts=stored_posts or normalized_posts,
                followers=pp.followers,
                max_posts=20,
            )

            # Record timestamped historical snapshot
            snap = InstagramMetric(
                creator_id=pp.creator_id,
                platform_profile_id=pp.id,
                followers=metrics.followers,
                posts_analyzed=metrics.posts_analyzed,
                views_analyzed=metrics.views_analyzed,
                likes_analyzed=metrics.likes_analyzed,
                comments_analyzed=metrics.comments_analyzed,
                average_views=metrics.average_views,
                median_views=metrics.median_views,
                average_likes=metrics.average_likes,
                median_likes=metrics.median_likes,
                average_comments=metrics.average_comments,
                median_comments=metrics.median_comments,
                engagement_rate=metrics.engagement_rate,
                last_post_date=metrics.last_post_date,
                metrics_calculated_at=metrics.metrics_calculated_at,
            )
            db.add(snap)
            total_snapshots += 1
            if metrics.posts_analyzed > 0:
                creators_with_analytics += 1

        await db.commit()

        logger.info("=" * 60)
        logger.info("Instagram Performance Analytics Backfill Summary:")
        logger.info(" - Total Profiles Processed: %d", len(profiles))
        logger.info(" - Total Posts Saved/Preserved: %d", total_posts_saved)
        logger.info(" - Video Posts with Valid Views: %d", total_video_posts)
        logger.info(" - Performance Snapshots Created: %d", total_snapshots)
        logger.info(" - Creators with Analyzed Posts: %d", creators_with_analytics)
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(backfill_instagram_analytics())
