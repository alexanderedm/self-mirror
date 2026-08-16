#!/usr/bin/env python3
"""
SelfMirror API server — minimal standalone launcher.

Runs only the /api/mirror/* routes without the full OpenBiliClaw dependency tree.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Add src/ to path so 'import selfmirror' resolves correctly
_src = Path(__file__).parent / "src"
if not any(p.match(str(_src)) for p in map(Path, sys.path)):
    sys.path.insert(0, str(_src))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from selfmirror.self_mirror.router import router as _self_mirror_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Runtime context — minimal stub for SelfMirror server
# -------------------------------------------------------------------


class SimpleMemoryManager:
    """Minimal memory manager — stores events in memory for init-status queries."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def propagate_event(self, event: dict[str, Any]) -> None:
        self._events.append(event)


class SimpleConfig:
    """Minimal config object."""

    def __init__(self, tier: str = "standard") -> None:
        self.self_mirror_tier = tier


class SimpleSoulEngine:
    """Minimal soul engine — returns a static or generated profile."""

    def __init__(self) -> None:
        self._profile: Any = None  # holds OnionProfile or None

    async def get_profile(self) -> Any:
        if self._profile is None:
            from selfmirror.soul.profile import OnionProfile
            self._profile = OnionProfile.empty()
        return self._profile

    def set_profile(self, profile: Any) -> None:
        self._profile = profile


class RuntimeContext:
    """Minimal runtime context for SelfMirror API server."""

    def __init__(self) -> None:
        from selfmirror.llm.service import MockLLMService
        self.soul_engine = SimpleSoulEngine()
        self.memory_manager = SimpleMemoryManager()
        self.config = SimpleConfig()
        self.database = None  # No SQLite for now
        self.llm_service = MockLLMService()  # replaced in main() if key exists


def create_mirror_app(*, runtime_context: RuntimeContext | None = None) -> FastAPI:
    """Create the FastAPI app with SelfMirror routes."""
    app = FastAPI(title="SelfMirror · 對鏡問話", version="0.1.0")

    # Attach runtime context (or a fresh one)
    if runtime_context is None:
        runtime_context = RuntimeContext()
    app.state.runtime_context = runtime_context

    # Include SelfMirror API routes
    app.include_router(_self_mirror_router)

    # CORS for browser extension
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:*", "http://localhost:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "SelfMirror"}

    return app


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SelfMirror API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8400)
    args = parser.parse_args()

    # Try to set up LLM service with API key
    runtime_context = RuntimeContext()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            from selfmirror.llm.service import AnthropicLLMService
            runtime_context.llm_service = AnthropicLLMService(api_key=api_key)
            logger.info("Anthropic LLM service configured (model: claude-sonnet-4-20250514)")
        except Exception as exc:
            logger.warning("Failed to configure Anthropic LLM service: %s — using mock", exc)
            from selfmirror.llm.service import MockLLMService
            runtime_context.llm_service = MockLLMService()
    else:
        from selfmirror.llm.service import MockLLMService
        runtime_context.llm_service = MockLLMService()
        logger.info("No ANTHROPIC_API_KEY found — using mock LLM service")

    app = create_mirror_app(runtime_context=runtime_context)
    logger.info("Starting SelfMirror API on http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
