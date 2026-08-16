"""Tests for selfmirror.self_mirror.models — Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from selfmirror.self_mirror.models import (
    GuidedStarterOut,
    InitScanResult,
    InitStatusOut,
    MirrorChatIn,
    MirrorChatOut,
    MirrorEventBatchIn,
    MirrorEventBatchIn as BatchIn,
    MirrorEventBatchResponse,
    MirrorEventIn,
    MirrorMode,
    PrivacyTier,
    ProfileSummaryOut,
)


class TestPrivacyTier:
    def test_off_value(self) -> None:
        assert PrivacyTier.OFF == "off"
        assert PrivacyTier.OFF.value == "off"

    def test_standard_value(self) -> None:
        assert PrivacyTier.STANDARD == "standard"

    def test_deep_value(self) -> None:
        assert PrivacyTier.DEEP == "deep"

    def test_from_string(self) -> None:
        assert PrivacyTier("off") is PrivacyTier.OFF
        assert PrivacyTier("deep") is PrivacyTier.DEEP
        assert PrivacyTier("standard") is PrivacyTier.STANDARD

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            PrivacyTier("unknown")


class TestMirrorMode:
    def test_free_value(self) -> None:
        assert MirrorMode.FREE == "free"

    def test_guided_value(self) -> None:
        assert MirrorMode.GUIDED == "guided"

    def test_from_string(self) -> None:
        assert MirrorMode("free") is MirrorMode.FREE
        assert MirrorMode("guided") is MirrorMode.GUIDED

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            MirrorMode("invalid")


class TestMirrorEventIn:
    def test_minimal_valid(self) -> None:
        event = MirrorEventIn(event_type="view")
        assert event.event_type == "view"
        assert event.url == ""
        assert event.title == ""
        assert event.context == ""
        assert event.duration_seconds == 0.0
        assert event.metadata == {}

    def test_full_valid(self) -> None:
        event = MirrorEventIn(
            event_type="search",
            url="https://www.google.com/search?q=test",
            title="Google Search",
            context="用戶搜尋了 test",
            duration_seconds=2.5,
            metadata={"source_platform": "web", "query": "test"},
        )
        assert event.event_type == "search"
        assert event.url == "https://www.google.com/search?q=test"
        assert event.duration_seconds == 2.5
        assert event.metadata["source_platform"] == "web"

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MirrorEventIn(event_type="view", duration_seconds=-1.0)

    def test_all_event_types_valid(self) -> None:
        for etype in ["view", "search", "click", "scroll", "hover", "favorite", "like", "dislike"]:
            event = MirrorEventIn(event_type=etype)
            assert event.event_type == etype


class TestMirrorEventBatchIn:
    def test_empty_batch(self) -> None:
        batch = MirrorEventBatchIn()
        assert batch.tier == PrivacyTier.STANDARD
        assert batch.events == []

    def test_with_events(self) -> None:
        events = [
            MirrorEventIn(event_type="view", url="https://example.com"),
            MirrorEventIn(event_type="search", title="test"),
        ]
        batch = MirrorEventBatchIn(tier=PrivacyTier.DEEP, events=events)
        assert batch.tier == PrivacyTier.DEEP
        assert len(batch.events) == 2

    def test_max_length(self) -> None:
        events = [MirrorEventIn(event_type="view") for _ in range(101)]
        with pytest.raises(ValidationError):
            MirrorEventBatchIn(events=events)

    def test_tier_defaults_to_standard(self) -> None:
        batch = MirrorEventBatchIn(events=[MirrorEventIn(event_type="click")])
        assert batch.tier == PrivacyTier.STANDARD


class TestMirrorEventBatchResponse:
    def test_response(self) -> None:
        resp = MirrorEventBatchResponse(received=5, stored=3)
        assert resp.received == 5
        assert resp.stored == 3


class TestMirrorChatIn:
    def test_minimal(self) -> None:
        msg = MirrorChatIn(message="我最近對很多事情都感到迷茫")
        assert msg.message == "我最近對很多事情都感到迷茫"
        assert msg.mode == MirrorMode.FREE

    def test_guided_mode(self) -> None:
        msg = MirrorChatIn(message="test", mode=MirrorMode.GUIDED)
        assert msg.mode == MirrorMode.GUIDED

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MirrorChatIn(message="")

    def test_too_long_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MirrorChatIn(message="x" * 5001)


class TestMirrorChatOut:
    def test_reply(self) -> None:
        out = MirrorChatOut(
            reply="我覺得你是一個善於思考的人",
            mode=MirrorMode.FREE,
        )
        assert "思考" in out.reply
        assert out.mode == MirrorMode.FREE
        assert out.portrait == ""  # defaults to empty


class TestGuidedStarterOut:
    def test_question(self) -> None:
        out = GuidedStarterOut(
            question="你最近有沒有什麼事情讓你特別在意？",
            based_on="最近瀏覽記錄顯示對個人成長話題的興趣",
        )
        assert "什麼" in out.question
        assert "瀏覽" in out.based_on


class TestProfileSummaryOut:
    def test_empty_profile(self) -> None:
        profile = ProfileSummaryOut(portrait="")
        assert profile.portrait == ""
        assert profile.core_traits == []
        assert profile.values == []
        assert profile.deep_needs == []
        assert profile.top_interests == []

    def test_full_profile(self) -> None:
        profile = ProfileSummaryOut(
            portrait="一個喜歡深度思考的工程師",
            core_traits=["內向", "理性", "追求意義"],
            values=["真誠", "成長"],
            deep_needs=["被理解", "創造價值"],
            top_interests=["AI", "哲學"],
            life_stage="職業轉型期",
            current_phase="探索新方向",
            updated_at="2026-01-01",
        )
        assert len(profile.core_traits) == 3
        assert profile.life_stage == "職業轉型期"


class TestInitScanResult:
    def test_no_sources(self) -> None:
        result = InitScanResult(sessions_found=0, sources=[], sources_missing=[])
        assert result.sessions_found == 0
        assert result.total_chars == 0

    def test_with_data(self) -> None:
        result = InitScanResult(
            sessions_found=5,
            sources=["Claude Code", "DSH"],
            sources_missing=["Cursor"],
            total_chars=15000,
        )
        assert result.sessions_found == 5
        assert len(result.sources) == 2
        assert "Claude Code" in result.sources


class TestInitStatusOut:
    def test_default(self) -> None:
        status = InitStatusOut()
        assert status.has_profile is False
        assert status.profile_age_days is None
        assert status.events_collected == 0

    def test_with_profile(self) -> None:
        status = InitStatusOut(has_profile=True, profile_age_days=3, events_collected=150)
        assert status.has_profile is True
        assert status.profile_age_days == 3
        assert status.events_collected == 150
