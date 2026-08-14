"""CSV and Excel export endpoints."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.search import SearchFilters
from app.services.creator_service import CreatorService
from app.utils.helpers import creators_to_csv

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/csv")
async def export_csv(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    creator_type: str | None = None,
    broker: str | None = None,
    audience_bucket: int | None = None,
    platform: str | None = None,
    has_email: bool | None = None,
    status: str | None = None,
    min_score: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Export filtered creators as a CSV file."""
    filters = SearchFilters(
        q=q,
        category=category,
        language=language,
        creator_type=creator_type,
        broker=broker,
        audience_bucket=audience_bucket,
        platform=platform,
        has_email=has_email,
        status=status,
        min_score=min_score,
        page=1,
        page_size=5000,  # Export up to 5000 rows
    )

    service = CreatorService(db)
    result = await service.search_creators(filters)

    # Convert to dicts for CSV
    rows = [r.model_dump() if hasattr(r, "model_dump") else r for r in result.results]
    csv_data = creators_to_csv(rows)

    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=creators_export.csv"
        },
    )


@router.get("/excel")
async def export_excel(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    creator_type: str | None = None,
    broker: str | None = None,
    audience_bucket: int | None = None,
    platform: str | None = None,
    has_email: bool | None = None,
    status: str | None = None,
    min_score: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Export filtered creators as an Excel file."""
    from openpyxl import Workbook

    filters = SearchFilters(
        q=q,
        category=category,
        language=language,
        creator_type=creator_type,
        broker=broker,
        audience_bucket=audience_bucket,
        platform=platform,
        has_email=has_email,
        status=status,
        min_score=min_score,
        page=1,
        page_size=5000,
    )

    service = CreatorService(db)
    result = await service.search_creators(filters)

    # Build Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Creators"

    headers = [
        "ID", "Name", "Email", "Phone", "Status",
        "Audience Bucket", "Creator Type", "Language",
        "Category", "Score", "Platforms", "Followers",
    ]
    ws.append(headers)

    for creator in result.results:
        data = creator.model_dump() if hasattr(creator, "model_dump") else creator
        platforms = ", ".join(data.get("platforms", []))
        ws.append([
            data.get("id", ""),
            data.get("name", ""),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("status", ""),
            data.get("audience_bucket", ""),
            data.get("creator_type", ""),
            data.get("primary_language", ""),
            data.get("primary_category", ""),
            data.get("influencer_score", ""),
            platforms,
            data.get("followers", ""),
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=creators_export.xlsx"
        },
    )
