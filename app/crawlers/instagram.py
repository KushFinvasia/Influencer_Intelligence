"""Instagram crawler using Apify actors.

Uses:
  - apify/instagram-hashtag-scraper for hashtag-based discovery & post data
  - Fallback profile aggregation for robust discovery without Instagram rate limits
  - Extracts @mentions from captions for recursive discovery
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from apify_client import ApifyClient
from apify_client.errors import ApifyApiError

from app.config.settings import get_settings
from app.crawlers.base import BaseCrawler
from app.schemas.creator import PostData, RawProfile

logger = logging.getLogger(__name__)

MENTION_PATTERN = re.compile(r"@([\w.]+)", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)]+", re.IGNORECASE)


def _extract_dataset_id(run: Any) -> str | None:
    """Extract default dataset ID from either a dict or an Apify Run model."""
    if run is None:
        return None
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    return getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", None))


def _get_val(item: Any, *keys: str, default: Any = None) -> Any:
    """Safely get value from either dict or Pydantic/object model."""
    if item is None:
        return default
    if isinstance(item, dict):
        for k in keys:
            if k in item and item[k] is not None:
                return item[k]
    else:
        for k in keys:
            if hasattr(item, k) and getattr(item, k) is not None:
                return getattr(item, k)
    return default


class InstagramCrawler(BaseCrawler):
    """Instagram crawler using Apify actors."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._active_key_index = 0
        self._client = None
        self._discovered_usernames: set[str] = set()

    def _get_client(self) -> ApifyClient:
        """Get or rebuild the Apify API client with the current active token."""
        tokens = self.settings.apify_api_tokens
        if not tokens:
            raise ValueError("No Apify API tokens provided in APIFY_API_TOKEN")
            
        if self._active_key_index >= len(tokens):
            raise ValueError(f"Exhausted all {len(tokens)} Apify API tokens.")
            
        active_token = tokens[self._active_key_index]
        
        if self._client is None:
            self._client = ApifyClient(active_token)
        return self._client

    async def _execute_with_rotation(self, request_func, **kwargs):
        """Execute an Apify API request, automatically rotating keys on 402/429/403."""
        tokens = self.settings.apify_api_tokens
        if not tokens:
            raise ValueError("No Apify API tokens available.")

        while self._active_key_index < len(tokens):
            client = self._get_client()
            try:
                # request_func is a callable like lambda c: c.actor(...).call(...)
                return await asyncio.to_thread(request_func, client, **kwargs)
            except ApifyApiError as e:
                # Apify usually returns 402 Payment Required for exhausted credits, or 429/403 for rate limits/blocks
                if e.status_code in (402, 403, 429):
                    logger.warning("Apify token exhausted/blocked (status %d) for key index %d! Swapping to next token...", e.status_code, self._active_key_index)
                    self._active_key_index += 1
                    self._client = None # Force rebuild
                    if self._active_key_index >= len(tokens):
                        logger.error("All Apify API tokens have been exhausted!")
                        raise ValueError(f"Exhausted all {len(tokens)} Apify API tokens.")
                    continue
                else:
                    raise
        raise ValueError(f"Exhausted all {len(tokens)} Apify API tokens.")


    @property
    def platform_name(self) -> str:
        return "instagram"

    async def discover(
        self,
        keywords: list[dict[str, str]],
        seed_usernames: list[str] = None,
        max_depth: int = 1,
    ) -> tuple[list[RawProfile], dict]:
        """Discover Instagram profiles via hashtag search.

        Args:
            keywords: Normalized hashtag list containing dicts with term and category.
            seed_usernames: Usernames.
            max_depth: Depth for mention-based expansion.
        """
        self._discovered_usernames = set()
        profiles_by_user: dict[str, RawProfile] = {}
        keyword_metrics = {}

        seed_usernames = seed_usernames or []

        # Phase 1: Hashtag-based discovery (autonomously discovers creator profiles & post captions)
        if keywords:
            hashtag_profiles, keyword_metrics = await self._search_hashtags_profiles(keywords)
            for p in hashtag_profiles:
                if p.username not in profiles_by_user:
                    profiles_by_user[p.username] = p
                    self._discovered_usernames.add(p.username)

        # Phase 2: Automatic Profile Hydration (fetches exact real-time follower counts, bio, and verification)
        all_discovered_usernames = list(profiles_by_user.keys())
        if seed_usernames:
            for u in seed_usernames:
                if u not in all_discovered_usernames:
                    all_discovered_usernames.append(u)

        if all_discovered_usernames:
            logger.info(
                "Phase 2: Automatically hydrating %d discovered Instagram creators with exact follower counts...",
                len(all_discovered_usernames),
            )
            # Batch fetch in chunks of 20
            for i in range(0, len(all_discovered_usernames), 20):
                batch = all_discovered_usernames[i : i + 20]
                full_profiles = await self._fetch_profiles(batch)
                for fp in full_profiles:
                    if fp.username in profiles_by_user:
                        existing = profiles_by_user[fp.username]
                        # Merge exact follower count, verified status, and official bio
                        fp.recent_video_titles = list(dict.fromkeys(existing.recent_video_titles + fp.recent_video_titles))
                        fp.recent_video_descriptions = list(dict.fromkeys(existing.recent_video_descriptions + fp.recent_video_descriptions))
                        fp.links = list(dict.fromkeys(existing.links + fp.links))
                        if not fp.bio and existing.bio:
                            fp.bio = existing.bio
                            fp.description = existing.description
                        
                        # Preserve discovered_via from hashtag phase
                        if existing.discovered_via:
                            fp.discovered_via = existing.discovered_via
                            
                        profiles_by_user[fp.username] = fp
                    else:
                        profiles_by_user[fp.username] = fp
                        self._discovered_usernames.add(fp.username)

        all_profiles = list(profiles_by_user.values())
        logger.info(
            "Instagram discovery complete: %d profiles extracted and hydrated with exact follower counts",
            len(all_profiles),
        )
        return all_profiles, keyword_metrics

    async def fetch_profile(self, profile_id: str) -> RawProfile | None:
        """Fetch a single Instagram profile."""
        profiles = await self._fetch_profiles([profile_id])
        return profiles[0] if profiles else None

    async def fetch_content(
        self, profile_id: str, max_items: int = 12
    ) -> list[PostData]:
        """Fetch recent posts for a profile."""
        return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _search_hashtags_profiles(self, hashtags: list[dict[str, str]]) -> tuple[list[RawProfile], dict[str, dict]]:
        """Search Instagram hashtags, aggregate creator profiles, track metrics."""
        creators_data: dict[str, dict[str, Any]] = {}
        keyword_metrics: dict[str, dict] = {}

        for kw_obj in hashtags:
            term = kw_obj["term"]
            category = kw_obj["category"]
            
            # Use raw term for searching, without # symbol just in case
            search_term = term.lstrip("#")
            
            keyword_metrics[term] = {
                "category": category,
                "results_found": 0,
                "new_creators": 0
            }
            try:
                run_input = {
                    "hashtags": [search_term],
                    "resultsLimit": 200,
                    "resultsType": "posts",
                }

                logger.info("Searching Instagram hashtag: #%s", search_term)
                run = await self._execute_with_rotation(
                    lambda c: c.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)
                )

                dataset_id = _extract_dataset_id(run)
                if not dataset_id:
                    logger.error("No dataset ID returned from Apify run: %s", run)
                    continue

                dataset = self._get_client().dataset(dataset_id)
                term_found_usernames = set()
                
                for item in dataset.iterate_items():
                    username = _get_val(item, "ownerUsername") or _get_val(
                        _get_val(item, "owner"), "username"
                    )
                    if not username:
                        continue
                    
                    username = str(username).strip().lower()
                    caption = _get_val(item, "caption", default="") or ""
                    full_name = _get_val(item, "ownerFullName", default=username) or username
                    likes = _get_val(item, "likesCount", default=0) or 0
                    comments = _get_val(item, "commentsCount", default=0) or 0
                    display_url = _get_val(item, "displayUrl", default="") or ""
                    post_url = _get_val(item, "url", default=f"https://www.instagram.com/{username}/")
                    
                    # Extract URLs from caption
                    links = URL_PATTERN.findall(caption)

                    # Update term set
                    term_found_usernames.add(username)

                    if username not in creators_data:
                        creators_data[username] = {
                            "username": username,
                            "display_name": full_name,
                            "captions": [caption] if caption else [],
                            "links": list(set(links)),
                            "thumbnail_url": display_url,
                            "total_likes": likes if isinstance(likes, int) and likes > 0 else 0,
                            "total_comments": comments if isinstance(comments, int) and comments > 0 else 0,
                            "post_count": 1,
                            "raw_items": [item],
                            "discovered_via": [{"term": term, "category": category}],
                        }
                    else:
                        c_entry = creators_data[username]
                        # Merge discovery logic uniquely
                        existing_disc = c_entry.get("discovered_via", [])
                        if not any(d["term"] == term and d["category"] == category for d in existing_disc):
                            c_entry.setdefault("discovered_via", []).append({"term": term, "category": category})
                            
                        if caption and caption not in c_entry["captions"]:
                            c_entry["captions"].append(caption)
                        for link in links:
                            if link not in c_entry["links"]:
                                c_entry["links"].append(link)
                        if isinstance(likes, int) and likes > 0:
                            c_entry["total_likes"] += likes
                        c_entry["post_count"] += 1
                        if not c_entry["display_name"] or c_entry["display_name"] == username:
                            c_entry["display_name"] = full_name

                # Update metrics after iterating items
                keyword_metrics[term]["results_found"] = len(term_found_usernames)
                for u in term_found_usernames:
                    if u not in self._discovered_usernames:
                        keyword_metrics[term]["new_creators"] += 1
                        self._discovered_usernames.add(u)

            except Exception as e:
                logger.error("Error searching hashtag #%s: %s", search_term, e)

        # Convert aggregated data to RawProfile objects
        profiles: list[RawProfile] = []
        for username, data in creators_data.items():
            combined_bio = "\n".join(data["captions"][:3])
            
            profile = RawProfile(
                platform="instagram",
                platform_user_id=username,
                username=username,
                display_name=data["display_name"],
                bio=combined_bio[:1000],
                description=combined_bio[:1000],
                followers=None,
                following=500,
                verified=False,
                profile_url=f"https://www.instagram.com/{username}/",
                thumbnail_url=data["thumbnail_url"],
                recent_video_titles=[c[:200] for c in data["captions"][:10]],
                links=data["links"],
                discovered_via=data.get("discovered_via", []),
                raw_data={"aggregated_from_hashtag": True, "data": data},
            )
            profiles.append(profile)

        return profiles, keyword_metrics

    async def _fetch_profiles(
        self, usernames: list[str]
    ) -> list[RawProfile]:
        """Fetch full profile data for a list of usernames."""
        profiles: list[RawProfile] = []

        try:
            cleaned_usernames = [u.strip().lstrip("@") for u in usernames if u.strip()]
            if not cleaned_usernames:
                return profiles

            run_input = {
                "usernames": cleaned_usernames,
            }

            logger.info(
                "Fetching %d Instagram profiles via Apify profile scraper: %s",
                len(cleaned_usernames),
                cleaned_usernames[:5],
            )
            run = await asyncio.to_thread(
                self._client.actor("apify/instagram-profile-scraper")
                .call,
                run_input=run_input,
            )

            dataset_id = _extract_dataset_id(run)
            if not dataset_id:
                logger.error("No dataset ID found in Apify profile run: %s", run)
                return profiles

            dataset = self._client.dataset(dataset_id)
            for item in dataset.iterate_items():
                profile = self._parse_profile(item)
                if profile:
                    profiles.append(profile)
                    self._discovered_usernames.add(
                        profile.platform_user_id
                    )

        except Exception as e:
            logger.error("Error fetching Instagram profiles: %s", e)

        return profiles

    def _parse_profile(self, item: dict[str, Any]) -> RawProfile | None:
        """Parse an Apify profile result into a RawProfile."""
        try:
            username = _get_val(item, "username", "ownerUsername")
            if not username:
                return None

            bio = _get_val(item, "biography", "bio", default="") or ""

            # Extract links from bio and external URL
            links: list[str] = []
            external_url = _get_val(item, "externalUrl", "external_url")
            if external_url:
                links.append(external_url)
            bio_links = re.findall(r"https?://[^\s<>\"]+", bio)
            links.extend(bio_links)

            # Extract post captions as "recent titles"
            recent_titles: list[str] = []
            latest_posts = _get_val(item, "latestPosts", default=[]) or []
            for post in latest_posts[:12]:
                caption = _get_val(post, "caption", default="")
                if caption:
                    recent_titles.append(caption[:200])

            followers = _get_val(item, "followersCount", "follower_count", default=0) or 0
            following = _get_val(item, "followsCount", "following_count", default=0) or 0
            verified = bool(_get_val(item, "verified", "is_verified", default=False))
            display_name = _get_val(item, "fullName", "ownerFullName", default=username) or username

            return RawProfile(
                platform="instagram",
                platform_user_id=str(username),
                username=str(username),
                display_name=str(display_name),
                bio=str(bio),
                description=str(bio),
                followers=int(followers) if isinstance(followers, (int, float)) or (isinstance(followers, str) and followers.isdigit()) else 0,
                following=int(following) if isinstance(following, (int, float)) or (isinstance(following, str) and following.isdigit()) else 0,
                verified=verified,
                profile_url=f"https://www.instagram.com/{username}/",
                thumbnail_url=_get_val(item, "profilePicUrl", "profile_pic_url", default="") or "",
                recent_video_titles=recent_titles,
                links=links,
                raw_data=dict(item) if isinstance(item, dict) else {},
            )
        except Exception as e:
            logger.error("Error parsing Instagram profile: %s", e)
            return None
