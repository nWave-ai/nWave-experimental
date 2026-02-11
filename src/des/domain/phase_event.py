"""Phase event domain model and parser.

Pure domain types for representing TDD phase execution events
parsed from execution-log.yaml pipe-delimited event strings.

Format (5-field legacy): "step_id|phase_name|status|outcome|timestamp"
Format (7-field with stats): "step_id|phase_name|status|outcome|timestamp|turns_used|tokens_used"
Example: "01-01|PREPARE|EXECUTED|PASS|2026-02-02T10:00:00Z"
Example: "01-01|COMMIT|EXECUTED|PASS|2026-02-02T10:30:00Z|12|45000"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseEvent:
    """Immutable representation of a single TDD phase execution event.

    Attributes:
        step_id: Step identifier (e.g., "01-01")
        phase_name: TDD phase name (e.g., "PREPARE", "RED_ACCEPTANCE")
        status: Execution status (e.g., "EXECUTED", "SKIPPED")
        outcome: Outcome data (e.g., "PASS", "FAIL", or skip reason)
        timestamp: ISO 8601 timestamp string
        turns_used: Optional number of turns consumed (for COMMIT phase stats)
        tokens_used: Optional number of tokens consumed (for COMMIT phase stats)
    """

    step_id: str
    phase_name: str
    status: str
    outcome: str
    timestamp: str
    turns_used: int | None = None
    tokens_used: int | None = None


class PhaseEventParser:
    """Parses pipe-delimited event strings into PhaseEvent domain objects.

    Replaces inline parsing in:
    - SubagentStopHook._validate_from_execution_log() (lines 190-197)
    - claude_code_hook_adapter._verify_step_from_append_only_log()

    This is a stateless parser with no I/O dependencies.
    """

    MINIMUM_FIELDS = 5
    STATS_FIELDS = 7
    FIELD_SEPARATOR = "|"

    def parse(self, event_str: str) -> PhaseEvent | None:
        """Parse a pipe-delimited event string into a PhaseEvent.

        Args:
            event_str: Raw event string in format
                "step_id|phase_name|status|outcome|timestamp" (5-field legacy)
                or "step_id|phase_name|status|outcome|timestamp|turns|tokens" (7-field)

        Returns:
            PhaseEvent if the string has enough fields, None otherwise.
        """
        parts = event_str.split(self.FIELD_SEPARATOR)
        if len(parts) < self.MINIMUM_FIELDS:
            return None

        turns_used = None
        tokens_used = None
        if len(parts) >= self.STATS_FIELDS:
            try:
                turns_used = int(parts[5])
                tokens_used = int(parts[6])
            except ValueError:
                pass  # Non-integer extra fields: ignore gracefully

        return PhaseEvent(
            step_id=parts[0],
            phase_name=parts[1],
            status=parts[2],
            outcome=parts[3],
            timestamp=parts[4],
            turns_used=turns_used,
            tokens_used=tokens_used,
        )

    def parse_many(self, event_strings: list[str], step_id: str) -> list[PhaseEvent]:
        """Parse multiple event strings, filtering by step_id.

        Args:
            event_strings: List of raw pipe-delimited event strings
            step_id: Only return events matching this step_id

        Returns:
            List of PhaseEvent objects matching the step_id
        """
        events = []
        for event_str in event_strings:
            event = self.parse(event_str)
            if event is not None and event.step_id == step_id:
                events.append(event)
        return events

    def parse_all(self, event_strings: list[str]) -> list[PhaseEvent]:
        """Parse all event strings without filtering by step_id.

        Args:
            event_strings: List of raw pipe-delimited event strings

        Returns:
            List of all successfully parsed PhaseEvent objects
        """
        events = []
        for event_str in event_strings:
            event = self.parse(event_str)
            if event is not None:
                events.append(event)
        return events
