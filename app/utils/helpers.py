"""Shared utility functions."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truncate_string(text: str | None, max_length: int = 500) -> str:
    """Truncate a string to a maximum length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def creators_to_csv(creators: list[dict]) -> str:
    """Convert a list of creator dicts to CSV string."""
    if not creators:
        return ""

    output = io.StringIO()
    fieldnames = [
        "id", "name", "email", "phone", "website",
        "status", "audience_bucket", "creator_type",
        "primary_language", "primary_category",
        "influencer_score", "platforms", "followers",
    ]

    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore"
    )
    writer.writeheader()

    for creator in creators:
        row = {k: creator.get(k, "") for k in fieldnames}
        if isinstance(row.get("platforms"), list):
            row["platforms"] = ", ".join(row["platforms"])
        writer.writerow(row)

    return output.getvalue()
