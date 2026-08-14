"""Tests for the LLM text preprocessor."""

import pytest
from app.llm.preprocessor import TextPreprocessor
from app.schemas.creator import RawProfile


@pytest.fixture
def preprocessor():
    return TextPreprocessor()


class TestTextCleaning:
    def test_remove_urls(self, preprocessor):
        text = "Visit https://example.com for more info"
        result = preprocessor.remove_urls(text)
        assert "https://example.com" not in result
        assert "Visit" in result

    def test_remove_emojis(self, preprocessor):
        text = "Stock market 📈🚀 tips"
        result = preprocessor.remove_emojis(text)
        assert "📈" not in result
        assert "🚀" not in result
        assert "Stock market" in result
        assert "tips" in result

    def test_normalize_whitespace(self, preprocessor):
        text = "too   many    spaces   here"
        result = preprocessor.normalize_whitespace(text)
        assert "  " not in result

    def test_deduplicate_lines(self, preprocessor):
        text = "Line 1\nLine 2\nLine 1\nLine 3"
        result = preprocessor.deduplicate_lines(text)
        assert result.count("Line 1") == 1

    def test_full_clean(self, preprocessor):
        text = "🚀 Check https://bit.ly/abc 🔥🔥 for tips!! 🔥"
        result = preprocessor.clean(text)
        assert "https://" not in result
        assert "🚀" not in result

    def test_truncate(self, preprocessor):
        text = "a" * 3000
        result = preprocessor.truncate(text, max_chars=100)
        assert len(result) <= 103  # 100 + "..."


class TestLLMInputPreparation:
    def test_basic_profile(self, preprocessor):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test123",
            bio="Stock trader and educator",
            description="I teach options trading on YouTube",
            followers=50000,
            recent_video_titles=[
                "NIFTY Analysis Today",
                "Options Trading for Beginners",
            ],
        )
        result = preprocessor.prepare_llm_input(profile)
        assert "Bio:" in result
        assert "Description:" in result
        assert "Recent content:" in result
        assert "Platform: youtube" in result
        assert "Followers:" in result

    def test_deduplicates_similar_bio_description(self, preprocessor):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test123",
            bio="Stock market educator",
            description="Stock market educator and trader",
        )
        result = preprocessor.prepare_llm_input(profile)
        # Should not repeat very similar text
        assert result.count("Bio:") <= 1

    def test_deduplicates_similar_titles(self, preprocessor):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test123",
            recent_video_titles=[
                "NIFTY Analysis 12 Jan",
                "NIFTY Analysis 13 Jan",
                "NIFTY Analysis 14 Jan",
                "Options Trading Basics",
            ],
        )
        result = preprocessor.prepare_llm_input(profile)
        # Should deduplicate similar titles
        assert "Recent content:" in result

    def test_empty_profile(self, preprocessor):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test123",
        )
        result = preprocessor.prepare_llm_input(profile)
        assert "Platform: youtube" in result

    def test_max_length_respected(self, preprocessor):
        profile = RawProfile(
            platform="youtube",
            platform_user_id="test123",
            bio="x" * 5000,
            description="y" * 5000,
        )
        result = preprocessor.prepare_llm_input(profile)
        assert len(result) <= 2010  # 2000 + "..."
