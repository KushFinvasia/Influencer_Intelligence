"""Pydantic schemas for search and filtering."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """All supported search/filter parameters."""
    q: str | None = None  # Free text search (name, bio)
    category: str | None = None
    language: str | None = None
    creator_type: str | None = None
    broker: str | None = None
    audience_bucket: int | None = None
    platform: str | None = None  # youtube, instagram
    has_email: bool | None = None
    has_phone: bool | None = None
    verified: bool | None = None
    min_followers: int | None = None
    max_followers: int | None = None
    min_engagement: float | None = None
    min_score: float | None = None
    status: str | None = None
    region: str | None = None
    needs_review: bool | None = None
    recent_upload_days: int | None = None  # Uploaded within N days
    sort_by: str = Field(default="influencer_score")
    sort_order: str = Field(default="desc")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=5000)


class SearchResponse(BaseModel):
    """Paginated search response."""
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list = Field(default_factory=list)
