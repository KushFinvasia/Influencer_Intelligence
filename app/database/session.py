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
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

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

    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
        
        # Idempotent migration for new columns
        if is_sqlite:
            import logging
            logger = logging.getLogger(__name__)
            try:
                # Check if discovered_via exists in platform_profiles
                res = await conn.exec_driver_sql("PRAGMA table_info(platform_profiles)")
                columns = [row[1] for row in res.fetchall()]
                if "discovered_via" not in columns:
                    logger.info("Adding discovered_via column to platform_profiles")
                    await conn.exec_driver_sql("ALTER TABLE platform_profiles ADD COLUMN discovered_via JSON")
                    await conn.commit()
                    
                # Check if keyword_metrics exists in scrape_jobs
                res = await conn.exec_driver_sql("PRAGMA table_info(scrape_jobs)")
                columns = [row[1] for row in res.fetchall()]
                if "keyword_metrics" not in columns:
                    logger.info("Adding keyword_metrics column to scrape_jobs")
                    await conn.exec_driver_sql("ALTER TABLE scrape_jobs ADD COLUMN keyword_metrics JSON")
                    await conn.commit()
            except Exception as e:
                logger.error(f"Error during schema migration: {e}")


async def close_db() -> None:
    """Dispose of the engine on shutdown."""
    await engine.dispose()
