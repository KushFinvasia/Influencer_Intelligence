"""Pipeline orchestrator — coordinates the full discovery workflow.

Crawler → Preprocessor → Contact Extractor → Rule Engine →
LLM (if needed) → Normalizer → Deduplicator → Scorer → Database
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_exclusions_config, get_settings
from app.crawlers.youtube import YouTubeCrawler
from app.crawlers.instagram import InstagramCrawler
from app.dedupe.deduplicator import Deduplicator
from app.extractors.contact import ContactExtractor
from app.extractors.transcript import VideoTranscriptExtractor
from app.extractors.category import CategoryExtractor
from app.llm.client import LLMClient
from app.llm.preprocessor import TextPreprocessor
from app.llm.prompts import (
    build_broker_verification_prompt,
    build_category_prompt,
    build_creator_type_prompt,
    build_language_prompt,
    build_relevance_prompt,
)
from app.normalization.normalizer import Normalizer
from app.schemas.creator import (
    BrokerInfo,
    BrokerRelationshipEnum,
    CategoryResult,
    ClassificationResult,
    CreatorStatusEnum,
    DetectionMethodEnum,
    EngagementData,
    EnrichedProfile,
    RawProfile,
    ScoreBreakdown,
)
from app.services.creator_service import CreatorService
from app.services.enrichment import EnrichmentEngine
from app.services.scoring import ScoringEngine

logger = logging.getLogger(__name__)


class DiscoveryPipeline:
    """Orchestrates the full creator discovery and enrichment pipeline."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.exclusions = get_exclusions_config()
        self.preprocessor = TextPreprocessor()
        self.contact_extractor = ContactExtractor()
        self.transcript_extractor = VideoTranscriptExtractor()
        self.category_extractor = CategoryExtractor()
        self.enrichment = EnrichmentEngine()
        self.normalizer = Normalizer()
        self.deduplicator = Deduplicator()
        self.scoring = ScoringEngine()
        self.llm = LLMClient()

    def _is_excluded(self, profile: RawProfile) -> tuple[bool, str]:
        """Check if profile matches known non-financial channels or media patterns."""
        name_lower = (profile.display_name or "").lower()
        user_lower = (profile.username or "").lower()
        bio_lower = (f"{profile.bio or ''} {profile.description or ''}").lower()

        # 1. Check blacklist of channel patterns
        excluded_channels = self.exclusions.get("excluded_channel_patterns", [])
        for pattern in excluded_channels:
            p_clean = pattern.lower().strip()
            if p_clean and (p_clean in name_lower or p_clean in user_lower):
                return True, f"Matched blacklisted channel pattern: '{p_clean}'"

        # 2. Content relevance check using video titles & bio
        fin_keywords = self.exclusions.get("financial_keywords", [])
        excl_keywords = self.exclusions.get("excluded_keywords", [])
        
        all_titles = " ".join(profile.recent_video_titles or []).lower()
        combined_text = f"{name_lower} {bio_lower} {all_titles}"

        has_fin_kw = any(kw.lower() in combined_text for kw in fin_keywords)
        has_excl_kw = any(kw.lower() in combined_text for kw in excl_keywords)

        # If has multiple video titles and ZERO financial keywords, but has explicit exclusion keywords
        if profile.recent_video_titles and len(profile.recent_video_titles) >= 3:
            title_fin_matches = sum(
                1 for t in profile.recent_video_titles if any(kw.lower() in t.lower() for kw in fin_keywords)
            )
            # If 0 out of >= 3 recent video titles contain any financial term and bio has none
            if title_fin_matches == 0 and not any(kw.lower() in bio_lower for kw in fin_keywords):
                return True, "No financial keywords detected across recent video titles and bio"

        # 3. Creator vs Organization/Media filter
        org_patterns = self.exclusions.get("organization_patterns", [])
        for pattern in org_patterns:
            p_clean = pattern.lower().strip()
            # Only checking name and bio, not recent video titles, since titles can contain news terms
            if p_clean and (p_clean in name_lower or p_clean in user_lower or p_clean in bio_lower):
                return True, f"Identified as organization/media (matched '{p_clean}')"

        return False, ""

    async def run_youtube(
        self,
        db: AsyncSession,
        keywords: list[dict[str, str]],
        max_depth: int = 3,
        job_id: int | None = None,
    ) -> dict:
        """Run the YouTube discovery pipeline."""
        service = CreatorService(db)
        crawler = YouTubeCrawler()

        if job_id:
            await service.update_scrape_job(job_id, status="running")
            await db.commit()

        try:
            logger.info(
                "YouTube discovery: %d keywords, depth %d",
                len(keywords),
                max_depth,
            )
            raw_profiles, keyword_metrics = await crawler.discover(keywords, max_depth)
            logger.info("Discovered %d YouTube profiles", len(raw_profiles))

            stats = {"discovered": len(raw_profiles), "new": 0, "updated": 0, "rejected": 0}
            for profile in raw_profiles:
                try:
                    enriched = await self._process_profile(profile, db, service)
                    if enriched:
                        stats["new"] += 1
                    else:
                        stats["rejected"] += 1
                    
                    # Commit every 10 creators so progress is immediately saved to disk
                    if (stats["new"] + stats["rejected"]) % 10 == 0:
                        await db.commit()
                except Exception as e:
                    logger.error(
                        "Error processing profile %s: %s",
                        profile.platform_user_id,
                        e,
                        exc_info=True,
                    )

            import os
            is_paused = os.path.exists("youtube_resume_state.json")

            if job_id:
                await service.update_scrape_job(
                    job_id,
                    status="failed" if is_paused else "completed",
                    error_message="Quota Exceeded. Saved state to resume later." if is_paused else None,
                    total_discovered=stats["discovered"],
                    total_new=stats["new"],
                    keyword_metrics=keyword_metrics,
                    completed_at=datetime.now(timezone.utc),
                )

            await db.commit()
            return stats

        except Exception as e:
            logger.error("YouTube pipeline failed: %s", e, exc_info=True)
            if job_id:
                await service.update_scrape_job(
                    job_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now(timezone.utc),
                )
            raise

    async def run_instagram(
        self,
        db: AsyncSession,
        hashtags: list[dict[str, str]],
        usernames: list[str] | None = None,
        max_depth: int = 1,
        job_id: int | None = None,
    ) -> dict:
        """Run the Instagram discovery pipeline."""
        service = CreatorService(db)
        crawler = InstagramCrawler()

        if job_id:
            await service.update_scrape_job(job_id, status="running")
            await db.commit()

        try:
            logger.info(
                "Instagram discovery: %d terms, depth %d",
                len(hashtags) + len(usernames or []),
                max_depth,
            )
            raw_profiles, keyword_metrics = await crawler.discover(hashtags, usernames, max_depth)
            logger.info("Discovered %d Instagram profiles", len(raw_profiles))

            stats = {"discovered": len(raw_profiles), "new": 0, "updated": 0, "rejected": 0}
            for profile in raw_profiles:
                try:
                    enriched = await self._process_profile(profile, db, service)
                    if enriched:
                        stats["new"] += 1
                    else:
                        stats["rejected"] += 1
                except Exception as e:
                    logger.error(
                        "Error processing Instagram profile %s: %s",
                        profile.platform_user_id,
                        e,
                        exc_info=True,
                    )

            if job_id:
                await service.update_scrape_job(
                    job_id,
                    status="completed",
                    total_discovered=stats["discovered"],
                    total_new=stats["new"],
                    keyword_metrics=keyword_metrics,
                    completed_at=datetime.now(timezone.utc),
                )

            await db.commit()
            return stats

        except Exception as e:
            logger.error("Instagram pipeline failed: %s", e, exc_info=True)
            if job_id:
                await service.update_scrape_job(
                    job_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now(timezone.utc),
                )
            raise

    async def run_full(
        self,
        db: AsyncSession,
        youtube_keywords: list[str],
        instagram_hashtags: list[str],
        instagram_usernames: list[str] | None = None,
        max_depth: int = 3,
        job_id: int | None = None,
    ) -> dict:
        """Run both YouTube and Instagram pipelines."""
        yt_stats = await self.run_youtube(
            db, youtube_keywords, max_depth, job_id
        )
        ig_stats = await self.run_instagram(
            db, instagram_hashtags, instagram_usernames, 1, job_id
        )
        return {
            "youtube": yt_stats,
            "instagram": ig_stats,
            "total_discovered": (
                yt_stats["discovered"] + ig_stats["discovered"]
            ),
            "total_new": yt_stats["new"] + ig_stats["new"],
        }

    async def refresh_active_creators(self) -> None:
        """Refresh stats for all active creators (called by scheduler)."""
        logger.info("Refreshing active creators...")

    async def graph_expansion(self) -> None:
        """Discover new creators via graph traversal (called by scheduler)."""
        logger.info("Running graph expansion...")

    # ------------------------------------------------------------------
    # Private: Process a single profile through the full pipeline
    # ------------------------------------------------------------------

    async def _process_profile(
        self,
        profile: RawProfile,
        db: AsyncSession,
        service: CreatorService,
    ) -> EnrichedProfile | None:
        """Process a single profile through the full enrichment pipeline.

        Flow:
          0. Exclusion and relevance filter
          1. Contact extraction (regex)
          2. Text preprocessing
          3. Rule-based enrichment (brokers, bucket, status)
          4. LLM enrichment (with domain relevance gatekeeper)
          5. Scoring
          6. Normalization
          7. Deduplication check
          8. Database upsert
        """
        # 0a. Instagram strict follower filter
        if profile.platform == "instagram":
            actual_followers = profile.followers or 0
            if actual_followers < self.settings.min_instagram_followers:
                logger.info("Filtered out Instagram profile '%s': Only %d followers (minimum %d)", profile.username, actual_followers, self.settings.min_instagram_followers)
                return None

        # 0. Fast pre-filter: Reject blacklisted media channels or non-finance profiles
        is_excl, reason = self._is_excluded(profile)
        if is_excl:
            logger.info("Filtered out profile '%s': %s", profile.display_name or profile.username, reason)
            return None

        # 1. Contact and social media handle extraction from bio, description, and last 5 video descriptions
        contacts = self.contact_extractor.extract(
            bio=profile.bio or "",
            description=profile.description or "",
            video_descriptions=profile.recent_video_descriptions[:5],
            links=profile.links,
        )

        # 2. Rule-based enrichment
        brokers = self.enrichment.detect_brokers(profile, contacts)
        audience_bucket = self.enrichment.calculate_audience_bucket(
            profile.followers
        )
        status = CreatorStatusEnum.ACTIVE

        # 3. LLM enrichment
        classification = None
        needs_llm = True

        if needs_llm:
            llm_input = self.preprocessor.prepare_llm_input(profile)

            if llm_input.strip():
                classification = await self._run_llm_classification(
                    llm_input, brokers, service, db, profile
                )

        # Disqualify if LLM gatekeeper determined this is not a financial creator
        if classification and not classification.is_financial_creator:
            logger.info(
                "Discarding non-financial creator '%s' based on LLM relevance evaluation.",
                profile.display_name or profile.username,
            )
            return None

        # 4. Build enriched profile
        enriched = EnrichedProfile(
            raw_profile=profile,
            contacts=contacts,
            brokers=brokers,
            classification=classification,
            audience_bucket=audience_bucket,
            status=status,
        )

        # 5. Check review threshold
        broker_conf = max(
            (b.confidence for b in brokers), default=None
        )
        cat_conf = (
            classification.categories[0].confidence
            if classification and classification.categories
            else None
        )
        lang_conf = (
            classification.language_confidence if classification else None
        )
        type_conf = (
            classification.creator_type_confidence
            if classification
            else None
        )

        needs_review, review_reason = self.enrichment.check_needs_review(
            broker_conf, cat_conf, lang_conf, type_conf
        )
        enriched.needs_review = needs_review
        enriched.review_reason = review_reason

        # 6. Scoring
        engagement = EngagementData()
        enriched.score = self.scoring.calculate(
            followers=profile.followers or 0,
            engagement=engagement,
            contacts=contacts,
            broker_count=len(brokers),
            verified=profile.verified,
            primary_category_confidence=cat_conf or 0.0,
            platform=profile.platform,
        )

        # 7. Normalization
        enriched = self.normalizer.normalize(enriched)

        # 8. Deduplication check
        existing_id = await self.deduplicator.find_duplicate(
            db, enriched
        )

        if existing_id:
            await self.deduplicator.merge_profiles(
                db, existing_id, enriched
            )
        else:
            await service.upsert_creator(enriched)

        return enriched

    async def _run_llm_classification(
        self,
        llm_input: str,
        rule_brokers: list[BrokerInfo],
        service: CreatorService,
        db: AsyncSession,
        profile: RawProfile | None = None,
    ) -> ClassificationResult:
        """Run all LLM classification tasks and combine results."""
        classification = ClassificationResult()

        # Step 1: Financial Domain Relevance Gatekeeper
        try:
            rel_response = await self.llm.classify(
                system_prompt=build_relevance_prompt(),
                user_input=llm_input,
            )
            if rel_response.success:
                rel_result = rel_response.parsed_result
                is_fin = rel_result.get("is_financial_creator", True)
                classification.is_financial_creator = is_fin
                classification.relevance_score = rel_result.get("relevance_score")

                if not is_fin:
                    logger.info(
                        "LLM gatekeeper: '%s' is NOT a financial creator (%s): %s",
                        (profile.display_name if profile else "Unknown"),
                        rel_result.get("detected_genre"),
                        rel_result.get("reasoning"),
                    )
                    return classification
        except Exception as e:
            logger.error("Relevance gatekeeper LLM failed: %s", e)

        # Step 2: Category classification (Rule Pattern Matcher -> LLM refinement)
        rule_primary_cat, rule_categories = self.category_extractor.extract_categories(profile)
        classification.primary_category = rule_primary_cat
        classification.categories = rule_categories

        try:
            cat_response = await self.llm.classify(
                system_prompt=build_category_prompt(),
                user_input=llm_input,
            )
            if cat_response.success:
                result = cat_response.parsed_result
                if result.get("primary_category"):
                    classification.primary_category = result.get(
                        "primary_category"
                    )
                if result.get("categories"):
                    classification.categories = [
                        CategoryResult(**c)
                        for c in result.get("categories", [])
                    ]
                classification.reasoning = result.get("reasoning")
                classification.evidence = result.get("evidence", [])

                await service.log_llm_call(
                    creator_id=None,
                    task="category",
                    model_used=cat_response.model_used,
                    input_text=llm_input,
                    raw_response=cat_response.raw_response,
                    parsed_result=result,
                    reasoning=result.get("reasoning"),
                    evidence=result.get("evidence"),
                    confidence=(
                        classification.categories[0].confidence
                        if classification.categories
                        else None
                    ),
                    input_tokens=cat_response.input_tokens,
                    output_tokens=cat_response.output_tokens,
                    latency_ms=cat_response.latency_ms,
                )
        except Exception as e:
            logger.error("Category LLM failed: %s", e)

        # Step 3: Language detection (Direct Video Transcript -> LLM Fallback)
        detected_via_transcript = False
        if profile and profile.platform == "youtube" and profile.recent_video_ids:
            try:
                t_res = self.transcript_extractor.detect_channel_language(
                    profile.recent_video_ids, max_videos=3
                )
                if t_res:
                    classification.primary_language = t_res.primary_language
                    classification.language_confidence = t_res.confidence
                    detected_via_transcript = True
                    logger.info(
                        "Language detected via video transcripts for '%s': %s (confidence: %.2f)",
                        profile.display_name or profile.username,
                        t_res.primary_language,
                        t_res.confidence,
                    )
            except Exception as e:
                logger.debug("Transcript language detection skipped: %s", e)

        if not detected_via_transcript:
            try:
                lang_response = await self.llm.classify(
                    system_prompt=build_language_prompt(),
                    user_input=llm_input,
                )
                if lang_response.success:
                    result = lang_response.parsed_result
                    classification.primary_language = result.get(
                        "primary_language"
                    )
                    classification.language_confidence = result.get(
                        "confidence"
                    )

                    await service.log_llm_call(
                        creator_id=None,
                        task="language",
                        model_used=lang_response.model_used,
                        input_text=llm_input,
                        raw_response=lang_response.raw_response,
                        parsed_result=result,
                        reasoning=result.get("reasoning"),
                        confidence=result.get("confidence"),
                        input_tokens=lang_response.input_tokens,
                        output_tokens=lang_response.output_tokens,
                        latency_ms=lang_response.latency_ms,
                    )
            except Exception as e:
                logger.error("Language LLM failed: %s", e)

        # Step 4: Creator type
        try:
            type_response = await self.llm.classify(
                system_prompt=build_creator_type_prompt(),
                user_input=llm_input,
            )
            if type_response.success:
                result = type_response.parsed_result
                classification.creator_type = result.get("creator_type")
                classification.creator_type_confidence = result.get(
                    "confidence"
                )

                await service.log_llm_call(
                    creator_id=None,
                    task="creator_type",
                    model_used=type_response.model_used,
                    input_text=llm_input,
                    raw_response=type_response.raw_response,
                    parsed_result=result,
                    reasoning=result.get("reasoning"),
                    confidence=result.get("confidence"),
                    input_tokens=type_response.input_tokens,
                    output_tokens=type_response.output_tokens,
                    latency_ms=type_response.latency_ms,
                )
        except Exception as e:
            logger.error("Creator type LLM failed: %s", e)

        # Step 5: Broker verification (only if rule-based detection is uncertain)
        if self.enrichment.needs_llm_broker_verification(rule_brokers):
            try:
                broker_response = await self.llm.classify(
                    system_prompt=build_broker_verification_prompt(),
                    user_input=llm_input,
                )
                if broker_response.success:
                    result = broker_response.parsed_result
                    broker_name = result.get("broker_name", "")
                    if broker_name and broker_name.lower() != "none":
                        rel_type = result.get("relationship_type")
                        classification.broker = BrokerInfo(
                            broker_name=broker_name,
                            relationship_type=(
                                BrokerRelationshipEnum(rel_type)
                                if rel_type
                                in [e.value for e in BrokerRelationshipEnum]
                                else BrokerRelationshipEnum.MENTION_ONLY
                            ),
                            confidence=result.get("confidence", 0.5),
                            detection_method=DetectionMethodEnum.LLM,
                            evidence=result.get("reasoning"),
                            evidence_urls=[],
                        )

                    await service.log_llm_call(
                        creator_id=None,
                        task="broker",
                        model_used=broker_response.model_used,
                        input_text=llm_input,
                        raw_response=broker_response.raw_response,
                        parsed_result=result,
                        reasoning=result.get("reasoning"),
                        evidence=result.get("evidence"),
                        confidence=result.get("confidence"),
                        input_tokens=broker_response.input_tokens,
                        output_tokens=broker_response.output_tokens,
                        latency_ms=broker_response.latency_ms,
                    )
            except Exception as e:
                logger.error("Broker LLM failed: %s", e)

        return classification
