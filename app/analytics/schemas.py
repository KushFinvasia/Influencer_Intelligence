"""Pydantic schemas and defensive normalization for Instagram performance analytics."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def defensive_int_or_none(val: Any) -> int | None:
    """Defensively convert a value to int or return None.
    
    Handles integers, floats, strings, None, and empty/invalid values.
    Does NOT treat missing values as zero.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val) if val >= 0 else None
    
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "").replace(" ", "")
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", "undefined", "-"):
            return None
        # Handle k/m suffixes defensively if present
        if cleaned.lower().endswith("k"):
            try:
                return int(float(cleaned[:-1]) * 1000)
            except ValueError:
                return None
        if cleaned.lower().endswith("m"):
            try:
                return int(float(cleaned[:-1]) * 1000000)
            except ValueError:
                return None
        try:
            val_num = float(cleaned)
            return int(val_num) if val_num >= 0 else None
        except ValueError:
            return None
            
    return None


def defensive_datetime_or_none(val: Any) -> datetime | None:
    """Defensively parse a datetime value or return None.
    
    Handles ISO-8601 strings, UNIX epoch timestamps (seconds or ms), and datetimes.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    
    if isinstance(val, (int, float)):
        # UNIX epoch in seconds or milliseconds
        ts = float(val)
        if ts > 1e11:  # milliseconds
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None
            
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", ""):
            return None
        try:
            # Handle standard ISO formats with Z or timezone offset
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
            
    return None


class InstagramPostNormalized(BaseModel):
    """Normalized post-level metric data preserving original values without loss."""
    post_id: str
    creator_username: str | None = None
    posted_at: datetime | None = None
    media_type: str = "Image"
    likes: int | None = None
    comments: int | None = None
    views: int | None = None
    caption: str | None = None
    url: str | None = None
    raw_payload: dict[str, Any] | None = None


def normalize_apify_instagram_post(
    item: dict[str, Any], default_username: str | None = None
) -> InstagramPostNormalized | None:
    """Defensively extract and normalize a post from raw Apify actor payloads.
    
    Handles variations between apify/instagram-profile-scraper and
    apify/instagram-hashtag-scraper across different schema versions.
    """
    if not isinstance(item, dict):
        return None

    # 1. Post ID
    post_id = (
        item.get("id")
        or item.get("shortCode")
        or item.get("code")
        or item.get("pk")
    )
    if not post_id:
        # Fallback from URL if available
        url = item.get("url") or ""
        match = re.search(r"/(?:p|reel|tv)/([^/?#]+)", str(url))
        if match:
            post_id = match.group(1)
        else:
            return None

    post_id = str(post_id).strip()

    # 2. Creator Username
    owner = item.get("owner")
    owner_username = None
    if isinstance(owner, dict):
        owner_username = owner.get("username")
    creator_username = (
        item.get("ownerUsername")
        or item.get("username")
        or owner_username
        or default_username
    )
    if creator_username:
        creator_username = str(creator_username).strip().lstrip("@").lower()

    # 3. Posted At Timestamp
    raw_time = (
        item.get("timestamp")
        or item.get("takenAt")
        or item.get("taken_at_timestamp")
        or item.get("publishedAt")
        or item.get("date")
    )
    posted_at = defensive_datetime_or_none(raw_time)

    # 4. Media Type
    raw_type = item.get("type") or item.get("__typename") or item.get("productType") or ""
    raw_type_str = str(raw_type).lower()
    is_video = bool(
        item.get("isVideo")
        or item.get("is_video")
        or "video" in raw_type_str
        or "reel" in raw_type_str
        or item.get("videoPlayCount") is not None
        or item.get("videoViewCount") is not None
    )

    if "sidecar" in raw_type_str or "carousel" in raw_type_str or "graphsidecar" in raw_type_str:
        media_type = "Sidecar"
    elif "reel" in raw_type_str or "clips" in raw_type_str:
        media_type = "Reel"
    elif is_video:
        media_type = "Video"
    else:
        media_type = "Image"

    # 5. Likes (Nullable, NOT 0 if missing)
    likes = defensive_int_or_none(
        item.get("likesCount")
        if item.get("likesCount") is not None
        else item.get("like_count")
        if item.get("like_count") is not None
        else item.get("likes")
    )

    # 6. Comments (Nullable, NOT 0 if missing)
    comments = defensive_int_or_none(
        item.get("commentsCount")
        if item.get("commentsCount") is not None
        else item.get("comment_count")
        if item.get("comment_count") is not None
        else item.get("comments")
    )

    # 7. Views (Nullable, only for videos/reels or when explicit view count provided)
    views = defensive_int_or_none(
        item.get("videoPlayCount")
        if item.get("videoPlayCount") is not None
        else item.get("videoViewCount")
        if item.get("videoViewCount") is not None
        else item.get("viewCount")
        if item.get("viewCount") is not None
        else item.get("play_count")
        if item.get("play_count") is not None
        else item.get("views")
    )

    # 8. Caption
    caption = item.get("caption") or item.get("text") or item.get("title")
    if caption is not None:
        caption = str(caption).strip()

    # 9. URL
    short_code = item.get("shortCode") or item.get("code") or post_id
    url = item.get("url") or f"https://www.instagram.com/p/{short_code}/"

    return InstagramPostNormalized(
        post_id=post_id,
        creator_username=creator_username,
        posted_at=posted_at,
        media_type=media_type,
        likes=likes,
        comments=comments,
        views=views,
        caption=caption,
        url=str(url),
        raw_payload=item,
    )


class InstagramMetricsResult(BaseModel):
    """Creator-level performance metric snapshot."""
    followers: int | None = None
    posts_analyzed: int = 0
    views_analyzed: int = 0
    likes_analyzed: int = 0
    comments_analyzed: int = 0
    average_views: float | None = None
    median_views: float | None = None
    average_likes: float | None = None
    median_likes: float | None = None
    average_comments: float | None = None
    median_comments: float | None = None
    engagement_rate: float | None = None
    last_post_date: datetime | None = None
    metrics_calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# YouTube Schemas & Defensive Normalization
# ---------------------------------------------------------------------------

def is_youtube_short(duration: str | None, title: str | None = None, description: str | None = None) -> bool:
    """Check if a video is a YouTube Short (duration <= 60s or #shorts tag)."""
    if duration:
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            total_seconds = hours * 3600 + minutes * 60 + seconds
            if total_seconds <= 60 and total_seconds > 0:
                return True
    
    text_content = f"{title or ''} {description or ''}".lower()
    if "#shorts" in text_content or "#short" in text_content:
        return True
    return False


class YouTubeVideoNormalized(BaseModel):
    """Normalized YouTube video metric data preserving raw values without loss."""
    video_id: str
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    duration: str | None = None
    is_short: bool = False
    thumbnail_url: str | None = None
    url: str | None = None
    raw_payload: dict[str, Any] | None = None


def normalize_youtube_video(
    item: dict[str, Any] | Any,
) -> YouTubeVideoNormalized | None:
    """Defensively extract and normalize a video from raw YouTube API payload.
    
    Preserves raw_payload and does NOT coerce missing stats to 0.
    """
    if not isinstance(item, dict):
        return None

    # 1. Video ID
    video_id = item.get("id")
    if isinstance(video_id, dict):
        video_id = video_id.get("videoId")
    if not video_id:
        return None
    video_id = str(video_id).strip()

    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    content_details = item.get("contentDetails") or {}

    # 2. Metadata
    channel_id = snippet.get("channelId")
    title = snippet.get("title")
    description = snippet.get("description")
    raw_published = snippet.get("publishedAt")
    published_at = defensive_datetime_or_none(raw_published)

    # 3. Duration & Shorts detection
    duration = content_details.get("duration")
    is_short = is_youtube_short(duration, title, description)

    # 4. Metrics (Nullable, NOT 0 if missing)
    views = defensive_int_or_none(
        stats.get("viewCount")
        if stats.get("viewCount") is not None
        else item.get("views")
    )
    likes = defensive_int_or_none(
        stats.get("likeCount")
        if stats.get("likeCount") is not None
        else item.get("likes")
    )
    comments = defensive_int_or_none(
        stats.get("commentCount")
        if stats.get("commentCount") is not None
        else stats.get("commentsCount")
        if stats.get("commentsCount") is not None
        else item.get("comments_count")
    )

    # 5. Thumbnail & URL
    thumbnails = snippet.get("thumbnails") or {}
    high_thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
    thumbnail_url = high_thumb.get("url") if isinstance(high_thumb, dict) else None
    url = f"https://www.youtube.com/watch?v={video_id}"

    return YouTubeVideoNormalized(
        video_id=video_id,
        channel_id=str(channel_id) if channel_id else None,
        title=str(title) if title else None,
        description=str(description) if description else None,
        published_at=published_at,
        views=views,
        likes=likes,
        comments=comments,
        duration=str(duration) if duration else None,
        is_short=is_short,
        thumbnail_url=thumbnail_url,
        url=url,
        raw_payload=item,
    )


class YouTubeMetricsResult(BaseModel):
    """Creator-level YouTube performance metric snapshot."""
    subscribers: int | None = None
    videos_analyzed: int = 0
    views_analyzed: int = 0
    likes_analyzed: int = 0
    comments_analyzed: int = 0
    engagement_eligible_videos: int = 0
    average_views: float | None = None
    median_views: float | None = None
    average_likes: float | None = None
    median_likes: float | None = None
    average_comments: float | None = None
    median_comments: float | None = None
    engagement_rate: float | None = None
    shorts_ratio: float | None = None
    last_video_date: datetime | None = None
    metrics_calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

