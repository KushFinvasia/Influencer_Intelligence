"""Influencer scoring engine.

Computes a 0-100 score from weighted factors loaded from scoring_weights.json.
Uses logarithmic/sigmoid curves for non-linear scaling.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.config.settings import get_scoring_weights_config
from app.schemas.creator import (
    ContactInfo,
    EngagementData,
    ScoreBreakdown,
)

_config = None


def _get_config() -> dict:
    global _config
    if _config is None:
        _config = get_scoring_weights_config()
    return _config


class ScoringEngine:
    """Compute influencer_score (0-100) from weighted factors."""

    def __init__(self) -> None:
        config = _get_config()
        self.weights = config.get("weights", {})
        self.follower_thresholds = config.get("follower_thresholds", {})
        self.engagement_benchmarks = config.get("engagement_benchmarks", {})
        self.recency_decay_days = config.get("recency_decay_days", 90)
        self.contact_scores = config.get("contact_scores", {})

    def calculate(
        self,
        followers: int = 0,
        engagement: EngagementData | None = None,
        contacts: ContactInfo | None = None,
        broker_count: int = 0,
        verified: bool = False,
        primary_category_confidence: float = 0.0,
        platform: str = "youtube",
    ) -> ScoreBreakdown:
        """Calculate the influencer score with full breakdown.

        Returns:
            ScoreBreakdown with total_score (0-100) and per-component scores.
        """
        engagement = engagement or EngagementData()
        contacts = contacts or ContactInfo()

        components = {
            "followers": self._score_followers(followers),
            "avg_views": self._score_views(engagement.avg_views),
            "engagement_rate": self._score_engagement(
                engagement.engagement_rate, platform
            ),
            "posting_frequency": self._score_frequency(
                engagement.upload_frequency_per_month
            ),
            "broker_association": min(broker_count * 0.5, 1.0),
            "contact_availability": self._score_contacts(contacts),
            "verified": 1.0 if verified else 0.0,
            "recency": self._score_recency(engagement.last_upload_at),
            "content_relevance": min(primary_category_confidence, 1.0),
        }

        # Weighted sum → scale to 0-100
        total = sum(
            components.get(k, 0.0) * self.weights.get(k, 0.0)
            for k in self.weights
        )
        total_score = round(total * 100, 2)

        return ScoreBreakdown(
            total_score=min(total_score, 100.0),
            **components,
        )

    def _score_followers(self, followers: int) -> float:
        """Logarithmic scoring for follower count."""
        if followers <= 0:
            return 0.0
        min_at = self.follower_thresholds.get("min_score_at", 1000)
        max_at = self.follower_thresholds.get("max_score_at", 5000000)
        if followers >= max_at:
            return 1.0
        if followers <= min_at:
            return 0.1
        # Log scale between min and max
        log_min = math.log10(min_at)
        log_max = math.log10(max_at)
        log_val = math.log10(followers)
        return min(max((log_val - log_min) / (log_max - log_min), 0.1), 1.0)

    def _score_views(self, avg_views: float) -> float:
        """Logarithmic scoring for average views."""
        if avg_views <= 0:
            return 0.0
        # Similar log scale: 100 views = 0.1, 1M views = 1.0
        if avg_views >= 1_000_000:
            return 1.0
        if avg_views <= 100:
            return 0.1
        return min(max(math.log10(avg_views) / 6, 0.1), 1.0)

    def _score_engagement(
        self, rate: float, platform: str = "youtube"
    ) -> float:
        """Score engagement rate against platform benchmarks."""
        if rate <= 0:
            return 0.0
        benchmarks = self.engagement_benchmarks.get(platform, {})
        excellent = benchmarks.get("excellent", 5.0)
        good = benchmarks.get("good", 3.0)
        average = benchmarks.get("average", 1.5)

        if rate >= excellent:
            return 1.0
        elif rate >= good:
            return 0.8
        elif rate >= average:
            return 0.6
        else:
            return max(rate / average * 0.6, 0.1)

    @staticmethod
    def _score_frequency(uploads_per_month: float) -> float:
        """Score posting frequency. Sweet spot: 8-20 uploads/month."""
        if uploads_per_month <= 0:
            return 0.0
        if uploads_per_month >= 20:
            return 1.0
        if uploads_per_month >= 8:
            return 0.8
        if uploads_per_month >= 4:
            return 0.6
        if uploads_per_month >= 1:
            return 0.3
        return 0.1

    def _score_contacts(self, contacts: ContactInfo) -> float:
        """Score based on available contact methods."""
        score = 0.0
        if contacts.emails:
            score += self.contact_scores.get("email", 0.35)
        if contacts.phones:
            score += self.contact_scores.get("phone", 0.25)
        if contacts.website:
            score += self.contact_scores.get("website", 0.15)
        if contacts.telegram:
            score += self.contact_scores.get("telegram", 0.10)
        if contacts.linkedin:
            score += self.contact_scores.get("linkedin", 0.10)
        if contacts.whatsapp:
            score += self.contact_scores.get("whatsapp", 0.05)
        return min(score, 1.0)

    def _score_recency(self, last_upload: datetime | None) -> float:
        """Exponential decay based on days since last upload."""
        if not last_upload:
            return 0.0
        now = datetime.now(timezone.utc)
        if last_upload.tzinfo is None:
            last_upload = last_upload.replace(tzinfo=timezone.utc)
        days = (now - last_upload).days
        if days <= 0:
            return 1.0
        decay = self.recency_decay_days
        return max(math.exp(-days / decay), 0.0)
