"""Minimal LLM abstractions for SelfMirror."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Simple LLM response object."""

    content: str
    raw: dict[str, Any] | None = None


class LLMService(ABC):
    """Abstract LLM service — minimal interface for SelfMirror dialogue."""

    @abstractmethod
    async def complete_socratic_dialogue(
        self,
        user_message: str,
        history: list[dict[str, str]],
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> LLMResponse:
        """Complete a socratic dialogue turn.

        Args:
            user_message: The user's latest message.
            history: List of {"role": "user"|"assistant", "content": str} turns.
            caller: Identifier of the calling code (e.g. "soul.mirror.free").
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            LLMResponse with the assistant's reply.
        """
        ...

    @abstractmethod
    async def complete_structured_task(
        self,
        system_instruction: str,
        user_input: str,
        caller: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> LLMResponse:
        """Run a structured (single-turn) task with system + user prompt.

        Args:
            system_instruction: System prompt.
            user_input: User input/prompt.
            caller: Identifier of the calling code.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            LLMResponse with the content.
        """
        ...
