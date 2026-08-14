"""Search and filter endpoints with 15+ filter dimensions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.search import SearchFilters, SearchResponse
from app.services.creator_service import CreatorService

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("", response_model=SearchResponse)
async def search_creators(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    creator_type: str | None = None,
    broker: str | None = None,
    audience_bucket: int | None = None,
    platform: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    verified: bool | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    min_engagement: float | None = None,
    min_score: float | None = None,
    status: str | None = None,
    region: str | None = None,
    needs_review: bool | None = None,
    recent_upload_days: int | None = None,
    sort_by: str = Query(default="influencer_score"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search creators with comprehensive filters.

    Supports 15+ filter dimensions including category, language,
    broker, engagement, score, platform, contact availability, etc.
    """
    filters = SearchFilters(
        q=q,
        category=category,
        language=language,
        creator_type=creator_type,
        broker=broker,
        audience_bucket=audience_bucket,
        platform=platform,
        has_email=has_email,
        has_phone=has_phone,
        verified=verified,
        min_followers=min_followers,
        max_followers=max_followers,
        min_engagement=min_engagement,
        min_score=min_score,
        status=status,
        region=region,
        needs_review=needs_review,
        recent_upload_days=recent_upload_days,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    service = CreatorService(db)
    return await service.search_creators(filters)
