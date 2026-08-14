"""Unit tests for YouTube and Instagram Content Format Classification."""

import pytest
from app.analytics.content_format import (
    ContentFormat,
    classify_instagram_format,
    classify_youtube_format,
)


def test_youtube_longform_classification():
    """Verify creators with <= 20% shorts are classified as Longform."""
    res = classify_youtube_format(shorts_ratio=0.05, videos_analyzed=20)
    assert res.format_type == ContentFormat.LONGFORM
    assert "🎬 Longform (95%)" in res.label
    assert res.filter_group == "longform"

    res_zero = classify_youtube_format(shorts_ratio=0.0, videos_analyzed=20)
    assert res_zero.format_type == ContentFormat.LONGFORM
    assert "🎬 Longform (100%)" in res_zero.label


def test_youtube_shorts_classification():
    """Verify creators with >= 80% shorts are classified as Short-Form."""
    res = classify_youtube_format(shorts_ratio=0.90, videos_analyzed=20)
    assert res.format_type == ContentFormat.SHORT_FORM
    assert "📱 Shorts (90%)" in res.label
    assert res.filter_group == "shortform"

    res_all_shorts = classify_youtube_format(shorts_ratio=1.0, videos_analyzed=20)
    assert res_all_shorts.format_type == ContentFormat.SHORT_FORM
    assert "📱 Shorts (100%)" in res_all_shorts.label


def test_youtube_hybrid_classification():
    """Verify creators with 21%-79% shorts are classified as Hybrid."""
    res = classify_youtube_format(shorts_ratio=0.50, videos_analyzed=20)
    assert res.format_type == ContentFormat.HYBRID
    assert "⚖️ Hybrid" in res.label
    assert res.filter_group == "hybrid"


def test_youtube_empty_data():
    """Verify no videos or None shorts ratio returns unknown/empty."""
    res = classify_youtube_format(shorts_ratio=None, videos_analyzed=0)
    assert res.format_type == ContentFormat.UNKNOWN
    assert res.label == "-"
    assert res.filter_group == "all"


def test_instagram_reels_classification():
    """Verify Instagram creator with >=70% videos is classified as Reels / Short-Form."""
    counts = {"video": 18, "sidecar": 2, "image": 0}
    res = classify_instagram_format(counts, total_posts=20)
    assert res.format_type == ContentFormat.SHORT_FORM
    assert "📱 Reels (90%)" in res.label
    assert res.filter_group == "shortform"


def test_instagram_carousels_classification():
    """Verify Instagram creator with >=50% carousels is classified as Educational Carousels."""
    counts = {"video": 3, "sidecar": 12, "image": 5}
    res = classify_instagram_format(counts, total_posts=20)
    assert res.format_type == ContentFormat.CAROUSELS
    assert "📑 Carousels (60%)" in res.label
    assert res.filter_group == "carousels"


def test_instagram_images_classification():
    """Verify Instagram creator with >=50% images is classified as Single Images."""
    counts = {"video": 2, "sidecar": 2, "image": 16}
    res = classify_instagram_format(counts, total_posts=20)
    assert res.format_type == ContentFormat.IMAGES
    assert "🖼️ Images (80%)" in res.label
    assert res.filter_group == "images"


def test_instagram_mixed_classification():
    """Verify Instagram creator with balanced media types is classified as Mixed."""
    counts = {"video": 8, "sidecar": 8, "image": 4}
    res = classify_instagram_format(counts, total_posts=20)
    assert res.format_type == ContentFormat.HYBRID
    assert "⚖️ Mixed" in res.label
    assert res.filter_group == "hybrid"


def test_instagram_empty_data():
    """Verify empty Instagram posts defaults cleanly to Reels/Short-form."""
    res = classify_instagram_format({}, total_posts=0)
    assert res.format_type == ContentFormat.SHORT_FORM
    assert "📱 Reels / Short-Form" in res.label
