"""
E2E Acceptance Test: US-009 Dual-Layer DES Enforcement (SubagentStop + PostToolUse)

PERSONA: Orchestrator (Parent Agent)
STORY: As an orchestrator, I want deterministic notification when a sub-agent fails
       to complete TDD phases, so I can take corrective action.

BUSINESS VALUE:
- Layer 1 (SubagentStop): Blocks sub-agent on first attempt, allows on second to prevent loops
- Layer 2 (PostToolUse): Fires AFTER Task returns to parent, injects additionalContext if FAILED
- Together: Parent ALWAYS knows when a sub-agent failed, even if SubagentStop couldn't fix it

SCOPE: Covers US-009 Acceptance Criteria (AC-009.1 through AC-009.7)
WAVE: DISTILL (Acceptance Test Creation)

TEST BOUNDARY: External protocol (JSON stdin, exit code, JSON stdout).
Tests invoke the hook adapter as a subprocess, matching Claude Code's actual
integration protocol.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


# =============================================================================
# TEST HELPER: Invoke hook through external protocol boundary
# =============================================================================


def invoke_hook(hook_type: str, payload: dict) -> tuple[int, dict]:
    """Invoke hook adapter through its external protocol (subprocess + JSON).

    Args:
        hook_type: Hook command name (e.g., "subagent-stop", "post-tool-use")
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


def _seed_audit_log_entry(audit_dir: Path, entry: dict) -> None:
    """Write a single audit log entry to today's JSONL file.

    Pre-seeds the audit log so PostToolUse can read it.
    Uses same file naming convention as JsonlAuditLogWriter.

    Args:
        audit_dir: Directory for audit log files
        entry: Audit event dict to write
    """
    from datetime import datetime, timezone

    audit_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = audit_dir / f"audit-{today}.log"
    json_line = json.dumps(entry, separators=(",", ":"), sort_keys=True)
    with open(log_file, "a") as f:
        f.write(json_line + "\n")


# =============================================================================
# ACCEPTANCE TESTS
# =============================================================================


