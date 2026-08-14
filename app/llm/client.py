"""Unified LLM client with Groq primary and OpenRouter fallback.

All calls return structured JSON parsed into Pydantic models.
Every call is logged to the llm_logs table.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from groq import Groq
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client: Groq primary, OpenRouter fallback.

    All calls use structured JSON output (json_schema with Groq,
    json_object with OpenRouter).
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._groq_client: Groq | None = None
        self._openrouter_client: OpenAI | None = None

    @property
    def groq(self) -> Groq | None:
        """Lazy-init Groq client."""
        if self._groq_client is None and self.settings.groq_api_key:
            self._groq_client = Groq(api_key=self.settings.groq_api_key, max_retries=0)
        return self._groq_client

    @property
    def openrouter(self) -> OpenAI | None:
        """Lazy-init OpenRouter client (OpenAI-compatible)."""
        if (
            self._openrouter_client is None
            and self.settings.openrouter_api_key
        ):
            self._openrouter_client = OpenAI(
                api_key=self.settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        return self._openrouter_client

    async def classify(
        self,
        system_prompt: str,
        user_input: str,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send a classification request to the LLM.

        Tries Groq first, falls back to OpenRouter on failure.

        Args:
            system_prompt: System instruction for the model.
            user_input: Preprocessed text input.
            json_schema: Optional JSON schema for structured output.

        Returns:
            LLMResponse with parsed result, model used, and timing.
        """
        # Try Groq first
        if self.groq:
            try:
                return await self._call_groq(
                    system_prompt, user_input, json_schema
                )
            except Exception as e:
                logger.warning("Groq call failed, falling back to OpenRouter: %s", e)

        # Fallback to OpenRouter
        if self.openrouter:
            try:
                return await self._call_openrouter(
                    system_prompt, user_input
                )
            except Exception as e:
                logger.error("OpenRouter call also failed: %s", e)

        # Both failed
        return LLMResponse(
            success=False,
            parsed_result={},
            raw_response="Both Groq and OpenRouter failed",
            model_used="none",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
        )

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def _call_groq(
        self,
        system_prompt: str,
        user_input: str,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Call Groq API with structured JSON output."""
        start = time.monotonic()

        response_format: dict[str, Any] = {"type": "json_object"}
        if json_schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "classification",
                    "schema": json_schema,
                },
            }

        completion = self.groq.chat.completions.create(
            model=self.settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            response_format=response_format,
            temperature=0.1,
        )

        latency = int((time.monotonic() - start) * 1000)
        raw = completion.choices[0].message.content
        parsed = self._safe_parse_json(raw)

        return LLMResponse(
            success=True,
            parsed_result=parsed,
            raw_response=raw,
            model_used=self.settings.groq_model,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
            latency_ms=latency,
        )

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        retry=retry_if_exception_type(Exception),
    )
    async def _call_openrouter(
        self,
        system_prompt: str,
        user_input: str,
    ) -> LLMResponse:
        """Call OpenRouter API with JSON mode."""
        start = time.monotonic()

        completion = self.openrouter.chat.completions.create(
            model=self.settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        latency = int((time.monotonic() - start) * 1000)
        raw = completion.choices[0].message.content
        parsed = self._safe_parse_json(raw)

        return LLMResponse(
            success=True,
            parsed_result=parsed,
            raw_response=raw,
            model_used=self.settings.openrouter_model,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
            latency_ms=latency,
        )

    @staticmethod
    def _safe_parse_json(raw: str) -> dict[str, Any]:
        """Safely parse JSON from LLM output."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.error("Failed to parse LLM JSON output: %s", raw[:500])
            return {}


class LLMResponse:
    """Container for LLM call results."""

    def __init__(
        self,
        success: bool,
        parsed_result: dict[str, Any],
        raw_response: str,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ):
        self.success = success
        self.parsed_result = parsed_result
        self.raw_response = raw_response
        self.model_used = model_used
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
