"""Minimal OnionProfile stub for SelfMirror runtime context.

This provides the profile interface expected by mirror_dialogue.py
without requiring the full OpenBiliClaw soul engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CoreLayer:
    core_traits: list[str] = field(default_factory=list)
    deep_needs: list[str] = field(default_factory=list)


@dataclass
class RoleLayer:
    life_stage: str = ""
    current_phase: str = ""


@dataclass
class ValuesLayer:
    values: list[str] = field(default_factory=list)


@dataclass
class InterestLayer:
    likes: list = field(default_factory=list)


@dataclass
class OnionProfile:
    """Minimal onion profile for SelfMirror."""

    personality_portrait: str = ""
    core: CoreLayer = field(default_factory=CoreLayer)
    role: RoleLayer = field(default_factory=RoleLayer)
    values_layer: ValuesLayer = field(default_factory=ValuesLayer)
    interest: InterestLayer = field(default_factory=InterestLayer)
    recent_awareness: list = field(default_factory=list)
    active_insights: list = field(default_factory=list)
    updated_at: str | None = None

    @classmethod
    def empty(cls) -> OnionProfile:
        return cls(
            personality_portrait="（尚未建立畫像）",
            core=CoreLayer(),
            role=RoleLayer(),
            values_layer=ValuesLayer(),
            interest=InterestLayer(),
        )
