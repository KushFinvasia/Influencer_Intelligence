"""Tests for the enrichment engine."""

import pytest
from datetime import datetime, timezone, timedelta

from app.services.enrichment import EnrichmentEngine
from app.schemas.creator import ContactInfo, RawProfile, CreatorStatusEnum


@pytest.fixture
def engine():
    return EnrichmentEngine()


class TestBrokerDetection:
    def test_referral_link_detection(self, engine):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test",
            links=["https://zerodha.com/open-account?ref=abc123"],
        )
        contacts = ContactInfo()
        brokers = engine.detect_brokers(profile, contacts)
        assert len(brokers) >= 1
        zerodha = next(
            (b for b in brokers if b.broker_name == "Zerodha"), None
        )
        assert zerodha is not None
        assert zerodha.confidence >= 0.90

    def test_domain_match_detection(self, engine):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test",
            links=["https://groww.in/stocks"],
        )
        contacts = ContactInfo(website=["https://groww.in/stocks"])
        brokers = engine.detect_brokers(profile, contacts)
        groww = next(
            (b for b in brokers if b.broker_name == "Groww"), None
        )
        assert groww is not None
        assert groww.confidence >= 0.80

    def test_alias_mention_in_bio(self, engine):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test",
            bio="Open your demat account with Angel One today!",
        )
        contacts = ContactInfo()
        brokers = engine.detect_brokers(profile, contacts)
        angel = next(
            (b for b in brokers if b.broker_name == "Angel One"), None
        )
        assert angel is not None

    def test_no_broker_found(self, engine):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test",
            bio="I love cooking and travel",
        )
        contacts = ContactInfo()
        brokers = engine.detect_brokers(profile, contacts)
        assert len(brokers) == 0


class TestAudienceBucketing:
    def test_bucket_1(self, engine):
        assert engine.calculate_audience_bucket(5000) == 1

    def test_bucket_2(self, engine):
        assert engine.calculate_audience_bucket(50000) == 2

    def test_bucket_3(self, engine):
        assert engine.calculate_audience_bucket(500000) == 3

    def test_bucket_4(self, engine):
        assert engine.calculate_audience_bucket(2000000) == 4

    def test_none_followers(self, engine):
        assert engine.calculate_audience_bucket(None) == 1

    def test_zero_followers(self, engine):
        assert engine.calculate_audience_bucket(0) == 1

    def test_boundary_10k(self, engine):
        assert engine.calculate_audience_bucket(10000) == 2

    def test_boundary_300k(self, engine):
        assert engine.calculate_audience_bucket(300000) == 3

    def test_boundary_1m(self, engine):
        assert engine.calculate_audience_bucket(1000000) == 4


class TestStatusDetection:
    def test_active_creator(self, engine):
        last_upload = datetime.now(timezone.utc) - timedelta(days=5)
        assert engine.detect_status(last_upload) == CreatorStatusEnum.ACTIVE

    def test_dormant_creator(self, engine):
        last_upload = datetime.now(timezone.utc) - timedelta(days=60)
        assert engine.detect_status(last_upload) == CreatorStatusEnum.DORMANT

    def test_inactive_creator(self, engine):
        last_upload = datetime.now(timezone.utc) - timedelta(days=365)
        assert engine.detect_status(last_upload) == CreatorStatusEnum.INACTIVE

    def test_private_account(self, engine):
        assert engine.detect_status(None, is_private=True) == CreatorStatusEnum.PRIVATE

    def test_suspended_account(self, engine):
        assert engine.detect_status(None, is_suspended=True) == CreatorStatusEnum.SUSPENDED

    def test_no_uploads(self, engine):
        assert engine.detect_status(None) == CreatorStatusEnum.INACTIVE


class TestReviewFlagging:
    def test_low_confidence_flagged(self, engine):
        needs_review, reason = engine.check_needs_review(
            category_confidence=0.5
        )
        assert needs_review is True
        assert "category" in reason

    def test_high_confidence_not_flagged(self, engine):
        needs_review, reason = engine.check_needs_review(
            category_confidence=0.9,
            language_confidence=0.85,
            broker_confidence=0.95,
        )
        assert needs_review is False
        assert reason is None

    def test_multiple_low_confidence(self, engine):
        needs_review, reason = engine.check_needs_review(
            category_confidence=0.4,
            language_confidence=0.3,
        )
        assert needs_review is True
        assert "category" in reason
        assert "language" in reason
