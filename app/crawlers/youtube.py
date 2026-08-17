"""Recursive YouTube Data API v3 crawler.

Quota-optimized strategy:
  - search.list (100 units) used ONCE per keyword → extract channel IDs
  - channels.list (1 unit per 50 channels) for metadata
  - playlistItems.list (1 unit) for recent videos
  - Recursive expansion via featured channels, mentions, collaborations

Depth control via DISCOVERY_MAX_DEPTH setting.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config.settings import get_settings
from app.crawlers.base import BaseCrawler
from app.schemas.creator import RawProfile, VideoData

logger = logging.getLogger(__name__)

# Patterns for discovering related channels from video text
CHANNEL_URL_PATTERNS = [
    re.compile(r"youtube\.com/(?:channel/|c/|@)([\w\-]+)", re.IGNORECASE),
    re.compile(r"youtu\.be/([\w\-]+)", re.IGNORECASE),
]

MENTION_PATTERNS = [
    re.compile(r"@([\w.]+)", re.IGNORECASE),
]

COLLABORATION_PATTERNS = [
    re.compile(
        r"(?:ft\.?|feat\.?|featuring|with|×|x)\s+@?([\w\s]+?)(?:\s*[|\-–—]|\s*$)",
        re.IGNORECASE,
    ),
]

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)]+", re.IGNORECASE)


class QuotaExceededError(Exception):
    """Raised when all YouTube API keys have exhausted their daily quota."""
    pass


class YouTubeCrawler(BaseCrawler):
    """Recursive YouTube crawler with quota optimization."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._active_key_index = 0
        self._service = None
        self._discovered_ids: set[str] = set()
        self._quota_used: int = 0

    @property
    def platform_name(self) -> str:
        return "youtube"

    def _get_service(self):
        """Get or rebuild the YouTube API service with the current active key."""
        keys = self.settings.youtube_api_keys
        if not keys:
            raise ValueError("No YouTube API keys provided in YOUTUBE_API_KEY")
            
        if self._active_key_index >= len(keys):
            raise ValueError(f"Exhausted all {len(keys)} YouTube API keys.")
            
        active_key = keys[self._active_key_index]
        
        if self._service is None:
            self._service = build(
                "youtube",
                "v3",
                developerKey=active_key,
            )
        return self._service

    async def _execute_with_rotation(self, request_func, **kwargs):
        """Execute an API request, automatically rotating keys on 429/403 Quota Exceeded."""
        keys = self.settings.youtube_api_keys
        if not keys:
            raise ValueError("No YouTube API keys available.")

        while self._active_key_index < len(keys):
            service = self._get_service()
            try:
                # request_func is a callable like lambda svc: svc.search().list(...)
                request = request_func(service, **kwargs)
                return await asyncio.to_thread(request.execute)
            except HttpError as e:
                err_msg = str(e).lower()
                if "quotaexceeded" in err_msg or e.resp.status in (403, 429):
                    logger.warning("YouTube quota exceeded for key index %d! Swapping to next key...", self._active_key_index)
                    self._active_key_index += 1
                    self._service = None # Force rebuild
                    if self._active_key_index >= len(keys):
                        logger.error("All YouTube API keys have been exhausted!")
                        raise QuotaExceededError(f"Exhausted all {len(keys)} YouTube API keys.")
                    continue
                else:
                    raise
        raise QuotaExceededError(f"Exhausted all {len(keys)} YouTube API keys.")

    def _track_quota(self, units: int, action: str) -> None:
        """Track API quota usage."""
        self._quota_used += units
        logger.info(
            "YouTube API: %s — %d units (total: %d)",
            action,
            units,
            self._quota_used,
        )

    async def discover(
        self,
        keywords: list[dict[str, str]],
        max_depth: int = 3,
    ) -> tuple[list[RawProfile], dict]:
        """Recursive discovery pipeline.

        Phase 1: search.list (once per keyword) → video results → channel IDs
        Phase 2: channels.list batch (1 unit / 50 channels)
        Phase 3: Fetch recent videos → engagement data + mentions
        Phase 4: Recursive expansion → featured, collaborations, mentions
        """
        self._discovered_ids = set()
        all_profiles: list[RawProfile] = []

        import json
        import os
        STATE_FILE = "youtube_resume_state.json"
        remaining_keywords: list[dict[str, str]] = []
        
        if os.path.exists(STATE_FILE):
            logger.info("Found existing %s, loading state to resume...", STATE_FILE)
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    seed_channel_ids = set(state.get("channels_to_process", []))
                    keyword_metrics = state.get("keyword_metrics", {})
                    channel_discovery_map = state.get("channel_discovery_map", {})
                    remaining_keywords = state.get("remaining_keywords", [])
                os.remove(STATE_FILE)
                logger.info("Resuming with %d pending channels and %d remaining keywords", len(seed_channel_ids), len(remaining_keywords))
            except Exception as e:
                logger.error("Failed to load resume state: %s. Starting fresh.", e)
                remaining_keywords = list(keywords)
                seed_channel_ids = set()
                keyword_metrics = {}
                channel_discovery_map = {}
        else:
            remaining_keywords = list(keywords)
            seed_channel_ids = set()
            keyword_metrics = {}
            channel_discovery_map = {}

        # Phase 1: Search remaining keywords if any
        if remaining_keywords:
            try:
                new_cids, new_metrics, new_map, remaining_keywords = await self._search_keywords(remaining_keywords)
                seed_channel_ids.update(new_cids)
                keyword_metrics.update(new_metrics)
                channel_discovery_map.update(new_map)
                logger.info(
                    "Phase 1 update: %d seed channels found (%d keywords left)",
                    len(seed_channel_ids),
                    len(remaining_keywords),
                )
            except QuotaExceededError:
                logger.warning("Quota exceeded during keyword search phase.")

        # Recursive expansion
        channels_to_process = list(seed_channel_ids)
        
        try:
            for depth in range(max_depth):
                if not channels_to_process:
                    break

                logger.info(
                    "Depth %d: processing %d channels",
                    depth,
                    len(channels_to_process),
                )

                # Phase 2: Batch fetch channel metadata
                # Note: We do NOT catch QuotaExceededError inside _batch_fetch_channels, 
                # we let it bubble up so we can save channels_to_process.
                profiles = await self._batch_fetch_channels(
                    channels_to_process, 
                    channel_discovery_map=channel_discovery_map if depth == 0 else None
                )

                # Phase 3 & 4: Fetch videos and discover new channels
                new_channel_ids: set[str] = set()
                
                # To accurately track progress, we only remove a channel from channels_to_process
                # AFTER we successfully process its videos.
                pending_channels_for_this_depth = set(channels_to_process)
                
                for profile in profiles:
                    videos = await self.fetch_content(
                        profile.platform_user_id, max_items=15
                    )
                    # Store video titles and descriptions for LLM classification, broker detection, and contact extraction
                    profile.recent_video_titles = [
                        v.title for v in videos if v.title
                    ]
                    profile.recent_video_descriptions = [
                        v.description for v in videos[:5] if v.description
                    ]
                    profile.recent_video_ids = [v.video_id for v in videos]
                    if not isinstance(profile.raw_data, dict):
                        profile.raw_data = {}
                    profile.raw_data["videos"] = [
                        v.raw_payload if (hasattr(v, "raw_payload") and v.raw_payload)
                        else (v.model_dump() if hasattr(v, "model_dump") else getattr(v, "__dict__", {}))
                        for v in videos
                    ]

                    # Extract mentioned channels and URLs from video text (last 5 videos)
                    for video in videos[:5]:
                        v_text = (video.title or "") + " " + (video.description or "")
                        mentions = self._extract_channel_mentions(v_text)
                        new_channel_ids.update(mentions)

                        if video.description:
                            found_links = URL_PATTERN.findall(video.description)
                            for link in found_links:
                                clean_link = link.rstrip(".,;)\"'>")
                                if clean_link not in profile.links:
                                    profile.links.append(clean_link)

                    # Get featured channels
                    featured = self._extract_featured_channels(profile.raw_data)
                    new_channel_ids.update(featured)
                    
                    # Successfully processed this profile, safe to append and remove from pending
                    all_profiles.append(profile)
                    self._discovered_ids.add(profile.platform_user_id)
                    pending_channels_for_this_depth.discard(profile.platform_user_id)

                # Filter to only truly new channels for the next depth
                channels_to_process = list(
                    new_channel_ids - self._discovered_ids
                )
                logger.info(
                    "Depth %d: discovered %d new channels",
                    depth,
                    len(channels_to_process),
                )
                
        except (QuotaExceededError, Exception) as e:
            # We hit an error mid-loop. 
            # Calculate what we haven't processed yet.
            if 'pending_channels_for_this_depth' in locals():
                remaining = list(pending_channels_for_this_depth)
            else:
                remaining = channels_to_process
                
            logger.error("Error occurred mid-scrape! Saving %d remaining channels to %s", len(remaining), STATE_FILE)
            state = {
                "remaining_keywords": remaining_keywords,
                "channels_to_process": remaining,
                "keyword_metrics": keyword_metrics,
                "channel_discovery_map": channel_discovery_map
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
            logger.info("Gracefully returning %d successfully fetched profiles due to: %s", len(all_profiles), e)
            if not isinstance(e, QuotaExceededError):
                raise e

        logger.info(
            "Discovery complete: %d total profiles, %d quota units used",
            len(all_profiles),
            self._quota_used,
        )
        return all_profiles, keyword_metrics

    async def fetch_profile(self, profile_id: str) -> RawProfile | None:
        """Fetch a single channel profile with its last 5 video descriptions."""
        profiles = await self._batch_fetch_channels([profile_id])
        if not profiles:
            return None
        profile = profiles[0]
        videos = await self.fetch_content(profile.platform_user_id, max_items=5)
        profile.recent_video_titles = [v.title for v in videos if v.title]
        profile.recent_video_descriptions = [v.description for v in videos[:5] if v.description]
        profile.recent_video_ids = [v.video_id for v in videos]
        for video in videos[:5]:
            if video.description:
                for link in URL_PATTERN.findall(video.description):
                    clean_link = link.rstrip(".,;)\"'>")
                    if clean_link not in profile.links:
                        profile.links.append(clean_link)
        return profile

    async def fetch_content(
        self, profile_id: str, max_items: int = 20
    ) -> list[VideoData]:
        """Fetch recent videos via uploads playlist."""
        try:
            # Get uploads playlist ID
            response = await self._execute_with_rotation(
                lambda svc: svc.channels().list(part="contentDetails", id=profile_id)
            )
            self._track_quota(1, f"channels.list(contentDetails) for {profile_id}")

            items = response.get("items", [])
            if not items:
                return []

            uploads_playlist_id = (
                items[0]
                .get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads")
            )
            if not uploads_playlist_id:
                return []

            # Fetch playlist items
            playlist_response = await self._execute_with_rotation(
                lambda svc: svc.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=min(max_items, 50),
                )
            )
            self._track_quota(1, f"playlistItems.list for {profile_id}")

            video_ids = [
                item["contentDetails"]["videoId"]
                for item in playlist_response.get("items", [])
                if "contentDetails" in item
            ]

            if not video_ids:
                return []

            # Batch fetch video details (50 per call)
            return await self._batch_fetch_videos(video_ids)

        except HttpError as e:
            logger.error("Error fetching content for %s: %s", profile_id, e)
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _search_keywords(
        self, keywords: list[dict[str, str]]
    ) -> tuple[set[str], dict[str, dict], dict[str, list[dict]], list[dict[str, str]]]:
        """Phase 1: Search once per keyword, track metrics and build discovery map."""
        channel_ids: set[str] = set()
        keyword_metrics: dict[str, dict] = {}
        channel_discovery_map: dict[str, list[dict]] = {}
        remaining_keywords: list[dict[str, str]] = list(keywords)

        for kw_obj in keywords:
            term = kw_obj["term"]
            category = kw_obj["category"]
            
            keyword_metrics[term] = {
                "category": category,
                "results_found": 0,
                "new_creators": 0
            }

            try:
                term_found_cids = set()
                next_page_token = None
                max_pages = 3
                
                for _ in range(max_pages):
                    response = await self._execute_with_rotation(
                        lambda svc: svc.search().list(
                            part="snippet",
                            q=term,
                            type="video",
                            maxResults=50,
                            regionCode="IN",
                            relevanceLanguage="en",
                            pageToken=next_page_token
                        )
                    )
                    self._track_quota(100, f"search.list(q={term})")

                    items = response.get("items", [])
                    
                    # Count valid unique creators found in this specific search
                    for item in items:
                        cid = item["snippet"].get("channelId")
                        if cid:
                            term_found_cids.add(cid)
                            
                    next_page_token = response.get("nextPageToken")
                    if not next_page_token:
                        break
                        
                keyword_metrics[term]["results_found"] = len(term_found_cids)
                
                for cid in term_found_cids:
                    # Update discovery map
                    if cid not in channel_discovery_map:
                        channel_discovery_map[cid] = []
                    channel_discovery_map[cid].append({"term": term, "category": category})
                    
                    # Update new_creators metric (idempotent for this run)
                    if cid not in self._discovered_ids:
                        keyword_metrics[term]["new_creators"] += 1
                        self._discovered_ids.add(cid)
                        channel_ids.add(cid)

                remaining_keywords.remove(kw_obj)

            except QuotaExceededError:
                logger.error("Quota Exceeded while searching keyword '%s'. Stopping search phase.", term)
                break
            except Exception as e:
                logger.error("Search error for '%s': %s", term, e)
                remaining_keywords.remove(kw_obj)

            # Small delay between searches to be respectful
            await asyncio.sleep(0.5)

        return channel_ids, keyword_metrics, channel_discovery_map, remaining_keywords

    async def _batch_fetch_channels(
        self, channel_ids: list[str], channel_discovery_map: dict[str, list[dict]] = None
    ) -> list[RawProfile]:
        """Phase 2: Batch fetch channel metadata (50 per call = 1 unit)."""
        profiles: list[RawProfile] = []

        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]
            try:
                response = await self._execute_with_rotation(
                    lambda svc: svc.channels().list(
                        part="snippet,statistics,contentDetails,brandingSettings",
                        id=",".join(batch),
                    )
                )
                self._track_quota(1, f"channels.list(batch of {len(batch)})")

                for item in response.get("items", []):
                    profile = self._parse_channel(item)
                    if profile:
                        profiles.append(profile)
                        self._discovered_ids.add(profile.platform_user_id)

            except HttpError as e:
                logger.error("Error fetching channel batch: %s", e)

        return profiles

    async def _batch_fetch_videos(
        self, video_ids: list[str]
    ) -> list[VideoData]:
        """Batch fetch video details (50 per call = 1 unit)."""
        videos: list[VideoData] = []

        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            try:
                response = await self._execute_with_rotation(
                    lambda svc: svc.videos().list(
                        part="snippet,statistics,contentDetails",
                        id=",".join(batch),
                    )
                )
                self._track_quota(1, f"videos.list(batch of {len(batch)})")

                for item in response.get("items", []):
                    video = self._parse_video(item)
                    if video:
                        videos.append(video)

            except HttpError as e:
                logger.error("Error fetching video batch: %s", e)

        return videos

    def _parse_channel(self, item: dict[str, Any]) -> RawProfile | None:
        """Parse a channels.list response item into a RawProfile."""
        try:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            branding = item.get("brandingSettings", {})

            channel_id = item["id"]
            description = snippet.get("description", "")

            # Extract links from description
            links = re.findall(r"https?://[^\s<>\"]+", description)

            return RawProfile(
                platform="youtube",
                platform_user_id=channel_id,
                username=snippet.get("customUrl", ""),
                display_name=snippet.get("title", ""),
                bio=snippet.get("description", ""),
                description=description,
                followers=int(stats.get("subscriberCount", 0)),
                video_count=int(stats.get("videoCount", 0)),
                verified=False,  # YouTube API doesn't expose this directly
                profile_url=f"https://www.youtube.com/channel/{channel_id}",
                thumbnail_url=(
                    snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
                country=snippet.get("country", ""),
                links=links,
                raw_data=item,
            )
        except Exception as e:
            logger.error("Error parsing channel: %s", e)
            return None

    def _parse_video(self, item: dict[str, Any]) -> VideoData | None:
        """Parse a videos.list response item into VideoData."""
        try:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            duration = content.get("duration", "")

            # Detect shorts: duration under 60 seconds (PT1M or less)
            is_short = self._is_short_duration(duration)

            published_str = snippet.get("publishedAt", "")
            published_at = None
            if published_str:
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )

            views = int(stats["viewCount"]) if "viewCount" in stats and stats["viewCount"] is not None else None
            likes = int(stats["likeCount"]) if "likeCount" in stats and stats["likeCount"] is not None else None
            comments_count = int(stats["commentCount"]) if "commentCount" in stats and stats["commentCount"] is not None else None

            return VideoData(
                video_id=item["id"],
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                views=views,
                likes=likes,
                comments_count=comments_count,
                duration=duration,
                is_short=is_short,
                published_at=published_at,
                thumbnail_url=(
                    snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
                raw_payload=item,
            )
        except Exception as e:
            logger.error("Error parsing video: %s", e)
            return None

    @staticmethod
    def _is_short_duration(duration: str) -> bool:
        """Check if an ISO 8601 duration is under 60 seconds (a Short)."""
        if not duration:
            return False
        # PT30S, PT1M, PT1M30S, etc.
        match = re.match(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
        )
        if not match:
            return False
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds <= 60

    def _extract_channel_mentions(self, text: str) -> set[str]:
        """Extract channel IDs/handles from video title + description text."""
        mentions: set[str] = set()
        for pattern in CHANNEL_URL_PATTERNS:
            for match in pattern.finditer(text):
                mentions.add(match.group(1))
        return mentions

    def _extract_featured_channels(self, raw_data: dict) -> set[str]:
        """Extract featured channel IDs from branding settings."""
        featured: set[str] = set()
        try:
            branding = raw_data.get("brandingSettings", {})
            channel_settings = branding.get("channel", {})
            featured_ids = channel_settings.get("featuredChannelsUrls", [])
            featured.update(featured_ids)
        except Exception:
            pass
        return featured
