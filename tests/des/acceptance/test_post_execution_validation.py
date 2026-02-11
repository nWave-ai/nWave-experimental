"""
E2E Acceptance Test: US-003 Post-Execution State Validation (Schema v2.0)

PERSONA: Marcus (Senior Developer)
STORY: As a senior developer, I want DES to automatically detect when phases are
       left abandoned (IN_PROGRESS) after sub-agent completion, so that I'm
       immediately alerted to incomplete work instead of discovering it hours later.

BUSINESS VALUE:
- Detects crashed agents before developers waste debugging time
- Catches silent completions where agent returned without updating state
- Validates execution integrity with specific, actionable error messages
- Enables immediate intervention instead of hours-later discovery

SCOPE: Covers US-003 Acceptance Criteria (AC-003.1 through AC-003.6)
WAVE: DISTILL (Acceptance Test Creation)
STATUS: Migrated to Schema v2.0 (execution-log.yaml format)

TEST BOUNDARY: External protocol (JSON stdin, exit code, JSON stdout).
Tests invoke the hook adapter as a subprocess, matching Claude Code's actual
integration protocol. Internal classes are implementation details.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


# =============================================================================
# TEST HELPER: Invoke hook through external protocol boundary
# =============================================================================


def invoke_hook(hook_type: str, payload: dict) -> tuple[int, dict]:
    """Invoke hook adapter through its external protocol (subprocess + JSON).

    This is the public interface that Claude Code uses:
    - JSON on stdin
    - Exit code: 0=allow, 1=error, 2=block
    - JSON on stdout

    Args:
        hook_type: Hook command name (e.g., "subagent-stop", "pre-task")
        payload: JSON-serializable dict to send on stdin

    Returns:
        Tuple of (exit_code, response_dict)
    """
    env = os.environ.copy()
    project_root = str(Path(__file__).parent.parent.parent.parent)
    src_path = str(Path(project_root) / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            hook_type,
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    response = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, response


# =============================================================================
# DEVELOP WAVE MAPPING
# =============================================================================
#
# All 8 scenarios map to single DEVELOP step:
#   Step: "Implement SubagentStop validation hook"
#
# Each scenario represents a VALIDATION RULE the hook must enforce:
#   - Scenario 1: Hook fires on completion (AC-003.1)
#   - Scenario 2: Abandoned phases detected (AC-003.2)
#   - Scenario 3: Silent completion flagged (AC-003.3)
#   - Scenario 4: Missing outcome detected (AC-003.4)
#   - Scenario 5: Invalid skip detected (AC-003.5)
#   - Scenario 6: Multiple errors with recovery (AC-003.6)
#   - Scenario 7: Clean completion passes (happy path)
#   - Scenario 8: Valid skip passes (happy path)
#
# Recovery Suggestion Quality Requirements:
#   - Each suggestion >= 1 complete sentence (20+ chars)
#   - At least one explains WHY error occurred
#   - At least one explains HOW to fix
#   - Example: "Phase GREEN_UNIT left IN_PROGRESS because agent crashed.
#              Run `/nw:execute @software-crafter steps/01-01.json` to resume."
# =============================================================================


class TestPostExecutionStateValidation:
    """E2E acceptance tests for US-003: Post-execution state validation (Schema v2.0).

    All tests invoke the hook adapter through its external protocol boundary:
    JSON on stdin -> subprocess -> exit code + JSON on stdout.
    This matches Claude Code's actual integration and survives internal refactoring.
    """

    # =========================================================================
    # AC-003.1: SubagentStop hook fires for every sub-agent completion
    # Scenario 1: SubagentStop hook invoked on agent completion
    # =========================================================================

    def test_subagent_stop_hook_fires_on_agent_completion(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN software-crafter agent completes step 01-01 execution
        WHEN the sub-agent returns control to orchestrator
        THEN SubagentStop hook fires and validates execution-log state

        Business Value: Marcus receives immediate feedback on execution state
                       the moment an agent completes, preventing silent failures
                       from going unnoticed until the next day.

        Domain Example: Software-crafter finishes step 01-01, hook validates
                       that all started phases were properly completed.
        """
        # Arrange: Create execution-log.yaml with completed execution (Schema v2.0)
        log_data = _create_execution_log_with_all_phases_executed(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol (JSON stdin, exit code, JSON stdout)
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Hook fired and validation passed
        assert exit_code == 0, f"Expected allow (exit 0), got {exit_code}: {response}"
        assert response["decision"] == "allow"

    # =========================================================================
    # AC-003.2: Phases with status "IN_PROGRESS" after completion are flagged
    # Scenario 2: Abandoned phase detected after agent crash
    # =========================================================================

    def test_abandoned_in_progress_phase_detected(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN software-crafter agent crashed during GREEN phase
        AND execution-log.yaml shows GREEN phase never logged (missing from events)
        WHEN SubagentStop hook fires after agent process terminates
        THEN hook detects abandoned phase and flags it with specific error

        Business Value: Marcus is immediately alerted when an agent crashes
                       mid-execution, avoiding 2+ hours of debugging time
                       discovering the issue the next day.

        Domain Example: Agent was implementing GREEN, crashed due to
                       network error. GREEN phase never appears in event log,
                       indicating work was started but never completed.

        Error Format: "Missing phases: GREEN" (in v2.0, abandoned = missing from log)
        """
        # Arrange: Create execution-log.yaml with abandoned phase (Schema v2.0)
        log_data = _create_execution_log_with_abandoned_phase(
            tdd_phases, abandoned_phase="GREEN", last_completed_phase="RED_UNIT"
        )
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Abandoned phase detected with specific error
        # Exit 0 so Claude Code processes JSON (exit 2 ignores stdout)
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"
        assert "GREEN" in response["reason"]
        assert "Missing phases" in response["reason"]

    # =========================================================================
    # AC-003.3: Tasks marked "DONE" with "NOT_EXECUTED" phases are flagged
    # Scenario 3: Silent completion detected (agent returned without executing)
    # =========================================================================

    def test_done_task_with_not_executed_phases_flagged(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN software-crafter agent returned without updating execution-log
        AND events list is empty (no phases logged)
        WHEN SubagentStop hook fires
        THEN hook detects mismatch and flags as silent completion error

        Business Value: Marcus catches agents that claimed to work but
                       actually did nothing, preventing false confidence
                       in task completion.

        Domain Example: Agent received step 01-01 but encountered an error
                       early and returned without logging any phases.
                       Events list is empty.

        Error Format: All phases listed as missing in the error reason
        """
        # Arrange: Create execution-log.yaml with no events (Schema v2.0)
        log_data = _create_execution_log_with_silent_completion()
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Silent completion detected - all phases missing
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"
        assert "Missing phases" in response["reason"]
        # All TDD phases should appear in the missing phases list
        for phase in tdd_phases:
            assert phase in response["reason"], (
                f"Phase {phase} should be listed as missing in: {response['reason']}"
            )
        # Recovery guidance provided in hook output
        additional_context = response.get("hookSpecificOutput", {}).get(
            "additionalContext", ""
        )
        assert "RECOVERY REQUIRED" in additional_context

    # =========================================================================
    # AC-003.4: "EXECUTED" phases without outcome field are flagged
    # Scenario 4: Incomplete phase execution detected (no outcome recorded)
    # =========================================================================

    def test_executed_phase_without_outcome_flagged(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml shows GREEN phase with status "EXECUTED"
        AND the phase has invalid outcome (empty string instead of PASS/FAIL)
        WHEN SubagentStop hook validates the execution log
        THEN hook flags the phase as incomplete execution

        Business Value: Marcus ensures all executed phases have documented
                       outcomes, maintaining audit trail for Priya's PR reviews
                       and preventing "I finished but didn't record what I did"
                       situations.

        Domain Example: Agent marked GREEN as EXECUTED but forgot to
                       record outcome. Without valid outcome, there's no evidence
                       of work completion.

        Error Format: "Invalid outcome ''"  (in v2.0, outcome is in data field)
        """
        # Arrange: Create execution-log.yaml with EXECUTED phase with invalid outcome
        log_data = _create_execution_log_with_missing_outcome(tdd_phases, "GREEN")
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Missing outcome detected
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"
        assert "GREEN" in response["reason"]
        assert "Invalid outcome" in response["reason"]

    # =========================================================================
    # AC-003.5: "SKIPPED" phases must have valid `blocked_by` reason
    # Scenario 5: Skipped phase with missing blocked_by reason flagged
    # =========================================================================

    def test_skipped_phase_without_blocked_by_reason_flagged(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml shows GREEN phase with status "SKIPPED"
        AND the phase has invalid skip reason (no valid prefix)
        WHEN SubagentStop hook validates the execution log
        THEN hook flags the skip as invalid (must have valid prefix)

        Business Value: Marcus ensures all skipped phases have documented
                       reasons, preventing arbitrary phase skipping without
                       justification. Priya can verify during PR review that
                       skips were legitimate.

        Domain Example: Agent skipped GREEN but didn't provide valid reason.
                       Without valid prefix (BLOCKED_BY_DEPENDENCY,
                       NOT_APPLICABLE, APPROVED_SKIP, etc.), we can't verify
                       if skip was legitimate.

        Error Format: "Invalid skip reason" (in v2.0, must start with valid prefix)
        """
        # Arrange: Create execution-log.yaml with SKIPPED phase with invalid reason
        log_data = _create_execution_log_with_invalid_skip(tdd_phases, "GREEN")
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Invalid skip detected
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"
        assert "GREEN" in response["reason"]
        assert "skip reason" in response["reason"].lower()

    # =========================================================================
    # AC-003.6: Validation errors trigger FAILED state with recovery suggestions
    # Scenario 6: Multiple validation errors trigger FAILED state
    # =========================================================================

    def test_validation_errors_trigger_failed_state_with_recovery(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml has multiple issues:
          - Missing phases (abandoned)
          - Invalid outcome (incomplete)
          - Invalid skip reason
        WHEN SubagentStop hook validates the execution log
        THEN validation status is FAILED with all errors listed
        AND recovery suggestions are provided for each error type

        Business Value: Marcus receives comprehensive failure report with
                       clear recovery path, enabling immediate resolution
                       without guesswork.

        Domain Example: Agent only logged first 3 phases, then crashed.
                       One phase has invalid outcome, another has invalid skip.
                       All issues reported together with recovery steps.

        Recovery Suggestions Expected:
        - "Resume execution to complete missing phases"
        - "Fix invalid phase entries in execution-log.yaml"
        - "Ensure EXECUTED phases have PASS/FAIL outcome"
        """
        # Arrange: Create execution-log.yaml with multiple validation issues
        log_data = _create_execution_log_with_multiple_issues(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: FAILED state set with comprehensive error reporting
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"

        # Assert: Multiple issue types captured in reason
        reason = response["reason"]
        assert "Missing phases" in reason, "Should report abandoned/missing phases"
        assert "Invalid" in reason, "Should report invalid phases (outcome or skip)"

        # Assert: Recovery suggestions provided in hook output
        additional_context = response.get("hookSpecificOutput", {}).get(
            "additionalContext", ""
        )
        assert "RECOVERY REQUIRED" in additional_context

        # CONTENT: Specific recovery guidance with numbered steps
        assert "1." in additional_context, "Recovery steps should be numbered"

        # Recovery suggestions should be actionable
        context_lower = additional_context.lower()
        assert any(
            keyword in context_lower
            for keyword in ["fix", "ensure", "append", "format"]
        ), "Should provide actionable recovery guidance"

    # =========================================================================
    # Happy Path: Clean completion passes validation silently
    # Scenario 7: All phases executed correctly - validation passes
    # =========================================================================

    def test_clean_completion_passes_validation(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN software-crafter agent completes all 5 phases successfully
        AND each phase shows "EXECUTED" with valid outcome (PASS)
        WHEN SubagentStop hook validates the execution log
        THEN validation passes successfully

        Business Value: Marcus confirms that properly completed steps are
                       validated silently without unnecessary alerts, allowing
                       smooth workflow continuation.

        Domain Example: Agent executed all 5 phases (PREPARE through COMMIT),
                       each with PASS outcome. Validation confirms integrity
                       and logs success.
        """
        # Arrange: Create execution-log.yaml with clean, complete execution
        log_data = _create_execution_log_with_clean_completion(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Validation passes silently
        assert exit_code == 0, f"Expected allow (exit 0), got {exit_code}: {response}"
        assert response["decision"] == "allow"

    # =========================================================================
    # Edge Case: Valid skip with proper blocked_by reason passes
    # Scenario 8: Legitimately skipped phases pass validation
    # =========================================================================

    def test_valid_skip_with_blocked_by_passes_validation(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml shows GREEN phase with status "SKIPPED"
        AND the phase has valid skip reason with APPROVED_SKIP prefix
        WHEN SubagentStop hook validates the execution log
        THEN validation passes (skip is legitimate)

        Business Value: Marcus confirms that legitimate skips with proper
                       justification are accepted, not flagged as errors.
                       Allows appropriate phase skipping when conditions warrant.

        Domain Example: Agent determined GREEN tests already pass. Properly
                       documented with APPROVED_SKIP prefix:
                       "APPROVED_SKIP:Code already meets quality standards"
        """
        # Arrange: Create execution-log.yaml with legitimately skipped phase
        log_data = _create_execution_log_with_valid_skip(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke hook through external protocol
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
            },
        )

        # Assert: Valid skip accepted
        assert exit_code == 0, f"Expected allow (exit 0), got {exit_code}: {response}"
        assert response["decision"] == "allow"


# =============================================================================
# Test Data Builders (Helper Functions)
# =============================================================================


def _create_execution_log_with_all_phases_complete(tdd_phases):
    """Create execution-log.yaml data where all 5 phases are EXECUTED with PASS (Schema v2.0)."""
    events = []
    for phase in tdd_phases:
        events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_missing_phases(tdd_phases, phases_to_include):
    """Create execution-log.yaml with only some phases (simulates incomplete execution - Schema v2.0).

    Args:
        tdd_phases: List of all canonical TDD phase names
        phases_to_include: List of phase names to include in events (others will be missing)
    """
    events = []
    for phase in tdd_phases:
        if phase in phases_to_include:
            events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_no_phases():
    """Create execution-log.yaml with empty events (no phases executed - Schema v2.0)."""
    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": [],  # No phases executed
    }


def _create_step_file_with_missing_outcome(phase_name: str):
    """Create step file with EXECUTED phase missing outcome field."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    target_idx = phases.index(phase_name)

    phase_log = []
    for i, phase in enumerate(phases):
        if i <= target_idx:
            status = "EXECUTED"
            # Missing outcome for target phase
            outcome = None if phase == phase_name else "PASS"
            outcome_details = None if phase == phase_name else f"{phase} completed"
        else:
            status = "NOT_EXECUTED"
            outcome = None
            outcome_details = None

        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": status,
                "outcome": outcome,
                "outcome_details": outcome_details,
                "blocked_by": None,
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "IN_PROGRESS",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": None,
        },
        "tdd_cycle": {"phase_execution_log": phase_log},
    }


def _create_step_file_with_invalid_skip(skipped_phase: str):
    """Create step file with SKIPPED phase missing blocked_by reason."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    target_idx = phases.index(skipped_phase)

    phase_log = []
    for i, phase in enumerate(phases):
        if i < target_idx:
            status = "EXECUTED"
            outcome = "PASS"
        elif phase == skipped_phase:
            status = "SKIPPED"
            outcome = "SKIPPED"
        elif i > target_idx:
            status = "EXECUTED"
            outcome = "PASS"
        else:
            status = "EXECUTED"
            outcome = "PASS"

        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": status,
                "outcome": outcome,
                "outcome_details": f"{phase} completed"
                if status == "EXECUTED"
                else None,
                "blocked_by": None,  # Missing blocked_by for skipped phase!
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "DONE",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": "2026-01-22T11:30:00Z",
        },
        "tdd_cycle": {"phase_execution_log": phase_log},
    }


def _create_step_file_with_multiple_issues():
    """Create step file with multiple validation issues."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    phase_log = []
    for i, phase in enumerate(phases):
        if phase == "GREEN_UNIT":
            # Issue 1: Abandoned IN_PROGRESS phase
            status = "IN_PROGRESS"
            outcome = None
            outcome_details = None
        elif phase == "REVIEW":
            # Issue 2: EXECUTED but missing outcome
            status = "EXECUTED"
            outcome = None
            outcome_details = None
        elif phases.index(phase) < phases.index("GREEN_UNIT"):
            status = "EXECUTED"
            outcome = "PASS"
            outcome_details = f"{phase} completed"
        else:
            status = "NOT_EXECUTED"
            outcome = None
            outcome_details = None

        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": status,
                "outcome": outcome,
                "outcome_details": outcome_details,
                "blocked_by": None,
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "IN_PROGRESS",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": None,
        },
        "tdd_cycle": {"phase_execution_log": phase_log},
    }


def _create_step_file_with_timeout_exceeded():
    """Create step file where total execution duration exceeds configured time limit."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    # Set timeout limits: 5 minutes base + 2 minutes extensions = 7 minutes = 420 seconds
    # Set actual duration: 8 minutes = 480 seconds (exceeds limit by 60 seconds)
    phase_log = []
    duration_per_phase = 480 // len(phases)  # ~34 seconds per phase

    for i, phase in enumerate(phases):
        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": "EXECUTED",
                "outcome": "PASS",
                "outcome_details": f"{phase} completed",
                "duration_seconds": duration_per_phase,
                "blocked_by": None,
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "DONE",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": "2026-01-22T10:08:00Z",
        },
        "tdd_cycle": {
            "duration_minutes": 5,
            "total_extensions_minutes": 2,
            "phase_execution_log": phase_log,
        },
    }


def _create_step_file_with_missing_limits():
    """Create step file missing required max_turns and duration_minutes configuration."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    phase_log = []
    for i, phase in enumerate(phases):
        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": "EXECUTED",
                "outcome": "PASS",
                "outcome_details": f"{phase} completed",
                "blocked_by": None,
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "DONE",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": "2026-01-22T11:30:00Z",
        },
        "tdd_cycle": {
            # Missing max_turns and duration_minutes fields!
            "phase_execution_log": phase_log
        },
    }


