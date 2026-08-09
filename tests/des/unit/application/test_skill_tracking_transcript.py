"""Unit tests for SkillTrackingService transcript extraction.

Tests the service through its public API (track_from_transcript), verifying
observable outcomes at the driven port boundary (SkillTrackingPort).

Test Budget: skill tracking 3 behaviors x 2 = 6 max; mode selection has
4 semantic partitions x 1 = 4 max. Actual: 9 test functions (4 parametrized).

Behaviors:
1. Extracts skill loads from JSONL transcript with Read + skill paths
2. Ignores non-skill entries (non-Read tools, non-skill paths, malformed lines)
3. Batch method logs all extracted events via tracker port
"""

import json

import pytest

from des.application.skill_tracking_service import (
    SkillTrackingService,
    mode_select_observed_before_mutation,
)
from des.domain.skill_load_event import SkillLoadEvent
from des.ports.driven_ports.skill_tracking_port import SkillTrackingPort
from tests.des.adapters.mocked_time import MockedTimeProvider


class InMemorySkillTracker(SkillTrackingPort):
    """In-memory test double for SkillTrackingPort."""

    def __init__(self) -> None:
        self.events: list[SkillLoadEvent] = []

    def log_skill_load(self, event: SkillLoadEvent) -> None:
        self.events.append(event)


def _write_transcript(
    tmp_path, lines: list[dict], filename: str = "transcript.jsonl"
) -> str:
    """Write JSONL transcript lines to a temp file, return path."""
    transcript = tmp_path / filename
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


class TestEstimatesTokens:
    """track_from_transcript estimates token count from file size when
    strategy is token-tracking."""

    def test_estimates_tokens_from_file_size(self, tmp_path) -> None:
        """Token count is chars // 4 when strategy is token-tracking."""
        skill_dir = tmp_path / "skills" / "nw" / "software-crafter"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "tdd-methodology.md"
        skill_file.write_text("x" * 400, encoding="utf-8")
        transcript_path = _write_transcript(
            tmp_path,
            [
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": str(skill_file)},
                },
            ],
        )

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="token-tracking",
        )

        events = service.track_from_transcript(transcript_path)

        assert events[0].estimated_tokens == 100

    def test_passive_logging_skips_token_estimation(self, tmp_path) -> None:
        """Token count is 0 when strategy is passive-logging."""
        skill_dir = tmp_path / "skills" / "nw" / "software-crafter"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "tdd-methodology.md"
        skill_file.write_text("x" * 400, encoding="utf-8")
        transcript_path = _write_transcript(
            tmp_path,
            [
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": str(skill_file)},
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

        assert events[0].estimated_tokens == 0


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


class TestModeSelectObservedBeforeMutation:
    """mode_select_observed_before_mutation recognises an actual
    `Skill(nw-mode-select)` tool_use, fails closed otherwise."""

    @pytest.mark.parametrize(
        "line",
        [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "nw-mode-select"},
                        }
                    ]
                },
            },
            {
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "nw-mode-select"},
            },
            {
                "type": "content_block",
                "content_block": {
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"skill": "nw-mode-select"},
                },
            },
        ],
        ids=["real_assistant", "direct_tool_use", "content_block"],
    )
    def test_true_for_supported_authoritative_call_shapes(
        self, tmp_path, line: dict
    ) -> None:
        """A real assistant call and supported trace shapes authorize mutation.

        CONTRACT_SHAPE: bounded-change
        """
        transcript_path = _write_transcript(
            tmp_path,
            [line],
        )

        assert mode_select_observed_before_mutation(transcript_path) is True

    @pytest.mark.parametrize(
        "line,reason",
        [
            (
                {"type": "text", "text": "I will invoke nw-mode-select next."},
                "prose_mention_not_a_tool_call",
            ),
            (
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "nw-mode-select"},
                            }
                        ]
                    },
                },
                "user_event_is_not_authoritative",
            ),
            (
                {
                    "type": "system",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "nw-mode-select"},
                            }
                        ]
                    },
                },
                "system_event_is_not_authoritative",
            ),
            (
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {
                        "file_path": "/repo/nWave/skills/nw-mode-select/SKILL.md"
                    },
                },
                "read_of_unrelated_file_not_skill_call",
            ),
            (
                {
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"skill": "nw-bugfix"},
                },
                "other_skill_name",
            ),
            (
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                "unrelated_tool",
            ),
        ],
        ids=[
            "prose_mention_not_a_tool_call",
            "user_event_is_not_authoritative",
            "system_event_is_not_authoritative",
            "read_of_unrelated_file_not_skill_call",
            "other_skill_name",
            "unrelated_tool",
        ],
    )
    def test_false_for_unauthorized_or_non_call_entries(
        self, tmp_path, line: dict, reason: str
    ) -> None:
        """Only an authoritative mode-select Skill call satisfies the gate.

        CONTRACT_SHAPE: bounded-change
        """
        transcript_path = _write_transcript(tmp_path, [line])

        assert mode_select_observed_before_mutation(transcript_path) is False

    @pytest.mark.parametrize(
        "available", [False, True], ids=["unavailable", "malformed"]
    )
    def test_false_for_malformed_or_unavailable_transcript(
        self, tmp_path, available: bool
    ) -> None:
        """Unavailable and malformed evidence both fail closed.

        CONTRACT_SHAPE: bounded-change
        """
        transcript = tmp_path / "mode-select-transcript.jsonl"
        if available:
            transcript.write_text("not-json\nalso not json\n", encoding="utf-8")

        assert mode_select_observed_before_mutation(str(transcript)) is False

    def test_true_when_call_present_among_other_noise(self, tmp_path) -> None:
        """Deterministic/irrelevant-event invariance: unrelated events before
        and after the real call do not change the outcome.

        CONTRACT_SHAPE: bounded-change
        """
        transcript_path = _write_transcript(
            tmp_path,
            [
                {"type": "text", "text": "Starting work."},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "nw-mode-select"},
                            }
                        ]
                    },
                },
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/x.py"}},
            ],
        )

        assert mode_select_observed_before_mutation(transcript_path) is True
