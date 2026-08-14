"""Integration tests for FastAPI endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.session import get_db
from app.main import app
from app.models.database import Base


@pytest_asyncio.fixture
async def client():
    """Create test client with in-memory database override."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with test_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_list_creators_empty(client):
    response = await client.get("/api/creators")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_search_creators_endpoint(client):
    response = await client.get("/api/search?q=trading&page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_review_endpoints(client):
    response = await client.get("/api/review")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0

    stats_res = await client.get("/api/review/stats")
    assert stats_res.status_code == 200
    assert "pending_reviews" in stats_res.json()


@pytest.mark.asyncio
async def test_export_csv(client):
    response = await client.get("/api/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
async def test_export_excel(client):
    response = await client.get("/api/export/excel")
    assert response.status_code == 200
    assert "openxmlformats" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_scrape_jobs_list(client):
    response = await client.get("/api/scrape/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