def _create_step_file_with_valid_skip():
    """Create step file with legitimately skipped phase (has blocked_by)."""
    phases = [
        "PREPARE",
        "RED_ACCEPTANCE",
        "RED_UNIT",
        "GREEN_UNIT",
        "CHECK_ACCEPTANCE",
        "GREEN_ACCEPTANCE",
        "REVIEW",
        "REFACTOR_L1",
        "REFACTOR_L2",
        "REFACTOR_L3",
        "REFACTOR_L4",
        "POST_REFACTOR_REVIEW",
        "FINAL_VALIDATE",
        "COMMIT",
    ]

    phase_log = []
    for i, phase in enumerate(phases):
        if phase == "REFACTOR_L2":
            # Legitimately skipped with proper reason
            status = "SKIPPED"
            outcome = "SKIPPED"
            outcome_details = "No L2 complexity detected"
            blocked_by = "Code already meets L2 quality standards - no complexity, responsibility, or abstraction issues"
        else:
            status = "EXECUTED"
            outcome = "PASS"
            outcome_details = f"{phase} completed successfully"
            blocked_by = None

        phase_log.append(
            {
                "phase_number": i,
                "phase_name": phase,
                "status": status,
                "outcome": outcome,
                "outcome_details": outcome_details,
                "blocked_by": blocked_by,
            }
        )

    return {
        "task_id": "01-01",
        "project_id": "test-project",
        "workflow_type": "tdd_cycle",
        "state": {
            "status": "DONE",
            "started_at": "2026-01-22T10:00:00Z",
            "completed_at": "2026-01-22T11:30:00Z",
        },
        "tdd_cycle": {"phase_execution_log": phase_log},
    }


