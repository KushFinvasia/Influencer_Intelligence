"""YouTube Creator Performance Analytics Engine.

Deterministic Python calculations for video-level metrics, summary statistics
(mean & median views, likes, comments), engagement rates, shorts ratio,
and sample-size tracking.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Sequence

from app.analytics.schemas import (
    YouTubeMetricsResult,
    YouTubeVideoNormalized,
    normalize_youtube_video,
)

logger = logging.getLogger(__name__)


class YouTubeMetricsCalculator:
    """Calculates YouTube creator-level performance metrics deterministically in Python."""

    DEFAULT_MAX_VIDEOS = 20

    @classmethod
    def calculate_video_engagement_rate(
        cls,
        likes: int | None,
        comments: int | None,
        views: int | None,
    ) -> float | None:
        """Calculate engagement rate for an individual video if all 3 metrics exist and views > 0.
        
        Formula: ((likes + comments) / views) * 100
        Returns None if views, likes, or comments are missing or views <= 0.
        """
        if views is None or views <= 0 or likes is None or comments is None:
            return None
        total_interactions = likes + comments
        return round((total_interactions / views) * 100.0, 2)

    @classmethod
    def calculate_metrics(
        cls,
        videos: Sequence[YouTubeVideoNormalized | dict[str, Any] | Any],
        subscribers: int | None = None,
        max_videos: int = DEFAULT_MAX_VIDEOS,
    ) -> YouTubeMetricsResult:
        """Calculate creator-level performance metrics over the latest eligible videos.
        
        Args:
            videos: Sequence of normalized video objects, ORM models, or raw API dicts.
            subscribers: Current subscriber count of the channel.
            max_videos: Number of latest videos to analyze (configurable, default 20).
            
        Returns:
            YouTubeMetricsResult containing mean/median metrics, engagement rate,
            sample counts, and shorts ratio.
        """
        now = datetime.now(timezone.utc)
        if not videos:
            return YouTubeMetricsResult(
                subscribers=subscribers,
                videos_analyzed=0,
                views_analyzed=0,
                likes_analyzed=0,
                comments_analyzed=0,
                engagement_eligible_videos=0,
                metrics_calculated_at=now,
            )

        # 1. Normalize all inputs defensively
        normalized_videos: list[YouTubeVideoNormalized] = []
        for v in videos:
            if isinstance(v, YouTubeVideoNormalized):
                normalized_videos.append(v)
            elif isinstance(v, dict):
                norm = normalize_youtube_video(v)
                if norm:
                    normalized_videos.append(norm)
            elif hasattr(v, "video_id"):
                # Handle SQLAlchemy Video ORM model or VideoData schema
                raw_payload = getattr(v, "raw_payload", None)
                norm = YouTubeVideoNormalized(
                    video_id=str(getattr(v, "video_id")),
                    channel_id=getattr(v, "channel_id", None),
                    title=getattr(v, "title", None),
                    description=getattr(v, "description", None),
                    published_at=getattr(v, "published_at", None),
                    views=getattr(v, "views", None),
                    likes=getattr(v, "likes", None),
                    comments=getattr(v, "comments_count", None) or getattr(v, "comments", None),
                    duration=getattr(v, "duration", None),
                    is_short=bool(getattr(v, "is_short", False)),
                    thumbnail_url=getattr(v, "thumbnail_url", None),
                    raw_payload=raw_payload if isinstance(raw_payload, dict) else None,
                )
                normalized_videos.append(norm)

        if not normalized_videos:
            return YouTubeMetricsResult(
                subscribers=subscribers,
                videos_analyzed=0,
                views_analyzed=0,
                likes_analyzed=0,
                comments_analyzed=0,
                engagement_eligible_videos=0,
                metrics_calculated_at=now,
            )

        # 2. Sort videos by published_at DESC (videos without date sorted to end)
        min_dt = datetime.min.replace(tzinfo=timezone.utc)
        sorted_videos = sorted(
            normalized_videos,
            key=lambda x: x.published_at if x.published_at is not None else min_dt,
            reverse=True,
        )

        # 3. Take latest configurable sample window (default 20)
        recent_videos = sorted_videos[:max_videos]
        videos_analyzed = len(recent_videos)

        # 4. Extract valid metric samples (DO NOT treat missing as zero)
        views_sample: list[int] = [
            v.views for v in recent_videos if v.views is not None and v.views >= 0
        ]
        likes_sample: list[int] = [
            v.likes for v in recent_videos if v.likes is not None and v.likes >= 0
        ]
        comments_sample: list[int] = [
            v.comments for v in recent_videos if v.comments is not None and v.comments >= 0
        ]

        views_analyzed = len(views_sample)
        likes_analyzed = len(likes_sample)
        comments_analyzed = len(comments_sample)

        # 5. Deterministic Stats (Mean & Median)
        average_views: float | None = None
        median_views: float | None = None
        if views_sample:
            average_views = round(float(statistics.mean(views_sample)), 2)
            median_views = round(float(statistics.median(views_sample)), 2)

        average_likes: float | None = None
        median_likes: float | None = None
        if likes_sample:
            average_likes = round(float(statistics.mean(likes_sample)), 2)
            median_likes = round(float(statistics.median(likes_sample)), 2)

        average_comments: float | None = None
        median_comments: float | None = None
        if comments_sample:
            average_comments = round(float(statistics.mean(comments_sample)), 2)
            median_comments = round(float(statistics.median(comments_sample)), 2)

        # 6. Engagement Rate calculation ONLY from videos where views + likes + comments are all available
        eligible_videos = [
            v for v in recent_videos
            if (
                v.views is not None
                and v.views > 0
                and v.likes is not None
                and v.likes >= 0
                and v.comments is not None
                and v.comments >= 0
            )
        ]
        engagement_eligible_videos = len(eligible_videos)

        engagement_rate: float | None = None
        if engagement_eligible_videos > 0:
            tot_views = sum(v.views for v in eligible_videos if v.views is not None)
            tot_interactions = sum(
                (v.likes or 0) + (v.comments or 0) for v in eligible_videos
            )
            if tot_views > 0:
                engagement_rate = round((tot_interactions / tot_views) * 100.0, 2)

        # 7. Shorts ratio
        shorts_count = sum(1 for v in recent_videos if v.is_short)
        shorts_ratio: float | None = (
            round(float(shorts_count) / float(videos_analyzed), 2)
            if videos_analyzed > 0
            else None
        )

        # 8. Last video date
        valid_dates = [v.published_at for v in recent_videos if v.published_at is not None]
        last_video_date = max(valid_dates) if valid_dates else None

        return YouTubeMetricsResult(
            subscribers=subscribers,
            videos_analyzed=videos_analyzed,
            views_analyzed=views_analyzed,
            likes_analyzed=likes_analyzed,
            comments_analyzed=comments_analyzed,
            engagement_eligible_videos=engagement_eligible_videos,
            average_views=average_views,
            median_views=median_views,
            average_likes=average_likes,
            median_likes=median_likes,
            average_comments=average_comments,
            median_comments=median_comments,
            engagement_rate=engagement_rate,
            shorts_ratio=shorts_ratio,
            last_video_date=last_video_date,
            metrics_calculated_at=now,
        )
