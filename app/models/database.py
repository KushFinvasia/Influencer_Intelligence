"""SQLAlchemy ORM models for the Creator Intelligence Platform.

14 tables covering creators, platform profiles, content, engagement,
relationships, classifications, and operational logs.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship

# Use JSONB on PostgreSQL, standard JSON on SQLite/others
JSONB_TYPE = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CreatorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DORMANT = "DORMANT"
    SUSPENDED = "SUSPENDED"
    PRIVATE = "PRIVATE"


class DetectionMethod(str, enum.Enum):
    RULE = "rule"
    LLM = "llm"
    MANUAL = "manual"


class BrokerRelationshipType(str, enum.Enum):
    AFFILIATE = "affiliate"
    REFERRAL = "referral"
    BRAND_AMBASSADOR = "brand_ambassador"
    SPONSORED = "sponsored"
    PAST_PARTNER = "past_partner"
    MENTION_ONLY = "mention_only"


class RelationshipType(str, enum.Enum):
    COLLABORATION = "collaboration"
    MENTION = "mention"
    FEATURED = "featured"
    PODCAST = "podcast"
    PLAYLIST = "playlist"
    COMMENT = "comment"


class ScrapeJobType(str, enum.Enum):
    FULL = "full"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    REFRESH = "refresh"


class ScrapeJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PostType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"


# ---------------------------------------------------------------------------
# Lookup Tables
# ---------------------------------------------------------------------------

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)

    creator_categories = relationship("CreatorCategory", back_populates="category")


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)


# ---------------------------------------------------------------------------
# Core Tables
# ---------------------------------------------------------------------------

class Creator(Base):
    """Central deduplicated creator entity."""
    __tablename__ = "creators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False, index=True)
    email = Column(String(500), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(1000), nullable=True)

    # Classification
    audience_bucket = Column(Integer, nullable=True)  # 1, 2, 3, 4
    creator_type = Column(String(100), nullable=True)
    creator_type_confidence = Column(Float, nullable=True)
    creator_type_method = Column(
        Enum(DetectionMethod), nullable=True
    )
    primary_language = Column(String(100), nullable=True)
    language_confidence = Column(Float, nullable=True)
    language_method = Column(
        Enum(DetectionMethod), nullable=True
    )
    primary_category = Column(String(100), nullable=True)

    # Status & scoring
    status = Column(
        Enum(CreatorStatus), default=CreatorStatus.ACTIVE, nullable=False, index=True
    )
    influencer_score = Column(Float, nullable=True, index=True)
    score_breakdown = Column(JSONB_TYPE, nullable=True)

    # Review
    needs_review = Column(Boolean, default=False, nullable=False, index=True)
    review_reason = Column(Text, nullable=True)

    # Cache
    last_enriched_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    platform_profiles = relationship(
        "PlatformProfile", back_populates="creator", cascade="all, delete-orphan"
    )
    social_links = relationship(
        "SocialLink", back_populates="creator", cascade="all, delete-orphan"
    )
    broker_associations = relationship(
        "BrokerAssociation", back_populates="creator", cascade="all, delete-orphan"
    )
    creator_categories = relationship(
        "CreatorCategory", back_populates="creator", cascade="all, delete-orphan"
    )
    llm_logs = relationship(
        "LLMLog", back_populates="creator", cascade="all, delete-orphan"
    )
    instagram_metrics = relationship(
        "InstagramMetric", back_populates="creator", cascade="all, delete-orphan"
    )
    youtube_metrics = relationship(
        "YouTubeMetric", back_populates="creator", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_creators_bucket_score", "audience_bucket", "influencer_score"),
    )


class PlatformProfile(Base):
    """One profile per platform per creator."""
    __tablename__ = "platform_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    platform = Column(String(50), nullable=False, index=True)  # youtube, instagram
    platform_user_id = Column(String(500), nullable=False)  # channel_id, username
    username = Column(String(500), nullable=True)
    display_name = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    followers = Column(Integer, nullable=True)
    following = Column(Integer, nullable=True)
    video_count = Column(Integer, nullable=True)
    verified = Column(Boolean, default=False)
    profile_url = Column(String(1000), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    raw_data = Column(JSONB_TYPE, nullable=True)  # Original API response
    discovered_via = Column(JSONB_TYPE, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    creator = relationship("Creator", back_populates="platform_profiles")
    videos = relationship(
        "Video", back_populates="platform_profile", cascade="all, delete-orphan"
    )
    posts = relationship(
        "Post", back_populates="platform_profile", cascade="all, delete-orphan"
    )
    engagement_metrics = relationship(
        "EngagementMetric",
        back_populates="platform_profile",
        cascade="all, delete-orphan",
    )
    instagram_metrics = relationship(
        "InstagramMetric",
        back_populates="platform_profile",
        cascade="all, delete-orphan",
    )
    youtube_metrics = relationship(
        "YouTubeMetric",
        back_populates="platform_profile",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_platform_user"),
        Index("ix_platform_profiles_creator", "creator_id"),
    )


# ---------------------------------------------------------------------------
# Content Tables
# ---------------------------------------------------------------------------

class Video(Base):
    """YouTube videos / Instagram reels."""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_profile_id = Column(
        Integer,
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_id = Column(String(500), nullable=False, index=True)
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments_count = Column(Integer, nullable=True)
    duration = Column(String(50), nullable=True)  # ISO 8601 duration
    is_short = Column(Boolean, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    raw_payload = Column(JSONB_TYPE, nullable=True)  # Original API response

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    platform_profile = relationship("PlatformProfile", back_populates="videos")

    __table_args__ = (
        UniqueConstraint("platform_profile_id", "video_id", name="uq_video"),
    )


class Post(Base):
    """Instagram posts and reels."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_profile_id = Column(
        Integer,
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_id = Column(String(500), nullable=False, index=True)
    creator_username = Column(String(500), nullable=True, index=True)
    caption = Column(Text, nullable=True)
    media_type = Column(String(50), nullable=True)  # Video, Image, Sidecar, Reel
    likes = Column(Integer, nullable=True)
    comments_count = Column(Integer, nullable=True)
    views = Column(Integer, nullable=True)  # NULL for non-videos, not 0
    post_type = Column(Enum(PostType), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    url = Column(String(1000), nullable=True)
    raw_payload = Column(JSONB_TYPE, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    platform_profile = relationship("PlatformProfile", back_populates="posts")

    __table_args__ = (
        UniqueConstraint("platform_profile_id", "post_id", name="uq_post"),
    )


class InstagramMetric(Base):
    """Timestamped historical performance metric snapshot for an Instagram creator."""
    __tablename__ = "instagram_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_profile_id = Column(
        Integer,
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    followers = Column(Integer, nullable=True)
    posts_analyzed = Column(Integer, default=0, nullable=False)
    views_analyzed = Column(Integer, default=0, nullable=False)
    likes_analyzed = Column(Integer, default=0, nullable=False)
    comments_analyzed = Column(Integer, default=0, nullable=False)
    average_views = Column(Float, nullable=True)
    median_views = Column(Float, nullable=True)
    average_likes = Column(Float, nullable=True)
    median_likes = Column(Float, nullable=True)
    average_comments = Column(Float, nullable=True)
    median_comments = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)  # ((avg_likes + avg_comments) / avg_views) * 100
    last_post_date = Column(DateTime(timezone=True), nullable=True)
    metrics_calculated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    creator = relationship("Creator", back_populates="instagram_metrics")
    platform_profile = relationship("PlatformProfile", back_populates="instagram_metrics")

    __table_args__ = (
        Index("ix_insta_metrics_creator_time", "creator_id", "metrics_calculated_at"),
    )


class YouTubeMetric(Base):
    """Timestamped historical performance metric snapshot for a YouTube creator."""
    __tablename__ = "youtube_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_profile_id = Column(
        Integer,
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subscribers = Column(Integer, nullable=True)
    videos_analyzed = Column(Integer, default=0, nullable=False)
    views_analyzed = Column(Integer, default=0, nullable=False)
    likes_analyzed = Column(Integer, default=0, nullable=False)
    comments_analyzed = Column(Integer, default=0, nullable=False)
    engagement_eligible_videos = Column(Integer, default=0, nullable=False)
    average_views = Column(Float, nullable=True)
    median_views = Column(Float, nullable=True)
    average_likes = Column(Float, nullable=True)
    median_likes = Column(Float, nullable=True)
    average_comments = Column(Float, nullable=True)
    median_comments = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)  # ((avg_likes + avg_comments) / avg_views) * 100 on eligible sample
    shorts_ratio = Column(Float, nullable=True)
    last_video_date = Column(DateTime(timezone=True), nullable=True)
    metrics_calculated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    creator = relationship("Creator", back_populates="youtube_metrics")
    platform_profile = relationship("PlatformProfile", back_populates="youtube_metrics")

    __table_args__ = (
        Index("ix_youtube_metrics_creator_time", "creator_id", "metrics_calculated_at"),
    )