# =============================================================================
# WIRING TESTS: Validation through DESOrchestrator Entry Point (CM-A/CM-D)
# =============================================================================
# These tests invoke validation through the system entry point (DESOrchestrator)
# instead of directly instantiating SubagentStopHook. This ensures the
# integration is wired correctly and prevents "Testing Theatre" where tests
# pass but the feature is not actually connected to the system.
# =============================================================================


@pytest.mark.skip(
    reason="Internal SubagentStopHook wiring test, needs hexagonal service rewrite"
)
class TestOrchestratorHookIntegration:
    """
    Integration tests that verify SubagentStopHook is wired into DESOrchestrator.

    These tests exercise the ENTRY POINT (DESOrchestrator) rather than the
    internal component (SubagentStopHook) directly. This is the 10% E2E test
    that proves the wiring works (per CM-D 90/10 rule).
    """

    def test_orchestrator_invokes_subagent_stop_hook_on_completion(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml with completed execution (all phases EXECUTED)
        WHEN on_subagent_complete is called through DESOrchestrator entry point
        THEN the SubagentStopHook fires and returns validation result

        WIRING TEST: Proves SubagentStopHook is integrated into orchestrator.
        This test would FAIL if the import or delegation is missing.
        """
        # Arrange: Import entry point and real hook adapter
        from unittest.mock import Mock

        from des.adapters.driven.filesystem.real_filesystem import RealFileSystem

        # from des.adapters.driven.hooks.subagent_stop_hook import SubagentStopHook  # Legacy
        from des.adapters.driven.time.system_time import SystemTimeProvider
        from des.application.orchestrator import DESOrchestrator
        from des.application.validator import TemplateValidator

        # Create execution-log.yaml with clean completion (Schema v2.0)
        log_data = _create_execution_log_with_clean_completion(tdd_phases)
        minimal_step_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke validation through ENTRY POINT with real SubagentStopHook
        time_provider = SystemTimeProvider()
        orchestrator = DESOrchestrator(
            hook=SubagentStopHook(audit_logger=Mock(), time_provider=time_provider),
            validator=TemplateValidator(),
            filesystem=RealFileSystem(),
            time_provider=time_provider,
        )
        compound_path = f"{minimal_step_file}?project_id=test-project&step_id=01-01"
        result = orchestrator.on_subagent_complete(step_file_path=compound_path)

        # Assert: Hook fired through wired integration
        assert result.validation_status == "PASSED"
        assert result.abandoned_phases == []
        assert result.error_count == 0

    def test_orchestrator_detects_abandoned_phase_via_entry_point(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN execution-log.yaml with abandoned phase (missing from events)
        WHEN on_subagent_complete is called through DESOrchestrator entry point
        THEN validation fails and abandoned phase is reported

        WIRING TEST: Proves validation logic is executed through orchestrator,
        not just returning success by default.
        """
        # Arrange: Import entry point and real hook adapter
        from unittest.mock import Mock

        from des.adapters.driven.filesystem.real_filesystem import RealFileSystem

        # from des.adapters.driven.hooks.subagent_stop_hook import SubagentStopHook  # Legacy
        from des.adapters.driven.time.system_time import SystemTimeProvider
        from des.application.orchestrator import DESOrchestrator
        from des.application.validator import TemplateValidator

        # Create execution-log.yaml with abandoned phase (Schema v2.0)
        log_data = _create_execution_log_with_abandoned_phase(
            tdd_phases, abandoned_phase="GREEN", last_completed_phase="RED_UNIT"
        )
        minimal_step_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke validation through ENTRY POINT with real SubagentStopHook
        time_provider = SystemTimeProvider()
        orchestrator = DESOrchestrator(
            hook=SubagentStopHook(audit_logger=Mock(), time_provider=time_provider),
            validator=TemplateValidator(),
            filesystem=RealFileSystem(),
            time_provider=time_provider,
        )
        compound_path = f"{minimal_step_file}?project_id=test-project&step_id=01-01"
        result = orchestrator.on_subagent_complete(step_file_path=compound_path)

        # Assert: Validation fails through wired validator
        assert result.validation_status == "FAILED"
        assert "GREEN" in result.abandoned_phases
        assert result.error_count > 0


# =============================================================================
# Schema v2.0 Helper Functions (execution-log.yaml format)
# =============================================================================


def _create_execution_log_with_all_phases_executed(tdd_phases):
    """Create execution-log.yaml with all phases EXECUTED with PASS (Schema v2.0)."""
    events = []
    for phase in tdd_phases:
        events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_abandoned_phase(
    tdd_phases, abandoned_phase, last_completed_phase
):
    """Create execution-log.yaml where a phase is missing (simulates abandoned IN_PROGRESS - Schema v2.0).

    In v2.0, there's no IN_PROGRESS status in append-only log.
    Abandoned phase = phase never appears in events list.
    """
    events = []
    last_idx = tdd_phases.index(last_completed_phase)

    # Add events up to (and including) last completed phase
    for i, phase in enumerate(tdd_phases):
        if i <= last_idx:
            events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    # Abandoned phase and subsequent phases are NOT in events list

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_silent_completion():
    """Create execution-log.yaml with no events (simulates silent completion - Schema v2.0)."""
    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": [],  # No phases executed
    }


