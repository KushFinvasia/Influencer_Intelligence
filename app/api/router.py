"""Main API router — includes all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.scrape import router as scrape_router
from app.api.creators import router as creators_router
from app.api.search import router as search_router
from app.api.review import router as review_router
from app.api.export import router as export_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(scrape_router)
api_router.include_router(creators_router)
api_router.include_router(search_router)
api_router.include_router(review_router)
api_router.include_router(export_router)
