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


@pytest.mark.asyncio
async def test_similar_creators_not_found(client):
    response = await client.get("/api/creators/424242/similar")
    assert response.status_code == 404
    assert response.json()["detail"] == "Creator not found"


@pytest.mark.asyncio
async def test_similar_creators_invalid_limit(client):
    assert (await client.get("/api/creators/1/similar?limit=0")).status_code == 422
    assert (await client.get("/api/creators/1/similar?limit=500")).status_code == 422
    assert (await client.get("/api/creators/1/similar?limit=abc")).status_code == 422


@pytest.mark.asyncio
async def test_similar_creators_returns_ranked_results(client):
    from app.models.database import Creator, PlatformProfile

    async def seed(session):
        creators = [
            Creator(
                name="Source Creator",
                primary_category="Technical Analysis",
                creator_type="Trader",
                primary_language="Hindi",
                influencer_score=80.0,
                audience_bucket=2,
            ),
            Creator(
                name="Close Peer",
                primary_category="Technical Analysis",
                creator_type="Trader",
                primary_language="Hindi",
                influencer_score=70.0,
                audience_bucket=2,
            ),
            Creator(
                name="Loose Peer",
                primary_category="Intraday",
                creator_type="Educator",
                primary_language="Tamil",
                influencer_score=60.0,
                audience_bucket=2,
            ),
        ]
        session.add_all(creators)
        await session.flush()
        for creator in creators:
            session.add(
                PlatformProfile(
                    creator_id=creator.id,
                    platform="youtube",
                    platform_user_id=f"UC_{creator.id}",
                    followers=200_000,
                )
            )
        await session.commit()
        return creators[0].id

    # Reuse the same overridden session factory the client fixture installs.
    from app.database.session import get_db

    async for session in app.dependency_overrides[get_db]():
        source_id = await seed(session)
        break

    response = await client.get(f"/api/creators/{source_id}/similar?limit=5")
    assert response.status_code == 200

    data = response.json()
    assert data["creator_id"] == source_id
    assert data["count"] == len(data["results"])
    assert [r["name"] for r in data["results"]] == ["Close Peer", "Loose Peer"]
    assert all(r["id"] != source_id for r in data["results"])

    scores = [r["similarity_score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True)
    assert "Same category" in data["results"][0]["match_reasons"]
