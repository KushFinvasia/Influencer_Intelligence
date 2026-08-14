"""Abstract base crawler interface.

All platform crawlers implement this interface, ensuring new platforms
(X, LinkedIn, Telegram) can be added without changing downstream modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.creator import RawProfile, VideoData, PostData


class BaseCrawler(ABC):
    """Base interface for all platform crawlers."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g. 'youtube', 'instagram')."""
        ...

    @abstractmethod
    async def discover(
        self,
        keywords: list[str],
        max_depth: int = 1,
    ) -> list[RawProfile]:
        """Discover creator profiles from seed keywords.

        Args:
            keywords: Seed search terms or hashtags.
            max_depth: How deep to recursively expand discovery.

        Returns:
            List of raw profiles discovered.
        """
        ...

    @abstractmethod
    async def fetch_profile(self, profile_id: str) -> RawProfile | None:
        """Fetch a single profile by platform-specific ID.

        Args:
            profile_id: Channel ID, username, etc.

        Returns:
            Raw profile or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_content(
        self, profile_id: str, max_items: int = 20
    ) -> list[VideoData] | list[PostData]:
        """Fetch recent content (videos/posts) for a profile.

        Args:
            profile_id: Platform-specific profile identifier.
            max_items: Maximum number of content items to fetch.

        Returns:
            List of video or post data.
        """
        ...
