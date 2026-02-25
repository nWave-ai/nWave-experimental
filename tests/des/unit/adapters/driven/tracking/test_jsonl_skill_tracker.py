"""Unit tests for JsonlSkillTracker adapter.

Tests the JSONL file output behavior using real filesystem (tmp_path).

Test Budget: 3 behaviors x 2 = 6 max. Actual: 3 tests.

Behaviors:
1. Appends events to JSONL file
2. Creates directory if missing
3. Fail-silent on write errors
"""

import json

from des.adapters.driven.tracking.jsonl_skill_tracker import JsonlSkillTracker
from des.domain.skill_load_event import SkillLoadEvent


def _make_event(**overrides) -> SkillLoadEvent:
    """Create a SkillLoadEvent with sensible defaults."""
    defaults = {
        "timestamp": "2026-02-25T10:00:00+00:00",
        "agent_name": "software-crafter",
        "skill_name": "tdd-methodology",
        "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md",
        "estimated_tokens": 250,
    }
    defaults.update(overrides)
    return SkillLoadEvent(**defaults)


class TestJsonlSkillTrackerAppendsEvents:
    """Tracker appends each event as one JSON line to the JSONL file."""

    def test_appends_to_jsonl_file(self, tmp_path) -> None:
        """Two logged events produce two JSON lines with correct fields."""
        log_file = tmp_path / "skill-loading-log.jsonl"
        tracker = JsonlSkillTracker(log_path=log_file)

        tracker.log_skill_load(_make_event(skill_name="tdd-methodology"))
        tracker.log_skill_load(_make_event(skill_name="quality-framework"))

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["agent_name"] == "software-crafter"
        assert first["skill_name"] == "tdd-methodology"
        assert first["estimated_tokens"] == 250

        second = json.loads(lines[1])
        assert second["skill_name"] == "quality-framework"


class TestJsonlSkillTrackerCreatesDirectory:
    """Tracker creates parent directory if it does not exist."""

    def test_creates_directory_if_missing(self, tmp_path) -> None:
        """Logging to a path with non-existent parent creates the directory."""
        log_file = tmp_path / "new-dir" / "skill-loading-log.jsonl"
        tracker = JsonlSkillTracker(log_path=log_file)

        tracker.log_skill_load(_make_event())

        assert log_file.exists()
        assert log_file.parent.is_dir()


class TestJsonlSkillTrackerFailSilent:
    """Tracker never raises exceptions on I/O errors."""

    def test_fail_silent_on_write_error(self, tmp_path) -> None:
        """Writing to an invalid path does not raise."""
        # Use a path that cannot be written to (directory as file)
        bad_path = tmp_path / "blocked"
        bad_path.mkdir()
        log_file = bad_path / "subdir" / "file" / "deep" / "skill-loading-log.jsonl"
        # Make the parent a file to block mkdir
        blocker = bad_path / "subdir"
        blocker.rmdir() if blocker.is_dir() else None
        # Create a file where a directory is expected
        (bad_path / "subdir").write_text("blocker", encoding="utf-8")

        tracker = JsonlSkillTracker(log_path=log_file)

        # Must not raise
        tracker.log_skill_load(_make_event())
