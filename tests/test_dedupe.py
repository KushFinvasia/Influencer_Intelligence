"""Tests for cross-platform deduplicator."""

import pytest
from app.dedupe.deduplicator import Deduplicator
from app.schemas.creator import ContactInfo, RawProfile, EnrichedProfile, CreatorStatusEnum


@pytest.fixture
def deduplicator():
    return Deduplicator()


class TestDeduplicationHelpers:
    def test_extract_instagram_username(self, deduplicator):
        assert deduplicator._extract_instagram_username("https://www.instagram.com/stock_guru_india/") == "stock_guru_india"
        assert deduplicator._extract_instagram_username("https://instagram.com/trader101?igshid=123") == "trader101"
        assert deduplicator._extract_instagram_username("https://instagram.com/p/Cxyz123") is None
        assert deduplicator._extract_instagram_username("https://instagram.com/reel/Cxyz123") is None
        assert deduplicator._extract_instagram_username("https://instagram.com/explore") is None

    def test_extract_youtube_channel_id(self, deduplicator):
        assert deduplicator._extract_youtube_channel_id("https://www.youtube.com/channel/UC1234567890abcdef") == "UC1234567890abcdef"
        assert deduplicator._extract_youtube_channel_id("https://youtube.com/watch?v=123") is None
