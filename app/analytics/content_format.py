"""Content Format Classification for YouTube and Instagram creators.

Differentiates:
- YouTube: Longform vs Short-Form (Shorts) vs Hybrid
- Instagram: Reels (Short-Form) vs Educational Carousels vs Images vs Mixed Media
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContentFormat(str, Enum):
    LONGFORM = "Longform"
    SHORT_FORM = "Short-Form"
    HYBRID = "Hybrid"
    CAROUSELS = "Carousels"
    IMAGES = "Images"
    UNKNOWN = "Unknown"


@dataclass
class FormatAnalysisResult:
    format_type: ContentFormat
    label: str
    filter_group: str  # "longform", "shortform", "hybrid", "carousels", "images"
    breakdown_text: str
    primary_ratio: float


def classify_youtube_format(
    shorts_ratio: float | None, videos_analyzed: int = 0
) -> FormatAnalysisResult:
    """Classify YouTube creator based on shorts ratio."""
    if shorts_ratio is None or videos_analyzed == 0:
        return FormatAnalysisResult(
            format_type=ContentFormat.UNKNOWN,
            label="-",
            filter_group="all",
            breakdown_text="No videos analyzed",
            primary_ratio=0.0,
        )

    longform_ratio = max(0.0, min(1.0, 1.0 - shorts_ratio))
    long_pct = int(round(longform_ratio * 100))
    short_pct = int(round(shorts_ratio * 100))

    if shorts_ratio <= 0.20:
        return FormatAnalysisResult(
            format_type=ContentFormat.LONGFORM,
            label=f"🎬 Longform ({long_pct}%)",
            filter_group="longform",
            breakdown_text=f"{long_pct}% Longform, {short_pct}% Shorts",
            primary_ratio=longform_ratio,
        )
    elif shorts_ratio >= 0.80:
        return FormatAnalysisResult(
            format_type=ContentFormat.SHORT_FORM,
            label=f"📱 Shorts ({short_pct}%)",
            filter_group="shortform",
            breakdown_text=f"{short_pct}% Shorts, {long_pct}% Longform",
            primary_ratio=shorts_ratio,
        )
    else:
        return FormatAnalysisResult(
            format_type=ContentFormat.HYBRID,
            label=f"⚖️ Hybrid ({long_pct}% L / {short_pct}% S)",
            filter_group="hybrid",
            breakdown_text=f"{long_pct}% Longform, {short_pct}% Shorts",
            primary_ratio=max(longform_ratio, shorts_ratio),
        )


def classify_instagram_format(
    media_counts: dict[str, int], total_posts: int = 0
) -> FormatAnalysisResult:
    """Classify Instagram creator format based on post media types."""
    if total_posts == 0:
        return FormatAnalysisResult(
            format_type=ContentFormat.SHORT_FORM,
            label="📱 Reels / Short-Form",
            filter_group="shortform",
            breakdown_text="Instagram Short-Form / Reels",
            primary_ratio=1.0,
        )

    videos = media_counts.get("video", 0) + media_counts.get("reel", 0)
    carousels = (
        media_counts.get("sidecar", 0)
        + media_counts.get("carousel", 0)
        + media_counts.get("album", 0)
    )
    images = media_counts.get("image", 0) + media_counts.get("photo", 0)

    video_pct = int(round((videos / total_posts) * 100))
    carousel_pct = int(round((carousels / total_posts) * 100))
    image_pct = int(round((images / total_posts) * 100))

    if videos / total_posts >= 0.70 or (carousels == 0 and images == 0):
        return FormatAnalysisResult(
            format_type=ContentFormat.SHORT_FORM,
            label=f"📱 Reels ({video_pct}%)",
            filter_group="shortform",
            breakdown_text=f"{video_pct}% Reels, {carousel_pct}% Carousels, {image_pct}% Images",
            primary_ratio=videos / total_posts,
        )
    elif carousels / total_posts >= 0.50:
        return FormatAnalysisResult(
            format_type=ContentFormat.CAROUSELS,
            label=f"📑 Carousels ({carousel_pct}%)",
            filter_group="carousels",
            breakdown_text=f"{carousel_pct}% Educational Carousels, {video_pct}% Reels, {image_pct}% Images",
            primary_ratio=carousels / total_posts,
        )
    elif images / total_posts >= 0.50:
        return FormatAnalysisResult(
            format_type=ContentFormat.IMAGES,
            label=f"🖼️ Images ({image_pct}%)",
            filter_group="images",
            breakdown_text=f"{image_pct}% Single Images, {video_pct}% Reels, {carousel_pct}% Carousels",
            primary_ratio=images / total_posts,
        )
    else:
        return FormatAnalysisResult(
            format_type=ContentFormat.HYBRID,
            label=f"⚖️ Mixed ({video_pct}% R / {carousel_pct}% C)",
            filter_group="hybrid",
            breakdown_text=f"{video_pct}% Reels, {carousel_pct}% Carousels, {image_pct}% Images",
            primary_ratio=max(video_pct, carousel_pct) / 100.0,
        )
