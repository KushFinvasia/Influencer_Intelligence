"""Scrape trigger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_keywords_config
from app.database.session import get_db
from app.pipelines.discovery import DiscoveryPipeline
from app.schemas.scrape import ScrapeRequest, ScrapeJobResponse
from app.services.creator_service import CreatorService

router = APIRouter(prefix="/api/scrape", tags=["Scrape"])


async def _run_youtube_pipeline(
    keywords: list[dict[str, str]], max_depth: int, job_id: int
) -> None:
    """Background task for YouTube scrape."""
    from app.database.session import async_session_factory

    pipeline = DiscoveryPipeline()
    async with async_session_factory() as db:
        try:
            await pipeline.run_youtube(db, keywords, max_depth, job_id)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _run_instagram_pipeline(
    hashtags: list[str],
    usernames: list[str],
    max_depth: int,
    job_id: int,
) -> None:
    """Background task for Instagram scrape."""
    from app.database.session import async_session_factory

    pipeline = DiscoveryPipeline()
    async with async_session_factory() as db:
        try:
            await pipeline.run_instagram(
                db, hashtags, usernames, max_depth, job_id
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _run_full_pipeline(
    youtube_keywords: list[str],
    instagram_hashtags: list[str],
    instagram_usernames: list[str],
    max_depth: int,
    job_id: int,
) -> None:
    """Background task for full pipeline."""
    from app.database.session import async_session_factory

    pipeline = DiscoveryPipeline()
    async with async_session_factory() as db:
        try:
            await pipeline.run_full(
                db,
                youtube_keywords,
                instagram_hashtags,
                instagram_usernames,
                max_depth,
                job_id,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


@router.post("/youtube", response_model=ScrapeJobResponse)
async def scrape_youtube(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a YouTube recursive discovery scrape."""
    service = CreatorService(db)

    # Build keyword list
    normalized_terms = []
    
    if request.use_defaults:
        from app.utils.keyword_parser import parse_keywords
        config = get_keywords_config()
        # Parse youtube configuration dynamically
        normalized_terms = parse_keywords(config.get("youtube", {}))
        
    # Append any custom keywords manually provided (if any)
    for kw in request.keywords:
        normalized_terms.append({"term": kw, "category": "manual"})

    # Create scrape job (store raw terms in keywords column for legacy support)
    raw_keywords = [t["term"] for t in normalized_terms]
    job_id = await service.create_scrape_job(
        job_type="youtube",
        keywords=raw_keywords,
        depth=request.max_depth,
    )
    await db.commit()

    # Run in background
    background_tasks.add_task(
        _run_youtube_pipeline, normalized_terms, request.max_depth, job_id
    )

    return ScrapeJobResponse(
        id=job_id,
        job_type="youtube",
        status="queued",
        keywords=raw_keywords,
        discovery_depth=request.max_depth,
    )


@router.post("/instagram", response_model=ScrapeJobResponse)
async def scrape_instagram(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an Instagram discovery scrape."""
    service = CreatorService(db)

    # Build hashtag/username lists
    normalized_hashtags = []
    usernames = list(request.usernames)
    
    if request.use_defaults:
        from app.utils.keyword_parser import parse_keywords
        config = get_keywords_config()
        ig_config = config.get("instagram", {})
        normalized_hashtags = parse_keywords(ig_config)
        default_usernames = ig_config.get("seed_usernames", [])
        usernames.extend(default_usernames)

    for h in request.hashtags:
        normalized_hashtags.append({"term": h, "category": "manual"})

    usernames = list(set(usernames))
    raw_keywords = [t["term"] for t in normalized_hashtags] + usernames

    job_id = await service.create_scrape_job(
        job_type="instagram",
        keywords=raw_keywords,
        depth=request.max_depth,
    )
    await db.commit()

    background_tasks.add_task(
        _run_instagram_pipeline,
        normalized_hashtags,
        usernames,
        request.max_depth,
        job_id,
    )

    return ScrapeJobResponse(
        id=job_id,
        job_type="instagram",
        status="queued",
        keywords=raw_keywords,
        discovery_depth=request.max_depth,
    )


@router.post("/full", response_model=ScrapeJobResponse)
async def scrape_full(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full pipeline (YouTube + Instagram)."""
    service = CreatorService(db)

    # Build all keyword lists
    normalized_yt_terms = []
    normalized_ig_terms = []
    usernames = list(request.usernames)

    if request.use_defaults:
        from app.utils.keyword_parser import parse_keywords
        config = get_keywords_config()
        normalized_yt_terms = parse_keywords(config.get("youtube", {}))
        ig_config = config.get("instagram", {})
        normalized_ig_terms = parse_keywords(ig_config)
        default_usernames = ig_config.get("seed_usernames", [])
        usernames.extend(default_usernames)
        
    for kw in request.keywords:
        normalized_yt_terms.append({"term": kw, "category": "manual"})
    for h in request.hashtags:
        normalized_ig_terms.append({"term": h, "category": "manual"})

    usernames = list(set(usernames))
    
    raw_keywords = [t["term"] for t in normalized_yt_terms] + [t["term"] for t in normalized_ig_terms] + usernames

    job_id = await service.create_scrape_job(
        job_type="full",
        keywords=raw_keywords,
        depth=request.max_depth,
    )
    await db.commit()

    async def run_full_pipeline():
        await _run_youtube_pipeline(normalized_yt_terms, request.max_depth, job_id)
        await _run_instagram_pipeline(
            normalized_ig_terms, usernames, request.max_depth, job_id
        )

    background_tasks.add_task(run_full_pipeline)

    return ScrapeJobResponse(
        id=job_id,
        job_type="full",
        status="queued",
        keywords=raw_keywords,
        discovery_depth=request.max_depth,
    )


@router.get("/jobs", response_model=list[ScrapeJobResponse])
async def list_scrape_jobs(
    db: AsyncSession = Depends(get_db),
):
    """List all scrape jobs."""
    from sqlalchemy import select
    from app.models.database import ScrapeJob

    result = await db.execute(
        select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(50)
    )
    jobs = result.scalars().all()

    return [
        ScrapeJobResponse(
            id=j.id,
            job_type=j.job_type.value if j.job_type else "",
            status=j.status.value if j.status else "",
            keywords=j.keywords,
            total_discovered=j.total_discovered,
            total_processed=j.total_processed,
            total_new=j.total_new,
            total_updated=j.total_updated,
            discovery_depth=j.discovery_depth,
            error_message=j.error_message,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
        )
        for j in jobs
    ]
