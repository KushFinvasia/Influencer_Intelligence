"""Async database engine and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import os
from pathlib import Path

from app.config.settings import get_settings

settings = get_settings()

db_url = settings.database_url
is_sqlite = "sqlite" in db_url

if is_sqlite and ":///" in db_url and not db_url.startswith("sqlite+aiosqlite:////") and not (len(db_url) > 19 and db_url[18] == ":"):
    # Convert relative sqlite URL to absolute project root
    project_root = Path(__file__).resolve().parent.parent.parent
    rel_path = db_url.split(":///", 1)[1].lstrip("./")
    abs_path = (project_root / rel_path).resolve().as_posix()
    db_url = f"sqlite+aiosqlite:///{abs_path}"

engine_kwargs = {
    "echo": settings.app_env == "development",
}

from sqlalchemy import event
from sqlalchemy.pool import NullPool

if is_sqlite:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
        }
    )

engine = create_async_engine(
    db_url,
    **engine_kwargs,
)

if is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on startup. For production, use Alembic migrations."""
    from app.models.database import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Idempotent migration for new columns
    if is_sqlite:
        import sqlite3
        import logging
        logger = logging.getLogger(__name__)
        
        # We need the absolute path to the database
        db_path_str = db_url.replace("sqlite+aiosqlite:///", "")
        try:
            with sqlite3.connect(db_path_str) as sync_conn:
                cursor = sync_conn.cursor()
                
                # Check if discovered_via exists in platform_profiles
                cursor.execute("PRAGMA table_info(platform_profiles)")
                columns = [col[1] for col in cursor.fetchall()]
                if "discovered_via" not in columns:
                    logger.info("Adding discovered_via column to platform_profiles")
                    cursor.execute("ALTER TABLE platform_profiles ADD COLUMN discovered_via JSON")
                    
                # Check if keyword_metrics exists in scrape_jobs
                cursor.execute("PRAGMA table_info(scrape_jobs)")
                columns = [col[1] for col in cursor.fetchall()]
                if "keyword_metrics" not in columns:
                    logger.info("Adding keyword_metrics column to scrape_jobs")
                    cursor.execute("ALTER TABLE scrape_jobs ADD COLUMN keyword_metrics JSON")
                    
                sync_conn.commit()
        except Exception as e:
            logger.error(f"Error during schema migration: {e}")


async def close_db() -> None:
    """Dispose of the engine on shutdown."""
    await engine.dispose()