class TestDualLayerEnforcement:
    """E2E acceptance tests for US-009: Dual-layer DES enforcement.

    All tests invoke the hook adapter through its external protocol boundary:
    JSON on stdin -> subprocess -> exit code + JSON on stdout.
    """

    # =========================================================================
    # AC-009.1: SubagentStop blocks on first attempt (stop_hook_active=false)
    # Scenario 001
    # =========================================================================

    def test_subagent_stop_blocks_on_first_attempt(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN a sub-agent completes with missing TDD phases
        AND stop_hook_active is false (first attempt)
        WHEN SubagentStop hook fires
        THEN decision is "block" with exit code 0
        AND reason contains actionable instructions

        Business Value: Sub-agent gets one chance to fix missing phases
                       before being allowed through.
        """
        # Arrange: execution-log with only first 2 phases (missing rest)
        log_data = _create_incomplete_execution_log(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act: Invoke SubagentStop with stop_hook_active=false (default/first attempt)
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
                "stop_hook_active": False,
            },
        )

        # Assert: Block decision (sub-agent should try to fix)
        assert exit_code == 0, (
            f"Expected exit 0 with decision:block, got {exit_code}: {response}"
        )
        assert response["decision"] == "block"
        assert "Missing phases" in response["reason"]

    # =========================================================================
    # AC-009.2: SubagentStop allows on second attempt (stop_hook_active=true)
    # Scenario 002
    # =========================================================================

    def test_subagent_stop_allows_on_second_attempt(
        self, tmp_project_root, minimal_step_file, tdd_phases, tmp_path, monkeypatch
    ):
        """
        GIVEN a sub-agent completes with missing TDD phases
        AND stop_hook_active is true (second attempt, loop prevention)
        WHEN SubagentStop hook fires
        THEN decision is "allow" (prevent infinite loop)
        AND audit log records HOOK_SUBAGENT_STOP_FAILED with allowed_despite_failure

        Business Value: Prevents infinite SubagentStop loops while still
                       recording the failure for PostToolUse to pick up.
        """
        # Arrange: execution-log with missing phases
        log_data = _create_incomplete_execution_log(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Direct audit log to temp dir for verification
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        # Act: Invoke SubagentStop with stop_hook_active=true (second attempt)
        exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
                "stop_hook_active": True,
            },
        )

        # Assert: Allow decision (prevent loop)
        assert exit_code == 0, (
            f"Expected exit 0 with decision:allow, got {exit_code}: {response}"
        )
        assert response["decision"] == "allow"

        # Assert: Audit log records FAILED with allowed_despite_failure
        audit_entries = _read_audit_entries(audit_dir)
        failed_entries = [
            e for e in audit_entries if e.get("event") == "HOOK_SUBAGENT_STOP_FAILED"
        ]
        assert len(failed_entries) >= 1, (
            f"Expected HOOK_SUBAGENT_STOP_FAILED audit entry, got: {audit_entries}"
        )
        assert failed_entries[-1].get("allowed_despite_failure") is True

    # =========================================================================
    # AC-009.3: Block reason has actionable instructions
    # Scenario 003
    # =========================================================================

    def test_block_reason_has_actionable_instructions(
        self, tmp_project_root, minimal_step_file, tdd_phases
    ):
        """
        GIVEN a sub-agent completes with missing TDD phases
        AND stop_hook_active is false (first attempt)
        WHEN SubagentStop hook fires and blocks
        THEN reason mentions specific missing phases AND step_id
        AND reason contains recovery instructions

        Business Value: Sub-agent receives clear, actionable instructions
                       to complete the missing work.
        """
        # Arrange: execution-log with only first 2 phases
        log_data = _create_incomplete_execution_log(tdd_phases)
        log_file = tmp_project_root / "execution-log.yaml"
        log_file.write_text(yaml.dump(log_data, default_flow_style=False))

        # Act
        _exit_code, response = invoke_hook(
            "subagent-stop",
            {
                "executionLogPath": str(log_file),
                "projectId": "test-project",
                "stepId": "01-01",
                "stop_hook_active": False,
            },
        )

        # Assert: Block with actionable reason
        assert response["decision"] == "block"
        reason = response["reason"]
        assert "01-01" in reason, "Reason should mention step_id"
        assert "Missing phases" in reason, "Reason should mention missing phases"
        # Should mention at least one specific missing phase
        missing_phases = tdd_phases[2:]  # First 2 included, rest missing
        assert any(phase in reason for phase in missing_phases), (
            f"Reason should mention specific missing phases, got: {reason}"
        )

    # =========================================================================
    # AC-009.4: PostToolUse detects FAILED in audit log
    # Scenario 004
    # =========================================================================

    def test_post_tool_use_detects_failed_audit(self, tmp_path, monkeypatch):
        """
        GIVEN the audit log contains a HOOK_SUBAGENT_STOP_FAILED entry
        WHEN PostToolUse hook fires after Task returns to parent
        THEN response includes additionalContext with failure notification

        Business Value: Parent orchestrator is ALWAYS notified of sub-agent
                       failure, even when SubagentStop couldn't prevent it.
        """
        # Arrange: Pre-seed audit log with FAILED entry
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_FAILED",
                "timestamp": "2026-02-06T10:00:00+00:00",
                "feature_name": "test-project",
                "step_id": "01-01",
                "validation_errors": ["Missing phases: GREEN, REVIEW, COMMIT"],
                "allowed_despite_failure": True,
            },
        )

        # Act: Invoke PostToolUse
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {"prompt": "...", "subagent_type": "software-crafter"},
            },
        )

        # Assert: additionalContext injected
        assert exit_code == 0
        additional_context = response.get("additionalContext")
        assert additional_context is not None, (
            f"Expected additionalContext, got: {response}"
        )
        assert "FAILED" in additional_context or "failed" in additional_context.lower()

    # =========================================================================
    # AC-009.5: PostToolUse passes through on PASSED
    # Scenario 005
    # =========================================================================

    def test_post_tool_use_passes_through_on_passed(self, tmp_path, monkeypatch):
        """
        GIVEN the audit log contains only HOOK_SUBAGENT_STOP_PASSED entries
        WHEN PostToolUse hook fires after Task returns to parent
        THEN no additionalContext is injected (clean passthrough)

        Business Value: Successful sub-agents don't trigger unnecessary
                       notifications to the parent.
        """
        # Arrange: Pre-seed audit log with PASSED entry
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_PASSED",
                "timestamp": "2026-02-06T10:00:00+00:00",
                "feature_name": "test-project",
                "step_id": "01-01",
            },
        )

        # Act
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {"prompt": "...", "subagent_type": "software-crafter"},
            },
        )

        # Assert: No additionalContext
        assert exit_code == 0
        assert response.get("additionalContext") is None

    # =========================================================================
    # AC-009.5: PostToolUse passes through for non-DES tasks
    # Scenario 005b
    # =========================================================================

    def test_post_tool_use_passes_through_for_non_des(self, tmp_path, monkeypatch):
        """
        GIVEN no audit log entries exist (non-DES task)
        WHEN PostToolUse hook fires after Task returns to parent
        THEN no additionalContext is injected

        Business Value: Non-DES tasks are not affected by DES enforcement.
        """
        # Arrange: Empty audit dir
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        # Act
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "some non-DES task",
                    "subagent_type": "researcher",
                },
            },
        )

        # Assert: Clean passthrough
        assert exit_code == 0
        assert response.get("additionalContext") is None

    # =========================================================================
    # AC-009.6: additionalContext has recovery details
    # Scenario 006
    # =========================================================================

    def test_post_tool_use_additional_context_has_recovery_details(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN the audit log contains HOOK_SUBAGENT_STOP_FAILED with details
        WHEN PostToolUse hook fires
        THEN additionalContext includes feature_name, step_id, and errors

        Business Value: Parent receives enough context to decide whether
                       to retry, resume, or escalate.
        """
        # Arrange
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_FAILED",
                "timestamp": "2026-02-06T10:00:00+00:00",
                "feature_name": "auth-upgrade",
                "step_id": "02-03",
                "validation_errors": ["Missing phases: GREEN, COMMIT"],
                "allowed_despite_failure": True,
            },
        )

        # Act
        _exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {"prompt": "...", "subagent_type": "software-crafter"},
            },
        )

        # Assert: Recovery details in additionalContext
        ctx = response.get("additionalContext", "")
        assert "auth-upgrade" in ctx, f"Should include feature_name, got: {ctx}"
        assert "02-03" in ctx, f"Should include step_id, got: {ctx}"
        assert "Missing phases" in ctx or "GREEN" in ctx, (
            f"Should include errors, got: {ctx}"
        )

    # =========================================================================
    # AC-009.7: Missing audit log = graceful passthrough
    # Scenario 007
    # =========================================================================

    def test_missing_audit_log_graceful_passthrough(self, tmp_path, monkeypatch):
        """
        GIVEN the audit log directory does not exist
        WHEN PostToolUse hook fires
        THEN no crash, decision:allow, no additionalContext

        Business Value: System remains stable even when audit infrastructure
                       is missing.
        """
        # Arrange: Point to non-existent directory
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(tmp_path / "nonexistent"))

        # Act
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {"prompt": "...", "subagent_type": "software-crafter"},
            },
        )

        # Assert: Graceful passthrough
        assert exit_code == 0
        assert response.get("additionalContext") is None

    # =========================================================================
    # AC-009.8: PostToolUse injects continuation context for DES task PASSED
    # Scenario 008
    # =========================================================================

    def test_post_tool_use_injects_continuation_on_des_passed(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN the audit log contains HOOK_SUBAGENT_STOP_PASSED
        AND the just-completed Task prompt contains DES markers
        WHEN PostToolUse hook fires
        THEN additionalContext includes continuation instructions with DES markers

        Business Value: Orchestrator is always reminded to continue the develop
                       workflow and include DES markers in the next dispatch,
                       ensuring every step is validated until feature completion.
        """
        # Arrange: Pre-seed audit log with PASSED entry
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_PASSED",
                "timestamp": "2026-02-09T10:00:00+00:00",
                "feature_name": "auth-upgrade",
                "step_id": "01-01",
            },
        )

        # Act: Invoke PostToolUse with a DES prompt (contains DES-VALIDATION marker)
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "<!-- DES-VALIDATION : required -->\n"
                    "<!-- DES-PROJECT-ID : auth-upgrade -->\n"
                    "<!-- DES-STEP-ID : 01-01 -->\n"
                    "Execute step 01-01",
                    "subagent_type": "nw-software-crafter",
                    "max_turns": 30,
                },
            },
        )

        # Assert: Continuation context injected with DES markers
        assert exit_code == 0
        ctx = response.get("additionalContext")
        assert ctx is not None, f"Expected continuation context, got: {response}"
        assert "COMPLETED" in ctx, f"Should indicate step completed, got: {ctx}"
        assert "auth-upgrade" in ctx, f"Should include project_id, got: {ctx}"
        assert "01-01" in ctx, f"Should include step_id, got: {ctx}"
        assert "DES-VALIDATION" in ctx, (
            f"Should include DES marker template, got: {ctx}"
        )
        assert "DES-PROJECT-ID" in ctx, (
            f"Should include DES-PROJECT-ID marker, got: {ctx}"
        )
        assert "DES-STEP-ID" in ctx, f"Should include DES-STEP-ID marker, got: {ctx}"
        assert "execute.md" in ctx, f"Should reference execute.md template, got: {ctx}"

    # =========================================================================
    # AC-009.9: PostToolUse failure includes DES reminder for DES tasks
    # Scenario 009
    # =========================================================================

    def test_post_tool_use_failure_includes_des_reminder_for_des_task(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN the audit log contains HOOK_SUBAGENT_STOP_FAILED
        AND the just-completed Task prompt contains DES markers
        WHEN PostToolUse hook fires
        THEN additionalContext includes failure details AND DES marker reminder

        Business Value: On failure, orchestrator gets both the error details
                       and a reminder to include DES markers when re-dispatching.
        """
        # Arrange
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_FAILED",
                "timestamp": "2026-02-09T10:00:00+00:00",
                "feature_name": "auth-upgrade",
                "step_id": "02-01",
                "validation_errors": ["Missing phases: GREEN, COMMIT"],
                "allowed_despite_failure": True,
            },
        )

        # Act: PostToolUse with DES prompt
        _exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "<!-- DES-VALIDATION : required -->\n"
                    "<!-- DES-PROJECT-ID : auth-upgrade -->\n"
                    "<!-- DES-STEP-ID : 02-01 -->\n"
                    "Execute step 02-01",
                    "subagent_type": "nw-software-crafter",
                    "max_turns": 30,
                },
            },
        )

        # Assert: Failure context with DES marker reminder
        ctx = response.get("additionalContext", "")
        assert "FAILED" in ctx, f"Should indicate failure, got: {ctx}"
        assert "auth-upgrade" in ctx, f"Should include project_id, got: {ctx}"
        assert "02-01" in ctx, f"Should include step_id, got: {ctx}"
        assert "DES-VALIDATION" in ctx, (
            f"Should include DES marker reminder, got: {ctx}"
        )
        assert "execute.md" in ctx, f"Should reference execute.md, got: {ctx}"

    # =========================================================================
    # AC-009.10: Non-DES task still passes through even with PASSED audit
    # Scenario 010
    # =========================================================================

    def test_post_tool_use_non_des_task_no_continuation_despite_passed_audit(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN the audit log contains HOOK_SUBAGENT_STOP_PASSED from an earlier DES task
        AND the just-completed Task prompt does NOT contain DES markers
        WHEN PostToolUse hook fires
        THEN no additionalContext is injected (non-DES tasks unaffected)

        Business Value: Non-DES tasks are never polluted with DES continuation
                       context, even when DES events exist in the audit log.
        """
        # Arrange: PASSED entry exists from earlier DES task
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        _seed_audit_log_entry(
            audit_dir,
            {
                "event": "HOOK_SUBAGENT_STOP_PASSED",
                "timestamp": "2026-02-09T10:00:00+00:00",
                "feature_name": "auth-upgrade",
                "step_id": "01-01",
            },
        )

        # Act: Non-DES task (no DES markers in prompt)
        exit_code, response = invoke_hook(
            "post-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Research best practices for authentication",
                    "subagent_type": "nw-researcher",
                    "max_turns": 25,
                },
            },
        )

        # Assert: No continuation context for non-DES tasks
        assert exit_code == 0
        assert response.get("additionalContext") is None

    # =========================================================================
    # AC-009.7: SubagentStop empty stdin = fail-closed
    # Scenario 007b
    # =========================================================================

    def test_subagent_stop_empty_stdin_fail_closed(self):
        """
        GIVEN empty stdin (protocol error)
        WHEN SubagentStop hook fires
        THEN exit code 1 (fail-closed)

        Business Value: Protocol errors are fail-closed for safety.
        """
        # Act: Invoke with empty stdin
        env = os.environ.copy()
        project_root = str(Path(__file__).parent.parent.parent.parent)
        src_path = str(Path(project_root) / "src")
        env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.adapters.drivers.hooks.claude_code_hook_adapter",
                "subagent-stop",
            ],
            input="",
            capture_output=True,
            text=True,
            env=env,
        )

        # Assert: Fail-closed
        assert proc.returncode == 1


# =============================================================================
# Test Data Builders
# =============================================================================


def _create_incomplete_execution_log(tdd_phases):
    """Create execution-log.yaml with only first 2 phases completed."""
    events = []
    for phase in tdd_phases[:2]:
        events.append(f"01-01|{phase}|EXECUTED|PASS|2026-02-06T10:00:00+00:00")

    return {
        "project_id": "test-project",
        "created_at": "2026-02-06T09:00:00+00:00",
        "total_steps": 1,
        "events": events,
    }


def _read_audit_entries(audit_dir: Path) -> list[dict]:
    """Read all JSONL audit entries from an audit directory."""
    entries = []
    if not audit_dir.exists():
        return entries
    for log_file in audit_dir.glob("audit-*.log"):
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries
