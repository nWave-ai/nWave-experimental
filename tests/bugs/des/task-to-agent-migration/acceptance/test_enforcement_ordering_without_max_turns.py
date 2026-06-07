"""
Regression Tests: Validation Flow Ordering After max_turns Removal

PROBLEM STATEMENT:
With max_turns validation removed from PreToolUseService, the remaining
validation steps must execute in correct order:
1. DES enforcement policy (step-id without markers -> block)
2. Non-DES passthrough (no markers, no step-id -> allow)
3. Marker completeness check (markers present but incomplete -> block)
4. Template validation (complete markers but invalid structure -> block)
5. Full validation pass (everything valid -> allow)

These tests verify the validation pipeline remains intact and correctly
ordered after the max_turns step was removed.

BUSINESS IMPACT:
If validation ordering is broken, users receive confusing error messages
that don't help them fix the actual problem (e.g., "markers incomplete"
when the real issue is "you're referencing a step outside DES context").
"""

import json

import pytest


def _make_valid_des_prompt() -> str:
    """Build a fully valid DES prompt with all mandatory sections."""
    return """<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : test-project -->
<!-- DES-STEP-ID : 01-01 -->

# DES_METADATA
Project: test-project
Step: 01-01
Command: /nw-execute

# AGENT_IDENTITY
Agent: @software-crafter
Role: Implement features through Outside-In TDD

# TASK_CONTEXT
**Title**: Implement feature
**Type**: feature

Acceptance Criteria:
- Feature works as expected

# TDD_PHASES
Execute all 5 phases:
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

# RECORDING_INTEGRITY
Valid Skip Prefixes: NOT_APPLICABLE, BLOCKED_BY_DEPENDENCY, APPROVED_SKIP, CHECKPOINT_PENDING
Anti-Fraud Rules: NEVER write EXECUTED for phases not performed. DES audits all entries.

# BOUNDARY_RULES
- Follow hexagonal architecture

Files to modify:
- src/feature.py

# TIMEOUT_INSTRUCTION
Turn budget: 50 turns
Exit on: completion or blocking issue
"""


class TestEnforcementOrderingWithoutMaxTurns:
    """Tests that validation steps fire in correct order after max_turns removal.

    The validation pipeline must produce actionable, correctly-prioritized
    error messages. Enforcement fires before completeness, completeness
    fires before template validation. No step should mention max_turns.

    All tests invoke through the driving port (handle_pre_tool_use).
    """

    def test_enforcement_fires_before_completeness(self, claude_code_hook_stdin):
        """
        GIVEN a prompt with step-id pattern but NO DES markers and NO max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook BLOCKS with DES_MARKERS_MISSING
        AND block reason does NOT mention max_turns

        Enforcement policy detects step-id references without DES context.
        This must fire first so users get actionable guidance ("add DES markers")
        rather than a confusing downstream error.
        """
        # GIVEN: Prompt mentions step-id but has no DES markers
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "Execute step 02-03 for the authentication feature",
                # No DES markers, no max_turns
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Blocked by enforcement policy
        assert exit_code == 2, (
            f"Should be blocked by enforcement. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "block"

        reason = output.get("reason", "")
        assert "DES_MARKERS_MISSING" in reason, (
            f"Should be blocked by enforcement (DES_MARKERS_MISSING). Got: {reason}"
        )

        # THEN: No mention of max_turns
        assert "MAX_TURNS" not in reason and "max_turns" not in reason, (
            f"Should NOT mention max_turns after removal. Got: {reason}"
        )

    def test_completeness_check_runs_for_des_tasks(self, claude_code_hook_stdin):
        """
        GIVEN a DES prompt with markers but missing mandatory sections
        WHEN PreToolUse hook processes the invocation
        THEN hook BLOCKS by completeness or template validation
        AND block reason does NOT mention max_turns

        After enforcement passes (markers present), the next checks are
        completeness and template validation. Both must still function
        correctly with max_turns removed from the pipeline.
        """
        # GIVEN: DES prompt with markers but missing mandatory sections
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": (
                    "<!-- DES-VALIDATION : required -->\n"
                    "<!-- DES-PROJECT-ID : test-project -->\n"
                    "<!-- DES-STEP-ID : 01-01 -->\n"
                    "Do something without proper template sections"
                ),
                # No max_turns
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Blocked by completeness or template validation
        assert exit_code == 2, (
            f"Incomplete DES prompt should be blocked. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "block"

        # THEN: Block reason is about missing sections, not max_turns
        reason = output.get("reason", "")
        assert "MAX_TURNS" not in reason and "max_turns" not in reason, (
            f"Block reason should not mention max_turns. Got: {reason}"
        )
        assert reason, "Block reason should not be empty"

    def test_valid_des_prompt_allowed_without_max_turns(self, claude_code_hook_stdin):
        """
        GIVEN a fully valid DES prompt with all mandatory sections, no max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook ALLOWS with exit code 0

        The complete validation pipeline (enforcement -> completeness ->
        template validation) passes for a valid prompt, confirming that
        removing max_turns did not break the allow path.
        """
        # GIVEN: Fully valid DES prompt, no max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": _make_valid_des_prompt(),
                "description": "Execute step 01-01",
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: ALLOWED
        assert exit_code == 0, (
            f"Valid DES prompt should be allowed. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        # Allow path: silent exit 0, no stdout (Claude Code protocol)
        assert stdout.strip() == "", (
            f"Allow path should produce no stdout. Got: {stdout!r}"
        )


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def claude_code_hook_stdin(tmp_path):
    """
    Fixture to invoke Claude Code hook adapter directly (no subprocess).

    Returns callable that:
    1. Takes (command, stdin_data)
    2. Invokes hook adapter function directly with mocked stdin/stdout
    3. Returns (exit_code, stdout, stderr)

    Note: Direct function calls are ~10x faster than subprocess invocation.
    """
    from io import StringIO
    from unittest.mock import patch

    def invoke_hook(command: str, stdin_data: str) -> tuple[int, str, str]:
        """Invoke hook adapter function directly with mocked I/O."""
        from des.adapters.drivers.hooks.claude_code_hook_adapter import (
            handle_pre_tool_use,
        )

        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = handle_pre_tool_use()
                stdout = mock_stdout.getvalue()

        stderr = ""
        return exit_code, stdout, stderr

    return invoke_hook
