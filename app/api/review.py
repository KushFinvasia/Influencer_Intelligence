"""Manual review endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.creator import CreatorUpdateRequest
from app.schemas.search import SearchResponse
from app.services.creator_service import CreatorService

router = APIRouter(prefix="/api/review", tags=["Review"])


@router.get("", response_model=SearchResponse)
async def get_review_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get creators that need manual review.

    Returns creators where needs_review is True,
    typically due to low confidence classifications.
    """
    service = CreatorService(db)
    return await service.get_review_queue(page, page_size)


@router.put("/{creator_id}")
async def approve_review(
    creator_id: int,
    request: CreatorUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve a reviewed creator with optional corrections.

    Clears the needs_review flag and sets detection_method to 'manual'
    for any updated classification fields.
    """
    service = CreatorService(db)
    updates = request.model_dump(exclude_none=True)
    success = await service.approve_review(creator_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Creator not found")
    return {"status": "approved", "creator_id": creator_id}


@router.get("/stats")
async def review_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get review queue statistics."""
    from sqlalchemy import select, func
    from app.models.database import Creator

    total = await db.execute(
        select(func.count(Creator.id)).where(
            Creator.needs_review == True  # noqa: E712
        )
    )
    pending = total.scalar() or 0

    return {
        "pending_reviews": pending,
    }
