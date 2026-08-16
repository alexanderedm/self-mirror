"""Local AI tool session scanner for initial profile generation.

Scans local AI coding assistant session directories to build an initial
user portrait without requiring external data collection. All data stays
on the local filesystem.

Supported tools:
- Claude Code (claude.ai/code): ~/.claude/
- DeepSeek Harness (dsh): ~/.dsh/
- Cursor: ~/.cursor/
- Windsurf: ~/.windsurf/
- Codex: ~/.codex/
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from selfmirror.llm.base import LLMResponse
    from selfmirror.llm.service import LLMService

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Directory configuration
# -------------------------------------------------------------------


@dataclass
class SessionSource:
    """A session directory to scan."""

    name: str  # Display name e.g. "Claude Code"
    path: Path
    session_glob: str = "*.json"
    description: str = ""

    def exists(self) -> bool:
        return self.path.exists() and self.path.is_dir()


# Expand user home path safely
def _expand(s: str | None) -> Path | None:
    if s is None:
        return None
    try:
        return Path(os.path.expanduser(s))
    except Exception:
        return None


# -------------------------------------------------------------------
# Default source list — user can override via config
# -------------------------------------------------------------------

DEFAULT_SOURCES: list[SessionSource] = [
    SessionSource(
        name="Claude Code",
        path=_expand("~/.claude/") or Path(),
        session_glob="**/*.md",
        description="Claude Code conversation logs",
    ),
    SessionSource(
        name="DeepSeek Harness",
        path=_expand("~/.dsh/sessions/") or Path(),
        session_glob="**/*.jsonl",
        description="DSH session logs",
    ),
    SessionSource(
        name="Cursor",
        path=_expand("~/.cursor chat/") or Path(),
        session_glob="**/*.md",
        description="Cursor AI chat history",
    ),
    SessionSource(
        name="Windsurf",
        path=_expand("~/.windsurf/") or Path(),
        session_glob="**/*.md",
        description="Windsurf session logs",
    ),
    SessionSource(
        name="Codex",
        path=_expand("~/.codex/") or Path(),
        session_glob="**/*.json",
        description="OpenAI Codex session data",
    ),
]


# -------------------------------------------------------------------
# Session content extraction
# -------------------------------------------------------------------


@dataclass
class ScannedSession:
    """A single scanned session with extracted text content."""

    source_name: str
    file_path: str
    content: str
    timestamp: datetime | None = None
    topic_hint: str | None = None  # Optional topic extracted from filename/path


@dataclass
class ScanResult:
    """Result of scanning all configured sources."""

    sessions: list[ScannedSession] = field(default_factory=list)
    sources_found: list[str] = field(default_factory=list)
    sources_missing: list[str] = field(default_factory=list)
    total_chars: int = 0
    errors: list[str] = field(default_factory=list)


def _extract_content_from_markdown_file(path: Path) -> str:
    """Extract meaningful text from a markdown session file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Remove common markdown noise: long code blocks, binary, etc.
        lines = text.splitlines()
        meaningful_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            # Skip very short lines that are likely UI elements
            if len(line.strip()) < 5:
                continue
            meaningful_lines.append(line)
        return "\n".join(meaningful_lines)[:10_000]  # Cap at 10k chars per file
    except Exception:
        return ""


def _extract_content_from_jsonl(path: Path) -> str:
    """Extract meaningful text from a JSONL (JSON Lines) session file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        texts = []
        for line in lines[:100]:  # Limit to first 100 lines
            try:
                obj = json.loads(line)
                # Try to extract text from common fields
                for key in ("content", "text", "message", "prompt", "response"):
                    val = obj.get(key, "")
                    if isinstance(val, str) and len(val) > 20:
                        texts.append(val[:2000])
                        break
            except json.JSONDecodeError:
                continue
        return "\n\n".join(texts)[:10_000]
    except Exception:
        return ""


def _extract_content_from_json(path: Path) -> str:
    """Extract meaningful text from a JSON session file."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        texts = []

        # Recursive extraction of string content
        def extract_strings(obj: Any, depth: int = 0) -> None:
            if depth > 5 or not obj:
                return
            if isinstance(obj, str) and len(obj) > 20:
                texts.append(obj[:2000])
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract_strings(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj[:50]:
                    extract_strings(item, depth + 1)

        extract_strings(obj)
        return "\n\n".join(texts)[:10_000]
    except Exception:
        return ""


def _guess_timestamp_from_path(path: Path) -> datetime | None:
    """Try to extract a timestamp from the file path or name."""
    # Look for ISO-like date patterns in the path
    text = str(path)
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{8})",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                s = m.group(1).replace("-", "")
                if len(s) == 8:
                    return datetime.strptime(s, "%Y%m%d")
                return datetime.fromisoformat(m.group(1))
            except ValueError:
                pass
    return None


