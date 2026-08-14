"""Text preprocessor for cleaning profile data before LLM calls.

Removes URLs, emojis, special characters, deduplicates lines, and
truncates to reduce token usage by ~50%.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.schemas.creator import RawProfile

# Regex to match most emojis
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F780-\U0001F7FF"  # geometric shapes extended
    "\U0001F800-\U0001F8FF"  # supplemental arrows-C
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended-A
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "]+",
    flags=re.UNICODE,
)

URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"\s+")
SPECIAL_CHARS_PATTERN = re.compile(r"[★☆●◆▪▸►▶◇◆♦♣♠♥♡✦✧✨✩✪✫✬✭✮✯✰]")
HASHTAG_PATTERN = re.compile(r"#\w+")


class TextPreprocessor:
    """Clean and prepare text before sending to the LLM."""

    def clean(self, text: str) -> str:
        """Full cleaning pipeline for arbitrary text."""
        if not text:
            return ""
        text = self.remove_urls(text)
        text = self.remove_emojis(text)
        text = self.remove_special_chars(text)
        text = self.normalize_whitespace(text)
        text = self.deduplicate_lines(text)
        return text.strip()

    def prepare_llm_input(self, profile: RawProfile) -> str:
        """Combine and clean all text fields into a single LLM input.

        Produces a compact, structured input that saves tokens while
        retaining classification-relevant information.
        """
        parts: list[str] = []

        # Bio
        bio = self.clean(profile.bio or "")
        if bio:
            parts.append(f"Bio: {bio}")

        # Description (only if different from bio)
        description = self.clean(profile.description or "")
        if description and not self._is_similar(bio, description):
            parts.append(f"Description: {description}")

        # Recent content titles (deduplicated, top 10)
        if profile.recent_video_titles:
            unique_titles = self._deduplicate_titles(
                profile.recent_video_titles[:15]
            )
            titles_text = " | ".join(unique_titles[:10])
            parts.append(f"Recent content: {titles_text}")

        # Platform info
        parts.append(f"Platform: {profile.platform}")
        if profile.followers:
            parts.append(f"Followers: {profile.followers:,}")

        combined = "\n".join(parts)
        return self.truncate(combined, max_chars=2000)

    def remove_urls(self, text: str) -> str:
        """Remove all URLs from text."""
        return URL_PATTERN.sub("", text)

    def remove_emojis(self, text: str) -> str:
        """Remove emoji characters."""
        return EMOJI_PATTERN.sub("", text)

    def remove_special_chars(self, text: str) -> str:
        """Remove decorative special characters."""
        return SPECIAL_CHARS_PATTERN.sub("", text)

    def normalize_whitespace(self, text: str) -> str:
        """Collapse multiple whitespace into single spaces."""
        return WHITESPACE_PATTERN.sub(" ", text)

    def deduplicate_lines(self, text: str) -> str:
        """Remove duplicate lines from text."""
        seen: set[str] = set()
        unique_lines: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped and stripped.lower() not in seen:
                seen.add(stripped.lower())
                unique_lines.append(stripped)
        return "\n".join(unique_lines)

    def truncate(self, text: str, max_chars: int = 2000) -> str:
        """Truncate text to a maximum character count."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def _deduplicate_titles(self, titles: list[str]) -> list[str]:
        """Remove near-duplicate titles using fuzzy matching."""
        cleaned = [self.clean(t) for t in titles if t]
        unique: list[str] = []
        for title in cleaned:
            if not title:
                continue
            is_dup = False
            for existing in unique:
                if self._is_similar(title, existing, threshold=0.7):
                    is_dup = True
                    break
            if not is_dup:
                unique.append(title)
        return unique

    @staticmethod
    def _is_similar(
        text_a: str, text_b: str, threshold: float = 0.8
    ) -> bool:
        """Check if two strings are similar using SequenceMatcher."""
        if not text_a or not text_b:
            return False
        ratio = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
        return ratio >= threshold
