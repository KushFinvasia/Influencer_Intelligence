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


@app.get("/api/table-data", tags=["Dashboard"])
async def table_data_json():
    """JSON API for the React dashboard — returns all creator data."""
    from scripts.view_creators import fetch_creators_table_data
    creators = fetch_creators_table_data()
    return {
        "creators": creators,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/table", response_class=HTMLResponse, tags=["Dashboard"])
async def view_table():
    """Interactive Web Table Dashboard for all creators (legacy)."""
    from scripts.view_creators import fetch_creators_table_data, export_html, HTML_FILE
    creators = fetch_creators_table_data()
    export_html(creators)
    if HTML_FILE.exists():
        return HTMLResponse(content=HTML_FILE.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>No creators found</h1>")



