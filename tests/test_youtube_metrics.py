"""Unit tests for YouTube Creator Performance Analytics engine and defensive normalization."""

from datetime import datetime, timezone
import pytest

from app.analytics.schemas import (
    YouTubeMetricsResult,
    YouTubeVideoNormalized,
    defensive_datetime_or_none,
    defensive_int_or_none,
    is_youtube_short,
    normalize_youtube_video,
)
from app.analytics.youtube_metrics import YouTubeMetricsCalculator


def test_defensive_normalization_raw_payload():
    """Verify defensive normalization correctly parses YouTube API videos.list item and retains raw_payload."""
    raw_item = {
        "kind": "youtube#video",
        "id": "vid_abc123",
        "snippet": {
            "channelId": "UC_test_channel",
            "title": "Nifty 50 Trading Strategy",
            "description": "Full options trading breakdown #finance",
            "publishedAt": "2026-05-10T14:30:00Z",
            "thumbnails": {
                "high": {"url": "https://img.youtube.com/vi/vid_abc123/hqdefault.jpg"}
            },
        },
        "contentDetails": {
            "duration": "PT15M30S",
        },
        "statistics": {
            "viewCount": "45000",
            "likeCount": "1200",
            "commentCount": "85",
        },
    }

    norm = normalize_youtube_video(raw_item)
    assert norm is not None
    assert norm.video_id == "vid_abc123"
    assert norm.channel_id == "UC_test_channel"
    assert norm.title == "Nifty 50 Trading Strategy"
    assert norm.views == 45000
    assert norm.likes == 1200
    assert norm.comments == 85
    assert norm.is_short is False
    assert norm.duration == "PT15M30S"
    assert norm.published_at == datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert norm.raw_payload == raw_item


def test_shorts_detection():
    """Verify shorts detection via duration (<=60s) or #shorts tag."""
    assert is_youtube_short("PT30S", "My video", "description") is True
    assert is_youtube_short("PT1M", "My video", "description") is True
    assert is_youtube_short("PT1M1S", "My video", "description") is False
    assert is_youtube_short("PT5M", "Quick option trick #shorts", "description") is True
    assert is_youtube_short(None, "Another video", "Check this #short out") is True
    assert is_youtube_short("PT10M", "Standard video", "No tags") is False


def test_missing_metrics_preserved_as_none():
    """Verify that disabled comments or hidden likes produce None, not 0."""
    raw_item = {
        "id": "vid_hidden_stats",
        "snippet": {
            "title": "Video with disabled comments",
            "publishedAt": "2026-06-01T10:00:00Z",
        },
        "statistics": {
            "viewCount": "10000",
            # likeCount and commentCount intentionally omitted by API
        },
    }
    norm = normalize_youtube_video(raw_item)
    assert norm is not None
    assert norm.views == 10000
    assert norm.likes is None
    assert norm.comments is None


def test_median_vs_mean_viral_distortion():
    """Verify median protects against 1 viral video skewing creator averages."""
    # 9 videos at 1,000 views, 1 viral video at 1,000,000 views
    videos = [
        YouTubeVideoNormalized(
            video_id=f"vid_{i}",
            views=1000,
            likes=50,
            comments=10,
            published_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        )
        for i in range(9)
    ]
    viral_video = YouTubeVideoNormalized(
        video_id="vid_viral",
        views=1000000,
        likes=50000,
        comments=10000,
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    videos.append(viral_video)

    metrics = YouTubeMetricsCalculator.calculate_metrics(videos, subscribers=100000, max_videos=20)
    assert metrics.videos_analyzed == 10
    assert metrics.views_analyzed == 10
    # Mean views: (9000 + 1000000) / 10 = 100,900
    assert metrics.average_views == 100900.0
    # Median views should be 1,000 (typical performance)
    assert metrics.median_views == 1000.0
    assert metrics.median_likes == 50.0
    assert metrics.median_comments == 10.0


def test_engagement_only_from_eligible_videos():
    """Verify engagement rate is computed ONLY from videos where views, likes, and comments are all present."""
    videos = [
        # Eligible video 1: 10,000 views, 200 likes, 50 comments (250 interactions / 10,000 = 2.5%)
        YouTubeVideoNormalized(
            video_id="v1",
            views=10000,
            likes=200,
            comments=50,
            published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
        # Eligible video 2: 20,000 views, 400 likes, 100 comments (500 interactions / 20,000 = 2.5%)
        YouTubeVideoNormalized(
            video_id="v2",
            views=20000,
            likes=400,
            comments=100,
            published_at=datetime(2026, 2, 2, tzinfo=timezone.utc),
        ),
        # Ineligible video 3: views present, but likes disabled (None)
        YouTubeVideoNormalized(
            video_id="v3",
            views=50000,
            likes=None,
            comments=20,
            published_at=datetime(2026, 2, 3, tzinfo=timezone.utc),
        ),
        # Ineligible video 4: views present, but comments disabled (None)
        YouTubeVideoNormalized(
            video_id="v4",
            views=80000,
            likes=500,
            comments=None,
            published_at=datetime(2026, 2, 4, tzinfo=timezone.utc),
        ),
    ]

    metrics = YouTubeMetricsCalculator.calculate_metrics(videos, subscribers=50000, max_videos=20)
    assert metrics.videos_analyzed == 4
    assert metrics.views_analyzed == 4
    assert metrics.likes_analyzed == 3
    assert metrics.comments_analyzed == 3
    # Only v1 and v2 are eligible for engagement calculation
    assert metrics.engagement_eligible_videos == 2
    # Total eligible interactions: (200 + 50) + (400 + 100) = 750
    # Total eligible views: 10,000 + 20,000 = 30,000
    # Engagement rate: (750 / 30,000) * 100 = 2.5%
    assert metrics.engagement_rate == 2.5


def test_shorts_ratio_and_empty_edge_cases():
    """Verify shorts ratio and handling of empty / zero views cases."""
    # Empty videos
    res_empty = YouTubeMetricsCalculator.calculate_metrics([], subscribers=1000)
    assert res_empty.videos_analyzed == 0
    assert res_empty.engagement_eligible_videos == 0
    assert res_empty.engagement_rate is None
    assert res_empty.shorts_ratio is None

    # Mixed shorts and long-form videos
    mixed_videos = [
        YouTubeVideoNormalized(video_id="s1", views=5000, likes=100, comments=10, is_short=True),
        YouTubeVideoNormalized(video_id="s2", views=6000, likes=120, comments=12, is_short=True),
        YouTubeVideoNormalized(video_id="l1", views=20000, likes=400, comments=40, is_short=False),
        YouTubeVideoNormalized(video_id="l2", views=30000, likes=600, comments=60, is_short=False),
    ]
    res_mixed = YouTubeMetricsCalculator.calculate_metrics(mixed_videos, subscribers=10000)
    assert res_mixed.videos_analyzed == 4
    assert res_mixed.shorts_ratio == 0.5  # 2 out of 4 are shorts
    assert res_mixed.engagement_eligible_videos == 4
