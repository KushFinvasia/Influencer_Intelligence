"""Application configuration loaded from environment variables and JSON config files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings
from pydantic import Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent


class Settings(BaseSettings):
    """Central settings loaded from .env file."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/creator_intel",
        alias="DATABASE_URL",
    )

    # YouTube Data API v3
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")

    @property
    def youtube_api_keys(self) -> list[str]:
        """Return list of API keys parsed from comma-separated string."""
        if not self.youtube_api_key:
            return []
        return [k.strip() for k in self.youtube_api_key.split(",") if k.strip()]

    # Apify (Instagram)
    apify_api_token: str = Field(default="", alias="APIFY_API_TOKEN")

    @property
    def apify_api_tokens(self) -> list[str]:
        """Return list of Apify API tokens parsed from comma-separated string."""
        if not self.apify_api_token:
            return []
        return [k.strip() for k in self.apify_api_token.split(",") if k.strip()]

    # Groq (Primary LLM)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # OpenRouter (Fallback LLM)
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct", alias="OPENROUTER_MODEL"
    )

    # Queue
    queue_workers: int = Field(default=5, alias="QUEUE_WORKERS")

    # Discovery
    discovery_max_depth: int = Field(default=3, alias="DISCOVERY_MAX_DEPTH")
    enrichment_cache_days: int = Field(default=7, alias="ENRICHMENT_CACHE_DAYS")
    min_instagram_followers: int = Field(default=5000, alias="MIN_INSTAGRAM_FOLLOWERS")

    # Review
    review_confidence_threshold: float = Field(
        default=0.7, alias="REVIEW_CONFIDENCE_THRESHOLD"
    )

    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # SMTP Email
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    smtp_timeout: int = Field(default=10, alias="SMTP_TIMEOUT")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def _load_json(filename: str) -> dict[str, Any]:
    """Load a JSON config file from the config directory."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        logger.warning("Config file not found: %s", filepath)
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache()
def get_brokers_config() -> dict[str, Any]:
    """Load broker definitions with aliases, domains, and referral patterns."""
    return _load_json("brokers.json")


@lru_cache()
def get_categories_config() -> dict[str, Any]:
    """Load category definitions with aliases."""
    return _load_json("categories.json")


@lru_cache()
def get_languages_config() -> dict[str, Any]:
    """Load language definitions with aliases."""
    return _load_json("languages.json")


@lru_cache()
def get_creator_types_config() -> dict[str, Any]:
    """Load creator type definitions with aliases."""
    return _load_json("creator_types.json")


@lru_cache()
def get_social_platforms_config() -> dict[str, Any]:
    """Load social platform definitions with URL patterns."""
    return _load_json("social_platforms.json")


@lru_cache()
def get_regions_config() -> dict[str, Any]:
    """Load region/state definitions."""
    return _load_json("regions.json")


@lru_cache()
def get_keywords_config() -> dict[str, Any]:
    """Load seed keywords for YouTube and Instagram discovery."""
    return _load_json("keywords.json")


@lru_cache()
def get_scoring_weights_config() -> dict[str, Any]:
    """Load scoring weights and thresholds."""
    return _load_json("scoring_weights.json")


@lru_cache()
def get_exclusions_config() -> dict[str, Any]:
    """Load exclusion patterns and financial keywords for relevance gating."""
    return _load_json("exclusions.json")

