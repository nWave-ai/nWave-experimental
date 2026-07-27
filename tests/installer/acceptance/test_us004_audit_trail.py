"""
E2E Acceptance Test: US-004 Audit Trail for Compliance Verification

PERSONA: Priya (Tech Lead)
STORY: As a tech lead, I want DES to maintain a complete audit trail of all state
       transitions, so that I can verify TDD compliance during PR review with
       concrete evidence.

BUSINESS VALUE:
- Enables verifiable TDD compliance evidence for PR review
- Provides complete execution history with timestamps
- Creates immutable audit records for accountability

SCOPE: AC-004.1 (ISO timestamp formatting) and AC-004.2 (append-only
immutability) of the JsonlAuditLogWriter production adapter.
STATUS: implemented and green (`JsonlAuditLogWriter`,
`des/adapters/driven/logging/jsonl_audit_log_writer.py`).

REMOVED 2026-07-27 (techdebt row
`ten-of-twelve-audit-trail-acceptance-tests-have-an-empty-body`): this file
originally declared TEN additional `test_scenario_*` methods (3a, 3b, 3c, 004,
005, 006, 007, 008, 009, 010) whose bodies were nothing but a docstring plus
every Arrange/Act/Assert line commented out -- they ran, asserted nothing, and
passed GREEN, falsely declaring the corresponding ACs verified. They targeted
a `DESExecutor` / `des_executor.execute_all_phases` /
`audit_log.read_entries_for_step` API that never existed in `src/des`, keyed
on the 14-phase execution model this repo's CLAUDE.md marks as the retired
legacy contract (the current canon is the 3-phase RED/GREEN/COMMIT cycle,
ADR-025). The concrete event-logging behaviour they gestured at
(TASK_INVOCATION_*, PHASE_*, SUBAGENT_STOP_*, COMMIT_* events) is exercised
for real, against the CURRENT architecture, by
`tests/des/unit/application/test_orchestrator_audit_helper.py` and
`tests/des/unit/adapters/driven/logging/test_audit_events.py` /
`test_audit_events_hook_types.py` -- so their removal drops no coverage, only
a placeholder that was never redeemed. See
`test_us004_audit_trail_no_empty_scenarios.py` (sibling file) for the
regression guard pinning that no empty-bodied scenario returns to this file.
"""

import json
from datetime import datetime

import pytest

from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.ports.driven_ports.audit_log_writer import AuditEvent


def _make_timestamp() -> str:
    """Generate ISO 8601 timestamp with millisecond precision."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z"


def _read_all_entries(writer: JsonlAuditLogWriter) -> list[dict]:
    """Read all entries from the writer's current log file."""
    log_file = writer._get_log_file()
    entries = []
    if log_file.exists():
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return entries


def _read_entries_by_step_path(
    writer: JsonlAuditLogWriter, step_path: str
) -> list[dict]:
    """Read entries filtered by step_path data field (legacy filtering)."""
    return [e for e in _read_all_entries(writer) if e.get("step_path") == step_path]


