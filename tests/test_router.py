"""Tests for selfmirror.self_mirror.router — API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from selfmirror.self_mirror.models import (
    MirrorChatIn,
    MirrorEventBatchIn,
    MirrorEventIn,
    MirrorMode,
    PrivacyTier,
)
from selfmirror.self_mirror.router import router


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------


class FakeRuntimeContext:
    """Minimal RuntimeContext mock for router tests."""

    def __init__(self, *, has_profile: bool = False):
        self.soul_engine = MagicMock()
        self.memory_manager = MagicMock()
        self.llm_service = MagicMock()
        self.config = MagicMock()
        self.config.self_mirror_tier = "standard"
        # Profile mock — must have all attrs accessed by get_profile endpoint
        profile = MagicMock()
        profile.personality_portrait = "一個安靜的思考者"
        profile.core.core_traits = ["內斂", "理性"]
        profile.core.deep_needs = ["被理解"]
        profile.values_layer.values = ["真誠"]
        profile.role.life_stage = ""
        profile.role.current_phase = ""
        profile.recent_awareness = []
        profile.active_insights = []
        profile.interest.likes = []
        profile.updated_at = "2026-01-01T00:00:00Z"
        self.soul_engine.get_profile = AsyncMock(return_value=profile)
        self.soul_engine.has_profile = has_profile
        self.database = None


def make_app(ctx: FakeRuntimeContext | None = None) -> FastAPI:
    app = FastAPI()
    if ctx is not None:
        app.state.runtime_context = ctx
    app.include_router(router)
    return app


# -------------------------------------------------------------------
# Privacy endpoints
# -------------------------------------------------------------------


class TestPrivacyStatusEndpoint:
    def test_503_when_not_initialized(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/privacy-status")
        assert resp.status_code == 503
        assert "not initialized" in resp.json()["detail"]

    def test_returns_tier_info(self) -> None:
        ctx = FakeRuntimeContext()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/privacy-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "tier" in data

    def test_privacy_status_response_shape(self) -> None:
        ctx = FakeRuntimeContext()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/privacy-status")
        assert resp.status_code == 200
        data = resp.json()
        # Should have tier and description
        assert "tier" in data
        assert "description" in data


class TestPrivacyTierEndpoint:
    def test_post_sets_tier_off(self) -> None:
        # /privacy-tier takes tier as query param (Body defaults to query for primitives)
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/privacy-tier", params={"tier": "off"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "off"

    def test_post_sets_tier_deep(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/privacy-tier", params={"tier": "deep"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "deep"
        assert resp.json()["status"] == "ok"


# -------------------------------------------------------------------
# Event ingestion
# -------------------------------------------------------------------


class TestEventsEndpoint:
    def test_503_when_not_initialized(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        batch = MirrorEventBatchIn(
            tier=PrivacyTier.STANDARD,
            events=[MirrorEventIn(event_type="view", url="https://example.com")],
        )
        resp = client.post("/api/mirror/events", json=batch.model_dump())
        assert resp.status_code == 503

    def test_off_tier_returns_zero_stored(self) -> None:
        ctx = FakeRuntimeContext()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        batch = {
            "tier": "off",
            "events": [{"event_type": "view", "url": "https://example.com"}],
        }
        resp = client.post("/api/mirror/events", json=batch)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stored"] == 0
        assert data["received"] == 1

    def test_standard_tier_stores_events(self) -> None:
        ctx = FakeRuntimeContext()
        # Mock propagate_event to not raise
        ctx.memory_manager.propagate_event = MagicMock()

        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        batch = {
            "tier": "standard",
            "events": [{"event_type": "view", "url": "https://example.com", "title": "Example"}],
        }
        resp = client.post("/api/mirror/events", json=batch)
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] == 1

    def test_deep_tier_stores_events(self) -> None:
        ctx = FakeRuntimeContext()
        ctx.memory_manager.propagate_event = MagicMock()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        batch = {
            "tier": "deep",
            "events": [
                {
                    "event_type": "search",
                    "url": "https://google.com",
                    "title": "Search",
                    "context": "用戶搜尋",
                    "metadata": {"source_platform": "web"},
                }
            ],
        }
        resp = client.post("/api/mirror/events", json=batch)
        assert resp.status_code == 200

    def test_batch_without_events(self) -> None:
        ctx = FakeRuntimeContext()
        ctx.memory_manager.propagate_event = MagicMock()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        batch = {"tier": "standard", "events": []}
        resp = client.post("/api/mirror/events", json=batch)
        assert resp.status_code == 200
        assert resp.json()["received"] == 0


# -------------------------------------------------------------------
# Mirror dialogue
# -------------------------------------------------------------------


class TestMirrorChatEndpoint:
    def test_503_when_not_initialized(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/chat", json={"message": "test", "mode": "free"})
        assert resp.status_code == 503

    def test_chat_requires_message(self) -> None:
        ctx = FakeRuntimeContext()
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/chat", json={"mode": "free"})
        assert resp.status_code == 422  # Validation error

    def test_chat_free_mode_response_shape(self) -> None:
        ctx = FakeRuntimeContext()
        # Mock the LLM call
        mock_response = MagicMock()
        mock_response.content = "我覺得你是一個理性的人"

        async def fake_complete(user_message, history, caller, **kwargs):
            return mock_response

        ctx.llm_service.complete_socratic_dialogue = fake_complete

        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/chat", json={"message": "我是一個什麼樣的人？", "mode": "free"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["mode"] == "free"

    @pytest.mark.skip(reason="guided mode requires selfmirror.soul.dialogue (not yet implemented)")
    def test_chat_guided_mode_response_shape(self) -> None:
        ...  # Guided mode uses SocraticDialogue from selfmirror.soul.dialogue


# -------------------------------------------------------------------
# Profile endpoint
# -------------------------------------------------------------------


class TestProfileEndpoint:
    def test_503_when_not_initialized(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/profile")
        assert resp.status_code == 503

    def test_returns_profile_shape(self) -> None:
        ctx = FakeRuntimeContext(has_profile=True)
        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "portrait" in data
        assert "core_traits" in data


# -------------------------------------------------------------------
# Init endpoints
# -------------------------------------------------------------------


class TestInitScanEndpoint:
    def test_init_scan_no_ctx_needed(self) -> None:
        # init-scan does NOT require runtime context — it scans the filesystem directly
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/init-scan")
        # May succeed or return real filesystem scan results
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions_found" in data
        assert "sources" in data
        assert "sources_missing" in data
        assert "sources_missing" in data


class TestInitBuildEndpoint:
    def test_503_when_not_initialized(self) -> None:
        # init-build requires runtime context for llm_service
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mirror/init-build")
        assert resp.status_code == 503


# -------------------------------------------------------------------
# Guided starter endpoint
# -------------------------------------------------------------------


class TestGuidedStarterEndpoint:
    def test_503_when_not_initialized(self) -> None:
        app = make_app(ctx=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/guided-starter")
        assert resp.status_code == 503

    def test_returns_question_shape(self) -> None:
        ctx = FakeRuntimeContext()
        mock_response = MagicMock()
        mock_response.content = "你最近在探索什麼？"

        async def fake_complete(**kwargs):
            return mock_response

        ctx.llm_service.complete_structured_task = fake_complete

        app = make_app(ctx=ctx)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/mirror/guided-starter")
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
