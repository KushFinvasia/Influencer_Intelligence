"""Instagram Creator Performance Analytics Engine.

Deterministic Python calculations for post-level metrics, summary statistics
(mean & median views, likes, comments), engagement rates, and sample-size tracking.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Sequence

from app.analytics.schemas import (
    InstagramMetricsResult,
    InstagramPostNormalized,
    normalize_apify_instagram_post,
)

logger = logging.getLogger(__name__)


class InstagramMetricsCalculator:
    """Calculates creator-level performance metrics deterministically in Python."""

    DEFAULT_MAX_POSTS = 20

    @classmethod
    def calculate_post_engagement_rate(
        cls,
        likes: int | None,
        comments: int | None,
        views: int | None,
    ) -> float | None:
        """Calculate engagement rate for an individual post if valid views exist.
        
        Formula: ((likes + comments) / views) * 100
        Returns None if views are missing, zero, or negative.
        """
        if views is None or views <= 0:
            return None
        total_interactions = (likes or 0) + (comments or 0)
        return round((total_interactions / views) * 100.0, 2)

    @classmethod
    def calculate_metrics(
        cls,
        posts: Sequence[InstagramPostNormalized | dict[str, Any] | Any],
        followers: int | None = None,
        max_posts: int = DEFAULT_MAX_POSTS,
    ) -> InstagramMetricsResult:
        """Calculate creator-level performance metrics over the latest eligible posts.
        
        Args:
            posts: Sequence of normalized post objects, ORM models, or raw Apify dicts.
            followers: Current follower count of the creator.
            max_posts: Number of latest posts to analyze (configurable, default 20).
            
        Returns:
            InstagramMetricsResult containing mean/median metrics, engagement rate,
            and sample counts (views_analyzed, likes_analyzed, comments_analyzed).
        """
        now = datetime.now(timezone.utc)
        if not posts:
            return InstagramMetricsResult(
                followers=followers,
                posts_analyzed=0,
                views_analyzed=0,
                likes_analyzed=0,
                comments_analyzed=0,
                metrics_calculated_at=now,
            )

        # 1. Normalize all inputs defensively
        normalized_posts: list[InstagramPostNormalized] = []
        for p in posts:
            if isinstance(p, InstagramPostNormalized):
                normalized_posts.append(p)
            elif isinstance(p, dict):
                norm = normalize_apify_instagram_post(p)
                if norm:
                    normalized_posts.append(norm)
            elif hasattr(p, "post_id"):
                # Handle SQLAlchemy Post ORM model or custom object
                raw_payload = getattr(p, "raw_payload", None)
                norm = InstagramPostNormalized(
                    post_id=str(getattr(p, "post_id")),
                    creator_username=getattr(p, "creator_username", None),
                    posted_at=getattr(p, "posted_at", None) or getattr(p, "published_at", None),
                    media_type=getattr(p, "media_type", None) or "Image",
                    likes=getattr(p, "likes", None),
                    comments=getattr(p, "comments", None) or getattr(p, "comments_count", None),
                    views=getattr(p, "views", None),
                    caption=getattr(p, "caption", None),
                    url=getattr(p, "url", None),
                    raw_payload=raw_payload if isinstance(raw_payload, dict) else None,
                )
                normalized_posts.append(norm)

        if not normalized_posts:
            return InstagramMetricsResult(
                followers=followers,
                posts_analyzed=0,
                views_analyzed=0,
                likes_analyzed=0,
                comments_analyzed=0,
                metrics_calculated_at=now,
            )

        # 2. Sort posts by posted_at DESC (posts without date sorted to end)
        min_dt = datetime.min.replace(tzinfo=timezone.utc)
        sorted_posts = sorted(
            normalized_posts,
            key=lambda x: x.posted_at if x.posted_at is not None else min_dt,
            reverse=True,
        )

        # 3. Take latest configurable sample window (default 20)
        recent_posts = sorted_posts[:max_posts]
        posts_analyzed = len(recent_posts)

        # 4. Extract valid metric samples (DO NOT treat missing as zero)
        views_sample: list[int] = [
            p.views for p in recent_posts if p.views is not None and p.views >= 0
        ]
        likes_sample: list[int] = [
            p.likes for p in recent_posts if p.likes is not None and p.likes >= 0
        ]
        comments_sample: list[int] = [
            p.comments for p in recent_posts if p.comments is not None and p.comments >= 0
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

        # 6. Engagement Rate calculation on eligible sample
        # Formula: ((average_likes + average_comments) / average_views) * 100
        engagement_rate: float | None = None
        if (
            average_views is not None
            and average_views > 0
            and (average_likes is not None or average_comments is not None)
        ):
            tot_interactions = (average_likes or 0.0) + (average_comments or 0.0)
            engagement_rate = round((tot_interactions / average_views) * 100.0, 2)

        # 7. Last post date
        valid_dates = [p.posted_at for p in recent_posts if p.posted_at is not None]
        last_post_date = max(valid_dates) if valid_dates else None

        return InstagramMetricsResult(
            followers=followers,
            posts_analyzed=posts_analyzed,
            views_analyzed=views_analyzed,
            likes_analyzed=likes_analyzed,
            comments_analyzed=comments_analyzed,
            average_views=average_views,
            median_views=median_views,
            average_likes=average_likes,
            median_likes=median_likes,
            average_comments=average_comments,
            median_comments=median_comments,
            engagement_rate=engagement_rate,
            last_post_date=last_post_date,
            metrics_calculated_at=now,
        )
