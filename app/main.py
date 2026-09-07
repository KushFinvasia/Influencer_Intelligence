"""FastAPI application entry point.

Creator Intelligence Platform for Indian Stock Market Influencers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.router import api_router
from app.config.settings import get_settings
from app.database.session import close_db, init_db
from app.services.scheduler import DiscoveryScheduler

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = DiscoveryScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting Creator Intelligence Platform...")
    from app.database.session import engine
    logger.info("Using Database URL: %s", engine.url)
    await init_db()
    logger.info("Database tables created/verified")

    # Start scheduler (only in non-dev environments or explicitly)
    if settings.app_env != "development":
        scheduler.start()
        logger.info("Background scheduler started")
    else:
        logger.info("Scheduler skipped in development mode")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.stop()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Creator Intelligence Platform",
    description=(
        "Automatically discover, enrich, classify, and store "
        "Indian stock market creators from YouTube and Instagram."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def view_react_dashboard():
    """Serve the modern React-based creator intelligence dashboard."""
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(content="<h1>Dashboard build not found. Run 'npm run build' inside frontend/</h1>", status_code=404)


from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import engine, get_db

_TABLE_CACHE = None
_CACHE_TIME = 0.0

@app.get("/api/table-data", tags=["Dashboard"])
async def table_data_json():
    """Ultra-fast cached JSON endpoint serving complete pre-formatted table rows for dashboard rendering."""
    global _TABLE_CACHE, _CACHE_TIME
    import time, asyncio
    now = time.time()
    if _TABLE_CACHE is not None and (now - _CACHE_TIME < 60):
        return _TABLE_CACHE

    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT c.id, c.name, c.email, c.phone, c.website,
                   c.primary_category, c.primary_language, c.influencer_score,
                   c.audience_bucket, p.platform, p.followers, p.profile_url,
                   COALESCE(b.brokers, '') AS brokers,
                   COALESCE(sl.socials, '[]'::json) AS socials
            FROM creators c
            LEFT JOIN platform_profiles p ON p.creator_id = c.id
            LEFT JOIN (
                SELECT creator_id, string_agg(DISTINCT broker_name, ', ') AS brokers
                FROM broker_associations
                GROUP BY creator_id
            ) b ON b.creator_id = c.id
            LEFT JOIN (
                SELECT creator_id,
                       json_agg(json_build_object(
                           'platform', platform, 'url', COALESCE(url, value)
                       )) AS socials
                FROM social_links
                GROUP BY creator_id
            ) sl ON sl.creator_id = c.id
            ORDER BY c.influencer_score DESC NULLS LAST,
                     p.followers DESC NULLS LAST, c.id
        """))).mappings().all()

    def format_followers(value):
        value = value or 0
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(value)

    def bucket(value):
        value = value or 0
        if value >= 1_000_000:
            return "1M+"
        if value >= 300_000:
            return "300K–1M"
        if value >= 10_000:
            return "10K–300K"
        return "< 10K"

    creators = []
    for row in rows:
        followers = row["followers"] or 0
        creators.append({
            "id": row["id"],
            "platform": (row["platform"] or "YouTube").capitalize(),
            "name": (row["name"] or "N/A").strip(),
            "followers_raw": followers,
            "followers": format_followers(followers),
            "bucket": bucket(followers),
            "content_format": "-",
            "format_label": "-",
            "format_filter": "",
            "format_breakdown": "",
            "email": row["email"] or "-",
            "phone": row["phone"] or "-",
            "category": row["primary_category"] or "-",
            "language": row["primary_language"] or "-",
            "broker": row["brokers"] or "-",
            "website": row["website"] or "-",
            "social_handles": "",
            "structured_socials": row["socials"],
            "score": f"{row['influencer_score']:.1f}" if row["influencer_score"] is not None else "0.0",
            "profile_url": row["profile_url"] or "",
            "is_relevant": True,
            "targets_india": True,
            "posts_analyzed": 0,
        })
    result = {
        "creators": creators,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _TABLE_CACHE = result
    _CACHE_TIME = now
    return result


@app.get("/table", response_class=HTMLResponse, tags=["Dashboard"])
async def view_table():
    """Interactive Web Table Dashboard for all creators (legacy)."""
    from scripts.view_creators import fetch_creators_table_data, export_html, HTML_FILE
    creators = fetch_creators_table_data()
    export_html(creators)
    if HTML_FILE.exists():
        return HTMLResponse(content=HTML_FILE.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>No creators found</h1>")



