"""Tests for selfmirror.soul.init_scanner — local AI session scanning."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from selfmirror.soul.init_scanner import (
    InitScanner,
    ScanResult,
    ScannedSession,
    SessionSource,
    _extract_content_from_json,
    _extract_content_from_jsonl,
    _extract_content_from_markdown_file,
    _guess_timestamp_from_path,
    scan_directory,
)


class TestExtractContentFromMarkdownFile:
    def test_strips_code_blocks(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("```python\nprint('hello')\n```\nThis is meaningful text.\n")
            path = Path(f.name)

        try:
            content = _extract_content_from_markdown_file(path)
            assert "print" not in content
            assert "meaningful text" in content
        finally:
            path.unlink()

    def test_strips_short_lines(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("hi\n---\na\n")
            path = Path(f.name)

        try:
            content = _extract_content_from_markdown_file(path)
            # "hi", "---", "a" are all < 5 chars
            assert content.strip() == ""
        finally:
            path.unlink()

    def test_returns_empty_on_error(self) -> None:
        content = _extract_content_from_markdown_file(Path("/nonexistent/file.md"))
        assert content == ""

    def test_caps_at_10k_chars(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("x" * 20000)
            path = Path(f.name)

        try:
            content = _extract_content_from_markdown_file(path)
            assert len(content) == 10000
        finally:
            path.unlink()


class TestExtractContentFromJsonl:
    def test_extracts_content_field(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"content": "Hello this is a test message", "role": "user"}) + "\n")
            f.write(json.dumps({"content": "This is a response from the assistant", "role": "assistant"}) + "\n")
            path = Path(f.name)

        try:
            content = _extract_content_from_jsonl(path)
            assert "Hello" in content
            assert "assistant" in content
        finally:
            path.unlink()

    def test_skips_malformed_lines(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write('not valid json\n')
            f.write(json.dumps({"content": "valid line with enough characters to pass"}) + "\n")
            path = Path(f.name)

        try:
            content = _extract_content_from_jsonl(path)
            assert "valid line" in content
        finally:
            path.unlink()

    def test_returns_empty_on_error(self) -> None:
        content = _extract_content_from_jsonl(Path("/nonexistent/file.jsonl"))
        assert content == ""


class TestExtractContentFromJson:
    def test_extracts_nested_strings(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "messages": [
                        {"role": "user", "content": "This is a long enough user message"},
                        {"role": "assistant", "content": "This is a long enough assistant response"},
                    ]
                },
                f,
            )
            path = Path(f.name)

        try:
            content = _extract_content_from_json(path)
            assert "user message" in content
            assert "assistant" in content
        finally:
            path.unlink()

    def test_respects_depth_limit(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            # Depth > 5 should be skipped
            deeply_nested = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": "too deep message text here"}}}}}}
            json.dump(deeply_nested, f)
            path = Path(f.name)

        try:
            content = _extract_content_from_json(path)
            # depth 6 is skipped
            assert "too deep" not in content
        finally:
            path.unlink()


class TestGuessTimestampFromPath:
    def test_iso_date(self) -> None:
        path = Path("/home/user/.claude/2024-03-15/conversation.md")
        ts = _guess_timestamp_from_path(path)
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 3
        assert ts.day == 15

    def test_compact_date(self) -> None:
        path = Path("/home/user/.dsh/sessions/20240315.jsonl")
        ts = _guess_timestamp_from_path(path)
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 3
        assert ts.day == 15

    def test_no_timestamp(self) -> None:
        path = Path("/home/user/.cursor/chat/general.md")
        ts = _guess_timestamp_from_path(path)
        assert ts is None


class TestSessionSource:
    def test_exists_false_for_missing_dir(self) -> None:
        source = SessionSource(name="Test", path=Path("/nonexistent/path"))
        assert source.exists() is False

    def test_exists_true_for_real_dir(self, tmp_path: Path) -> None:
        source = SessionSource(name="Test", path=tmp_path)
        assert source.exists() is True


class TestScanDirectory:
    def test_returns_empty_for_nonexistent_source(self, tmp_path: Path) -> None:
        source = SessionSource(name="Test", path=tmp_path / "missing", session_glob="*.md")
        sessions = scan_directory(source)
        assert sessions == []

    def test_scans_markdown_files(self, tmp_path: Path) -> None:
        # Create a markdown session file
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        md_file = session_dir / "conversation.md"
        md_file.write_text(
            "This is a meaningful conversation about AI and philosophy.\n"
            "The user seems interested in existential questions.",
            encoding="utf-8",
        )

        source = SessionSource(name="Test", path=session_dir, session_glob="*.md")
        sessions = scan_directory(source, max_sessions=10)

        assert len(sessions) == 1
        assert sessions[0].source_name == "Test"
        assert "AI" in sessions[0].content
        assert sessions[0].file_path == str(md_file)

    def test_skips_small_files(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        small_file = session_dir / "tiny.md"
        small_file.write_text("hi", encoding="utf-8")

        source = SessionSource(name="Test", path=session_dir, session_glob="*.md")
        sessions = scan_directory(source)
        assert sessions == []

    def test_limits_to_max_sessions(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        for i in range(10):
            f = session_dir / f"session_{i}.md"
            # Use multiple sentences to ensure sufficient content after extraction
            f.write_text(
                "This is a meaningful conversation about personal growth and self-discovery. "
                "The user has been exploring questions about identity and purpose recently.",
                encoding="utf-8",
            )

        source = SessionSource(name="Test", path=session_dir, session_glob="*.md")
        sessions = scan_directory(source, max_sessions=3)
        assert len(sessions) == 3


class TestInitScanner:
    def test_empty_sources_when_no_dirs_exist(self, tmp_path: Path) -> None:
        """When no default source directories exist, scanner has empty sources."""
        # Create a scanner with a clearly nonexistent path
        source = SessionSource(name="Fake", path=tmp_path / "nonexistent")
        scanner = InitScanner(sources=[source])
        result = scanner.scan()
        assert result.sources_found == []
        assert "Fake" in result.sources_missing

    def test_scan_returns_found_sources(self, tmp_path: Path) -> None:
        """Scanner reports which sources were found."""
        session_dir = tmp_path / ".claude"
        session_dir.mkdir()
        md = session_dir / "chat.md"
        md.write_text(
            "I am exploring the concept of self-awareness through meditation. "
            "This is a conversation where the user reflects on their personal journey "
            "and discusses their interests in psychology and philosophy.",
            encoding="utf-8",
        )

        source = SessionSource(name="Claude Code", path=session_dir, session_glob="*.md")
        scanner = InitScanner(sources=[source])
        result = scanner.scan()

        assert "Claude Code" in result.sources_found
        assert len(result.sessions) == 1
        assert result.total_chars > 0

    def test_scan_accumulates_chars(self, tmp_path: Path) -> None:
        """Total chars counts all session content."""
        session_dir = tmp_path / "dsh"
        session_dir.mkdir()
        (session_dir / "session1.jsonl").write_text(
            json.dumps({"content": "A" * 500}) + "\n", encoding="utf-8"
        )
        (session_dir / "session2.jsonl").write_text(
            json.dumps({"content": "B" * 300}) + "\n", encoding="utf-8"
        )

        source = SessionSource(name="DSH", path=session_dir, session_glob="*.jsonl")
        scanner = InitScanner(sources=[source])
        result = scanner.scan()

        assert result.total_chars >= 800

    def test_build_init_prompt_content_empty(self, tmp_path: Path) -> None:
        """Empty scan result gives placeholder text."""
        source = SessionSource(name="Fake", path=tmp_path / "nonexistent")
        scanner = InitScanner(sources=[source])
        result = scanner.scan()
        content = scanner.build_init_prompt_content(result)
        assert "未找到" in content or "有限" in content

    def test_build_init_prompt_content_with_sessions(self, tmp_path: Path) -> None:
        """Non-empty scan result builds condensed prompt."""
        session_dir = tmp_path / ".claude"
        session_dir.mkdir()
        md = session_dir / "chat.md"
        md.write_text(
            "The user is interested in psychology and how people form their identities. "
            + "They often ask questions about meaning and purpose in life.",
            encoding="utf-8",
        )

        source = SessionSource(name="Claude Code", path=session_dir, session_glob="*.md")
        scanner = InitScanner(sources=[source])
        result = scanner.scan()
        content = scanner.build_init_prompt_content(result)

        assert "Claude Code" in content
        assert len(result.sessions) > 0

    def test_scan_nonexistent_source_in_default_skipped(self) -> None:
        """InitScanner with no explicit sources skips nonexistent default dirs gracefully."""
        # Create only sources that don't exist
        nonexistent = SessionSource(name="Ghost", path=Path("/ghost/path/that/does/not/exist"))
        scanner = InitScanner(sources=[nonexistent])
        result = scanner.scan()
        assert "Ghost" in result.sources_missing
        assert result.sessions == []


class TestScanResult:
    def test_default_fields(self) -> None:
        result = ScanResult()
        assert result.sessions == []
        assert result.sources_found == []
        assert result.sources_missing == []
        assert result.total_chars == 0
        assert result.errors == []

    def test_accumulates(self) -> None:
        result = ScanResult()
        result.sessions.append(
            ScannedSession(
                source_name="Test",
                file_path="/test/path.md",
                content="Meaningful content that is long enough",
            )
        )
        result.sources_found.append("Test")
        result.total_chars += 100
        assert len(result.sessions) == 1
        assert result.total_chars == 100
