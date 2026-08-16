"""Tests for selfmirror.soul.mirror_dialogue — mirror dialogue logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from selfmirror.soul.mirror_dialogue import (
    GUIDED_STARTER_PROMPTS,
    MirrorDialogue,
    MirrorMode,
    MirrorTurn,
    _build_guided_system_prompt,
    _build_mirror_system_prompt,
    generate_guided_starter,
)


# -------------------------------------------------------------------
# Minimal OnionProfile mock (matches the real interface)
# -------------------------------------------------------------------


@dataclass
class _CoreLayer:
    core_traits: list[str] = field(default_factory=list)
    deep_needs: list[str] = field(default_factory=list)


@dataclass
class _RoleLayer:
    life_stage: str = ""
    current_phase: str = ""


@dataclass
class _RecentAwareness:
    date: str
    observation: str


@dataclass
class _ValuesLayer:
    values: list[str] = field(default_factory=list)


@dataclass
class _Insight:
    hypothesis: str
    confidence: float


@dataclass
class _OnionProfile:
    personality_portrait: str = ""
    core: _CoreLayer = field(default_factory=_CoreLayer)
    role: _RoleLayer = field(default_factory=_RoleLayer)
    values_layer: _ValuesLayer = field(default_factory=_ValuesLayer)
    recent_awareness: list = field(default_factory=list)
    active_insights: list = field(default_factory=list)


# -------------------------------------------------------------------
# Prompt builder tests
# -------------------------------------------------------------------


class TestBuildMirrorSystemPrompt:
    def get_profile(self, **kwargs) -> _OnionProfile:
        return _OnionProfile(**kwargs)

    def test_basic_prompt_contains_mirror_instruction(self) -> None:
        profile = self.get_profile(personality_portrait="一個安靜的思考者")
        prompt = _build_mirror_system_prompt(profile)
        assert "鏡子" in prompt
        assert "用戶" in prompt

    def test_includes_personality_portrait(self) -> None:
        profile = self.get_profile(personality_portrait="熱愛冒險的建築師")
        prompt = _build_mirror_system_prompt(profile)
        assert "建築師" in prompt

    def test_includes_core_traits(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            core=_CoreLayer(core_traits=["理性", "追求完美", "內斂"]),
        )
        prompt = _build_mirror_system_prompt(profile)
        assert "理性" in prompt
        assert "追求完美" in prompt

    def test_includes_deep_needs(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            core=_CoreLayer(deep_needs=["被認可", "創造"],
                            core_traits=[]),
        )
        prompt = _build_mirror_system_prompt(profile)
        assert "被認可" in prompt

    def test_includes_values(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            values_layer=_ValuesLayer(values=["真誠", "自由"]),
            core=_CoreLayer(),
        )
        prompt = _build_mirror_system_prompt(profile)
        assert "真誠" in prompt
        assert "自由" in prompt

    def test_includes_life_stage(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            role=_RoleLayer(life_stage="大學畢業初期"),
            core=_CoreLayer(),
        )
        prompt = _build_mirror_system_prompt(profile)
        assert "大學畢業初期" in prompt

    def test_empty_portrait_shows_placeholder(self) -> None:
        profile = self.get_profile(personality_portrait="")
        prompt = _build_mirror_system_prompt(profile)
        assert "尚未建立畫像" in prompt

    def test_recent_awareness_included(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            recent_awareness=[_RecentAwareness("2026-01-01", "開始對禪宗有興趣")],
            core=_CoreLayer(),
        )
        prompt = _build_mirror_system_prompt(profile)
        assert "禪宗" in prompt


class TestBuildGuidedSystemPrompt:
    def get_profile(self, **kwargs) -> _OnionProfile:
        return _OnionProfile(**kwargs)

    def test_friend_role(self) -> None:
        profile = self.get_profile(personality_portrait="一個安靜的工程師")
        prompt = _build_guided_system_prompt(profile)
        assert "老朋友" in prompt or "朋友" in prompt

    def test_includes_portrait(self) -> None:
        profile = self.get_profile(personality_portrait="喜歡深度思考的人")
        prompt = _build_guided_system_prompt(profile)
        assert "深度思考" in prompt

    def test_includes_deep_needs(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            core=_CoreLayer(deep_needs=["連結", "意義感"], core_traits=[]),
        )
        prompt = _build_guided_system_prompt(profile)
        assert "連結" in prompt

    def test_includes_active_insights(self) -> None:
        profile = self.get_profile(
            personality_portrait="Test",
            active_insights=[_Insight("可能對哲學有興趣", 0.7)],
            core=_CoreLayer(),
        )
        prompt = _build_guided_system_prompt(profile)
        assert "可能對哲學有興趣" in prompt
        assert "70%" in prompt

    def test_empty_portrait_shows_placeholder(self) -> None:
        profile = self.get_profile(personality_portrait="")
        prompt = _build_guided_system_prompt(profile)
        assert "尚未建立畫像" in prompt


# -------------------------------------------------------------------
# MirrorTurn tests
# -------------------------------------------------------------------


class TestMirrorTurn:
    def test_default_timestamp(self) -> None:
        turn = MirrorTurn(role="user", content="我最近很迷茫")
        assert turn.role == "user"
        assert turn.content == "我最近很迷茫"
        assert turn.timestamp != ""

    def test_explicit_timestamp(self) -> None:
        turn = MirrorTurn(role="mirror", content="你可能在尋找方向", timestamp="2026-01-01T00:00:00Z")
        assert turn.timestamp == "2026-01-01T00:00:00Z"


# -------------------------------------------------------------------
# MirrorDialogue tests
# -------------------------------------------------------------------


class TestMirrorDialogue:
    @pytest.fixture
    def profile(self) -> _OnionProfile:
        return _OnionProfile(
            personality_portrait="一個喜歡探索新事物的設計師",
            core=_CoreLayer(core_traits=["創意", "好奇心"], deep_needs=["表達"]),
            role=_RoleLayer(life_stage="職業中期"),
        )

    @pytest.fixture
    def llm_service(self) -> MagicMock:
        svc = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "我覺得你是一個充滿好奇心的人"
        svc.complete_socratic_dialogue = AsyncMock(return_value=mock_response)
        return svc

    @pytest.fixture
    def dialogue(self) -> MirrorDialogue:
        return MirrorDialogue()

    @pytest.mark.asyncio
    async def test_respond_adds_to_history(self, dialogue, profile, llm_service) -> None:
        reply = await dialogue.respond("我最近對很多事情都好奇", llm_service=llm_service, profile=profile)
        assert len(dialogue.history) == 2  # user turn + mirror turn
        assert dialogue.history[0].role == "user"
        assert dialogue.history[1].role == "mirror"

    @pytest.mark.asyncio
    async def test_respond_calls_llm(self, dialogue, profile, llm_service) -> None:
        await dialogue.respond("測試消息", llm_service=llm_service, profile=profile)
        llm_service.complete_socratic_dialogue.assert_called_once()

    @pytest.mark.asyncio
    async def test_respond_free_mode(self, dialogue, profile, llm_service) -> None:
        dialogue.mode = MirrorMode.FREE
        await dialogue.respond("test", llm_service=llm_service, profile=profile)
        call_kwargs = llm_service.complete_socratic_dialogue.call_args
        assert call_kwargs.kwargs["caller"] == "soul.mirror.free"

    @pytest.mark.asyncio
    async def test_respond_guided_mode(self, dialogue, profile, llm_service) -> None:
        dialogue.mode = MirrorMode.GUIDED
        await dialogue.respond("test", llm_service=llm_service, profile=profile)
        call_kwargs = llm_service.complete_socratic_dialogue.call_args
        assert call_kwargs.kwargs["caller"] == "soul.mirror.guided"

    @pytest.mark.asyncio
    async def test_respond_error_returns_fallback(self, dialogue, profile) -> None:
        svc = MagicMock()
        svc.complete_socratic_dialogue = AsyncMock(side_effect=Exception("LLM error"))
        reply = await dialogue.respond("test", llm_service=svc, profile=profile)
        assert "出了點問題" in reply
        assert dialogue.history[-1].content == reply

    @pytest.mark.asyncio
    async def test_history_truncated_at_max(self, dialogue, profile) -> None:
        dialogue.max_history = 3
        svc = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "回應"
        svc.complete_socratic_dialogue = AsyncMock(return_value=mock_response)

        for i in range(5):
            await dialogue.respond(f"消息{i}", llm_service=svc, profile=profile)

        assert len(dialogue.history) <= 6  # 5 user + 5 mirror, but truncated to 3*2

    def test_switch_mode(self, dialogue) -> None:
        assert dialogue.mode == MirrorMode.FREE
        dialogue.switch_mode(MirrorMode.GUIDED)
        assert dialogue.mode == MirrorMode.GUIDED

    def test_reset_history(self, dialogue) -> None:
        dialogue.history.append(MirrorTurn(role="user", content="test"))
        dialogue.history.append(MirrorTurn(role="mirror", content="reply"))
        dialogue.reset_history()
        assert dialogue.history == []

    def test_default_mode_is_free(self) -> None:
        d = MirrorDialogue()
        assert d.mode == MirrorMode.FREE


class TestGuidedStarterPrompts:
    def test_starter_prompts_not_empty(self) -> None:
        assert len(GUIDED_STARTER_PROMPTS) > 0

    def test_all_start_with_prompt(self) -> None:
        for p in GUIDED_STARTER_PROMPTS:
            assert "？" in p  # All are questions
