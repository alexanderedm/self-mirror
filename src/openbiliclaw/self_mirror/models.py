"""Pydantic models for SelfMirror API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PrivacyTier(StrEnum):
    """Privacy tier levels for event collection."""

    OFF = "off"  # No tracking
    STANDARD = "standard"  # URL, title, dwell time, search terms
    DEEP = "deep"  # + active window/app title


class MirrorMode(StrEnum):
    """Mirror dialogue mode."""

    FREE = "free"  # AI plays "the user"
    GUIDED = "guided"  # AI asks exploratory questions


# -------------------------------------------------------------------
# Event ingestion
# -------------------------------------------------------------------


class MirrorEventIn(BaseModel):
    """A single browser event from the extension."""

    event_type: str = Field(
        ...,
        description="Event type: view, search, click, scroll, hover, favorite, like, dislike",
    )
    url: str = Field(default="", description="Page URL")
    title: str = Field(default="", description="Page title")
    context: str = Field(
        default="",
        description="Natural-language description of what happened",
    )
    duration_seconds: float = Field(default=0.0, ge=0, description="Time spent")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional context (source_platform, author, etc.)",
    )


class MirrorEventBatchIn(BaseModel):
    """Batch of events from the browser extension."""

    tier: PrivacyTier = Field(
        default=PrivacyTier.STANDARD,
        description="Current privacy tier when these events were collected",
    )
    events: list[MirrorEventIn] = Field(
        default_factory=list,
        max_length=100,
        description="Up to 100 events per batch",
    )


class MirrorEventBatchResponse(BaseModel):
    """Response from event batch ingestion."""

    received: int = Field(..., description="Number of events received")
    stored: int = Field(..., description="Number of events actually stored")


# -------------------------------------------------------------------
# Mirror dialogue
# -------------------------------------------------------------------


class MirrorChatIn(BaseModel):
    """A chat message in mirror dialogue."""

    message: str = Field(..., min_length=1, max_length=5000)
    mode: MirrorMode = Field(
        default=MirrorMode.FREE,
        description="Dialogue mode for this turn",
    )


class MirrorChatOut(BaseModel):
    """A response from the mirror."""

    reply: str = Field(..., description="Mirror's reply")
    mode: MirrorMode = Field(..., description="Mode used for this exchange")
    portrait: str = Field(
        default="",
        description="Current portrait (for reference)",
    )


class GuidedStarterOut(BaseModel):
    """A guided-mode opening question."""

    question: str = Field(..., description="The question to start guided exploration")
    based_on: str = Field(
        default="",
        description="What in the profile this question is based on",
    )


# -------------------------------------------------------------------
# Profile
# -------------------------------------------------------------------


class ProfileSummaryOut(BaseModel):
    """SelfMirror profile summary — simplified for web UI."""

    portrait: str = Field(..., description="Personality portrait narrative")
    core_traits: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    deep_needs: list[str] = Field(default_factory=list)
    top_interests: list[str] = Field(default_factory=list)
    life_stage: str = Field(default="")
    current_phase: str = Field(default="")
    updated_at: str = Field(default="")


# -------------------------------------------------------------------
# Init
# -------------------------------------------------------------------


class InitScanResult(BaseModel):
    """Result of scanning local AI tool sessions."""

    sessions_found: int = Field(..., description="Number of sessions scanned")
    sources: list[str] = Field(default_factory=list)
    sources_missing: list[str] = Field(default_factory=list)
    total_chars: int = Field(default=0)


class InitStatusOut(BaseModel):
    """Current init status."""

    has_profile: bool = Field(
        default=False,
        description="Whether a profile has been generated",
    )
    profile_age_days: int | None = Field(
        default=None,
        description="Days since profile was last updated",
    )
    events_collected: int = Field(default=0, description="Total events stored")
