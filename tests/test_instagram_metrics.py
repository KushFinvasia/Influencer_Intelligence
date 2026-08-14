"""Unit tests for Instagram performance metrics calculator and normalization."""

from datetime import datetime, timezone
import pytest
from app.analytics.instagram_metrics import InstagramMetricsCalculator
from app.analytics.schemas import (
    InstagramPostNormalized,
    defensive_int_or_none,
    defensive_datetime_or_none,
    normalize_apify_instagram_post,
)


def test_defensive_int_or_none():
    assert defensive_int_or_none(100) == 100
    assert defensive_int_or_none("1,500") == 1500
    assert defensive_int_or_none("12.5k") == 12500
    assert defensive_int_or_none("2M") == 2000000
    assert defensive_int_or_none(None) is None
    assert defensive_int_or_none("") is None
    assert defensive_int_or_none("N/A") is None
    assert defensive_int_or_none("null") is None
    assert defensive_int_or_none(False) is None


def test_defensive_datetime_or_none():
    dt = defensive_datetime_or_none("2026-08-07T12:00:00Z")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 8 and dt.day == 7
    assert dt.tzinfo == timezone.utc

    epoch_dt = defensive_datetime_or_none(1700000000)
    assert epoch_dt is not None
    assert epoch_dt.tzinfo == timezone.utc

    assert defensive_datetime_or_none(None) is None
    assert defensive_datetime_or_none("invalid") is None


def test_normalize_apify_instagram_post():
    raw_item = {
        "id": "123456789",
        "shortCode": "CxYz123",
        "ownerUsername": "trader_sharma",
        "type": "Video",
        "likesCount": 250,
        "commentsCount": 15,
        "videoViewCount": 5000,
        "timestamp": "2026-08-01T10:00:00Z",
        "caption": "BankNifty options strategy #trading",
    }
    post = normalize_apify_instagram_post(raw_item)
    assert post is not None
    assert post.post_id == "123456789"
    assert post.creator_username == "trader_sharma"
    assert post.media_type == "Video"
    assert post.likes == 250
    assert post.comments == 15
    assert post.views == 5000
    assert post.caption == "BankNifty options strategy #trading"


def test_median_vs_mean_viral_distortion():
    """Verify median handles viral skewness properly."""
    # 19 posts with 10K views, 1 viral post with 2M views
    posts = []
    for i in range(19):
        posts.append(
            InstagramPostNormalized(
                post_id=f"p_{i}",
                views=10000,
                likes=500,
                comments=20,
                posted_at=datetime(2026, 8, i + 1, tzinfo=timezone.utc),
            )
        )
    # Add viral post
    posts.append(
        InstagramPostNormalized(
            post_id="p_viral",
            views=2000000,
            likes=100000,
            comments=5000,
            posted_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        )
    )

    metrics = InstagramMetricsCalculator.calculate_metrics(posts, followers=50000, max_posts=20)
    assert metrics.posts_analyzed == 20
    assert metrics.views_analyzed == 20
    assert metrics.likes_analyzed == 20
    assert metrics.comments_analyzed == 20
    
    # Average views is pulled way up by 2M post
    assert metrics.average_views == pytest.approx(109500.0, rel=1e-2)
    # Median views remains accurately 10,000.0 (typical performance)
    assert metrics.median_views == 10000.0
    assert metrics.median_likes == 500.0
    assert metrics.median_comments == 20.0


def test_missing_views_handling():
    """Verify missing views are stored as None and omitted from views_analyzed."""
    posts = [
        # Image post: No views
        InstagramPostNormalized(post_id="p1", likes=100, comments=10, views=None, posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        # Sidecar post: No views
        InstagramPostNormalized(post_id="p2", likes=200, comments=20, views=None, posted_at=datetime(2026, 8, 2, tzinfo=timezone.utc)),
        # Video post: 5000 views
        InstagramPostNormalized(post_id="p3", likes=300, comments=30, views=5000, posted_at=datetime(2026, 8, 3, tzinfo=timezone.utc)),
        # Reel post: 15000 views
        InstagramPostNormalized(post_id="p4", likes=400, comments=40, views=15000, posted_at=datetime(2026, 8, 4, tzinfo=timezone.utc)),
    ]

    metrics = InstagramMetricsCalculator.calculate_metrics(posts, followers=10000, max_posts=20)
    assert metrics.posts_analyzed == 4
    assert metrics.views_analyzed == 2  # Only the 2 video posts
    assert metrics.likes_analyzed == 4
    assert metrics.comments_analyzed == 4

    assert metrics.average_views == 10000.0
    assert metrics.median_views == 10000.0
    assert metrics.average_likes == 250.0
    assert metrics.median_likes == 250.0


def test_engagement_rate_calculation():
    """Verify creator engagement rate calculation formula: ((avg_likes + avg_comments) / avg_views) * 100."""
    posts = [
        InstagramPostNormalized(post_id="p1", likes=3800, comments=200, views=40000, posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        InstagramPostNormalized(post_id="p2", likes=4200, comments=220, views=45000, posted_at=datetime(2026, 8, 2, tzinfo=timezone.utc)),
    ]

    metrics = InstagramMetricsCalculator.calculate_metrics(posts, followers=185000, max_posts=20)
    # avg_views = 42500, avg_likes = 4000, avg_comments = 210
    # total interactions = 4210
    # engagement rate = (4210 / 42500) * 100 = 9.91%
    assert metrics.average_views == 42500.0
    assert metrics.average_likes == 4000.0
    assert metrics.average_comments == 210.0
    assert metrics.engagement_rate == pytest.approx(9.91, abs=0.01)


def test_zero_and_empty_edge_cases():
    """Verify safe division by zero and empty lists."""
    empty_metrics = InstagramMetricsCalculator.calculate_metrics([], followers=1000)
    assert empty_metrics.posts_analyzed == 0
    assert empty_metrics.views_analyzed == 0
    assert empty_metrics.average_views is None
    assert empty_metrics.engagement_rate is None

    # Posts with 0 views
    zero_views_posts = [
        InstagramPostNormalized(post_id="p0", likes=0, comments=0, views=0, posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    ]
    zero_metrics = InstagramMetricsCalculator.calculate_metrics(zero_views_posts, followers=1000)
    assert zero_metrics.engagement_rate is None
