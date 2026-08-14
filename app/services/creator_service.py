"""Creator service — business logic for database operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    BrokerAssociation,
    Category,
    Creator,
    CreatorCategory,
    CreatorRelationship,
    EngagementMetric,
    LLMLog,
    PlatformProfile,
    ScrapeJob,
    ScrapeLog,
    SocialLink,
    Video,
    Post,
    InstagramMetric,
    YouTubeMetric,
)
from app.analytics import (
    InstagramMetricsCalculator,
    normalize_apify_instagram_post,
    InstagramPostNormalized,
    YouTubeMetricsCalculator,
    normalize_youtube_video,
    YouTubeVideoNormalized,
)
from app.schemas.creator import (
    BrokerInfo,
    CategoryResult,
    ClassificationResult,
    ContactInfo,
    CreatorDetailResponse,
    CreatorSummaryResponse,
    CreatorStatusEnum,
    DetectionMethodEnum,
    EngagementData,
    EnrichedProfile,
    PlatformProfileResponse,
    RawProfile,
    ScoreBreakdown,
    SocialLinkResponse,
    BrokerAssociationResponse,
    CategoryResponse,
    EngagementResponse,
)
from app.schemas.search import SearchFilters, SearchResponse

logger = logging.getLogger(__name__)


class CreatorService:
    """Database operations for creators and related entities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def upsert_creator(self, enriched: EnrichedProfile) -> int:
        """Insert or update a creator from an enriched profile.

        Returns the creator ID.
        """
        profile = enriched.raw_profile

        # Check if platform profile already exists
        existing_profile = await self.db.execute(
            select(PlatformProfile).where(
                PlatformProfile.platform == profile.platform,
                PlatformProfile.platform_user_id == profile.platform_user_id,
            )
        )
        existing = existing_profile.scalar_one_or_none()

        if existing and existing.creator_id:
            # Update existing creator
            creator_id = existing.creator_id
            profile_id = existing.id
            await self._update_creator(creator_id, enriched)
            await self._update_platform_profile(profile_id, enriched)
        else:
            # Create new creator
            creator_id, profile_id = await self._create_creator(enriched)

        # Upsert social links
        await self._upsert_social_links(creator_id, enriched.contacts)

        # Upsert broker associations
        await self._upsert_brokers(creator_id, enriched.brokers)

        # Upsert categories
        if enriched.classification:
            await self._upsert_categories(
                creator_id, enriched.classification
            )

        # Upsert Instagram content and metrics snapshot (append-only historical tracking)
        if profile.platform == "instagram":
            await self._upsert_instagram_content_and_metrics(
                creator_id, profile_id, enriched
            )
        elif profile.platform == "youtube":
            await self._upsert_youtube_content_and_metrics(
                creator_id, profile_id, enriched
            )

        await self.db.flush()
        return creator_id

    async def _create_creator(self, enriched: EnrichedProfile) -> tuple[int, int]:
        """Create a new creator + platform profile. Returns (creator_id, profile_id)."""
        profile = enriched.raw_profile

        creator = Creator(
            name=profile.display_name or profile.username or "",
            email=(
                enriched.contacts.emails[0]
                if enriched.contacts.emails
                else None
            ),
            phone=(
                enriched.contacts.phones[0]
                if enriched.contacts.phones
                else None
            ),
            website=(
                enriched.contacts.website[0]
                if enriched.contacts.website
                else None
            ),
            audience_bucket=enriched.audience_bucket,
            status=enriched.status.value,
            influencer_score=(
                enriched.score.total_score if enriched.score else None
            ),
            score_breakdown=(
                enriched.score.model_dump() if enriched.score else None
            ),
            needs_review=enriched.needs_review,
            review_reason=enriched.review_reason,
            last_enriched_at=datetime.now(timezone.utc),
        )

        if enriched.classification:
            cls = enriched.classification
            creator.primary_category = cls.primary_category
            creator.creator_type = cls.creator_type
            creator.creator_type_confidence = cls.creator_type_confidence
            creator.primary_language = cls.primary_language
            creator.language_confidence = cls.language_confidence

        self.db.add(creator)
        await self.db.flush()

        # Create platform profile
        pp = PlatformProfile(
            creator_id=creator.id,
            platform=profile.platform,
            platform_user_id=profile.platform_user_id,
            username=profile.username,
            display_name=profile.display_name,
            bio=profile.bio,
            description=profile.description,
            followers=profile.followers,
            following=profile.following,
            video_count=profile.video_count,
            verified=profile.verified,
            profile_url=profile.profile_url,
            thumbnail_url=profile.thumbnail_url,
            country=profile.country,
            raw_data=profile.raw_data,
            discovered_via=profile.discovered_via,
        )
        self.db.add(pp)
        await self.db.flush()

        return creator.id, pp.id

    async def _update_creator(
        self, creator_id: int, enriched: EnrichedProfile
    ) -> None:
        """Update an existing creator with new data."""
        result = await self.db.execute(
            select(Creator).where(Creator.id == creator_id)
        )
        creator = result.scalar_one_or_none()
        if not creator:
            return

        profile = enriched.raw_profile
        creator.name = profile.display_name or profile.username or creator.name
        creator.audience_bucket = enriched.audience_bucket or creator.audience_bucket
        creator.status = enriched.status.value
        creator.needs_review = enriched.needs_review
        creator.review_reason = enriched.review_reason
        creator.last_enriched_at = datetime.now(timezone.utc)

        if enriched.contacts.emails and not creator.email:
            creator.email = enriched.contacts.emails[0]
        if enriched.contacts.phones and not creator.phone:
            creator.phone = enriched.contacts.phones[0]
        if enriched.contacts.website and not creator.website:
            creator.website = enriched.contacts.website[0]

        if enriched.score:
            creator.influencer_score = enriched.score.total_score
            creator.score_breakdown = enriched.score.model_dump()

        if enriched.classification:
            cls = enriched.classification
            if cls.primary_category:
                creator.primary_category = cls.primary_category
            if cls.creator_type:
                creator.creator_type = cls.creator_type
                creator.creator_type_confidence = cls.creator_type_confidence
            if cls.primary_language:
                creator.primary_language = cls.primary_language
                creator.language_confidence = cls.language_confidence

    async def _update_platform_profile(
        self, profile_id: int, enriched: EnrichedProfile
    ) -> None:
        """Update an existing platform profile."""
        result = await self.db.execute(
            select(PlatformProfile).where(PlatformProfile.id == profile_id)
        )
        pp = result.scalar_one_or_none()
        if not pp:
            return

        profile = enriched.raw_profile
        pp.username = profile.username or pp.username
        pp.display_name = profile.display_name or pp.display_name
        pp.bio = profile.bio or pp.bio
        pp.description = profile.description or pp.description
        pp.followers = profile.followers or pp.followers
        pp.following = profile.following or pp.following
        pp.verified = profile.verified or pp.verified
        pp.profile_url = profile.profile_url or pp.profile_url
        pp.thumbnail_url = profile.thumbnail_url or pp.thumbnail_url
        pp.country = profile.country or pp.country
        
        # Idempotent merge of discovered_via
        if profile.discovered_via:
            existing_disc = pp.discovered_via or []
            new_disc = []
            
            # Use a set of tuples for O(1) duplicate checking
            seen = {(d.get("term"), d.get("category")) for d in existing_disc}
            
            for d in profile.discovered_via:
                key = (d.get("term"), d.get("category"))
                if key not in seen:
                    new_disc.append(d)
                    seen.add(key)
                    
            if new_disc:
                pp.discovered_via = existing_disc + new_disc
        pp.raw_data = profile.raw_data

    async def _upsert_social_links(
        self, creator_id: int, contacts: ContactInfo
    ) -> None:
        """Upsert social links for a creator."""
        link_map = {
            "email": [(e, e) for e in contacts.emails],
            "phone": [(p, p) for p in contacts.phones],
            "telegram": [(u, u) for u in contacts.telegram],
            "whatsapp": [(u, u) for u in contacts.whatsapp],
            "linkedin": [(u, u) for u in contacts.linkedin],
            "twitter": [(u, u) for u in contacts.twitter],
            "facebook": [(u, u) for u in contacts.facebook],
            "discord": [(u, u) for u in contacts.discord],
            "website": [(u, u) for u in contacts.website],
            "linktree": [(u, u) for u in contacts.linktree],
            "beacons": [(u, u) for u in contacts.beacons],
        }

        for platform, entries in link_map.items():
            for url, value in entries:
                existing = await self.db.execute(
                    select(SocialLink).where(
                        SocialLink.creator_id == creator_id,
                        SocialLink.platform == platform,
                        SocialLink.value == value,
                    )
                )
                if not existing.scalar_one_or_none():
                    self.db.add(
                        SocialLink(
                            creator_id=creator_id,
                            platform=platform,
                            url=url,
                            value=value,
                        )
                    )

    async def _upsert_brokers(
        self, creator_id: int, brokers: list[BrokerInfo]
    ) -> None:
        """Upsert broker associations."""
        for broker in brokers:
            existing = await self.db.execute(
                select(BrokerAssociation).where(
                    BrokerAssociation.creator_id == creator_id,
                    BrokerAssociation.broker_name == broker.broker_name,
                )
            )
            ba = existing.scalar_one_or_none()
            if ba:
                # Update if new confidence is higher
                if broker.confidence > ba.confidence:
                    ba.confidence = broker.confidence
                    ba.relationship_type = (
                        broker.relationship_type.value
                        if broker.relationship_type
                        else ba.relationship_type
                    )
                    ba.detection_method = broker.detection_method.value
                    ba.evidence = broker.evidence
                    ba.evidence_urls = broker.evidence_urls
            else:
                self.db.add(
                    BrokerAssociation(
                        creator_id=creator_id,
                        broker_name=broker.broker_name,
                        relationship_type=(
                            broker.relationship_type.value
                            if broker.relationship_type
                            else None
                        ),
                        confidence=broker.confidence,
                        detection_method=broker.detection_method.value,
                        evidence=broker.evidence,
                        evidence_urls=broker.evidence_urls,
                    )
                )

    async def _upsert_categories(
        self, creator_id: int, classification: ClassificationResult
    ) -> None:
        """Upsert category classifications."""
        for cat in classification.categories:
            # Get or create category
            result = await self.db.execute(
                select(Category).where(Category.name == cat.name)
            )
            category = result.scalar_one_or_none()
            if not category:
                category = Category(name=cat.name)
                self.db.add(category)
                await self.db.flush()

            # Upsert creator-category link
            existing = await self.db.execute(
                select(CreatorCategory).where(
                    CreatorCategory.creator_id == creator_id,
                    CreatorCategory.category_id == category.id,
                )
            )
            cc = existing.scalar_one_or_none()
            is_primary = cat.name == classification.primary_category
            if cc:
                cc.is_primary = is_primary
                cc.content_percentage = cat.content_percentage
                cc.confidence = cat.confidence
            else:
                self.db.add(
                    CreatorCategory(
                        creator_id=creator_id,
                        category_id=category.id,
                        is_primary=is_primary,
                        content_percentage=cat.content_percentage,
                        confidence=cat.confidence,
                    )
                )

    async def _upsert_instagram_content_and_metrics(
        self, creator_id: int, profile_id: int, enriched: EnrichedProfile, max_posts: int = 20
    ) -> None:
        """Upsert individual Instagram post records and append a historical performance snapshot."""
        profile = enriched.raw_profile
        if profile.platform != "instagram":
            return

        raw_data = profile.raw_data or {}
        raw_items: list[dict[str, Any]] = []

        if isinstance(raw_data, dict):
            if "latestPosts" in raw_data and isinstance(raw_data["latestPosts"], list):
                raw_items.extend(raw_data["latestPosts"])
            if "data" in raw_data and isinstance(raw_data["data"], dict):
                hashtag_items = raw_data["data"].get("raw_items", [])
                if isinstance(hashtag_items, list):
                    raw_items.extend(hashtag_items)

        # 1. Normalize and upsert post-level records (preserving NULLs without loss)
        normalized_posts: list[InstagramPostNormalized] = []
        for item in raw_items:
            norm = normalize_apify_instagram_post(item, default_username=profile.username)
            if not norm:
                continue
            normalized_posts.append(norm)

            existing_post_res = await self.db.execute(
                select(Post).where(
                    Post.platform_profile_id == profile_id,
                    Post.post_id == norm.post_id,
                )
            )
            p_record = existing_post_res.scalar_one_or_none()
            if p_record:
                p_record.creator_username = norm.creator_username
                p_record.caption = norm.caption
                p_record.media_type = norm.media_type
                p_record.likes = norm.likes
                p_record.comments_count = norm.comments
                p_record.views = norm.views
                p_record.published_at = norm.posted_at
                p_record.url = norm.url
                p_record.raw_payload = norm.raw_payload
            else:
                self.db.add(
                    Post(
                        platform_profile_id=profile_id,
                        post_id=norm.post_id,
                        creator_username=norm.creator_username,
                        caption=norm.caption,
                        media_type=norm.media_type,
                        likes=norm.likes,
                        comments_count=norm.comments,
                        views=norm.views,
                        published_at=norm.posted_at,
                        url=norm.url,
                        raw_payload=norm.raw_payload,
                    )
                )

        await self.db.flush()

        # 2. Query all posts for this profile to calculate performance metrics
        all_posts_res = await self.db.execute(
            select(Post)
            .where(Post.platform_profile_id == profile_id)
            .order_by(Post.published_at.desc().nullslast())
        )
        stored_posts = all_posts_res.scalars().all()

        # 3. Deterministically compute metrics over latest configurable sample (default 20)
        metrics_res = InstagramMetricsCalculator.calculate_metrics(
            posts=stored_posts or normalized_posts,
            followers=profile.followers,
            max_posts=max_posts,
        )

        # 4. Insert an append-only timestamped historical snapshot (do NOT overwrite previous history!)
        snap = InstagramMetric(
            creator_id=creator_id,
            platform_profile_id=profile_id,
            followers=metrics_res.followers,
            posts_analyzed=metrics_res.posts_analyzed,
            views_analyzed=metrics_res.views_analyzed,
            likes_analyzed=metrics_res.likes_analyzed,
            comments_analyzed=metrics_res.comments_analyzed,
            average_views=metrics_res.average_views,
            median_views=metrics_res.median_views,
            average_likes=metrics_res.average_likes,
            median_likes=metrics_res.median_likes,
            average_comments=metrics_res.average_comments,
            median_comments=metrics_res.median_comments,
            engagement_rate=metrics_res.engagement_rate,
            last_post_date=metrics_res.last_post_date,
            metrics_calculated_at=metrics_res.metrics_calculated_at,
        )
        self.db.add(snap)

    async def _upsert_youtube_content_and_metrics(
        self, creator_id: int, profile_id: int, enriched: EnrichedProfile, max_videos: int = 20
    ) -> None:
        """Upsert individual YouTube video records and append a historical performance snapshot."""
        profile = enriched.raw_profile
        if profile.platform != "youtube":
            return

        raw_data = profile.raw_data or {}
        raw_items: list[dict[str, Any]] = []

        if isinstance(raw_data, dict):
            if "videos" in raw_data and isinstance(raw_data["videos"], list):
                raw_items.extend(raw_data["videos"])
            elif "recent_videos" in raw_data and isinstance(raw_data["recent_videos"], list):
                raw_items.extend(raw_data["recent_videos"])
            elif "items" in raw_data and isinstance(raw_data["items"], list):
                raw_items.extend(raw_data["items"])

        # 1. Normalize and upsert video-level records (preserving raw_payload & NULLs without loss)
        normalized_videos: list[YouTubeVideoNormalized] = []
        for item in raw_items:
            norm = (
                item if isinstance(item, YouTubeVideoNormalized)
                else normalize_youtube_video(item) if isinstance(item, dict)
                else normalize_youtube_video(getattr(item, "__dict__", {}))
            )
            if not norm:
                continue
            normalized_videos.append(norm)

            existing_video_res = await self.db.execute(
                select(Video).where(
                    Video.platform_profile_id == profile_id,
                    Video.video_id == norm.video_id,
                )
            )
            v_record = existing_video_res.scalar_one_or_none()
            if v_record:
                v_record.title = norm.title
                v_record.description = norm.description
                v_record.views = norm.views
                v_record.likes = norm.likes
                v_record.comments_count = norm.comments
                v_record.duration = norm.duration
                v_record.is_short = norm.is_short
                v_record.published_at = norm.published_at
                v_record.thumbnail_url = norm.thumbnail_url
                v_record.raw_payload = norm.raw_payload
            else:
                self.db.add(
                    Video(
                        platform_profile_id=profile_id,
                        video_id=norm.video_id,
                        title=norm.title,
                        description=norm.description,
                        views=norm.views,
                        likes=norm.likes,
                        comments_count=norm.comments,
                        duration=norm.duration,
                        is_short=norm.is_short,
                        published_at=norm.published_at,
                        thumbnail_url=norm.thumbnail_url,
                        raw_payload=norm.raw_payload,
                    )
                )

        await self.db.flush()

        # 2. Query all stored videos for this profile ordered by published_at DESC
        all_videos_res = await self.db.execute(
            select(Video)
            .where(Video.platform_profile_id == profile_id)
            .order_by(Video.published_at.desc().nullslast())
        )
        stored_videos = all_videos_res.scalars().all()

        # 3. Deterministically compute metrics over latest configurable sample (default 20)
        metrics_res = YouTubeMetricsCalculator.calculate_metrics(
            videos=stored_videos or normalized_videos,
            subscribers=profile.followers,
            max_videos=max_videos,
        )

        # 4. Insert an append-only timestamped historical snapshot
        snap = YouTubeMetric(
            creator_id=creator_id,
            platform_profile_id=profile_id,
            subscribers=metrics_res.subscribers,
            videos_analyzed=metrics_res.videos_analyzed,
            views_analyzed=metrics_res.views_analyzed,
            likes_analyzed=metrics_res.likes_analyzed,
            comments_analyzed=metrics_res.comments_analyzed,
            engagement_eligible_videos=metrics_res.engagement_eligible_videos,
            average_views=metrics_res.average_views,
            median_views=metrics_res.median_views,
            average_likes=metrics_res.average_likes,
            median_likes=metrics_res.median_likes,
            average_comments=metrics_res.average_comments,
            median_comments=metrics_res.median_comments,
            engagement_rate=metrics_res.engagement_rate,
            shorts_ratio=metrics_res.shorts_ratio,
            last_video_date=metrics_res.last_video_date,
            metrics_calculated_at=metrics_res.metrics_calculated_at,
        )
        self.db.add(snap)

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    async def get_creator(self, creator_id: int) -> CreatorDetailResponse | None:
        """Fetch a creator with all related data."""
        result = await self.db.execute(
            select(Creator)
            .options(
                selectinload(Creator.platform_profiles),
                selectinload(Creator.social_links),
                selectinload(Creator.broker_associations),
                selectinload(Creator.creator_categories).selectinload(
                    CreatorCategory.category
                ),
            )
            .where(Creator.id == creator_id)
        )
        creator = result.scalar_one_or_none()
        if not creator:
            return None

        return self._to_detail_response(creator)

    async def list_creators(
        self, page: int = 1, page_size: int = 20
    ) -> SearchResponse:
        """List creators with pagination, sorted by score."""
        count_result = await self.db.execute(
            select(func.count(Creator.id))
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(Creator)
            .options(selectinload(Creator.platform_profiles))
            .order_by(Creator.influencer_score.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        creators = result.scalars().all()

        return SearchResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
            results=[self._to_summary_response(c) for c in creators],
        )

    async def search_creators(
        self, filters: SearchFilters
    ) -> SearchResponse:
        """Search creators with comprehensive filters."""
        query = select(Creator).options(
            selectinload(Creator.platform_profiles)
        )

        conditions = []

        if filters.q:
            conditions.append(
                or_(
                    Creator.name.ilike(f"%{filters.q}%"),
                    Creator.email.ilike(f"%{filters.q}%"),
                )
            )
        if filters.category:
            conditions.append(
                Creator.primary_category == filters.category
            )
        if filters.language:
            conditions.append(
                Creator.primary_language == filters.language
            )
        if filters.creator_type:
            conditions.append(
                Creator.creator_type == filters.creator_type
            )
        if filters.audience_bucket:
            conditions.append(
                Creator.audience_bucket == filters.audience_bucket
            )
        if filters.status:
            conditions.append(Creator.status == filters.status)
        if filters.min_score is not None:
            conditions.append(
                Creator.influencer_score >= filters.min_score
            )
        if filters.needs_review is not None:
            conditions.append(
                Creator.needs_review == filters.needs_review
            )
        if filters.has_email is not None:
            if filters.has_email:
                conditions.append(Creator.email.isnot(None))
            else:
                conditions.append(Creator.email.is_(None))
        if filters.has_phone is not None:
            if filters.has_phone:
                conditions.append(Creator.phone.isnot(None))
            else:
                conditions.append(Creator.phone.is_(None))
        if filters.verified is not None:
            # Check against platform profiles
            query = query.join(Creator.platform_profiles)
            conditions.append(
                PlatformProfile.verified == filters.verified
            )
        if filters.platform:
            if PlatformProfile not in [
                m.entity for m in query.column_descriptions
            ]:
                query = query.join(Creator.platform_profiles)
            conditions.append(
                PlatformProfile.platform == filters.platform
            )
        if filters.min_followers is not None:
            if PlatformProfile not in [
                m.entity for m in query.column_descriptions
            ]:
                query = query.join(Creator.platform_profiles)
            conditions.append(
                PlatformProfile.followers >= filters.min_followers
            )
        if filters.max_followers is not None:
            if PlatformProfile not in [
                m.entity for m in query.column_descriptions
            ]:
                query = query.join(Creator.platform_profiles)
            conditions.append(
                PlatformProfile.followers <= filters.max_followers
            )
        if filters.broker:
            query = query.join(Creator.broker_associations)
            conditions.append(
                BrokerAssociation.broker_name == filters.broker
            )

        if conditions:
            query = query.where(and_(*conditions))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Sort
        sort_col = getattr(
            Creator, filters.sort_by, Creator.influencer_score
        )
        if filters.sort_order == "asc":
            query = query.order_by(sort_col.asc().nullslast())
        else:
            query = query.order_by(sort_col.desc().nullslast())

        # Paginate
        query = query.offset(
            (filters.page - 1) * filters.page_size
        ).limit(filters.page_size)

        result = await self.db.execute(query)
        creators = result.scalars().unique().all()

        return SearchResponse(
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
            results=[self._to_summary_response(c) for c in creators],
        )

    async def update_creator(
        self, creator_id: int, updates: dict[str, Any]
    ) -> bool:
        """Update creator fields."""
        result = await self.db.execute(
            select(Creator).where(Creator.id == creator_id)
        )
        creator = result.scalar_one_or_none()
        if not creator:
            return False

        for key, value in updates.items():
            if hasattr(creator, key) and value is not None:
                setattr(creator, key, value)

        return True

    async def delete_creator(self, creator_id: int) -> bool:
        """Soft delete (set status to INACTIVE)."""
        result = await self.db.execute(
            select(Creator).where(Creator.id == creator_id)
        )
        creator = result.scalar_one_or_none()
        if not creator:
            return False
        creator.status = "INACTIVE"
        return True

    # ------------------------------------------------------------------
    # Review Operations
    # ------------------------------------------------------------------

    async def get_review_queue(
        self, page: int = 1, page_size: int = 20
    ) -> SearchResponse:
        """Get creators that need manual review."""
        filters = SearchFilters(
            needs_review=True, page=page, page_size=page_size
        )
        return await self.search_creators(filters)

    async def approve_review(
        self, creator_id: int, updates: dict[str, Any]
    ) -> bool:
        """Approve a reviewed creator with optional corrections."""
        updates["needs_review"] = False
        updates["review_reason"] = None
        # Mark detection method as manual for any updated fields
        if "creator_type" in updates:
            updates["creator_type_method"] = "manual"
        if "primary_language" in updates:
            updates["language_method"] = "manual"
        return await self.update_creator(creator_id, updates)

    # ------------------------------------------------------------------
    # Scrape Job Operations
    # ------------------------------------------------------------------

    async def create_scrape_job(
        self, job_type: str, keywords: list | None = None, depth: int = 1
    ) -> int:
        """Create a new scrape job and return its ID."""
        job = ScrapeJob(
            job_type=job_type,
            keywords=keywords,
            discovery_depth=depth,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()
        return job.id

    async def update_scrape_job(
        self, job_id: int, **kwargs
    ) -> None:
        """Update scrape job fields."""
        result = await self.db.execute(
            select(ScrapeJob).where(ScrapeJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)

    async def add_scrape_log(
        self,
        job_id: int,
        platform: str,
        action: str,
        status: str,
        keyword: str | None = None,
        api_units_used: int = 0,
        items_found: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Add a log entry to a scrape job."""
        log = ScrapeLog(
            scrape_job_id=job_id,
            platform=platform,
            keyword=keyword,
            action=action,
            status=status,
            api_units_used=api_units_used,
            items_found=items_found,
            error_message=error_message,
        )
        self.db.add(log)

    # ------------------------------------------------------------------
    # LLM Log Operations
    # ------------------------------------------------------------------

    async def log_llm_call(
        self,
        creator_id: int | None,
        task: str,
        model_used: str,
        input_text: str,
        raw_response: str,
        parsed_result: dict,
        reasoning: str | None = None,
        evidence: list | None = None,
        confidence: float | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
    ) -> None:
        """Log an LLM call for auditing."""
        log = LLMLog(
            creator_id=creator_id,
            task=task,
            model_used=model_used,
            input_text=input_text,
            raw_response=raw_response,
            parsed_result=parsed_result,
            reasoning=reasoning,
            evidence=evidence,
            confidence=confidence,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )
        self.db.add(log)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_summary_response(self, creator: Creator) -> CreatorSummaryResponse:
        """Convert a Creator ORM instance to a summary response."""
        platforms = [
            pp.platform for pp in (creator.platform_profiles or [])
        ]
        max_followers = max(
            (pp.followers or 0 for pp in (creator.platform_profiles or [])),
            default=None,
        )
        return CreatorSummaryResponse(
            id=creator.id,
            name=creator.name,
            email=creator.email,
            status=creator.status,
            audience_bucket=creator.audience_bucket,
            creator_type=creator.creator_type,
            primary_language=creator.primary_language,
            primary_category=creator.primary_category,
            influencer_score=creator.influencer_score,
            needs_review=creator.needs_review,
            platforms=platforms,
            followers=max_followers,
            created_at=creator.created_at,
        )

    def _to_detail_response(self, creator: Creator) -> CreatorDetailResponse:
        """Convert a Creator ORM instance to a full detail response."""
        return CreatorDetailResponse(
            id=creator.id,
            name=creator.name,
            email=creator.email,
            phone=creator.phone,
            website=creator.website,
            status=creator.status,
            audience_bucket=creator.audience_bucket,
            creator_type=creator.creator_type,
            creator_type_confidence=creator.creator_type_confidence,
            primary_language=creator.primary_language,
            language_confidence=creator.language_confidence,
            primary_category=creator.primary_category,
            influencer_score=creator.influencer_score,
            score_breakdown=creator.score_breakdown,
            needs_review=creator.needs_review,
            review_reason=creator.review_reason,
            last_enriched_at=creator.last_enriched_at,
            created_at=creator.created_at,
            updated_at=creator.updated_at,
            platform_profiles=[
                PlatformProfileResponse(
                    id=pp.id,
                    platform=pp.platform,
                    platform_user_id=pp.platform_user_id,
                    username=pp.username,
                    display_name=pp.display_name,
                    bio=pp.bio,
                    followers=pp.followers,
                    following=pp.following,
                    video_count=pp.video_count,
                    verified=pp.verified,
                    profile_url=pp.profile_url,
                    country=pp.country,
                    last_active_at=pp.last_active_at,
                )
                for pp in (creator.platform_profiles or [])
            ],
            social_links=[
                SocialLinkResponse(
                    platform=sl.platform,
                    url=sl.url,
                    value=sl.value,
                )
                for sl in (creator.social_links or [])
            ],
            broker_associations=[
                BrokerAssociationResponse(
                    broker_name=ba.broker_name,
                    relationship_type=(
                        ba.relationship_type.value
                        if ba.relationship_type
                        else None
                    ),
                    confidence=ba.confidence,
                    detection_method=(
                        ba.detection_method.value
                        if ba.detection_method
                        else None
                    ),
                    evidence=ba.evidence,
                )
                for ba in (creator.broker_associations or [])
            ],
            categories=[
                CategoryResponse(
                    name=cc.category.name if cc.category else "Unknown",
                    is_primary=cc.is_primary,
                    content_percentage=cc.content_percentage,
                    confidence=cc.confidence,
                )
                for cc in (creator.creator_categories or [])
            ],
        )
