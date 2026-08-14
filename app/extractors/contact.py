"""Regex-based contact and social link extraction.

No AI involved. Extracts from bio, description, about text, and linked
websites (Linktree, Beacons, Carrd) using regex and URL parsing.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config.settings import get_social_platforms_config
from app.schemas.creator import ContactInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Indian phone numbers: +91, 91, 0, or bare 10-digit
PHONE_PATTERN = re.compile(
    r"(?:\+91[\s\-]?|91[\s\-]?|0)?[6-9]\d{4}[\s\-]?\d{5}",
)

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)]+", re.IGNORECASE)


class ContactExtractor:
    """Extract contact information from text and URLs using regex."""

    def __init__(self) -> None:
        self._platforms_config = get_social_platforms_config()
        self._platform_patterns: dict[str, list[str]] = {}
        for platform in self._platforms_config.get("platforms", []):
            key = platform["key"]
            self._platform_patterns[key] = platform.get("url_patterns", [])

    def extract(
        self,
        bio: str = "",
        description: str = "",
        video_descriptions: list[str] | None = None,
        links: list[str] | None = None,
    ) -> ContactInfo:
        """Extract all contact info and social handles from bio, description, video descriptions, and links.

        Args:
            bio: Profile bio text.
            description: Channel/profile description.
            video_descriptions: Descriptions from the creator's recent videos (last 5 videos).
            links: Already-extracted URLs from the profile.

        Returns:
            ContactInfo with all detected contacts and social media handles.
        """
        video_desc_text = "\n".join(video_descriptions[:5]) if video_descriptions else ""
        combined_text = f"{bio}\n{description}\n{video_desc_text}".strip()
        all_links = list(links or [])

        # Extract all URLs from bio, description, and recent video descriptions
        found_urls = URL_PATTERN.findall(combined_text)
        for u in found_urls:
            clean_u = u.rstrip(".,;)\"'>")
            all_links.append(clean_u)

        # Deduplicate links
        all_links = list(dict.fromkeys(all_links))

        contacts = ContactInfo()

        # Extract emails
        contacts.emails = self._extract_emails(combined_text)

        # Extract phones
        contacts.phones = self._extract_phones(combined_text)

        # Classify links by platform
        for url in all_links:
            self._classify_link(url, contacts)

        # Scrape link aggregator pages for additional contacts
        aggregator_urls = (
            contacts.linktree + contacts.beacons + contacts.carrd
        )
        for agg_url in aggregator_urls:
            self._scrape_aggregator(agg_url, contacts)

        return contacts

    def _extract_emails(self, text: str) -> list[str]:
        """Extract unique email addresses from text."""
        emails = EMAIL_PATTERN.findall(text)
        # Filter out common false positives
        filtered = []
        skip_domains = {"example.com", "email.com", "gmail.con"}
        for email in emails:
            email_lower = email.lower()
            domain = email_lower.split("@")[1] if "@" in email_lower else ""
            if domain not in skip_domains and not email_lower.endswith(
                (".png", ".jpg", ".gif", ".svg")
            ):
                filtered.append(email_lower)
        return list(set(filtered))

    def _extract_phones(self, text: str) -> list[str]:
        """Extract unique Indian phone numbers from text."""
        raw_phones = PHONE_PATTERN.findall(text)
        normalized: set[str] = set()
        for phone in raw_phones:
            # Normalize: strip spaces, dashes, leading +91/91/0
            clean = re.sub(r"[\s\-]", "", phone)
            clean = re.sub(r"^(?:\+91|91|0)", "", clean)
            if len(clean) == 10 and clean[0] in "6789":
                normalized.add(f"+91{clean}")
        return list(normalized)

    def _classify_link(self, url: str, contacts: ContactInfo) -> None:
        """Classify a URL into the appropriate contact category."""
        url_lower = url.lower()
        try:
            parsed = urlparse(url_lower)
            netloc = (parsed.netloc or "").lstrip("www.")
            path = parsed.path or ""
            domain_path = f"{netloc}{path}"
        except Exception:
            netloc = ""
            domain_path = url_lower

        for key, patterns in self._platform_patterns.items():
            for pattern in patterns:
                p_lower = pattern.lower().rstrip("/")
                # Match only if the pattern is a domain prefix or exact domain/subdomain
                if (
                    domain_path.startswith(p_lower)
                    or f"://{p_lower}" in url_lower
                    or f"://www.{p_lower}" in url_lower
                    or (netloc and (netloc == p_lower or netloc.endswith(f".{p_lower}")))
                ):
                    target = getattr(contacts, key, None)
                    if target is not None and isinstance(target, list):
                        if url not in target:
                            target.append(url)
                        return

        # If no platform matched, treat as a generic website
        try:
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                # Skip social media domains we already handle
                known_domains = {
                    "youtube.com", "youtu.be", "instagram.com",
                    "twitter.com", "x.com", "facebook.com",
                    "linkedin.com", "t.me", "telegram.me",
                    "wa.me", "whatsapp.com", "discord.gg", "discord.com",
                    "linktr.ee", "beacons.ai",
                }
                domain = parsed.netloc.lower().lstrip("www.")
                if domain not in known_domains:
                    if url not in contacts.website:
                        contacts.website.append(url)
        except Exception:
            pass

    def _scrape_aggregator(
        self, url: str, contacts: ContactInfo
    ) -> None:
        """Scrape a link aggregator page (Linktree, Beacons, Carrd) for links and emails."""
        try:
            with httpx.Client(
                timeout=10, follow_redirects=True
            ) as client:
                response = client.get(url)
                if response.status_code != 200:
                    return

                soup = BeautifulSoup(response.text, "lxml")

                # Extract all href links
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if href.startswith(("http://", "https://")):
                        self._classify_link(href, contacts)

                # Extract emails from page text
                page_text = soup.get_text()
                page_emails = self._extract_emails(page_text)
                for email in page_emails:
                    if email not in contacts.emails:
                        contacts.emails.append(email)

                # Extract phone numbers from page text
                page_phones = self._extract_phones(page_text)
                for phone in page_phones:
                    if phone not in contacts.phones:
                        contacts.phones.append(phone)

        except Exception as e:
            logger.debug("Error scraping aggregator %s: %s", url, e)