class EngagementMetric(Base):
    """Computed engagement metrics for a platform profile."""
    __tablename__ = "engagement_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_profile_id = Column(
        Integer,
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    avg_views = Column(Float, nullable=True)
    avg_likes = Column(Float, nullable=True)
    avg_comments = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)  # percentage
    upload_frequency_per_month = Column(Float, nullable=True)
    last_upload_at = Column(DateTime(timezone=True), nullable=True)
    shorts_ratio = Column(Float, nullable=True)  # 0.0 – 1.0
    calculated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    platform_profile = relationship(
        "PlatformProfile", back_populates="engagement_metrics"
    )


# ---------------------------------------------------------------------------
# Relationship & Classification Tables
# ---------------------------------------------------------------------------

class SocialLink(Base):
    """Extracted contact and social links for a creator."""
    __tablename__ = "social_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    platform = Column(
        String(50), nullable=False
    )  # email, phone, telegram, whatsapp, etc.
    url = Column(String(1000), nullable=True)
    value = Column(String(500), nullable=True)  # e.g. email address, phone number
    extracted_from = Column(String(100), nullable=True)  # bio, description, linktree

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator = relationship("Creator", back_populates="social_links")

    __table_args__ = (
        Index("ix_social_links_creator", "creator_id"),
        UniqueConstraint(
            "creator_id", "platform", "value", name="uq_social_link"
        ),
    )


