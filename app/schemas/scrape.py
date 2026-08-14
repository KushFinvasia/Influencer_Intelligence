"""Pydantic schemas for scrape job management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    """Request body for triggering a scrape."""
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    usernames: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=3, ge=1, le=5)
    use_defaults: bool = Field(
        default=True,
        description="If true, also include keywords/hashtags from keywords.json",
    )


class ScrapeJobResponse(BaseModel):
    """Response for a scrape job."""
    id: int
    job_type: str
    status: str
    keywords: list | None = None
    total_discovered: int = 0
    total_processed: int = 0
    total_new: int = 0
    total_updated: int = 0
    discovery_depth: int = 1
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class ScrapeLogResponse(BaseModel):
    """Individual log entry within a scrape job."""
    id: int
    platform: str
    keyword: str | None = None
    action: str
    status: str
    api_units_used: int = 0
    items_found: int = 0
    error_message: str | None = None
    timestamp: datetime | None = None
