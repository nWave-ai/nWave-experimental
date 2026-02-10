"""Log integrity validator - detects crafter log manipulation.

Checks execution-log events for anomalies that indicate fabrication,
cross-step contamination, or timestamp manipulation. Warn-only: does
not block step completion.

Three checks:
1. Phase names: events with phase_name not in TDDSchema.tdd_phases
2. Foreign step_ids: events for OTHER step_ids within the task window
3. Timestamp plausibility: future timestamps or pre-task-start timestamps
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from des.domain.phase_event import PhaseEvent
    from des.domain.tdd_schema import TDDSchema
    from des.ports.driven_ports.time_provider_port import TimeProvider


@dataclass(frozen=True)
class IntegrityResult:
    """Result of log integrity validation. Warnings only, never blocks."""

    warnings: list[str] = field(default_factory=list)


class LogIntegrityValidator:
    """Validates execution-log events for integrity anomalies.

    Warn-only: produces warnings that are logged to the audit trail
    but never block step completion.
    """

    def __init__(
        self, schema: TDDSchema, time_provider: TimeProvider | None = None
    ) -> None:
        self._valid_phases = set(schema.tdd_phases)
        self._time_provider = time_provider

    def validate(
        self,
        step_id: str,
        all_events: list[PhaseEvent],
        task_start_time: str | None = None,
    ) -> IntegrityResult:
        """Validate events for integrity anomalies.

        Args:
            step_id: The current step being validated
            all_events: ALL events from the execution log (unfiltered)
            task_start_time: ISO 8601 timestamp when the task started (optional)

        Returns:
            IntegrityResult with any warnings found
        """
        warnings: list[str] = []
        warnings.extend(self._check_phase_names(step_id, all_events))
        warnings.extend(
            self._check_foreign_step_ids(step_id, all_events, task_start_time)
        )
        warnings.extend(self._check_timestamps(step_id, all_events, task_start_time))
        return IntegrityResult(warnings=warnings)

    def _check_phase_names(
        self, step_id: str, all_events: list[PhaseEvent]
    ) -> list[str]:
        """Check for unrecognized phase names in events for this step."""
        warnings: list[str] = []
        for event in all_events:
            if event.step_id != step_id:
                continue
            if event.phase_name not in self._valid_phases:
                suggestion = ""
                matches = get_close_matches(
                    event.phase_name, list(self._valid_phases), n=1, cutoff=0.5
                )
                if matches:
                    suggestion = f" (did you mean '{matches[0]}'?)"
                warnings.append(
                    f"Unrecognized phase name '{event.phase_name}'{suggestion}"
                )
        return warnings

    def _check_foreign_step_ids(
        self,
        step_id: str,
        all_events: list[PhaseEvent],
        task_start_time: str | None,
    ) -> list[str]:
        """Check for events written for other step_ids during task window."""
        if not task_start_time:
            return []

        try:
            start_dt = datetime.fromisoformat(task_start_time)
        except (ValueError, TypeError):
            return []

        warnings: list[str] = []
        foreign_ids: set[str] = set()
        for event in all_events:
            if event.step_id == step_id:
                continue
            try:
                event_dt = datetime.fromisoformat(event.timestamp)
            except (ValueError, TypeError):
                continue
            if event_dt >= start_dt:
                foreign_ids.add(event.step_id)

        for fid in sorted(foreign_ids):
            warnings.append(
                f"Foreign step_id '{fid}' has events written during task window"
            )
        return warnings

    def _check_timestamps(
        self,
        step_id: str,
        all_events: list[PhaseEvent],
        task_start_time: str | None,
    ) -> list[str]:
        """Check for implausible timestamps in events for this step."""
        if not task_start_time:
            return []

        try:
            start_dt = datetime.fromisoformat(task_start_time)
        except (ValueError, TypeError):
            return []

        if self._time_provider:
            now = self._time_provider.now_utc()
        else:
            now = datetime.now(timezone.utc)
        # Ensure timezone-aware for comparison
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        warnings: list[str] = []
        for event in all_events:
            if event.step_id != step_id:
                continue
            try:
                event_dt = datetime.fromisoformat(event.timestamp)
            except (ValueError, TypeError):
                continue
            if event_dt > now:
                warnings.append(
                    f"Future timestamp on {event.phase_name}: {event.timestamp}"
                )
            elif event_dt < start_dt:
                warnings.append(
                    f"Pre-task timestamp on {event.phase_name}: {event.timestamp}"
                )
        return warnings
