"""Backfill script: populate video-level metrics and calculate YouTube creator performance analytics.

Reads all YouTube platform profiles from SQLite, fetches recent video performance data via
YouTube Data API v3 (videos.list with snippet,contentDetails,statistics), persists individual video
records into the 'videos' table, deterministically calculates creator-level performance metrics
(mean & median views, likes, comments, engagement rate, engagement_eligible_videos, sample sizes),
and stores timestamped historical snapshots in 'youtube_metrics'.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from app.config.settings import get_settings
from app.models.database import Base, Creator, PlatformProfile, Video, YouTubeMetric
from app.analytics import YouTubeMetricsCalculator, normalize_youtube_video, YouTubeVideoNormalized
from app.crawlers.youtube import YouTubeCrawler
from app.database import async_session_factory, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("youtube_analytics")


async def backfill_youtube_analytics(max_items_per_creator: int = 20):
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        # Create any missing tables (e.g. youtube_metrics)
        await conn.run_sync(Base.metadata.create_all)

        # Handle column additions defensively for SQLite if existing table was created before
        try:
            await conn.execute(text("ALTER TABLE videos ADD COLUMN raw_payload JSON"))
        except Exception:
            pass

    crawler = YouTubeCrawler()

    async with async_session_factory() as db:
        # Fetch all YouTube platform profiles
        stmt = select(PlatformProfile).where(PlatformProfile.platform == "youtube")
        res = await db.execute(stmt)
        profiles = res.scalars().all()

        logger.info("Found %d YouTube platform profiles to process.", len(profiles))

        total_videos_saved = 0
        total_snapshots = 0
        creators_with_analytics = 0

        for idx, pp in enumerate(profiles, 1):
            channel_id = pp.platform_user_id
            creator_name = pp.display_name or pp.username or f"Channel {channel_id}"

            # Fetch recent videos via YouTubeCrawler
            logger.info(
                "[%d/%d] Fetching up to %d videos for '%s' (%s)...",
                idx,
                len(profiles),
                max_items_per_creator,
                creator_name,
                channel_id,
            )

            try:
                video_items = await crawler.fetch_content(channel_id, max_items=max_items_per_creator)
            except Exception as e:
                logger.error("Failed to fetch videos for '%s': %s", creator_name, e)
                video_items = []

            # Upsert video records
            normalized_videos: list[YouTubeVideoNormalized] = []
            for v_data in video_items:
                # v_data is VideoData instance or raw dict
                if hasattr(v_data, "raw_payload") and v_data.raw_payload:
                    norm = normalize_youtube_video(v_data.raw_payload)
                elif isinstance(v_data, dict):
                    norm = normalize_youtube_video(v_data)
                else:
                    norm = YouTubeVideoNormalized(
                        video_id=v_data.video_id,
                        channel_id=channel_id,
                        title=v_data.title,
                        description=v_data.description,
                        published_at=v_data.published_at,
                        views=v_data.views,
                        likes=v_data.likes,
                        comments=v_data.comments_count,
                        duration=v_data.duration,
                        is_short=v_data.is_short,
                        thumbnail_url=v_data.thumbnail_url,
                        raw_payload=getattr(v_data, "raw_payload", None),
                    )

                if not norm:
                    continue
                normalized_videos.append(norm)

                # Upsert to database
                existing_v = await db.execute(
                    select(Video).where(
                        Video.platform_profile_id == pp.id,
                        Video.video_id == norm.video_id,
                    )
                )
                v_rec = existing_v.scalar_one_or_none()
                if v_rec:
                    v_rec.title = norm.title
                    v_rec.description = norm.description
                    v_rec.views = norm.views
                    v_rec.likes = norm.likes
                    v_rec.comments_count = norm.comments
                    v_rec.duration = norm.duration
                    v_rec.is_short = norm.is_short
                    v_rec.published_at = norm.published_at
                    v_rec.thumbnail_url = norm.thumbnail_url
                    v_rec.raw_payload = norm.raw_payload
                else:
                    db.add(
                        Video(
                            platform_profile_id=pp.id,
                            video_id=norm.video_id,
                            title=norm.title,
                            description=norm.description,
                            views=norm.views,
                            likes=norm.likes,
                            comments_count=norm.comments,
                            duration=norm.duration,
                            is_short=norm.is_short,
                            published_at=norm.published_at,
                            thumbnail_url=norm.thumbnail_url,
                            raw_payload=norm.raw_payload,
                        )
                    )
                    total_videos_saved += 1

            await db.flush()

            # Query all stored videos for profile
            all_videos_res = await db.execute(
                select(Video)
                .where(Video.platform_profile_id == pp.id)
                .order_by(Video.published_at.desc().nullslast())
            )
            stored_videos = all_videos_res.scalars().all()

            # Calculate metrics
            metrics = YouTubeMetricsCalculator.calculate_metrics(
                videos=stored_videos or normalized_videos,
                subscribers=pp.followers,
                max_videos=max_items_per_creator,
            )

            # Insert snapshot
            snap = YouTubeMetric(
                creator_id=pp.creator_id,
                platform_profile_id=pp.id,
                subscribers=metrics.subscribers,
                videos_analyzed=metrics.videos_analyzed,
                views_analyzed=metrics.views_analyzed,
                likes_analyzed=metrics.likes_analyzed,
                comments_analyzed=metrics.comments_analyzed,
                engagement_eligible_videos=metrics.engagement_eligible_videos,
                average_views=metrics.average_views,
                median_views=metrics.median_views,
                average_likes=metrics.average_likes,
                median_likes=metrics.median_likes,
                average_comments=metrics.average_comments,
                median_comments=metrics.median_comments,
                engagement_rate=metrics.engagement_rate,
                shorts_ratio=metrics.shorts_ratio,
                last_video_date=metrics.last_video_date,
                metrics_calculated_at=metrics.metrics_calculated_at,
            )
            db.add(snap)
            total_snapshots += 1

            if metrics.videos_analyzed > 0:
                creators_with_analytics += 1
                logger.info(
                    "  ✓ '%s': %d videos (eligible: %d) | Avg Views: %s (Med: %s) | Avg Likes: %s | Eng Rate: %s%%",
                    creator_name,
                    metrics.videos_analyzed,
                    metrics.engagement_eligible_videos,
                    f"{metrics.average_views:,.0f}" if metrics.average_views else "N/A",
                    f"{metrics.median_views:,.0f}" if metrics.median_views else "N/A",
                    f"{metrics.average_likes:,.0f}" if metrics.average_likes else "N/A",
                    f"{metrics.engagement_rate:.2f}" if metrics.engagement_rate is not None else "N/A",
                )
            else:
                logger.warning("  ⚠ '%s': No videos found.", creator_name)

            # Small delay to keep API quota friendly
            await asyncio.sleep(0.1)

        await db.commit()

        logger.info("\n" + "=" * 60)
        logger.info("YOUTUBE PERFORMANCE ANALYTICS BACKFILL SUMMARY")
        logger.info("=" * 60)
        logger.info("Profiles processed: %d", len(profiles))
        logger.info("Total videos saved: %d", total_videos_saved)
        logger.info("Creators with analytics: %d", creators_with_analytics)
        logger.info("Total historical snapshots created: %d", total_snapshots)
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(backfill_youtube_analytics())
