"""Creator similarity service — deterministic, rule-based peer matching.

Scores candidates against a source creator using existing database columns
only. No embeddings, vector search, or LLM calls: the same inputs always
produce the same ranking.

Queries select individual columns rather than whole ORM entities on purpose.
`platform_profiles.raw_data` holds the original API response (~60KB/row), so
loading full entities for a few hundred candidates transfers megabytes of JSON
that this ranking never reads.
"""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    BrokerAssociation,
    Creator,
    CreatorStatus,
    PlatformProfile,
)
from app.schemas.creator import SimilarCreatorResponse, SimilarCreatorsResponse

logger = logging.getLogger(__name__)

# Weights per signal. TOTAL_WEIGHT normalises the raw score to a 0-100 scale.
W_CATEGORY = 30.0
W_CREATOR_TYPE = 20.0
W_LANGUAGE = 15.0
W_AUDIENCE = 15.0
W_PLATFORM = 10.0
W_SCORE_PROXIMITY = 10.0
W_BROKER = 10.0

TOTAL_WEIGHT = (
    W_CATEGORY
    + W_CREATOR_TYPE
    + W_LANGUAGE
    + W_AUDIENCE
    + W_PLATFORM
    + W_SCORE_PROXIMITY
    + W_BROKER
)

# Influencer-score gap at which the proximity signal decays to zero.
SCORE_PROXIMITY_RANGE = 40.0

# Upper bound on candidates scored in Python, applied after the SQL prefilter.
CANDIDATE_LIMIT = 500

# Only the columns the ranking actually reads.
CREATOR_COLUMNS = (
    Creator.id,
    Creator.name,
    Creator.primary_category,
    Creator.creator_type,
    Creator.primary_language,
    Creator.audience_bucket,
    Creator.influencer_score,
)


def _norm(value: str | None) -> str | None:
    """Casefold a nullable text attribute for comparison."""
    if not value:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


