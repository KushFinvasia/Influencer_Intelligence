"""Alias resolution and standardization.

Normalizes broker names, categories, languages, and creator types
using mappings from config files. Applied before database insertion.
"""

from __future__ import annotations

import logging
import re

from app.config.settings import (
    get_brokers_config,
    get_categories_config,
    get_creator_types_config,
    get_languages_config,
)
from app.schemas.creator import (
    BrokerInfo,
    CategoryResult,
    ClassificationResult,
    EnrichedProfile,
)

logger = logging.getLogger(__name__)


class Normalizer:
    """Normalize all classification outputs before database insertion."""

    def __init__(self) -> None:
        # Build alias lookup maps from config
        cat_config = get_categories_config()
        self._category_aliases: dict[str, str] = {
            k.lower(): v for k, v in cat_config.get("aliases", {}).items()
        }
        self._valid_categories: set[str] = set(
            cat_config.get("categories", [])
        )

        lang_config = get_languages_config()
        self._language_aliases: dict[str, str] = {
            k.lower(): v for k, v in lang_config.get("aliases", {}).items()
        }
        self._valid_languages: set[str] = set(
            lang_config.get("languages", [])
        )

        ct_config = get_creator_types_config()
        self._creator_type_aliases: dict[str, str] = {
            k.lower(): v for k, v in ct_config.get("aliases", {}).items()
        }
        self._valid_creator_types: set[str] = set(
            ct_config.get("creator_types", [])
        )

        broker_config = get_brokers_config()
        self._broker_alias_map: dict[str, str] = {}
        for broker in broker_config.get("brokers", []):
            canonical = broker["name"]
            for alias in broker.get("aliases", []):
                self._broker_alias_map[alias.lower()] = canonical

    def normalize(self, enriched: EnrichedProfile) -> EnrichedProfile:
        """Apply all normalizations to an enriched profile."""
        # Normalize brokers
        for broker in enriched.brokers:
            broker.broker_name = self.normalize_broker(broker.broker_name)

        # Normalize classification
        if enriched.classification:
            cls = enriched.classification

            if cls.primary_category:
                cls.primary_category = self.normalize_category(
                    cls.primary_category
                )
            for cat in cls.categories:
                cat.name = self.normalize_category(cat.name)

            if cls.primary_language:
                cls.primary_language = self.normalize_language(
                    cls.primary_language
                )

            if cls.creator_type:
                cls.creator_type = self.normalize_creator_type(
                    cls.creator_type
                )

        return enriched

    def normalize_broker(self, name: str) -> str:
        """Normalize a broker name to its canonical form."""
        if not name:
            return name
        lookup = name.lower().strip()
        return self._broker_alias_map.get(lookup, name)

    def normalize_category(self, name: str) -> str:
        """Normalize a category name to its canonical form."""
        if not name:
            return name
        lookup = name.lower().strip()
        # Check alias map first
        if lookup in self._category_aliases:
            return self._category_aliases[lookup]
        # Check if it's already a valid category (case-insensitive)
        for valid in self._valid_categories:
            if valid.lower() == lookup:
                return valid
        # Return as-is if no match
        return name

    def normalize_language(self, name: str) -> str:
        """Normalize a language name to its canonical form."""
        if not name:
            return name
        lookup = name.lower().strip()
        if lookup in self._language_aliases:
            return self._language_aliases[lookup]
        for valid in self._valid_languages:
            if valid.lower() == lookup:
                return valid
        return name

    def normalize_creator_type(self, name: str) -> str:
        """Normalize a creator type to its canonical form."""
        if not name:
            return name
        lookup = name.lower().strip()
        if lookup in self._creator_type_aliases:
            return self._creator_type_aliases[lookup]
        for valid in self._valid_creator_types:
            if valid.lower() == lookup:
                return valid
        return name

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize a URL for consistent comparison."""
        if not url:
            return url
        url = url.strip().rstrip("/")
        url = re.sub(r"^https?://(?:www\.)?", "", url, flags=re.IGNORECASE)
        return url.lower()
