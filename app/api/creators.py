"""Creator CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.creator import (
    CreatorDetailResponse,
    CreatorSummaryResponse,
    CreatorUpdateRequest,
    SimilarCreatorsResponse,
)
from app.schemas.search import SearchResponse
from app.services.creator_service import CreatorService
from app.services.similarity import SimilarityService

router = APIRouter(prefix="/api/creators", tags=["Creators"])


@router.get("", response_model=SearchResponse)
async def list_creators(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all creators, paginated and sorted by score."""
    service = CreatorService(db)
    return await service.list_creators(page, page_size)


@router.get("/{creator_id}", response_model=CreatorDetailResponse)
async def get_creator(
    creator_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full creator detail with profiles, links, brokers, categories."""
    service = CreatorService(db)
    creator = await service.get_creator(creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return creator


@router.get("/{creator_id}/similar", response_model=SimilarCreatorsResponse)
async def get_similar_creators(
    creator_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Find creators comparable to this one, ranked by similarity score."""
    service = SimilarityService(db)
    similar = await service.find_similar(creator_id, limit)
    if similar is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return similar


@router.put("/{creator_id}")
async def update_creator(
    creator_id: int,
    request: CreatorUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a creator's information."""
    service = CreatorService(db)
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = await service.update_creator(creator_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Creator not found")

    return {"status": "updated", "creator_id": creator_id}


@router.delete("/{creator_id}")
async def delete_creator(
    creator_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a creator (sets status to INACTIVE)."""
    service = CreatorService(db)
    success = await service.delete_creator(creator_id)
    if not success:
        raise HTTPException(status_code=404, detail="Creator not found")

    return {"status": "deleted", "creator_id": creator_id}
