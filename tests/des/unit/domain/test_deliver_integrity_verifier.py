"""Unit tests for Deliver Integrity Verifier.

Tests that roadmap steps are cross-referenced against execution-log entries
to detect steps implemented without DES monitoring.
"""

import pytest

from des.domain.deliver_integrity_verifier import (
    DeliverIntegrityVerifier,
)
from des.domain.deliver_progress_tracker import DeliverProgressState


REQUIRED_PHASES = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "REVIEW",
    "REFACTOR_CONTINUOUS",
    "COMMIT",
]


class TestDeliverIntegrityVerifier:
    """Unit tests for DeliverIntegrityVerifier."""

    @pytest.fixture
    def verifier(self):
        return DeliverIntegrityVerifier(required_phases=REQUIRED_PHASES)

    def test_all_steps_complete_is_valid(self, verifier):
        """All steps with 7 phases should be valid."""
        roadmap_steps = ["01-01", "01-02"]
        execution_log_entries = {
            "01-01": REQUIRED_PHASES.copy(),
            "01-02": REQUIRED_PHASES.copy(),
        }
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is True
        assert result.steps_verified == 2
        assert result.violations == []

    def test_missing_step_is_violation(self, verifier):
        """Step in roadmap but not in execution-log should be a violation."""
        roadmap_steps = ["01-01", "01-02"]
        execution_log_entries = {
            "01-01": REQUIRED_PHASES.copy(),
            # 01-02 missing entirely
        }
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].step_id == "01-02"
        assert result.violations[0].has_execution_log is False
        assert result.violations[0].phase_count == 0

    def test_partial_phases_is_violation(self, verifier):
        """Step with 4/7 phases should be a violation with missing phases listed."""
        roadmap_steps = ["01-01"]
        execution_log_entries = {
            "01-01": ["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN"],
        }
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is False
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.step_id == "01-01"
        assert v.has_execution_log is True
        assert v.phase_count == 4
        assert "REVIEW" in v.missing_phases
        assert "REFACTOR_CONTINUOUS" in v.missing_phases
        assert "COMMIT" in v.missing_phases

    def test_no_entries_flagged_as_no_des(self, verifier):
        """Step with zero entries should be flagged as 'implemented without DES'."""
        roadmap_steps = ["01-01"]
        execution_log_entries = {}
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is False
        assert "without DES" in (result.reason or "")

    def test_empty_roadmap_is_valid(self, verifier):
        """No steps to verify should be valid."""
        result = verifier.verify([], {})
        assert result.is_valid is True
        assert result.steps_verified == 0

    def test_violation_reason_contains_step_ids(self, verifier):
        """Reason string should include violating step IDs."""
        roadmap_steps = ["01-01", "02-01"]
        execution_log_entries = {}
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is False
        assert "01-01" in (result.reason or "")
        assert "02-01" in (result.reason or "")

    def test_multiple_violations_reported(self, verifier):
        """Multiple violating steps should all be reported."""
        roadmap_steps = ["01-01", "01-02", "01-03"]
        execution_log_entries = {
            "01-01": REQUIRED_PHASES.copy(),
            # 01-02 and 01-03 missing
        }
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is False
        assert len(result.violations) == 2
        violation_step_ids = [v.step_id for v in result.violations]
        assert "01-02" in violation_step_ids
        assert "01-03" in violation_step_ids

    def test_extra_steps_in_log_ignored(self, verifier):
        """Execution-log entries for unknown steps should be ignored."""
        roadmap_steps = ["01-01"]
        execution_log_entries = {
            "01-01": REQUIRED_PHASES.copy(),
            "99-99": REQUIRED_PHASES.copy(),  # not in roadmap
        }
        result = verifier.verify(roadmap_steps, execution_log_entries)
        assert result.is_valid is True
        assert result.steps_verified == 1


class TestCheckPhaseProgress:
    """Tests for check_phase_progress — orchestrator phase completion check."""

    @pytest.fixture
    def verifier(self):
        return DeliverIntegrityVerifier(required_phases=REQUIRED_PHASES)

    def test_warns_when_all_steps_done_but_phases_not_recorded(self, verifier):
        """AC1: all_steps_done=True + empty phases_completed -> warnings for phases 3-5."""
        progress = DeliverProgressState(
            project_id="test-feature",
            total_steps=3,
            completed_steps=3,
            all_steps_done=True,
            phases_completed={},
        )
        warnings = verifier.check_phase_progress(progress)
        assert len(warnings) == 3
        assert any("3" in w for w in warnings)
        assert any("4" in w for w in warnings)
        assert any("5" in w for w in warnings)

    def test_no_warnings_when_all_phases_recorded(self, verifier):
        """AC2: all_steps_done=True + phases 3,4,5 present -> no warnings."""
        progress = DeliverProgressState(
            project_id="test-feature",
            total_steps=3,
            completed_steps=3,
            all_steps_done=True,
            phases_completed={
                "3": "2026-03-16T10:00:00Z",
                "4": "2026-03-16T11:00:00Z",
                "5": "2026-03-16T12:00:00Z",
            },
        )
        warnings = verifier.check_phase_progress(progress)
        assert warnings == []

    def test_skips_check_when_progress_state_is_none(self, verifier):
        """AC3: no progress file -> None -> skip check, no error."""
        warnings = verifier.check_phase_progress(None)
        assert warnings == []

    def test_skips_check_when_not_all_steps_done(self, verifier):
        """Check only applies after all steps done; partial progress -> no warnings."""
        progress = DeliverProgressState(
            project_id="test-feature",
            total_steps=3,
            completed_steps=1,
            all_steps_done=False,
            phases_completed={},
        )
        warnings = verifier.check_phase_progress(progress)
        assert warnings == []

    def test_warns_only_for_missing_phases(self, verifier):
        """AC1 variant: only phase 5 missing -> exactly 1 warning mentioning phase 5."""
        progress = DeliverProgressState(
            project_id="test-feature",
            total_steps=2,
            completed_steps=2,
            all_steps_done=True,
            phases_completed={
                "3": "2026-03-16T10:00:00Z",
                "4": "2026-03-16T11:00:00Z",
            },
        )
        warnings = verifier.check_phase_progress(progress)
        assert len(warnings) == 1
        assert "5" in warnings[0]
