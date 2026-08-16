"""Mirror dialogue module — AI plays the user for self-reflection.

This module provides two dialogue modes:

1. Free Chat: The AI responds AS the user (mirrors the user's persona),
   allowing the user to ask "what would I think about X?"
2. Guided: The AI asks the user exploratory questions based on their
   profile, helping them reflect on their own patterns.

Both modes use the 5-layer onion portrait as the core identity context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openbiliclaw.llm.base import LLMResponse
    from openbiliclaw.llm.service import LLMService
    from openbiliclaw.soul.profile import OnionProfile

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Enums
# -------------------------------------------------------------------


class MirrorMode(StrEnum):
    """Dialogue mode."""

    FREE = "free"  # AI plays "the user"
    GUIDED = "guided"  # AI asks exploratory questions


# -------------------------------------------------------------------
# Prompt builders
# -------------------------------------------------------------------


def _build_mirror_system_prompt(profile: OnionProfile) -> str:
    """Build the system prompt for free-chat mirror mode.

    The AI is told to respond AS the user, using the portrait and
    profile data to embody the user's voice.
    """
    portrait = profile.personality_portrait or "（尚未建立畫像）"

    lines = [
        "你是用戶的真實鏡子。",
        "用戶會問你「我會怎麼想 / 我是什麼樣的人」，你要以用戶的身份回答。",
        "",
        "=== 用戶畫像 ===",
        portrait,
        "",
    ]

    if profile.core.core_traits:
        lines.append(f"核心特質：{', '.join(profile.core.core_traits)}")

    if profile.values_layer.values:
        lines.append(f"價值觀：{', '.join(profile.values_layer.values)}")

    if profile.core.deep_needs:
        lines.append(f"深層需求：{', '.join(profile.core.deep_needs)}")

    if profile.role.life_stage:
        lines.append(f"生活階段：{profile.role.life_stage}")

    if profile.role.current_phase:
        lines.append(f"當前狀態：{profile.role.current_phase}")

    if profile.recent_awareness:
        notes = "\n".join(f"- [{n.date}] {n.observation}" for n in profile.recent_awareness[-5:])
        lines.append(f"\n最近觀察：\n{notes}")

    lines.extend(
        [
            "",
            "=== 對話規則 ===",
            "1. 以「我」回答，不要說「你應該...」或「身為用戶...」",
            "2. 回答要真實、有溫度，可以輕微調侃",
            "3. 如果不確定，說「我不確定，但根據我的性格...」",
            "4. 不要迴避矛盾——人可以同時是多種特質的",
            "5. 永遠基於上面的畫像回答，不要凭空编造",
        ]
    )

    return "\n".join(lines)


def _build_guided_system_prompt(profile: OnionProfile) -> str:
    """Build the system prompt for guided mirror mode.

    The AI is a warm, insightful friend who asks exploratory questions
    based on the user's current profile state.
    """
    portrait = profile.personality_portrait or "（尚未建立畫像）"

    lines = [
        "你是用戶的老朋友，擅長透過提問幫助對方更了解自己。",
        "你的風格：溫暖、好奇、不評判、像朋友聊天。",
        "",
        "=== 現有用戶畫像 ===",
        portrait,
        "",
    ]

    if profile.core.core_traits:
        lines.append(f"核心特質：{', '.join(profile.core.core_traits)}")

    if profile.core.deep_needs:
        lines.append(f"深層需求：{', '.join(profile.core.deep_needs)}")

    if profile.values_layer.values:
        lines.append(f"價值觀：{', '.join(profile.values_layer.values)}")

    if profile.recent_awareness:
        lines.append(
            f"\n最近觀察到：[{profile.recent_awareness[-1].date}] "
            f"{profile.recent_awareness[-1].observation}"
        )

    if profile.active_insights:
        lines.append("\n現有洞察假設：")
        for insight in profile.active_insights[:3]:
            lines.append(f"- {insight.hypothesis}（置信度 {insight.confidence:.0%}）")

    lines.extend(
        [
            "",
            "=== 提問原則 ===",
            "1. 一次只問一個核心問題，不要一次問多個",
            "2. 問題要具體，不要問「你最近怎麼樣」這類空泛問題",
            "3. 問題要有深度，幫助用戶探索內在動機",
            "4. 根據用戶的回答自然跟進，順著興趣深入",
            "5. 如果用戶說的和他們的畫像矛盾，指出這個觀察（「你說的和你之前...」）",
            "6. 避免心理學術語，用日常語言",
            "7. 適時總結你聽到的，確認理解正確",
        ]
    )

    return "\n".join(lines)


# -------------------------------------------------------------------
# Conversation history
# -------------------------------------------------------------------


@dataclass
class MirrorTurn:
    """A single turn in the mirror dialogue."""

    role: str  # "user" | "mirror"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# -------------------------------------------------------------------
# Main class
# -------------------------------------------------------------------


@dataclass
class MirrorDialogue:
    """Mirror dialogue system with two modes.

    - FREE mode: AI plays "the user" — user asks "what would I think?"
    - GUIDED mode: AI asks exploratory questions — user reflects

    The profile is read fresh on each respond() call so the dialogue
    always uses the latest portrait.
    """

    mode: MirrorMode = MirrorMode.FREE
    history: list[MirrorTurn] = field(default_factory=list)
    max_history: int = 30  # Keep last 30 turns for context

    def _get_profile(self) -> OnionProfile | None:
        """Load the current profile. Override in subclass or inject."""

        # Lazy import to avoid circular
        try:
            # This would be injected in practice
            return None
        except Exception:
            return None

    async def respond(
        self,
        user_message: str,
        *,
        llm_service: LLMService,
        profile: OnionProfile,
    ) -> str:
        """Generate a mirror response to the user's message.

        Args:
            user_message: The user's input.
            llm_service: LLM service for generating responses.
            profile: Current onion profile for identity context.

        Returns:
            Mirror's response.
        """
        self.history.append(MirrorTurn(role="user", content=user_message))

        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        # Build conversation history for context
        history_messages = []
        for turn in self.history[:-1]:
            role = "assistant" if turn.role == "mirror" else "user"
            history_messages.append({"role": role, "content": turn.content})

        try:
            if self.mode == MirrorMode.FREE:
                response: LLMResponse = await llm_service.complete_socratic_dialogue(
                    user_message=user_message,
                    history=history_messages,
                    caller="soul.mirror.free",
                )
            else:
                response = await llm_service.complete_socratic_dialogue(
                    user_message=user_message,
                    history=history_messages,
                    caller="soul.mirror.guided",
                )

            reply = response.content

        except Exception as exc:
            logger.exception("Mirror dialogue failed: %s", exc)
            reply = "（鏡子出了點問題，請稍後再試。）"

        self.history.append(MirrorTurn(role="mirror", content=reply))
        return reply

    def switch_mode(self, mode: MirrorMode) -> None:
        """Switch dialogue mode (free <-> guided)."""
        self.mode = mode
        logger.info("Switched mirror dialogue mode to %s", mode.value)

    def reset_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        logger.debug("Mirror dialogue history reset")


# -------------------------------------------------------------------
# Guided mode question generator
# -------------------------------------------------------------------


GUIDED_STARTER_PROMPTS = [
    "你最近有沒有什麼事情讓你特別在意，但身邊沒人問你為什麼？",
    "根據你最近瀏覽的內容，你似乎對某些事情越來越感興趣——是什麼讓你開始關注這個？",
    "有沒有一個決定你一直在猶豫，背後真正的原因可能是什麼？",
    "你最近放棄了什麼事情？放棄的原因是外在的，還是其實是內在的什麼改變了？",
    "如果你要給曾經的自己一個建議，你會說什麼？這透露了你現在什麼樣的價值觀？",
]


def generate_guided_starter(
    llm_service: LLMService,
    profile: OnionProfile,
    *,
    history: list[MirrorTurn] | None = None,
) -> str:
    """Generate an opening question for guided mode based on profile state.

    If history is provided, generates a question that follows naturally
    from the previous exchange.
    """
    system_prompt = _build_guided_system_prompt(profile)

    if history:
        context = "\n".join(
            f"{'用戶' if t.role == 'user' else '我'}：{t.content}" for t in history[-6:]
        )
        user_prompt = f"根據以上對話，用一句話繼續深入問一個問題。\n\n{context}\n\n我的下一個問題："
    else:
        # No history — pick from starters or generate fresh
        context = "\n".join(GUIDED_STARTER_PROMPTS[:3])
        user_prompt = (
            "根據以下用戶畫像，用一句話問一個最有探索價值的問題。\n\n"
            f"{context}\n\n"
            "不要問「你最近怎麼樣」這類空泛問題。問一個具體的、有深度的問題。\n\n"
            "我的問題："
        )

    import asyncio

    async def _gen() -> str:
        response: LLMResponse = await llm_service.complete_structured_task(
            system_instruction=system_prompt,
            user_input=user_prompt,
            caller="soul.mirror.guided_starter",
            temperature=0.8,
            max_tokens=200,
        )
        return response.content.strip()

    # Run synchronously if not in async context
    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _gen())
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(_gen())
