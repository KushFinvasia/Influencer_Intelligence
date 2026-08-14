"""Pydantic schemas for creators, profiles, contacts, and classifications.

Every module communicates through these typed models — no raw dictionaries.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, EmailStr


# ---------------------------------------------------------------------------
# Enums (mirror DB enums for API layer)
# ---------------------------------------------------------------------------

class CreatorStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DORMANT = "DORMANT"
    SUSPENDED = "SUSPENDED"
    PRIVATE = "PRIVATE"


class DetectionMethodEnum(str, Enum):
    RULE = "rule"
    LLM = "llm"
    MANUAL = "manual"


class BrokerRelationshipEnum(str, Enum):
    AFFILIATE = "affiliate"
    REFERRAL = "referral"
    BRAND_AMBASSADOR = "brand_ambassador"
    SPONSORED = "sponsored"
    PAST_PARTNER = "past_partner"
    MENTION_ONLY = "mention_only"


# ---------------------------------------------------------------------------
# Pipeline Internal Models (used between modules)
# ---------------------------------------------------------------------------

class RawProfile(BaseModel):
    """Common format returned by all crawlers."""
    platform: str
    platform_user_id: str
    username: str | None = None
    display_name: str | None = None
    bio: str | None = None
    description: str | None = None
    followers: int | None = None
    following: int | None = None
    video_count: int | None = None
    verified: bool = False
    profile_url: str | None = None
    thumbnail_url: str | None = None
    country: str | None = None
    recent_video_titles: list[str] = Field(default_factory=list)
    recent_video_descriptions: list[str] = Field(default_factory=list)
    recent_video_ids: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    discovered_via: list[dict[str, str]] = Field(default_factory=list)


class ContactInfo(BaseModel):
    """Extracted contact information from a profile."""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    telegram: list[str] = Field(default_factory=list)
    whatsapp: list[str] = Field(default_factory=list)
    linkedin: list[str] = Field(default_factory=list)
    twitter: list[str] = Field(default_factory=list)
    facebook: list[str] = Field(default_factory=list)
    discord: list[str] = Field(default_factory=list)
    website: list[str] = Field(default_factory=list)
    linktree: list[str] = Field(default_factory=list)
    beacons: list[str] = Field(default_factory=list)
    carrd: list[str] = Field(default_factory=list)


class BrokerInfo(BaseModel):
    """Detected broker association."""
    broker_name: str
    relationship_type: BrokerRelationshipEnum | None = None
    confidence: float
    detection_method: DetectionMethodEnum
    evidence: str | None = None
    evidence_urls: list[str] = Field(default_factory=list)


class CategoryResult(BaseModel):
    """Single category classification result."""
    name: str
    content_percentage: float | None = None
    confidence: float


class ClassificationResult(BaseModel):
    """Full LLM classification output."""
    is_financial_creator: bool = True
    relevance_score: float | None = None
    primary_category: str | None = None
    categories: list[CategoryResult] = Field(default_factory=list)
    primary_language: str | None = None
    language_confidence: float | None = None
    creator_type: str | None = None
    creator_type_confidence: float | None = None
    broker: BrokerInfo | None = None
    reasoning: str | None = None
    evidence: list[str] = Field(default_factory=list)


class EngagementData(BaseModel):
    """Computed engagement metrics."""
    avg_views: float = 0.0
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    engagement_rate: float = 0.0
    upload_frequency_per_month: float = 0.0
    last_upload_at: datetime | None = None
    shorts_ratio: float = 0.0


class ScoreBreakdown(BaseModel):
    """Detailed scoring breakdown."""
    total_score: float = 0.0
    followers: float = 0.0
    avg_views: float = 0.0
    engagement_rate: float = 0.0
    posting_frequency: float = 0.0
    broker_association: float = 0.0
    contact_availability: float = 0.0
    verified: float = 0.0
    recency: float = 0.0
    content_relevance: float = 0.0


class EnrichedProfile(BaseModel):
    """Fully enriched profile ready for database insertion."""
    raw_profile: RawProfile
    contacts: ContactInfo
    brokers: list[BrokerInfo] = Field(default_factory=list)
    classification: ClassificationResult | None = None
    engagement: EngagementData | None = None
    score: ScoreBreakdown | None = None
    audience_bucket: int | None = None
    status: CreatorStatusEnum = CreatorStatusEnum.ACTIVE
    needs_review: bool = False
    review_reason: str | None = None
    discovered_channels: list[str] = Field(default_factory=list)


class VideoData(BaseModel):
    """Video data from YouTube API."""
    video_id: str
    title: str | None = None
    description: str | None = None
    views: int | None = None
    likes: int | None = None
    comments_count: int | None = None
    duration: str | None = None
    is_short: bool = False
    published_at: datetime | None = None
    thumbnail_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PostData(BaseModel):
    """Post data from Instagram."""
    post_id: str
    caption: str | None = None
    likes: int | None = None
    comments_count: int | None = None
    post_type: str | None = None
    published_at: datetime | None = None
    url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class SocialLinkResponse(BaseModel):
    platform: str
    url: str | None = None
    value: str | None = None


class BrokerAssociationResponse(BaseModel):
    broker_name: str
    relationship_type: str | None = None
    confidence: float
    detection_method: str | None = None
    evidence: str | None = None


class CategoryResponse(BaseModel):
    name: str
    is_primary: bool
    content_percentage: float | None = None
    confidence: float | None = None


class EngagementResponse(BaseModel):
    avg_views: float | None = None
    avg_likes: float | None = None
    avg_comments: float | None = None
    engagement_rate: float | None = None
    upload_frequency_per_month: float | None = None
    last_upload_at: datetime | None = None
    shorts_ratio: float | None = None


class PlatformProfileResponse(BaseModel):
    id: int
    platform: str
    platform_user_id: str
    username: str | None = None
    display_name: str | None = None
    bio: str | None = None
    followers: int | None = None
    following: int | None = None
    video_count: int | None = None
    verified: bool = False
    profile_url: str | None = None
    country: str | None = None
    last_active_at: datetime | None = None
    engagement: EngagementResponse | None = None


class CreatorSummaryResponse(BaseModel):
    """Compact creator view for list endpoints."""
    id: int
    name: str
    email: str | None = None
    status: str
    audience_bucket: int | None = None
    creator_type: str | None = None
    primary_language: str | None = None
    primary_category: str | None = None
    influencer_score: float | None = None
    needs_review: bool = False
    platforms: list[str] = Field(default_factory=list)
    followers: int | None = None  # Max across platforms
    created_at: datetime | None = None


class CreatorDetailResponse(BaseModel):
    """Full creator view for detail endpoints."""
    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    status: str
    audience_bucket: int | None = None
    creator_type: str | None = None
    creator_type_confidence: float | None = None
    primary_language: str | None = None
    language_confidence: float | None = None
    primary_category: str | None = None
    influencer_score: float | None = None
    score_breakdown: dict[str, Any] | None = None
    needs_review: bool = False
    review_reason: str | None = None
    last_enriched_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    platform_profiles: list[PlatformProfileResponse] = Field(default_factory=list)
    social_links: list[SocialLinkResponse] = Field(default_factory=list)
    broker_associations: list[BrokerAssociationResponse] = Field(default_factory=list)
    categories: list[CategoryResponse] = Field(default_factory=list)


class CreatorUpdateRequest(BaseModel):
    """Request body for updating a creator."""
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    status: CreatorStatusEnum | None = None
    creator_type: str | None = None
    primary_language: str | None = None
    primary_category: str | None = None
    needs_review: bool | None = None
    review_reason: str | None = None


class RelationshipResponse(BaseModel):
    """Creator relationship (graph edge)."""
    related_creator_id: int | None = None
    related_creator_name: str | None = None
    relationship_type: str
    evidence_url: str | None = None
    discovered_at: datetime | None = None
