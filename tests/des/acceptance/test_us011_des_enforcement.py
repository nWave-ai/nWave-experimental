"""
E2E Acceptance Test: US-011 DES Enforcement Hardening

PERSONA: Orchestrator (Parent Agent)
STORY: As an orchestrator, I want Task invocations referencing step IDs to be blocked
       unless they include DES markers, so that step execution is always monitored.

BUSINESS VALUE:
- Closes Scenario A: Task with step-id but without DES markers → BLOCKED
- Closes incomplete markers: DES-VALIDATION present but project/step IDs missing → BLOCKED
- Zero false positives on research/non-step tasks

SCOPE: Covers US-011 Acceptance Criteria (AC-011.1 through AC-011.9)
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


# =============================================================================
# TEST HELPER: Invoke hook through external protocol boundary
# =============================================================================


def invoke_hook(hook_type: str, payload: dict) -> tuple[int, dict]:
    """Invoke hook adapter through its external protocol (subprocess + JSON)."""
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


def _make_valid_des_prompt(project_id: str = "auth-upgrade", step_id: str = "01-01") -> str:
    """Build a fully valid DES prompt with all mandatory sections."""
    return f"""<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {project_id} -->
<!-- DES-STEP-ID : {step_id} -->

# DES_METADATA
Project: {project_id}
Step: {step_id}
Command: /nw:execute

# AGENT_IDENTITY
Agent: @software-crafter
Role: Implement features through Outside-In TDD

# TASK_CONTEXT
**Title**: Implement feature
**Type**: feature

Acceptance Criteria:
- Feature works as expected

# TDD_7_PHASES
Execute all 7 phases:
1. PREPARE
2. RED_ACCEPTANCE
3. RED_UNIT
4. GREEN
5. REVIEW
6. REFACTOR_CONTINUOUS
7. COMMIT

# QUALITY_GATES
- All tests must pass
- Code quality validated

# OUTCOME_RECORDING
Update execution-log.yaml after each phase.

# BOUNDARY_RULES
- Follow hexagonal architecture

Files to modify:
- src/feature.py

# TIMEOUT_INSTRUCTION
Turn budget: 50 turns
Exit on: completion or blocking issue
"""


# =============================================================================
# PHASE 1: Step-ID Enforcement Tests (AC-011.1 through AC-011.6)
# =============================================================================


class TestStepIdEnforcement:
    """E2E tests for step-id enforcement policy."""

    # AC-011.1: Step-id + no markers → BLOCKED
    def test_step_id_without_markers_blocked(self):
        """
        GIVEN a Task prompt containing step-id pattern 01-01
        AND no DES markers present
        WHEN PreToolUse hook fires
        THEN exit code is 2 (block)
        AND response contains block decision
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Execute step 01-01 for the authentication feature",
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 2, f"Expected exit 2 (block), got {exit_code}: {response}"
        assert response.get("decision") == "block"
        assert "DES_MARKERS_MISSING" in response.get("reason", "")

    # AC-011.2: Step-id + markers present → ALLOWED
    def test_step_id_with_markers_allowed(self):
        """
        GIVEN a Task prompt containing step-id pattern 01-01
        AND DES-VALIDATION marker present with full valid prompt
        WHEN PreToolUse hook fires
        THEN exit code is 0 (allow)
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": _make_valid_des_prompt(),
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"

    # AC-011.3: No step-id → ALLOWED
    def test_no_step_id_allowed(self):
        """
        GIVEN a Task prompt without step-id patterns
        WHEN PreToolUse hook fires
        THEN exit code is 0 (allow)
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Research authentication best practices for the project",
                    "max_turns": 30,
                    "subagent_type": "nw-researcher",
                },
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"

    # AC-011.4: Step-id + exempt marker → ALLOWED
    def test_exempt_marker_allowed(self):
        """
        GIVEN a Task prompt containing step-id pattern
        AND DES-ENFORCEMENT exempt marker present
        WHEN PreToolUse hook fires
        THEN exit code is 0 (allow)
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": (
                        "<!-- DES-ENFORCEMENT : exempt -->\n"
                        "Review roadmap step 01-01 for completeness"
                    ),
                    "max_turns": 30,
                    "subagent_type": "nw-solution-architect",
                },
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"

    # AC-011.5: Block reason contains DES marker template
    def test_block_reason_contains_recovery_suggestions(self):
        """
        GIVEN a Task prompt blocked by step-id enforcement
        WHEN PreToolUse hook fires
        THEN block reason contains DES_MARKERS_MISSING
        AND response includes marker template guidance
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Implement step 02-03 changes to the system",
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 2
        reason = response.get("reason", "")
        assert "DES_MARKERS_MISSING" in reason
        assert "02-03" in reason

    # AC-011.6: Audit log records blocked event
    def test_audit_log_records_blocked_event(self, tmp_path, monkeypatch):
        """
        GIVEN a Task prompt blocked by step-id enforcement
        WHEN PreToolUse hook fires
        THEN audit log contains HOOK_PRE_TOOL_USE_BLOCKED with DES_MARKERS_MISSING
        """
        audit_dir = tmp_path / "audit"
        monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))

        invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Execute step 01-01",
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )

        entries = _read_audit_entries(audit_dir)
        blocked_entries = [
            e for e in entries if e.get("event") == "HOOK_PRE_TOOL_USE_BLOCKED"
        ]
        assert len(blocked_entries) >= 1, (
            f"Expected HOOK_PRE_TOOL_USE_BLOCKED entry, got: {entries}"
        )
        assert "DES_MARKERS_MISSING" in blocked_entries[-1].get("reason", "")


