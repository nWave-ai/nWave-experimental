"""Unit tests for SkillTrackingService.

Tests the service through its public API (maybe_track), verifying
observable outcomes at the driven port boundary (SkillTrackingPort).

Test Budget: 5 behaviors x 2 = 10 max. Actual: 7 tests (2 parametrized).

Behaviors:
1. Tracks skill Read calls (happy path)
2. Ignores non-skill paths
3. Ignores non-Read tools
4. Parses agent/skill from path correctly
5. Estimates tokens from file size
"""

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


class BrokenSkillTracker(SkillTrackingPort):
    """Test double that raises on every call."""

    def log_skill_load(self, event: SkillLoadEvent) -> None:
        raise OSError("disk full")


class TestTracksSkillReadCalls:
    """Service logs an event when a Read targets a skill file."""

    def test_tracks_skill_read_call(self) -> None:
        """Read to /skills/nw/ path produces a logged SkillLoadEvent."""
        tracker = InMemorySkillTracker()
        time_provider = MockedTimeProvider()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=time_provider,
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={
                "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md"
            },
        )

        assert len(tracker.events) == 1
        event = tracker.events[0]
        assert event.agent_name == "software-crafter"
        assert event.skill_name == "tdd-methodology"
        assert event.timestamp == time_provider.now_utc().isoformat()

    def test_includes_step_id_from_des_context(self) -> None:
        """Step ID is extracted from DES context when available."""
        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={
                "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md"
            },
            des_context={"step_id": "01-03"},
        )

        assert tracker.events[0].step_id == "01-03"


class TestIgnoresNonSkillCalls:
    """Service does not log events for non-skill tool calls."""

    @pytest.mark.parametrize(
        "file_path",
        [
            "/home/user/project/src/main.py",
            "/home/user/.claude/CLAUDE.md",
            "/home/user/.claude/commands/nw/deliver.md",
        ],
        ids=["source_file", "claude_md", "command_file"],
    )
    def test_ignores_non_skill_read(self, file_path: str) -> None:
        """Read to non-skill paths does not produce events."""
        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={"file_path": file_path},
        )

        assert len(tracker.events) == 0

    @pytest.mark.parametrize(
        "tool_name",
        ["Write", "Edit", "Bash", "Glob", "Grep"],
    )
    def test_ignores_non_read_tools(self, tool_name: str) -> None:
        """Non-Read tools never produce events, even with skill paths."""
        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name=tool_name,
            tool_input={
                "file_path": "/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md"
            },
        )

        assert len(tracker.events) == 0


class TestParsesSkillInfo:
    """Service extracts agent name and skill name from file path."""

    def test_parses_agent_and_skill_from_path(self) -> None:
        """Extracts agent-name and skill-name from standard skill path."""
        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={
                "file_path": "/home/alexd/.claude/skills/nw/acceptance-designer/bdd-scenarios.md"
            },
        )

        event = tracker.events[0]
        assert event.agent_name == "acceptance-designer"
        assert event.skill_name == "bdd-scenarios"


class TestEstimatesTokens:
    """Service estimates token count from file size when strategy is token-tracking."""

    def test_estimates_tokens_from_file_size(self, tmp_path) -> None:
        """Token count is chars // 4 when strategy is token-tracking."""
        skill_dir = tmp_path / "skills" / "nw" / "software-crafter"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "tdd-methodology.md"
        skill_file.write_text("x" * 400, encoding="utf-8")

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="token-tracking",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={"file_path": str(skill_file)},
        )

        assert tracker.events[0].estimated_tokens == 100

    def test_passive_logging_skips_token_estimation(self, tmp_path) -> None:
        """Token count is 0 when strategy is passive-logging."""
        skill_dir = tmp_path / "skills" / "nw" / "software-crafter"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "tdd-methodology.md"
        skill_file.write_text("x" * 400, encoding="utf-8")

        tracker = InMemorySkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=MockedTimeProvider(),
            strategy="passive-logging",
        )

        service.maybe_track(
            tool_name="Read",
            tool_input={"file_path": str(skill_file)},
        )

        assert tracker.events[0].estimated_tokens == 0