def _create_execution_log_with_missing_outcome(tdd_phases, phase_name):
    """Create execution-log.yaml where EXECUTED phase has invalid outcome (Schema v2.0).

    In v2.0, outcome is in the data field. Invalid outcome = not "PASS" or "FAIL".
    """
    events = []
    for phase in tdd_phases:
        if phase == phase_name:
            # Invalid outcome (empty string instead of PASS/FAIL)
            events.append(f"01-01|{phase}|EXECUTED||2026-02-02T10:00:00+00:00")
        else:
            events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_invalid_skip(tdd_phases, skipped_phase):
    """Create execution-log.yaml where SKIPPED phase has invalid reason (Schema v2.0).

    In v2.0, skip reason is in the data field. Invalid = no valid prefix.
    """
    events = []
    for phase in tdd_phases:
        if phase == skipped_phase:
            # Invalid skip reason (no valid prefix)
            events.append(
                f"01-01|{phase}|SKIPPED|No reason given|2026-02-02T10:00:00+00:00"
            )
        else:
            events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_multiple_issues(tdd_phases):
    """Create execution-log.yaml with multiple validation issues (Schema v2.0).

    Issues:
    - Missing phase (abandoned)
    - Invalid outcome (incomplete)
    - Invalid skip reason
    """
    events = []
    # Only add first 3 phases
    events.append(f"01-01|{tdd_phases[0]}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")
    events.append(f"01-01|{tdd_phases[1]}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")
    events.append(f"01-01|{tdd_phases[2]}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    # Phase 4 is missing (abandoned)

    # Phase 5 has invalid outcome
    if len(tdd_phases) > 4:
        events.append(f"01-01|{tdd_phases[4]}|EXECUTED||2026-02-02T10:00:00+00:00")

    # Phase 6 has invalid skip
    if len(tdd_phases) > 5:
        events.append(
            f"01-01|{tdd_phases[5]}|SKIPPED|Bad reason|2026-02-02T10:00:00+00:00"
        )

    # Remaining phases missing

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _create_execution_log_with_clean_completion(tdd_phases):
    """Create execution-log.yaml with all phases properly completed (Schema v2.0)."""
    return _create_execution_log_with_all_phases_executed(tdd_phases)


def _create_execution_log_with_valid_skip(tdd_phases):
    """Create execution-log.yaml with legitimately skipped phase (Schema v2.0).

    Uses APPROVED_SKIP prefix which is valid and doesn't block commit.
    Skips GREEN phase (index 3) with valid justification.
    """
    events = []
    for phase in tdd_phases:
        if phase == "GREEN":
            events.append(
                f"01-01|{phase}|SKIPPED|APPROVED_SKIP:Code already meets quality standards|2026-02-02T10:00:00+00:00"
            )
        else:
            events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-02T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-02T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }
