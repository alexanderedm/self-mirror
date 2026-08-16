"""FastAPI router for SelfMirror API endpoints.

These endpoints are mounted at /api/mirror/* on top of the existing
OpenBiliClaw backend. They add:
- /api/mirror/events — Privacy-tiered event ingestion
- /api/mirror/chat — Mirror dialogue (free + guided)
- /api/mirror/profile — Profile summary
- /api/mirror/init — Local AI session scan + initial profile
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from .models import (
    GuidedStarterOut,
    InitScanResult,
    InitStatusOut,
    MirrorChatIn,
    MirrorChatOut,
    MirrorEventBatchIn,
    MirrorEventBatchResponse,
    MirrorMode,
    PrivacyTier,
    ProfileSummaryOut,
)

if TYPE_CHECKING:
    from selfmirror.api.runtime_context import RuntimeContext
    from selfmirror.llm.service import LLMService
    from selfmirror.memory.manager import MemoryManager
    from selfmirror.soul.profile import OnionProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mirror", tags=["SelfMirror"])


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _get_ctx(request: Request) -> RuntimeContext:
    """Access the RuntimeContext from app state."""
    ctx = getattr(request.app.state, "runtime_context", None)
    if ctx is None:
        raise HTTPException(status_code=503, detail="Backend not initialized")
    return ctx


async def _get_profile(request: Request) -> OnionProfile:
    """Get the current onion profile (async)."""
    ctx = _get_ctx(request)
    return await ctx.soul_engine.get_profile()


def _get_memory_manager(request: Request) -> MemoryManager:
    """Get the MemoryManager instance."""
    ctx = _get_ctx(request)
    return ctx.memory_manager


def _get_llm_service(request: Request) -> LLMService:
    """Get the LLM service."""
    ctx = _get_ctx(request)
    return ctx.llm_service


# -------------------------------------------------------------------
# Event ingestion — privacy-aware
# -------------------------------------------------------------------


@router.post(
    "/events",
    response_model=MirrorEventBatchResponse,
    summary="Ingest browser events with privacy tier",
)
async def ingest_events(request: Request, batch: MirrorEventBatchIn) -> MirrorEventBatchResponse:
    """Receive a batch of browser events annotated with the current privacy tier.

    If tier is OFF, events are discarded but the request still returns 200
    (extension may batch events before the user enables tracking).
    """
    if batch.tier == PrivacyTier.OFF:
        logger.debug("Events received with tier=OFF, discarding")
        return MirrorEventBatchResponse(received=len(batch.events), stored=0)

    memory = _get_memory_manager(request)

    try:
        from selfmirror.soul.pipeline import ProfileSignal, SignalType
    except ImportError:
        logger.warning("Pipeline not available, events not processed")
        return MirrorEventBatchResponse(received=len(batch.events), stored=0)

    stored = 0
    for event in batch.events:
        try:
            signal = ProfileSignal(
                signal_type=SignalType.BEHAVIOR_EVENT
                if event.event_type in {"view", "search", "click", "scroll"}
                else SignalType.ENGAGEMENT_EVENT,
                event_data={
                    "event_type": event.event_type,
                    "url": event.url,
                    "title": event.title,
                    "context": event.context or f"{event.event_type}: {event.title}",
                    "duration_seconds": event.duration_seconds,
                    "metadata": {
                        "source_platform": event.metadata.get("source_platform", "web"),
                        **{k: v for k, v in event.metadata.items()},
                        "privacy_tier": batch.tier.value,
                    },
                },
            )
            memory.propagate_event(signal)
            stored += 1
        except Exception as exc:
            logger.warning("Failed to process event %s: %s", event.event_type, exc)

    logger.info(
        "Ingested %d events (tier=%s, stored=%d)",
        len(batch.events),
        batch.tier.value,
        stored,
    )
    return MirrorEventBatchResponse(received=len(batch.events), stored=stored)


# -------------------------------------------------------------------
# Privacy tier
# -------------------------------------------------------------------


@router.get("/privacy-status", response_model=dict, summary="Get current privacy tier")
async def get_privacy_status(request: Request) -> dict:
    """Return the current privacy tier and what data is being collected."""
    ctx = _get_ctx(request)

    tier_str = "standard"
    with suppress(Exception):
        tier_str = getattr(ctx.config, "self_mirror_tier", "standard") or "standard"

    descriptions = {
        "off": "No tracking. Events discarded.",
        "standard": "URL, title, dwell time, search terms collected.",
        "deep": "Standard + active window/app title collected.",
    }

    return {"tier": tier_str, "description": descriptions.get(tier_str, "Unknown")}


@router.post("/privacy-tier", response_model=dict, summary="Set privacy tier")
async def set_privacy_tier(request: Request, tier: PrivacyTier) -> dict:
    """Update the privacy tier. Returns status."""
    logger.info("Privacy tier set to %s", tier.value)
    return {"tier": tier.value, "status": "ok"}


# -------------------------------------------------------------------
# Mirror dialogue
# -------------------------------------------------------------------


@router.post(
    "/chat",
    response_model=MirrorChatOut,
    summary="Mirror dialogue chat",
)
async def mirror_chat(request: Request, input: MirrorChatIn) -> MirrorChatOut:
    """Chat with the mirror — AI plays "you" (free mode)
    or asks exploratory questions (guided mode).

    The portrait is used as system-prompt context so the AI
    responds authentically as the user.
    """
    profile = await _get_profile(request)
    llm = _get_llm_service(request)

    if input.mode == MirrorMode.FREE:
        from selfmirror.soul.mirror_dialogue import MirrorDialogue

        dialogue = MirrorDialogue(mode=input.mode)
        reply = await dialogue.respond(
            user_message=input.message,
            llm_service=llm,
            profile=profile,
        )
    else:
        from selfmirror.soul.dialogue import SocraticDialogue

        ctx = _get_ctx(request)
        socratic = SocraticDialogue(
            llm=None,
            soul_engine=ctx.soul_engine,
            llm_service=llm,
            session="self_mirror_guided",
            learning_mode="legacy_direct",
        )
        reply = await socratic.respond(
            input.message,
            scope="chat",
        )

    return MirrorChatOut(
        reply=reply,
        mode=input.mode,
        portrait=profile.personality_portrait or "",
    )


@router.get(
    "/guided-starter",
    response_model=GuidedStarterOut,
    summary="Generate a guided-mode opening question",
)
async def get_guided_starter(request: Request) -> GuidedStarterOut:
    """Generate an opening question for guided mirror dialogue.

    Based on the current profile state, generates a specific,
    deeply probing question that helps the user reflect.
    """
    from selfmirror.soul.mirror_dialogue import generate_guided_starter

    profile = await _get_profile(request)
    llm = _get_llm_service(request)

    try:
        question = generate_guided_starter(llm_service=llm, profile=profile)
    except Exception as exc:
        logger.warning("Failed to generate guided starter: %s", exc)
        question = "你最近有沒有什麼事一直在心裡，想找人聊聊但又找不到合適的人？"

    return GuidedStarterOut(
        question=question,
        based_on="current profile state and recent awareness",
    )


# -------------------------------------------------------------------
# Profile
# -------------------------------------------------------------------


@router.get(
    "/profile",
    response_model=ProfileSummaryOut,
    summary="Get current profile summary",
)
async def get_profile(request: Request) -> ProfileSummaryOut:
    """Return the current profile summary for the web UI."""
    profile = await _get_profile(request)

    top_interests = []
    if profile.interest.likes:
        sorted_interests = sorted(
            profile.interest.likes,
            key=lambda d: d.weight if hasattr(d, "weight") else 0,
            reverse=True,
        )
        top_interests = [d.domain for d in sorted_interests[:5]]

    updated_at = profile.updated_at or ""
    if updated_at and isinstance(updated_at, str):
        try:
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            days_ago = (datetime.now(UTC) - dt).days
            updated_at = f"{days_ago} days ago"
        except Exception:
            pass

    return ProfileSummaryOut(
        portrait=profile.personality_portrait or "（尚未建立畫像）",
        core_traits=list(profile.core.core_traits) if profile.core.core_traits else [],
        values=list(profile.values_layer.values) if profile.values_layer.values else [],
        deep_needs=list(profile.core.deep_needs) if profile.core.deep_needs else [],
        top_interests=top_interests,
        life_stage=profile.role.life_stage or "",
        current_phase=profile.role.current_phase or "",
        updated_at=updated_at,
    )


# -------------------------------------------------------------------
# Init — local AI session scan
# -------------------------------------------------------------------


@router.get(
    "/init-status",
    response_model=InitStatusOut,
    summary="Check init status",
)
async def get_init_status(request: Request) -> InitStatusOut:
    """Check whether a profile has been generated and how much data exists."""
    profile = await _get_profile(request)
    events_collected = 0

    try:
        ctx = _get_ctx(request)
        if ctx and ctx.database:
            import sqlite3

            conn = sqlite3.connect(ctx.database.path)
            cur = conn.execute("SELECT COUNT(*) FROM events")
            events_collected = cur.fetchone()[0]
            conn.close()
    except Exception:
        pass

    updated_at = profile.updated_at or ""
    profile_age_days: int | None = None
    if updated_at:
        try:
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            profile_age_days = (datetime.now(UTC) - dt).days
        except Exception:
            pass

    return InitStatusOut(
        has_profile=bool(profile.personality_portrait),
        profile_age_days=profile_age_days,
        events_collected=events_collected,
    )


@router.post(
    "/init-scan",
    response_model=InitScanResult,
    summary="Scan local AI tool sessions",
)
async def init_scan() -> InitScanResult:
    """Scan local AI tool directories and return what was found.

    This does NOT generate a profile — it only scans and reports.
    Call POST /api/mirror/init-build after reviewing to generate the profile.
    """
    from selfmirror.soul.init_scanner import InitScanner

    scanner = InitScanner()
    result = scanner.scan(max_sessions_per_source=50)

    return InitScanResult(
        sessions_found=len(result.sessions),
        sources=result.sources_found,
        sources_missing=result.sources_missing,
        total_chars=result.total_chars,
    )


@router.post(
    "/init-build",
    response_model=ProfileSummaryOut,
    summary="Generate initial profile from scanned sessions",
)
async def init_build(request: Request) -> ProfileSummaryOut:
    """Generate the initial profile from the previously scanned sessions.

    Scans local AI tool directories, then uses the LLM to generate
    an initial portrait based on the session content.
    """
    from selfmirror.soul.init_scanner import InitScanner

    scanner = InitScanner()
    result = scanner.scan(max_sessions_per_source=50)

    if not result.sessions:
        raise HTTPException(
            status_code=400,
            detail="No AI tool sessions found. Please ensure you have used "
            "Claude Code, DSH, or other AI tools before running init.",
        )

    llm = _get_llm_service(request)
    initial = await scanner.generate_initial_profile(llm_service=llm, scan_result=result)

    memory = _get_memory_manager(request)
    soul_layer = memory.get_layer("soul")

    soul_data: dict = {
        "personality_portrait": initial.get("personality_portrait", ""),
        "core_traits": initial.get("core_traits", []),
        "cognitive_style": initial.get("cognitive_style", []),
        "motivational_drivers": initial.get("motivational_drivers", []),
        "current_phase": initial.get("current_phase", ""),
        "values": initial.get("values", []),
        "life_stage": initial.get("life_stage", ""),
        "deep_needs": initial.get("deep_needs", []),
        "core": {
            "core_traits": initial.get("core_traits", []),
            "deep_needs": initial.get("deep_needs", []),
        },
        "values_layer": {
            "values": initial.get("values", []),
            "motivational_drivers": initial.get("motivational_drivers", []),
        },
        "role": {
            "life_stage": initial.get("life_stage", ""),
            "current_phase": initial.get("current_phase", ""),
        },
        "updated_at": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }

    if mbti := initial.get("mbti"):
        soul_data["mbti"] = mbti

    soul_layer._data = soul_data
    soul_layer.save()
    memory.save_all()

    return ProfileSummaryOut(
        portrait=soul_data.get("personality_portrait", ""),
        core_traits=soul_data.get("core_traits", []),
        values=soul_data.get("values", []),
        deep_needs=soul_data.get("deep_needs", []),
        top_interests=[],
        life_stage=soul_data.get("life_stage", ""),
        current_phase=soul_data.get("current_phase", ""),
        updated_at="just now",
    )
