"""Integration tests for CreatorService and database operations."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.database import Base
from app.services.creator_service import CreatorService
from app.schemas.creator import (
    EnrichedProfile,
    RawProfile,
    ContactInfo,
    BrokerInfo,
    BrokerRelationshipEnum,
    DetectionMethodEnum,
    ClassificationResult,
    CategoryResult,
    ScoreBreakdown,
    CreatorStatusEnum,
)
from app.schemas.search import SearchFilters


@pytest_asyncio.fixture
async def test_db():
    """Create in-memory SQLite database session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_and_get_creator(test_db):
    service = CreatorService(test_db)

    raw = RawProfile(
        platform="youtube",
        platform_user_id="UC_test_123",
        username="StockTraderIndia",
        display_name="Stock Trader India",
        bio="Options trader and educator",
        followers=250000,
        links=["https://zerodha.com/ref123"],
    )
    contacts = ContactInfo(
        emails=["trader@stockindia.com"],
        phones=["+919876543210"],
        website=["https://stockindia.com"],
    )
    brokers = [
        BrokerInfo(
            broker_name="Zerodha",
            relationship_type=BrokerRelationshipEnum.AFFILIATE,
            confidence=0.95,
            detection_method=DetectionMethodEnum.RULE,
            evidence="Referral link found",
        )
    ]
    classification = ClassificationResult(
        primary_category="F&O",
        categories=[CategoryResult(name="F&O", content_percentage=80.0, confidence=0.92)],
        primary_language="Hindi",
        language_confidence=0.95,
        creator_type="Trader",
        creator_type_confidence=0.88,
    )
    score = ScoreBreakdown(
        total_score=82.5,
        followers=0.75,
        avg_views=0.6,
        engagement_rate=0.8,
        posting_frequency=0.7,
        broker_association=0.5,
        contact_availability=0.85,
        verified=0.0,
        recency=0.9,
        content_relevance=0.9,
    )

    enriched = EnrichedProfile(
        raw_profile=raw,
        contacts=contacts,
        brokers=brokers,
        classification=classification,
        score=score,
        audience_bucket=2,
        status=CreatorStatusEnum.ACTIVE,
    )

    creator_id = await service.upsert_creator(enriched)
    await test_db.commit()

    assert creator_id is not None
    assert creator_id > 0

    # Retrieve and verify
    creator = await service.get_creator(creator_id)
    assert creator is not None
    assert creator.name == "Stock Trader India"
    assert creator.email == "trader@stockindia.com"
    assert creator.phone == "+919876543210"
    assert creator.primary_category == "F&O"
    assert creator.primary_language == "Hindi"
    assert creator.creator_type == "Trader"
    assert creator.influencer_score == 82.5
    assert len(creator.platform_profiles) == 1
    assert creator.platform_profiles[0].platform == "youtube"
    assert len(creator.broker_associations) == 1
    assert creator.broker_associations[0].broker_name == "Zerodha"
    assert len(creator.categories) == 1
    assert creator.categories[0].name == "F&O"


@pytest.mark.asyncio
async def test_search_creators(test_db):
    service = CreatorService(test_db)

    # Insert two creators
    for i, name in enumerate(["Alpha Trader", "Beta Investor"]):
        raw = RawProfile(
            platform="youtube",
            platform_user_id=f"UC_user_{i}",
            display_name=name,
            followers=(i + 1) * 100000,
        )
        enriched = EnrichedProfile(
            raw_profile=raw,
            contacts=ContactInfo(),
            score=ScoreBreakdown(total_score=50.0 + i * 20),
            audience_bucket=2,
            status=CreatorStatusEnum.ACTIVE,
        )
        await service.upsert_creator(enriched)
    await test_db.commit()

    # Search with keyword filter
    res = await service.search_creators(SearchFilters(q="Alpha"))
    assert res.total == 1
    assert res.results[0].name == "Alpha Trader"

    # Search with min_score filter
    res_score = await service.search_creators(SearchFilters(min_score=60.0))
    assert res_score.total == 1
    assert res_score.results[0].name == "Beta Investor"
