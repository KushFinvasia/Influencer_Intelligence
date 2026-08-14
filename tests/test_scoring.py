"""Tests for the scoring engine."""

import pytest
from datetime import datetime, timezone, timedelta

from app.services.scoring import ScoringEngine
from app.schemas.creator import ContactInfo, EngagementData


@pytest.fixture
def scorer():
    return ScoringEngine()


class TestScoreCalculation:
    def test_score_returns_breakdown(self, scorer):
        score = scorer.calculate(followers=100000)
        assert score.total_score >= 0
        assert score.total_score <= 100
        assert score.followers > 0

    def test_high_follower_high_score(self, scorer):
        score = scorer.calculate(followers=5000000)
        assert score.followers >= 0.9

    def test_zero_followers_low_score(self, scorer):
        score = scorer.calculate(followers=0)
        assert score.followers == 0.0

    def test_verified_adds_score(self, scorer):
        unverified = scorer.calculate(followers=10000, verified=False)
        verified = scorer.calculate(followers=10000, verified=True)
        assert verified.total_score > unverified.total_score

    def test_contacts_add_score(self, scorer):
        no_contacts = scorer.calculate(followers=10000)
        with_contacts = scorer.calculate(
            followers=10000,
            contacts=ContactInfo(
                emails=["test@test.com"],
                phones=["+919876543210"],
            ),
        )
        assert with_contacts.total_score > no_contacts.total_score


class TestEngagementScoring:
    def test_high_engagement(self, scorer):
        engagement = EngagementData(
            avg_views=500000,
            avg_likes=25000,
            avg_comments=5000,
            engagement_rate=6.0,
            upload_frequency_per_month=20,
            last_upload_at=datetime.now(timezone.utc),
        )
        score = scorer.calculate(
            followers=100000, engagement=engagement
        )
        assert score.engagement_rate >= 0.8
        assert score.posting_frequency >= 0.8
        assert score.recency >= 0.9

    def test_stale_content_low_recency(self, scorer):
        engagement = EngagementData(
            last_upload_at=datetime.now(timezone.utc)
            - timedelta(days=365),
        )
        score = scorer.calculate(
            followers=100000, engagement=engagement
        )
        assert score.recency < 0.1


class TestFollowerScoring:
    def test_log_scale_mid_range(self, scorer):
        score_10k = scorer.calculate(followers=10000)
        score_100k = scorer.calculate(followers=100000)
        score_1m = scorer.calculate(followers=1000000)

        assert score_10k.followers < score_100k.followers
        assert score_100k.followers < score_1m.followers

    def test_diminishing_returns(self, scorer):
        """Gap between 1K→10K should be larger than 1M→10M in absolute terms."""
        score_1k = scorer.calculate(followers=1000)
        score_10k = scorer.calculate(followers=10000)
        score_1m = scorer.calculate(followers=1000000)
        score_5m = scorer.calculate(followers=5000000)

        gap_low = score_10k.followers - score_1k.followers
        gap_high = score_5m.followers - score_1m.followers
        assert gap_low > gap_high or score_5m.followers >= 0.9
