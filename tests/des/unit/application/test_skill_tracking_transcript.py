"""Unit tests for SkillTrackingService transcript extraction.

Tests the service through its public API (track_from_transcript), verifying
observable outcomes at the driven port boundary (SkillTrackingPort).

Test Budget: 3 behaviors x 2 = 6 max. Actual: 4 tests (1 parametrized).

Behaviors:
1. Extracts skill loads from JSONL transcript with Read + skill paths
2. Ignores non-skill entries (non-Read tools, non-skill paths, malformed lines)
3. Batch method logs all extracted events via tracker port
"""

import json

import pytest

from des.adapters.driven.time.mocked_time import MockedTimeProvider
from des.application.skill_tracking_service import SkillTrackingService
from des.domain.skill_load_event import SkillLoadEvent
from des.ports.driven_ports.skill_tracking_port import SkillTrackingPort


class InMemorySkillTracker(SkillTrackingPort):
    """In-memory test double for SkillTrackingPort."""

    def __init__(self) -> None:
        self.events: list[SkillLoadEvent] = []

    def log_skill_load(self, event: SkillLoadEvent) -> None:
        self.events.append(event)


def _write_transcript(tmp_path, lines: list[dict]) -> str:
    """Write JSONL transcript lines to a temp file, return path."""
    transcript = tmp_path / "transcript.jsonl"
    with open(transcript, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return str(transcript)


class TestExtractsSkillLoadsFromTranscript:
    """track_from_transcript extracts skill Read calls and logs events."""

    def test_extracts_skill_reads_from_transcript(self, tmp_path) -> None:
        """Transcript with two skill Read entries produces two logged events."""
        transcript_path = _write_transcript(
            tmp_path,
            [
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {
                        "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md"
                    },
                },
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {
                        "file_path": "/home/user/.claude/skills/nw/acceptance-designer/bdd-scenarios.md"
                    },
                },
            ],
        )

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        events = service.track_from_transcript(transcript_path)

        assert len(events) == 2
        assert len(tracker.events) == 2
        assert events[0].agent_name == "software-crafter"
        assert events[0].skill_name == "tdd-methodology"
        assert events[1].agent_name == "acceptance-designer"
        assert events[1].skill_name == "bdd-scenarios"

    def test_extracts_skill_reads_from_content_block_format(self, tmp_path) -> None:
        """Transcript with content_block tool_use format also extracts skill reads."""
        transcript_path = _write_transcript(
            tmp_path,
            [
                {
                    "type": "content_block",
                    "content_block": {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {
                            "file_path": "/home/user/.claude/skills/nw/software-crafter/hexagonal-testing.md"
                        },
                    },
                },
            ],
        )

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        events = service.track_from_transcript(transcript_path)

        assert len(events) == 1
        assert events[0].agent_name == "software-crafter"
        assert events[0].skill_name == "hexagonal-testing"


class TestIgnoresNonSkillTranscriptEntries:
    """track_from_transcript ignores non-skill entries in transcript."""

    @pytest.mark.parametrize(
        "line,reason",
        [
            (
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                "non_read_tool",
            ),
            (
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": "/home/user/project/src/main.py"},
                },
                "non_skill_path",
            ),
            (
                {"type": "text", "text": "Hello world"},
                "non_tool_use_entry",
            ),
            (
                {"type": "tool_use", "name": "Read", "input": {}},
                "missing_file_path",
            ),
        ],
        ids=[
            "non_read_tool",
            "non_skill_path",
            "non_tool_use_entry",
            "missing_file_path",
        ],
    )
    def test_ignores_non_skill_entries(self, tmp_path, line: dict, reason: str) -> None:
        """Non-skill entries produce no events."""
        transcript_path = _write_transcript(tmp_path, [line])

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        events = service.track_from_transcript(transcript_path)

        assert len(events) == 0
        assert len(tracker.events) == 0


class TestTranscriptTrackingFailOpen:
    """track_from_transcript never raises, returns empty on errors."""

    def test_returns_empty_on_missing_transcript(self) -> None:
        """Missing transcript file returns empty list, no exception."""
        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        events = service.track_from_transcript("/nonexistent/transcript.jsonl")

        assert events == []
        assert len(tracker.events) == 0

    def test_returns_empty_on_malformed_jsonl(self, tmp_path) -> None:
        """Malformed JSONL lines are skipped, valid lines still processed."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            "not-json\n"
            + json.dumps(
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {
                        "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md"
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        events = service.track_from_transcript(str(transcript))

        assert len(events) == 1
        assert events[0].skill_name == "tdd-methodology"