class TestAuditTrailForComplianceVerification:
    """E2E acceptance tests for US-004: Audit trail for compliance verification."""

    # =========================================================================
    # AC-004.1: All state transitions are logged with ISO timestamp
    # Scenario 1: State transitions capture accurate timestamps
    # =========================================================================

    def test_scenario_001_state_transitions_logged_with_iso_timestamp(self, tmp_path):
        """
        GIVEN DES is processing step 01-01 through TDD phases
        WHEN each phase transition occurs (NOT_EXECUTED -> IN_PROGRESS -> EXECUTED)
        THEN audit log contains entry with ISO 8601 timestamp for each transition

        Business Value: Priya can verify exact execution timeline during PR review,
                       proving phases were executed in correct order at specific times.

        ISO 8601 Format Required: YYYY-MM-DDTHH:MM:SS.sssZ (e.g., 2026-01-22T14:30:45.123Z)
        """
        # Arrange: Create audit log writer
        writer = JsonlAuditLogWriter(log_dir=str(tmp_path))
        step_file = "steps/01-01.json"

        # Act: Simulate phase transitions
        writer.log_event(
            AuditEvent(
                event_type="PHASE_STARTED",
                timestamp=_make_timestamp(),
                data={
                    "step_path": step_file,
                    "phase": "PREPARE",
                    "status": "IN_PROGRESS",
                },
            )
        )
        writer.log_event(
            AuditEvent(
                event_type="PHASE_COMPLETED",
                timestamp=_make_timestamp(),
                data={
                    "step_path": step_file,
                    "phase": "PREPARE",
                    "status": "EXECUTED",
                },
            )
        )

        # Assert: Audit log contains timestamped entries
        audit_entries = _read_entries_by_step_path(writer, step_file)
        assert len(audit_entries) >= 2, (
            "At least 2 phase transition events should be logged"
        )

        # Verify ISO 8601 timestamp format for each entry
        for entry in audit_entries:
            assert "timestamp" in entry, "Entry missing timestamp field"
            timestamp = entry["timestamp"]

            # Validate ISO 8601 format: YYYY-MM-DDTHH:MM:SS.sssZ
            assert isinstance(timestamp, str), "Timestamp not a string"
            assert "T" in timestamp, "Timestamp missing 'T' separator"
            assert timestamp.endswith("Z"), "Timestamp not ending with 'Z' (UTC)"
            assert len(timestamp) == 24, (
                f"ISO 8601 timestamp should be 24 chars, got {len(timestamp)}: {timestamp}"
            )

            # Should be parseable as ISO 8601
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                assert parsed is not None, "Timestamp could not be parsed"
            except ValueError as e:
                pytest.fail(f"Timestamp not valid ISO 8601: {timestamp} - {e}")

    # =========================================================================
    # AC-004.2: Audit log is append-only (no modifications to existing entries)
    # Scenario 2: Audit entries are immutable
    # =========================================================================

    def test_scenario_002_audit_log_is_append_only_immutable(self, tmp_path):
        """
        GIVEN audit log contains 5 existing entries from previous executions
        WHEN new execution occurs adding 3 more entries
        THEN original 5 entries remain unchanged (byte-level prefix matches)

        Business Value: Priya can trust audit evidence has not been tampered with,
                       ensuring accountability and preventing retroactive falsification.

        Immutability Guarantee: Existing entries cannot be modified or deleted.
        """
        # Arrange: Create audit log with 5 initial entries
        writer = JsonlAuditLogWriter(log_dir=str(tmp_path))
        initial_entries = [
            AuditEvent(
                event_type="TASK_INVOCATION_STARTED",
                timestamp="2026-01-22T10:00:00.000Z",
                data={},
            ),
            AuditEvent(
                event_type="PHASE_STARTED",
                timestamp="2026-01-22T10:00:05.000Z",
                data={"phase": "PREPARE"},
            ),
            AuditEvent(
                event_type="PHASE_COMPLETED",
                timestamp="2026-01-22T10:01:00.000Z",
                data={"phase": "PREPARE"},
            ),
            AuditEvent(
                event_type="PHASE_STARTED",
                timestamp="2026-01-22T10:01:05.000Z",
                data={"phase": "RED_ACCEPTANCE"},
            ),
            AuditEvent(
                event_type="PHASE_COMPLETED",
                timestamp="2026-01-22T10:02:00.000Z",
                data={"phase": "RED_ACCEPTANCE"},
            ),
        ]
        for event in initial_entries:
            writer.log_event(event)

        # Capture byte content of original 5 entries
        log_file = writer._get_log_file()
        with open(log_file, "rb") as f:
            original_bytes = f.read()

        initial_count = len(_read_all_entries(writer))
        assert initial_count == 5, f"Expected 5 initial entries, got {initial_count}"

        # Act: Add 3 new entries
        new_events = [
            AuditEvent(
                event_type="PHASE_STARTED",
                timestamp="2026-01-22T10:02:05.000Z",
                data={"phase": "RED_UNIT"},
            ),
            AuditEvent(
                event_type="PHASE_COMPLETED",
                timestamp="2026-01-22T10:03:00.000Z",
                data={"phase": "RED_UNIT"},
            ),
            AuditEvent(
                event_type="SUBAGENT_STOP_VALIDATION",
                timestamp="2026-01-22T10:03:05.000Z",
                data={"status": "success"},
            ),
        ]
        for event in new_events:
            writer.log_event(event)

        # Assert: Original entries unchanged (byte-level prefix matches)
        with open(log_file, "rb") as f:
            current_bytes = f.read()

        original_byte_count = len(original_bytes)
        assert current_bytes[:original_byte_count] == original_bytes, (
            "Original entries were modified - immutability violated"
        )
        assert len(_read_all_entries(writer)) == 8, (
            f"Expected 8 entries (5 original + 3 new), got {len(_read_all_entries(writer))}"
        )

        # Verify new entries are present
        all_entries = _read_all_entries(writer)
        assert len(all_entries) == 8, "All entries should be readable"
        assert all_entries[5]["event"] == "PHASE_STARTED"
        assert all_entries[6]["event"] == "PHASE_COMPLETED"
        assert all_entries[7]["event"] == "SUBAGENT_STOP_VALIDATION"