# =============================================================================
# PHASE 2: Marker Completeness Tests (AC-011.7 through AC-011.9)
# =============================================================================


class TestSessionGuard:
    """E2E tests for Write/Edit session guard (Scenario B prevention)."""

    # AC-011.10: Source write blocked during deliver without DES task
    def test_source_write_blocked_during_deliver(self, tmp_path, monkeypatch):
        """
        GIVEN deliver session is active (.nwave/des/deliver-session.json exists)
        AND no DES task signal (.nwave/des/des-task-active does NOT exist)
        WHEN Write tool targets a source file
        THEN exit code is 2 (block)
        """
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / ".nwave" / "des"
        session_dir.mkdir(parents=True)
        (session_dir / "deliver-session.json").write_text(
            '{"project_id":"test","started_at":"2026-02-09T10:00:00Z"}'
        )

        exit_code, response = invoke_hook(
            "pre-write",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/auth/user_auth.py", "content": "..."},
            },
        )
        assert exit_code == 2, f"Expected exit 2 (block), got {exit_code}: {response}"
        assert response.get("decision") == "block"

    # AC-011.11: Source write allowed with DES task active
    def test_source_write_allowed_with_des_task(self, tmp_path, monkeypatch):
        """
        GIVEN deliver session is active
        AND DES task signal exists (.nwave/des/des-task-active)
        WHEN Write tool targets a source file
        THEN exit code is 0 (allow)
        """
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / ".nwave" / "des"
        session_dir.mkdir(parents=True)
        (session_dir / "deliver-session.json").write_text(
            '{"project_id":"test","started_at":"2026-02-09T10:00:00Z"}'
        )
        (session_dir / "des-task-active").write_text(
            '{"step_id":"01-01","created_at":"2026-02-09T10:05:00Z"}'
        )

        exit_code, response = invoke_hook(
            "pre-write",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/auth/user_auth.py", "content": "..."},
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"

    # AC-011.12: Orchestration file allowed during deliver
    def test_orchestration_file_allowed_during_deliver(self, tmp_path, monkeypatch):
        """
        GIVEN deliver session is active
        AND no DES task signal
        WHEN Write tool targets docs/feature/ file
        THEN exit code is 0 (allow)
        """
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / ".nwave" / "des"
        session_dir.mkdir(parents=True)
        (session_dir / "deliver-session.json").write_text(
            '{"project_id":"test","started_at":"2026-02-09T10:00:00Z"}'
        )

        exit_code, response = invoke_hook(
            "pre-write",
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "docs/feature/test/roadmap.yaml",
                    "content": "...",
                },
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"

    # AC-011.13: No deliver session = all writes allowed
    def test_no_deliver_session_allows_all(self, tmp_path, monkeypatch):
        """
        GIVEN no deliver session marker exists
        WHEN Write tool targets a source file
        THEN exit code is 0 (allow)
        """
        monkeypatch.chdir(tmp_path)
        # No .nwave/des/deliver-session.json

        exit_code, response = invoke_hook(
            "pre-write",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/auth/user_auth.py", "content": "..."},
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"


class TestMarkerCompleteness:
    """E2E tests for DES marker completeness validation."""

    # AC-011.7: DES-VALIDATION present, DES-PROJECT-ID missing → BLOCKED
    def test_missing_project_id_blocked(self):
        """
        GIVEN DES-VALIDATION marker present
        AND DES-PROJECT-ID missing
        WHEN PreToolUse hook fires
        THEN exit code is 2 (block)
        AND reason contains DES_MARKERS_INCOMPLETE
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": (
                        "<!-- DES-VALIDATION : required -->\n"
                        "<!-- DES-STEP-ID : 01-01 -->\n"
                        "Execute step 01-01"
                    ),
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 2, f"Expected exit 2 (block), got {exit_code}: {response}"
        assert "DES_MARKERS_INCOMPLETE" in response.get("reason", "")
        assert "DES-PROJECT-ID" in response.get("reason", "")

    # AC-011.8: DES-VALIDATION present, DES-STEP-ID missing → BLOCKED
    def test_missing_step_id_blocked(self):
        """
        GIVEN DES-VALIDATION marker present
        AND DES-STEP-ID missing (non-orchestrator mode)
        WHEN PreToolUse hook fires
        THEN exit code is 2 (block)
        AND reason contains DES_MARKERS_INCOMPLETE
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": (
                        "<!-- DES-VALIDATION : required -->\n"
                        "<!-- DES-PROJECT-ID : auth-upgrade -->\n"
                        "Execute step 01-01"
                    ),
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 2, f"Expected exit 2 (block), got {exit_code}: {response}"
        assert "DES_MARKERS_INCOMPLETE" in response.get("reason", "")
        assert "DES-STEP-ID" in response.get("reason", "")

    # AC-011.9: DES-VALIDATION + both IDs → ALLOWED
    def test_complete_markers_allowed(self):
        """
        GIVEN DES-VALIDATION marker present
        AND both DES-PROJECT-ID and DES-STEP-ID present
        WHEN PreToolUse hook fires
        THEN exit code is 0 (allow)
        """
        exit_code, response = invoke_hook(
            "pre-tool-use",
            {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": _make_valid_des_prompt(),
                    "max_turns": 30,
                    "subagent_type": "nw-software-crafter",
                },
            },
        )
        assert exit_code == 0, f"Expected exit 0 (allow), got {exit_code}: {response}"
