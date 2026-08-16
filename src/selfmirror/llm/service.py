"""Anthropic-based LLM service for SelfMirror.

Uses the anthropic Python SDK (ANTHROPIC_API_KEY) for Claude completions.
Falls back to a clear error if the key is not configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

from selfmirror.llm.base import LLMResponse, LLMService

logger = logging.getLogger(__name__)

# System prompt used when the AI plays the user's mirror
_MIRROR_FREE_SYSTEM = """你是一面心理鏡子。你的任務是假裝你就是來諮詢者本人，根據他們的畫像和內心世界，用他們的視角、語氣、價值觀來回應他們的問題。

請完全代入這個角色。不是安慰，不是建議，而是直接「成為」他們，說出他們內心可能會說的話。
保持真誠，不要說場面話。用他們可能會用的詞彙和節奏。"""


class AnthropicLLMService(LLMService):
    """LLM service backed by Anthropic's Claude API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it as an environment variable or pass api_key to AnthropicLLMService."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    async def complete_socratic_dialogue(
        self,
        user_message: str,
        history: list[dict[str, str]],
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> LLMResponse:
        """Build a conversation with system + history + latest user message."""
        messages: list[dict[str, Any]] = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = self._client.messages.create(
                model=self._model,
                system=_MIRROR_FREE_SYSTEM,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = "".join(block.text for block in response.content if hasattr(block, "text"))
            return LLMResponse(content=text.strip(), raw=response.model_dump())
        except Exception as exc:
            logger.exception("Anthropic API error in complete_socratic_dialogue: %s", exc)
            raise

    async def complete_structured_task(
        self,
        system_instruction: str,
        user_input: str,
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> LLMResponse:
        """Single-turn completion with a dedicated system prompt."""
        try:
            response = self._client.messages.create(
                model=self._model,
                system=system_instruction,
                messages=[{"role": "user", "content": user_input}],  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = "".join(block.text for block in response.content if hasattr(block, "text"))
            return LLMResponse(content=text.strip(), raw=response.model_dump())
        except Exception as exc:
            logger.exception("Anthropic API error in complete_structured_task: %s", exc)
            raise


class MockLLMService(LLMService):
    """In-memory mock LLM for testing and offline development."""

    def __init__(self, response: str = "（這是一個測試回覆。）"):
        self._response = response

    async def complete_socratic_dialogue(
        self,
        user_message: str,
        history: list[dict[str, str]],
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> LLMResponse:
        return LLMResponse(content=self._response)

    async def complete_structured_task(
        self,
        system_instruction: str,
        user_input: str,
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> LLMResponse:
        return LLMResponse(content=self._response)


def create_llm_service() -> LLMService:
    """Create the best available LLM service.

    Checks ANTHROPIC_API_KEY first, then falls back to MockLLMService.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        return AnthropicLLMService(api_key=api_key)
    logger.warning("No ANTHROPIC_API_KEY found — using mock LLM service.")
    return MockLLMService()
