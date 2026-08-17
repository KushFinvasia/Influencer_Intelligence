"""Populate performance metrics and content formats for all YouTube creators in creator_intel.db."""

import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete
from app.database import async_session_factory
from app.models.database import Creator, PlatformProfile, Video, YouTubeMetric
from app.crawlers.youtube import YouTubeCrawler
from app.analytics import YouTubeMetricsCalculator, normalize_youtube_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("populate_metrics")


async def main():
    crawler = YouTubeCrawler()

    async with async_session_factory() as db:
        stmt = select(PlatformProfile).where(PlatformProfile.platform == "youtube")
        res = await db.execute(stmt)
        profiles = res.scalars().all()
        logger.info("Found %d YouTube profiles to populate analytics...", len(profiles))

        count = 0
        for idx, pp in enumerate(profiles, 1):
            channel_id = pp.platform_user_id
            name = pp.display_name or pp.username or f"Channel {channel_id}"

            try:
                # Fetch recent 15 videos
                v_items = await crawler.fetch_content(channel_id, max_items=15)
                norm_videos = []
                for v in v_items:
                    norm = normalize_youtube_video(
                        v.raw_payload
                        if hasattr(v, "raw_payload") and v.raw_payload
                        else (v.model_dump() if hasattr(v, "model_dump") else getattr(v, "__dict__", {}))
                    )
                    if norm:
                        norm_videos.append(norm)

                metrics = YouTubeMetricsCalculator.calculate_metrics(norm_videos, subscribers=pp.followers)

                # Delete previous empty/placeholder metric row
                await db.execute(delete(YouTubeMetric).where(YouTubeMetric.creator_id == pp.creator_id))

                db.add(
                    YouTubeMetric(
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
                    )
                )
                count += 1
                if count % 10 == 0:
                    await db.commit()
                    logger.info("[%d/%d] Committed metrics for %d creators...", idx, len(profiles), count)

            except Exception as e:
                logger.error("Error populating metrics for '%s': %s", name, e)

        await db.commit()
        logger.info("[SUCCESS] Populated metrics for all %d YouTube creators!", count)


if __name__ == "__main__":
    asyncio.run(main())
