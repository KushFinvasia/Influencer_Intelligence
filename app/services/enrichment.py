"""Rule-based enrichment engine.

Three-step broker detection (dictionary → domain → LLM),
audience bucketing, creator status detection, and manual review flagging.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.config.settings import (
    get_brokers_config,
    get_settings,
)
from app.schemas.creator import (
    BrokerInfo,
    BrokerRelationshipEnum,
    ContactInfo,
    CreatorStatusEnum,
    DetectionMethodEnum,
    RawProfile,
)

logger = logging.getLogger(__name__)


class EnrichmentEngine:
    """Rule-based enrichment: broker detection, bucketing, status, review flagging."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._brokers_config = get_brokers_config()
        self._brokers = self._brokers_config.get("brokers", [])

    # ------------------------------------------------------------------
    # Broker Detection (3-step)
    # ------------------------------------------------------------------

    def detect_brokers(
        self,
        profile: RawProfile,
        contacts: ContactInfo,
    ) -> list[BrokerInfo]:
        """Three-step broker detection: dictionary → domain → flag for LLM.

        Args:
            profile: Raw creator profile.
            contacts: Extracted contact information with links.

        Returns:
            List of detected broker associations.
        """
        detections: list[BrokerInfo] = []
        video_descs = (
            profile.recent_video_descriptions[:5]
            if hasattr(profile, "recent_video_descriptions") and profile.recent_video_descriptions
            else []
        )
        combined_text = (
            f"{profile.bio or ''} {profile.description or ''} "
            f"{' '.join(profile.recent_video_titles[:10])} "
            f"{' '.join(video_descs)}"
        ).lower()

        all_links = list(profile.links or [])
        all_links.extend(contacts.website)
        all_links.extend(contacts.linktree)
        all_links.extend(contacts.beacons)
        all_links.extend(contacts.carrd)
        all_links.extend(contacts.telegram)
        all_links.extend(contacts.twitter)
        all_links.extend(contacts.whatsapp)
        all_links.extend(contacts.linkedin)
        all_links.extend(contacts.facebook)
        all_links = list(set(all_links))

        for broker in self._brokers:
            broker_name = broker["name"]
            best_match: BrokerInfo | None = None

            # Step 1: Referral link match (highest confidence)
            for pattern in broker.get("referral_patterns", []):
                for link in all_links:
                    if pattern.lower() in link.lower():
                        match = BrokerInfo(
                            broker_name=broker_name,
                            relationship_type=BrokerRelationshipEnum.AFFILIATE,
                            confidence=0.95,
                            detection_method=DetectionMethodEnum.RULE,
                            evidence=f"Referral link found: {link}",
                            evidence_urls=[link],
                        )
                        if not best_match or match.confidence > best_match.confidence:
                            best_match = match
                        break

            # Step 2: Domain match in links
            if not best_match:
                for domain in broker.get("domains", []):
                    for link in all_links:
                        if domain.lower() in link.lower():
                            match = BrokerInfo(
                                broker_name=broker_name,
                                relationship_type=BrokerRelationshipEnum.MENTION_ONLY,
                                confidence=0.85,
                                detection_method=DetectionMethodEnum.RULE,
                                evidence=f"Domain match: {domain} in {link}",
                                evidence_urls=[link],
                            )
                            if not best_match or match.confidence > best_match.confidence:
                                best_match = match
                            break

            # Step 3: Alias mention in text
            if not best_match:
                for alias in broker.get("aliases", []):
                    # Word boundary match to avoid false positives
                    pattern = re.compile(
                        rf"\b{re.escape(alias)}\b", re.IGNORECASE
                    )
                    if pattern.search(combined_text):
                        best_match = BrokerInfo(
                            broker_name=broker_name,
                            relationship_type=BrokerRelationshipEnum.MENTION_ONLY,
                            confidence=0.70,
                            detection_method=DetectionMethodEnum.RULE,
                            evidence=f"Alias '{alias}' found in profile text",
                        )
                        break

            if best_match:
                detections.append(best_match)

        return detections

    def needs_llm_broker_verification(
        self, detections: list[BrokerInfo]
    ) -> bool:
        """Check if any broker detection needs LLM verification."""
        if not detections:
            return True  # No rule-based match — LLM should try
        return any(
            d.confidence < 0.75 for d in detections
        )

    # ------------------------------------------------------------------
    # Audience Bucketing
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_audience_bucket(followers: int | None) -> int:
        """Assign audience bucket based on follower count.

        Bucket 1: < 10,000
        Bucket 2: 10,000 – 300,000
        Bucket 3: 300,000 – 999,999
        Bucket 4: 1,000,000+
        """
        if not followers or followers < 10_000:
            return 1
        elif followers < 300_000:
            return 2
        elif followers < 1_000_000:
            return 3
        else:
            return 4

    # ------------------------------------------------------------------
    # Creator Status Detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_status(
        last_upload: datetime | None,
        is_private: bool = False,
        is_suspended: bool = False,
    ) -> CreatorStatusEnum:
        """Determine creator status based on activity.

        Args:
            last_upload: Datetime of the most recent upload/post.
            is_private: Whether the account is private.
            is_suspended: Whether the account is suspended.
        """
        if is_private:
            return CreatorStatusEnum.PRIVATE
        if is_suspended:
            return CreatorStatusEnum.SUSPENDED
        if last_upload is None:
            return CreatorStatusEnum.INACTIVE

        now = datetime.now(timezone.utc)
        if last_upload.tzinfo is None:
            last_upload = last_upload.replace(tzinfo=timezone.utc)

        days_since = (now - last_upload).days
        if days_since <= 30:
            return CreatorStatusEnum.ACTIVE
        elif days_since <= 180:
            return CreatorStatusEnum.DORMANT
        else:
            return CreatorStatusEnum.INACTIVE

    # ------------------------------------------------------------------
    # Manual Review Flagging
    # ------------------------------------------------------------------

    def check_needs_review(
        self,
        broker_confidence: float | None = None,
        category_confidence: float | None = None,
        language_confidence: float | None = None,
        creator_type_confidence: float | None = None,
    ) -> tuple[bool, str | None]:
        """Check if any classification falls below the review threshold.

        Returns:
            Tuple of (needs_review, review_reason).
        """
        threshold = self.settings.review_confidence_threshold
        reasons: list[str] = []

        checks = [
            ("broker", broker_confidence),
            ("category", category_confidence),
            ("language", language_confidence),
            ("creator_type", creator_type_confidence),
        ]

        for name, confidence in checks:
            if confidence is not None and confidence < threshold:
                reasons.append(
                    f"{name} confidence ({confidence:.2f}) below threshold ({threshold})"
                )

        if reasons:
            return True, "; ".join(reasons)
        return False, None
