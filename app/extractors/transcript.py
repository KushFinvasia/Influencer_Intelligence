"""Video transcript extractor using youtube-transcript-api.

Extracts official and auto-generated transcript tracks from YouTube videos
to directly determine spoken content language and extract spoken text.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# Map ISO language codes to canonical language names
YOUTUBE_LANGUAGE_MAP: dict[str, str] = {
    "hi": "Hindi",
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "bn": "Bengali",
    "or": "Odia",
    "od": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
}


@dataclass
class VideoTranscriptResult:
    """Result of transcript extraction for a single video."""

    video_id: str
    language: str
    language_code: str
    is_generated: bool
    confidence: float
    transcript_snippet: str | None = None
    total_segments: int = 0


@dataclass
class ChannelLanguageResult:
    """Aggregated language detection result across multiple videos."""

    primary_language: str
    confidence: float
    detection_method: str = "transcript"
    videos_analyzed: int = 0
    language_breakdown: dict[str, int] | None = None
    sample_transcript: str | None = None


class VideoTranscriptExtractor:
    """Extracts transcripts and detects spoken language from YouTube videos."""

    def __init__(self) -> None:
        self.api = YouTubeTranscriptApi()

    def detect_video_language(self, video_id: str) -> VideoTranscriptResult | None:
        """Detect the spoken language of a YouTube video via its transcript tracks."""
        if not video_id:
            return None

        try:
            transcript_list = self.api.list(video_id)
            if not transcript_list:
                return None

            # Priority 1: Check for manually uploaded captions
            manual_transcripts = [t for t in transcript_list if not t.is_generated]
            # Priority 2: Check for auto-generated captions
            auto_transcripts = [t for t in transcript_list if t.is_generated]

            selected_track = None
            if manual_transcripts:
                selected_track = manual_transcripts[0]
            elif auto_transcripts:
                selected_track = auto_transcripts[0]

            if not selected_track:
                return None

            raw_code = selected_track.language_code.split("-")[0].lower()
            canonical_lang = YOUTUBE_LANGUAGE_MAP.get(
                raw_code, selected_track.language or "English"
            )

            # High confidence for transcript detection
            confidence = 0.98 if not selected_track.is_generated else 0.95

            # Attempt to fetch a short sample snippet
            sample_snippet = None
            total_segments = 0
            try:
                fetched = selected_track.fetch()
                total_segments = len(fetched)
                if fetched:
                    sample_snippet = " ".join(
                        [item.text for item in fetched[:15]]
                    )
            except Exception as e:
                logger.debug("Could not fetch transcript segments for %s: %s", video_id, e)

            return VideoTranscriptResult(
                video_id=video_id,
                language=canonical_lang,
                language_code=raw_code,
                is_generated=selected_track.is_generated,
                confidence=confidence,
                transcript_snippet=sample_snippet,
                total_segments=total_segments,
            )

        except Exception as e:
            logger.debug("Transcript unavailable for video %s: %s", video_id, e)
            return None

    def detect_channel_language(
        self, video_ids: list[str], max_videos: int = 3
    ) -> ChannelLanguageResult | None:
        """Aggregate language detection across multiple recent channel videos."""
        if not video_ids:
            return None

        results: list[VideoTranscriptResult] = []
        sample_snippet: str | None = None

        for vid in video_ids[:max_videos]:
            res = self.detect_video_language(vid)
            if res:
                results.append(res)
                if not sample_snippet and res.transcript_snippet:
                    sample_snippet = res.transcript_snippet

        if not results:
            return None

        lang_counts = Counter(r.language for r in results)
        total = len(results)

        # Most common language
        most_common_lang, count = lang_counts.most_common(1)[0]
        ratio = count / total

        # If mixed languages across videos (e.g. 1 English and 1 Hindi)
        if len(lang_counts) > 1 and ratio < 0.67:
            primary_lang = "Mixed"
            confidence = 0.85
        else:
            primary_lang = most_common_lang
            confidence = 0.95 if ratio == 1.0 else 0.88

        return ChannelLanguageResult(
            primary_language=primary_lang,
            confidence=confidence,
            detection_method="transcript",
            videos_analyzed=total,
            language_breakdown=dict(lang_counts),
            sample_transcript=sample_snippet,
        )