class SimilarityService:
    """Finds comparable creators using existing creator attributes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_similar(
        self, creator_id: int, limit: int = 10
    ) -> SimilarCreatorsResponse | None:
        """Return the top `limit` peers for `creator_id`.

        Returns None when the source creator does not exist, so the caller
        can raise a 404.
        """
        source = await self._load_source(creator_id)
        if source is None:
            return None

        candidates = await self._load_candidates(source)
        if not candidates:
            return SimilarCreatorsResponse(creator_id=creator_id, count=0, results=[])

        ids = [source.id] + [c.id for c in candidates]
        platforms, followers = await self._load_platforms(ids)
        brokers = await self._load_brokers(ids)

        src_platforms = platforms.get(source.id, frozenset())
        src_brokers = brokers.get(source.id, frozenset())

        scored: list[tuple[float, float, int, SimilarCreatorResponse]] = []
        for candidate in candidates:
            cand_platforms = platforms.get(candidate.id, frozenset())
            score, reasons = self._score(
                source,
                candidate,
                src_platforms,
                cand_platforms,
                src_brokers,
                brokers.get(candidate.id, frozenset()),
            )
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    candidate.influencer_score or 0.0,
                    candidate.id,
                    SimilarCreatorResponse(
                        id=candidate.id,
                        name=candidate.name,
                        platforms=sorted(cand_platforms),
                        followers=followers.get(candidate.id),
                        category=candidate.primary_category,
                        language=candidate.primary_language,
                        similarity_score=score,
                        match_reasons=reasons,
                    ),
                )
            )

        # Deterministic ordering: score desc, then influencer score desc, then id asc.
        scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
        results = [row[3] for row in scored[:limit]]

        return SimilarCreatorsResponse(
            creator_id=creator_id,
            count=len(results),
            results=results,
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_source(self, creator_id: int):
        result = await self.db.execute(
            select(*CREATOR_COLUMNS).where(Creator.id == creator_id)
        )
        return result.one_or_none()

    async def _load_candidates(self, source) -> list:
        """Prefilter candidates sharing at least one comparable attribute.

        Keeps the Python scoring pass small without depending on any
        dialect-specific SQL.
        """
        conditions = []
        if source.primary_category:
            conditions.append(Creator.primary_category == source.primary_category)
        if source.creator_type:
            conditions.append(Creator.creator_type == source.creator_type)
        if source.primary_language:
            conditions.append(Creator.primary_language == source.primary_language)
        if source.audience_bucket is not None:
            conditions.append(Creator.audience_bucket == source.audience_bucket)

        if not conditions:
            # Nothing classified on the source — no meaningful peers to rank.
            return []

        result = await self.db.execute(
            select(*CREATOR_COLUMNS)
            .where(
                Creator.id != source.id,
                Creator.status != CreatorStatus.INACTIVE,
                or_(*conditions),
            )
            .order_by(Creator.influencer_score.desc().nullslast(), Creator.id)
            .limit(CANDIDATE_LIMIT)
        )
        return list(result.all())

    async def _load_platforms(
        self, creator_ids: list[int]
    ) -> tuple[dict[int, frozenset[str]], dict[int, int]]:
        """Return platforms per creator and their max follower count."""
        result = await self.db.execute(
            select(
                PlatformProfile.creator_id,
                PlatformProfile.platform,
                PlatformProfile.followers,
            ).where(PlatformProfile.creator_id.in_(creator_ids))
        )

        platforms: dict[int, set[str]] = {}
        followers: dict[int, int] = {}
        for creator_id, platform, follower_count in result.all():
            if platform:
                platforms.setdefault(creator_id, set()).add(platform)
            if follower_count is not None:
                current = followers.get(creator_id)
                if current is None or follower_count > current:
                    followers[creator_id] = follower_count

        return (
            {cid: frozenset(values) for cid, values in platforms.items()},
            followers,
        )

    async def _load_brokers(self, creator_ids: list[int]) -> dict[int, frozenset[str]]:
        result = await self.db.execute(
            select(
                BrokerAssociation.creator_id,
                BrokerAssociation.broker_name,
            ).where(BrokerAssociation.creator_id.in_(creator_ids))
        )

        brokers: dict[int, set[str]] = {}
        for creator_id, broker_name in result.all():
            if broker_name:
                brokers.setdefault(creator_id, set()).add(broker_name)
        return {cid: frozenset(values) for cid, values in brokers.items()}

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score(
        self,
        source,
        candidate,
        src_platforms: frozenset[str],
        cand_platforms: frozenset[str],
        src_brokers: frozenset[str],
        cand_brokers: frozenset[str],
    ) -> tuple[float, list[str]]:
        """Score one candidate against the source. Returns (0-100, reasons)."""
        raw = 0.0
        reasons: list[str] = []

        src_category = _norm(source.primary_category)
        if src_category and src_category == _norm(candidate.primary_category):
            raw += W_CATEGORY
            reasons.append("Same category")

        src_type = _norm(source.creator_type)
        if src_type and src_type == _norm(candidate.creator_type):
            raw += W_CREATOR_TYPE
            reasons.append("Same creator type")

        src_language = _norm(source.primary_language)
        if src_language and src_language == _norm(candidate.primary_language):
            raw += W_LANGUAGE
            reasons.append("Same language")

        raw += self._score_audience(source, candidate, reasons)
        raw += self._score_platform(src_platforms, cand_platforms, reasons)
        raw += self._score_proximity(source, candidate, reasons)
        raw += self._score_broker(src_brokers, cand_brokers, reasons)

        return round(raw / TOTAL_WEIGHT * 100, 1), reasons

    def _score_audience(self, source, candidate, reasons: list[str]) -> float:
        if source.audience_bucket is None or candidate.audience_bucket is None:
            return 0.0
        distance = abs(source.audience_bucket - candidate.audience_bucket)
        if distance == 0:
            reasons.append("Similar audience size")
            return W_AUDIENCE
        if distance == 1:
            reasons.append("Comparable audience size")
            return W_AUDIENCE / 2
        return 0.0

    def _score_platform(
        self,
        src_platforms: frozenset[str],
        cand_platforms: frozenset[str],
        reasons: list[str],
    ) -> float:
        shared = {_norm(p) for p in src_platforms} & {_norm(p) for p in cand_platforms}
        shared.discard(None)
        if not shared:
            return 0.0
        reasons.append(f"Also on {sorted(shared)[0].capitalize()}")
        return W_PLATFORM

    def _score_proximity(self, source, candidate, reasons: list[str]) -> float:
        """Reward creators with a comparable influencer score / reach."""
        if source.influencer_score is None or candidate.influencer_score is None:
            return 0.0
        gap = abs(source.influencer_score - candidate.influencer_score)
        # Linear falloff: identical scores earn full weight, a wide gap earns none.
        ratio = max(0.0, 1.0 - gap / SCORE_PROXIMITY_RANGE)
        if ratio >= 0.75:
            reasons.append("Similar performance level")
        return W_SCORE_PROXIMITY * ratio

    def _score_broker(
        self,
        src_brokers: frozenset[str],
        cand_brokers: frozenset[str],
        reasons: list[str],
    ) -> float:
        if not src_brokers:
            return 0.0
        normalised = {_norm(b): b for b in cand_brokers}
        shared = {_norm(b) for b in src_brokers} & set(normalised)
        shared.discard(None)
        if not shared:
            return 0.0
        reasons.append(f"Shared broker: {normalised[sorted(shared)[0]]}")
        return W_BROKER