class BrokerAssociation(Base):
    """Detected broker relationships for a creator."""
    __tablename__ = "broker_associations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    broker_name = Column(String(200), nullable=False, index=True)
    relationship_type = Column(
        Enum(BrokerRelationshipType), nullable=True
    )
    confidence = Column(Float, nullable=False, default=0.0)
    detection_method = Column(
        Enum(DetectionMethod), nullable=True
    )
    evidence = Column(Text, nullable=True)
    evidence_urls = Column(JSONB_TYPE, nullable=True)  # Array of URLs

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator = relationship("Creator", back_populates="broker_associations")


class CreatorCategory(Base):
    """Many-to-many relationship between creators and categories with % breakdown."""
    __tablename__ = "creator_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    is_primary = Column(Boolean, default=False, nullable=False)
    content_percentage = Column(Float, nullable=True)  # e.g. 60.0
    confidence = Column(Float, nullable=True)
    detection_method = Column(
        Enum(DetectionMethod), nullable=True
    )

    creator = relationship("Creator", back_populates="creator_categories")
    category = relationship("Category", back_populates="creator_categories")

    __table_args__ = (
        UniqueConstraint("creator_id", "category_id", name="uq_creator_category"),
        Index("ix_creator_categories_category", "category_id"),
    )


class CreatorRelationship(Base):
    """Discovery graph edges between creators."""
    __tablename__ = "creator_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    target_creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="CASCADE"), nullable=True
    )
    target_platform_id = Column(
        String(500), nullable=True
    )  # If target not yet in DB
    relationship_type = Column(
        Enum(RelationshipType), nullable=False
    )
    evidence_url = Column(String(1000), nullable=True)
    discovered_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_creator = relationship(
        "Creator", foreign_keys=[source_creator_id]
    )
    target_creator = relationship(
        "Creator", foreign_keys=[target_creator_id]
    )

    __table_args__ = (
        Index("ix_creator_rel_source", "source_creator_id"),
        Index("ix_creator_rel_target", "target_creator_id"),
    )


# ---------------------------------------------------------------------------
# Operational Tables
# ---------------------------------------------------------------------------

class ScrapeJob(Base):
    """Top-level scrape job tracker."""
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(Enum(ScrapeJobType), nullable=False)
    status = Column(
        Enum(ScrapeJobStatus), default=ScrapeJobStatus.QUEUED, nullable=False
    )
    keywords = Column(JSONB_TYPE, nullable=True)
    total_discovered = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    total_new = Column(Integer, default=0)
    total_updated = Column(Integer, default=0)
    discovery_depth = Column(Integer, default=1)
    error_message = Column(Text, nullable=True)
    keyword_metrics = Column(JSONB_TYPE, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    logs = relationship(
        "ScrapeLog", back_populates="scrape_job", cascade="all, delete-orphan"
    )


class ScrapeLog(Base):
    """Per-action audit trail within a scrape job."""
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scrape_job_id = Column(
        Integer, ForeignKey("scrape_jobs.id", ondelete="CASCADE"), nullable=False
    )
    platform = Column(String(50), nullable=False)
    keyword = Column(String(500), nullable=True)
    action = Column(
        String(100), nullable=False
    )  # search, channel_fetch, video_fetch, etc.
    status = Column(String(50), nullable=False)
    api_units_used = Column(Integer, default=0)
    items_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scrape_job = relationship("ScrapeJob", back_populates="logs")


class LLMLog(Base):
    """Full LLM call audit trail."""
    __tablename__ = "llm_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(
        Integer, ForeignKey("creators.id", ondelete="SET NULL"), nullable=True
    )
    task = Column(
        String(100), nullable=False
    )  # category, language, creator_type, broker
    model_used = Column(String(200), nullable=False)
    input_text = Column(Text, nullable=True)  # Cleaned/preprocessed input
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    raw_response = Column(Text, nullable=True)
    parsed_result = Column(JSONB_TYPE, nullable=True)
    reasoning = Column(Text, nullable=True)
    evidence = Column(JSONB_TYPE, nullable=True)  # Array of video_ids / post_ids
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator = relationship("Creator", back_populates="llm_logs")
