"""Cross-platform deduplication.

Merges creator profiles from YouTube and Instagram if they belong
to the same person, using email, phone, website, and cross-platform links.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Creator, PlatformProfile, SocialLink
from app.normalization.normalizer import Normalizer
from app.schemas.creator import ContactInfo, EnrichedProfile

logger = logging.getLogger(__name__)


class Deduplicator:
    """Cross-platform creator deduplication."""

    def __init__(self) -> None:
        self._normalizer = Normalizer()

    async def _creator_has_platform(
        self, db: AsyncSession, creator_id: int, platform: str
    ) -> bool:
        """Check if a creator already has a profile on the target platform."""
        result = await db.execute(
            select(PlatformProfile.id).where(
                PlatformProfile.creator_id == creator_id,
                PlatformProfile.platform == platform,
            )
        )
        return result.scalar_one_or_none() is not None

    async def find_duplicate(
        self,
        db: AsyncSession,
        enriched: EnrichedProfile,
    ) -> int | None:
        """Check if this profile matches an existing creator.

        Match strategies (in priority order):
        1. Email match → highest confidence
        2. Phone match → high confidence
        3. Website match → high confidence
        4. Cross-platform link match → high confidence
        5. Name + overlapping links → medium (flagged for review)

        Guard Rule: A creator cannot have multiple profiles on the SAME platform.
        If a candidate creator already has a profile on profile.platform, skip merge.

        Returns:
            Existing creator ID if match found, else None.
        """
        contacts = enriched.contacts
        profile = enriched.raw_profile

        # Strategy 1: Email match
        for email in contacts.emails:
            result = await db.execute(
                select(Creator.id).where(Creator.email == email.lower())
            )
            creator_id = result.scalar_one_or_none()
            if creator_id:
                if await self._creator_has_platform(db, creator_id, profile.platform):
                    logger.info(
                        "Dedup: email match '%s' -> creator %d, but creator already has a %s profile. Creating separate creator.",
                        email, creator_id, profile.platform
                    )
                    continue
                logger.info(
                    "Dedup: email match '%s' → creator %d", email, creator_id
                )
                return creator_id

        # Strategy 2: Phone match
        for phone in contacts.phones:
            result = await db.execute(
                select(SocialLink.creator_id).where(
                    SocialLink.platform == "phone",
                    SocialLink.value == phone,
                )
            )
            creator_id = result.scalar_one_or_none()
            if creator_id:
                if await self._creator_has_platform(db, creator_id, profile.platform):
                    logger.info(
                        "Dedup: phone match '%s' -> creator %d, but creator already has a %s profile. Creating separate creator.",
                        phone, creator_id, profile.platform
                    )
                    continue
                logger.info(
                    "Dedup: phone match '%s' → creator %d", phone, creator_id
                )
                return creator_id

        # Strategy 3: Website match
        for website in contacts.website:
            normalized = self._normalizer.normalize_url(website)
            result = await db.execute(
                select(SocialLink.creator_id).where(
                    SocialLink.platform == "website",
                    SocialLink.value == normalized,
                )
            )
            creator_id = result.scalar_one_or_none()
            if creator_id:
                if await self._creator_has_platform(db, creator_id, profile.platform):
                    logger.info(
                        "Dedup: website match '%s' -> creator %d, but creator already has a %s profile. Creating separate creator.",
                        website, creator_id, profile.platform
                    )
                    continue
                logger.info(
                    "Dedup: website match '%s' → creator %d",
                    website,
                    creator_id,
                )
                return creator_id

        # Strategy 4: Cross-platform link match
        # e.g., Instagram URL in YouTube bio, or YouTube URL in Instagram bio
        cross_platform_id = await self._check_cross_platform(
            db, profile, contacts
        )
        if cross_platform_id:
            if not await self._creator_has_platform(db, cross_platform_id, profile.platform):
                return cross_platform_id

        # Strategy 5: Name match (low confidence — flag for review)
        name = profile.display_name or profile.username
        if name and len(name) > 3:
            result = await db.execute(
                select(Creator).where(
                    Creator.name.ilike(f"%{name}%")
                )
            )
            potential_match = result.scalar_one_or_none()
            if potential_match:
                # Flag for manual review — don't auto-merge on name alone
                enriched.needs_review = True
                enriched.review_reason = (
                    f"Potential duplicate: name '{name}' matches "
                    f"creator {potential_match.id} ('{potential_match.name}'). "
                    "Verify manually."
                )
                logger.info(
                    "Dedup: possible name match '%s' → creator %d (flagged for review)",
                    name,
                    potential_match.id,
                )

        return None

    async def _check_cross_platform(
        self,
        db: AsyncSession,
        profile,
        contacts: ContactInfo,
    ) -> int | None:
        """Check if any link in the profile points to an existing platform profile."""
        all_links = list(profile.links or [])
        all_links.extend(contacts.website)

        for link in all_links:
            # Check if link is an Instagram URL → find matching Instagram profile
            if "instagram.com/" in link:
                username = self._extract_instagram_username(link)
                if username:
                    result = await db.execute(
                        select(PlatformProfile.creator_id).where(
                            PlatformProfile.platform == "instagram",
                            PlatformProfile.platform_user_id == username,
                        )
                    )
                    creator_id = result.scalar_one_or_none()
                    if creator_id:
                        logger.info(
                            "Dedup: cross-platform IG link → creator %d",
                            creator_id,
                        )
                        return creator_id

            # Check if link is a YouTube URL → find matching YouTube profile
            if "youtube.com/" in link or "youtu.be/" in link:
                channel_id = self._extract_youtube_channel_id(link)
                if channel_id:
                    result = await db.execute(
                        select(PlatformProfile.creator_id).where(
                            PlatformProfile.platform == "youtube",
                            PlatformProfile.platform_user_id == channel_id,
                        )
                    )
                    creator_id = result.scalar_one_or_none()
                    if creator_id:
                        logger.info(
                            "Dedup: cross-platform YT link → creator %d",
                            creator_id,
                        )
                        return creator_id

        return None

    @staticmethod
    def _extract_instagram_username(url: str) -> str | None:
        """Extract Instagram username from URL."""
        import re

        match = re.search(
            r"instagram\.com/([a-zA-Z0-9_.]+)", url, re.IGNORECASE
        )
        if match:
            username = match.group(1)
            if username not in ("p", "reel", "stories", "explore", "accounts"):
                return username
        return None

    @staticmethod
    def _extract_youtube_channel_id(url: str) -> str | None:
        """Extract YouTube channel ID from URL."""
        import re

        match = re.search(
            r"youtube\.com/channel/(UC[\w\-]+)", url, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    async def merge_profiles(
        self,
        db: AsyncSession,
        existing_creator_id: int,
        new_enriched: EnrichedProfile,
    ) -> None:
        """Merge a new profile into an existing creator.

        Updates the platform_profiles to point to the existing creator
        instead of creating a new one.
        """
        profile = new_enriched.raw_profile

        # Check if this platform profile already exists
        result = await db.execute(
            select(PlatformProfile).where(
                PlatformProfile.platform == profile.platform,
                PlatformProfile.platform_user_id == profile.platform_user_id,
            )
        )
        existing_pp = result.scalar_one_or_none()

        if existing_pp:
            # Update existing platform profile
            existing_pp.creator_id = existing_creator_id
            existing_pp.bio = profile.bio or existing_pp.bio
            existing_pp.followers = profile.followers or existing_pp.followers
        else:
            # Create new platform profile linked to existing creator
            pp = PlatformProfile(
                creator_id=existing_creator_id,
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
            )
            db.add(pp)

        logger.info(
            "Merged %s profile '%s' into creator %d",
            profile.platform,
            profile.platform_user_id,
            existing_creator_id,
        )