def scan_directory(source: SessionSource, max_sessions: int = 50) -> list[ScannedSession]:
    """Scan a single source directory and return extracted sessions."""
    if not source.exists():
        logger.debug("Source %s does not exist at %s", source.name, source.path)
        return []

    sessions = []
    try:
        all_files = list(source.path.rglob(source.session_glob))
        # Sort by modification time, newest first
        all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        all_files = all_files[:max_sessions]

        for file_path in all_files:
            if file_path.is_file() and file_path.stat().st_size > 100:
                if file_path.suffix == ".md":
                    content = _extract_content_from_markdown_file(file_path)
                elif file_path.suffix == ".jsonl":
                    content = _extract_content_from_jsonl(file_path)
                elif file_path.suffix == ".json":
                    content = _extract_content_from_json(file_path)
                else:
                    continue

                if len(content) < 100:  # Skip near-empty files
                    continue

                sessions.append(
                    ScannedSession(
                        source_name=source.name,
                        file_path=str(file_path),
                        content=content,
                        timestamp=_guess_timestamp_from_path(file_path),
                        topic_hint=file_path.parent.name,
                    )
                )

    except PermissionError:
        logger.warning("Permission denied scanning %s", source.path)
    except Exception as exc:
        logger.warning("Error scanning %s: %s", source.path, exc)

    return sessions


# -------------------------------------------------------------------
# Main scanner
# -------------------------------------------------------------------


@dataclass
class InitScanner:
    """Scans local AI tool sessions to build an initial user profile."""

    sources: list[SessionSource] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.sources:
            self.sources = [s for s in DEFAULT_SOURCES if s.exists()]

    def scan(self, max_sessions_per_source: int = 50) -> ScanResult:
        """Scan all configured sources and return collected sessions."""
        result = ScanResult()
        for source in self.sources:
            if source.exists():
                result.sources_found.append(source.name)
                sessions = scan_directory(source, max_sessions_per_source)
                result.sessions.extend(sessions)
                result.total_chars += sum(len(s.content) for s in sessions)
                logger.info(
                    "Scanned %d sessions from %s (%.1fk chars)",
                    len(sessions),
                    source.name,
                    result.total_chars / 1000,
                )
            else:
                result.sources_missing.append(source.name)

        return result

    def build_init_prompt_content(self, result: ScanResult) -> str:
        """Build a text summary of scanned sessions for the LLM prompt.

        Returns a condensed string suitable for the initial profile prompt.
        Each session is summarized to ~500 chars to stay within token limits.
        """
        if not result.sessions:
            return "（未找到任何 AI 工具對話記錄。請基於有限的上下文推斷用戶特質。）"

        source_list = ", ".join(result.sources_found)
        parts = [f"（共掃描 {len(result.sessions)} 個對話，來源：{source_list}）\n"]
        for session in result.sessions[:30]:  # Cap at 30 sessions
            # Condense each session
            condensed = session.content[:800].replace("\n", " ").strip()
            source_label = f"[{session.source_name}]"
            parts.append(f"{source_label} {condensed}")

        return "\n\n".join(parts)

    async def generate_initial_profile(
        self,
        llm_service: LLMService,
        scan_result: ScanResult | None = None,
    ) -> dict[str, Any]:
        """Generate the initial profile using the scanned session content.

        Uses the existing build_soul_profile_prompt from prompts.py but
        replaces the history input with scanned AI tool session content.
        """
        from selfmirror.llm.json_utils import (
            DEFAULT_STRUCTURED_MAX_TOKENS,
            format_parse_failure,
            parse_llm_json_tolerant,
        )
        from selfmirror.llm.prompts import build_soul_profile_prompt
        from selfmirror.llm.task_options import without_core_memory_kwargs

        if scan_result is None:
            scan_result = self.scan()

        # Build a history_summary-like structure from sessions
        history_summary: dict[str, Any] = {
            "count": len(scan_result.sessions),
            "sources": scan_result.sources_found,
            "contexts": [s.content[:200] for s in scan_result.sessions[:20]],
        }

        preference_summary: dict[str, Any] = {}
        recent_awareness: list[dict[str, Any]] = []
        active_insights: list[dict[str, Any]] = []

        tone_profile = None

        messages = build_soul_profile_prompt(
            history_summary=history_summary,
            preference_summary=preference_summary,
            recent_awareness=recent_awareness,
            active_insights=active_insights,
            tone_profile=tone_profile,
            source_platform_mix=None,
        )

        try:
            complete_structured = llm_service.complete_structured_task
            response: LLMResponse = await complete_structured(
                system_instruction=messages[0]["content"],
                user_input=messages[1]["content"],
                max_tokens=DEFAULT_STRUCTURED_MAX_TOKENS,
                caller="soul.init_scanner",
                temperature=0.5,
                **without_core_memory_kwargs(complete_structured),
            )
        except Exception as exc:
            logger.error("Initial profile generation failed: %s", exc)
            raise

        content = response.content
        if not content.strip():
            raise ValueError("LLM returned empty initial profile.")

        parsed = parse_llm_json_tolerant(content)
        if parsed is None:
            raise ValueError(
                f"LLM returned invalid JSON: {format_parse_failure(content, ValueError())}"
            )

        return dict(parsed)
