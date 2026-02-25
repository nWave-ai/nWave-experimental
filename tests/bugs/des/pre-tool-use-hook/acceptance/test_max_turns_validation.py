"""
Bug Test: PreToolUse Hook MUST Validate max_turns for DES Task Invocations

PROBLEM STATEMENT:
The PreToolUse hook must validate that DES Task invocations include the
mandatory max_turns parameter. Non-DES tasks bypass this check entirely
(see nwave-ai/nwave#9).

REQUIREMENT (from CLAUDE.md):
> **CRITICAL**: Always include `max_turns` when invoking the Task tool.

EXPECTED BEHAVIOR:
PreToolUse hook should:
1. Parse DES markers first
2. ALLOW non-DES tasks immediately (no max_turns check)
3. For DES tasks: BLOCK if max_turns is missing or invalid
4. For DES tasks: ALLOW if max_turns is present with valid value

BUSINESS IMPACT:
- Without max_turns validation on DES tasks, agents can run indefinitely
- Excessive token consumption
- No control over execution duration
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
Command: /nw:execute

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


def _make_des_prompt_minimal() -> str:
    """DES prompt with markers only (for block-path tests where template doesn't matter)."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : test-project -->\n"
        "<!-- DES-STEP-ID : 01-01 -->\n"
        "Do something"
    )


class TestPreToolUseMaxTurnsValidation:
    """Acceptance tests for max_turns validation in PreToolUse hook."""

    def test_missing_max_turns_should_block_des_invocation(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN DES Task tool invocation WITHOUT max_turns parameter
        WHEN PreToolUse hook processes the invocation
        THEN hook BLOCKS invocation with exit code 2
        AND error message indicates missing max_turns parameter
        AND provides guidance on adding max_turns

        Business Context:
        Developer calls Task(...) with DES markers but without max_turns.
        Hook must catch this before invoking sub-agent to prevent
        unbounded execution. Non-DES tasks bypass this check (nwave-ai/nwave#9).
        """
        # GIVEN: DES tool invocation WITHOUT max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": (
                    "<!-- DES-VALIDATION : required -->\n"
                    "<!-- DES-PROJECT-ID : test-project -->\n"
                    "<!-- DES-STEP-ID : 01-01 -->\n"
                    "Find all Python files"
                ),
                "description": "Quick exploration",
            }
        }

        # WHEN: Hook processes invocation
        exit_code, stdout, stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Invocation is BLOCKED
        assert exit_code == 2, (
            f"Hook should block with exit code 2 when max_turns missing. "
            f"Got: {exit_code}, stdout: {stdout}, stderr: {stderr}"
        )

        # THEN: Error message indicates missing max_turns
        output = json.loads(stdout)
        assert output.get("decision") == "block", "Decision should be 'block'"

        reason = output.get("reason", "").lower()
        assert "max_turns" in reason, (
            f"Error should mention max_turns. Got: {output.get('reason')}"
        )

        # THEN: Provides guidance
        assert any(
            keyword in reason
            for keyword in ["missing", "required", "must", "add", "include"]
        ), f"Error should indicate max_turns is required. Got: {reason}"

    def test_valid_max_turns_should_allow_invocation(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN Task tool invocation WITH valid max_turns parameter
        WHEN PreToolUse hook processes the invocation
        THEN hook ALLOWS invocation with exit code 0
        AND no error message about max_turns

        Business Context:
        Developer correctly includes max_turns=30 in Task call.
        Hook should validate and allow execution to proceed.
        """
        # GIVEN: Tool invocation WITH valid max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "Find all Python files",
                "description": "Quick exploration",
                "max_turns": 30,  # ✅ PRESENT
            }
        }

        # WHEN: Hook processes invocation
        exit_code, stdout, stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Invocation is ALLOWED
        assert exit_code == 0, (
            f"Hook should allow with exit code 0 when max_turns present. "
            f"Got: {exit_code}, stdout: {stdout}, stderr: {stderr}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "allow", "Decision should be 'allow'"

    def test_invalid_max_turns_values_should_block_des_tasks(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN DES Task invocation WITH invalid max_turns values
        WHEN PreToolUse hook processes the invocation
        THEN hook BLOCKS invocation with exit code 2
        AND error message indicates invalid value

        Business Context:
        Developer sets max_turns to invalid value (negative, zero, or too high)
        on a DES task. Hook should catch this configuration error.
        """
        invalid_values = [
            (0, "zero"),
            (-1, "negative"),
            (-50, "negative"),
            (1000, "too high"),  # Excessive, indicates misconfiguration
        ]

        for invalid_value, description in invalid_values:
            # GIVEN: DES tool invocation with invalid max_turns
            hook_input = {
                "tool_input": {
                    "subagent_type": "Explore",
                    "prompt": (
                        "<!-- DES-VALIDATION : required -->\n"
                        "<!-- DES-PROJECT-ID : test-project -->\n"
                        "<!-- DES-STEP-ID : 01-01 -->\n"
                        "Find files"
                    ),
                    "max_turns": invalid_value,
                }
            }

            # WHEN: Hook processes invocation
            exit_code, stdout, _stderr = claude_code_hook_stdin(
                "pre-task", json.dumps(hook_input)
            )

            # THEN: Invocation is BLOCKED
            assert exit_code == 2, (
                f"Hook should block {description} max_turns ({invalid_value}). "
                f"Got: {exit_code}"
            )

            output = json.loads(stdout)
            assert output.get("decision") == "block"

            reason = output.get("reason", "").lower()
            assert any(
                keyword in reason
                for keyword in ["invalid", "positive", "range", "value"]
            ), f"Error should indicate invalid value for {description}. Got: {reason}"

    def test_max_turns_boundaries_enforced_for_des_tasks(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN DES Task invocation with max_turns at boundary values
        WHEN PreToolUse hook processes the invocation
        THEN appropriate boundaries are enforced

        Boundaries (from CLAUDE.md):
        - Minimum: 10 (too low indicates likely error)
        - Maximum: 100 (too high indicates likely error)
        - Recommended ranges:
          * Quick edit: 15
          * Background task: 25
          * Standard task: 30
          * Research: 35
          * Complex refactoring: 50

        Note: Non-DES tasks bypass max_turns validation (nwave-ai/nwave#9).
        """
        test_cases = [
            (1, "block", "too low"),
            (5, "block", "too low"),
            (10, "allow", "minimum acceptable"),  # Edge case: barely acceptable
            (15, "allow", "quick edit"),
            (30, "allow", "standard"),
            (50, "allow", "complex"),
            (100, "allow", "maximum acceptable"),  # Edge case: barely acceptable
            (101, "block", "too high"),
            (500, "block", "too high"),
        ]

        for value, expected_decision, description in test_cases:
            hook_input = {
                "tool_input": {
                    "subagent_type": "Explore",
                    "prompt": _make_valid_des_prompt(),
                    "max_turns": value,
                }
            }

            _exit_code, stdout, _stderr = claude_code_hook_stdin(
                "pre-task", json.dumps(hook_input)
            )

            output = json.loads(stdout)
            actual_decision = output.get("decision")

            assert actual_decision == expected_decision, (
                f"max_turns={value} ({description}) should result in '{expected_decision}'. "
                f"Got: '{actual_decision}', reason: {output.get('reason')}"
            )

    def test_non_des_tasks_bypass_max_turns_validation(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN ad-hoc Task invocation (no DES marker) WITHOUT max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook should ALLOW (non-DES tasks bypass all DES validation)

        Fix for nwave-ai/nwave#9:
        Non-DES tasks pass through with no validation at all.
        max_turns enforcement is scoped to DES tasks only.
        """
        # GIVEN: Ad-hoc task (no DES marker) without max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "Simple search - no DES markers",
                # No DES-VALIDATION marker
                # No max_turns — allowed for non-DES tasks
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: ALLOWED — non-DES tasks bypass max_turns validation
        assert exit_code == 0, (
            f"Non-DES tasks should be allowed without max_turns. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "allow"

    def test_step_id_without_markers_blocked_before_max_turns(
        self, tmp_path, claude_code_hook_stdin
    ):
        """
        GIVEN Task prompt with step-id pattern but NO DES markers and NO max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook blocks with DES_MARKERS_MISSING (not MISSING_MAX_TURNS)

        This proves ordering: enforcement policy fires before max_turns check.
        Without correct ordering, the user would see a confusing "missing max_turns"
        error instead of the actionable "add DES markers" guidance.
        """
        # GIVEN: Prompt mentions step-id but has no DES markers and no max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "Execute step 02-03 for the authentication feature",
                # No DES markers
                # No max_turns
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Blocked by enforcement policy, NOT by max_turns
        assert exit_code == 2, (
            f"Should be blocked. Got exit code: {exit_code}, stdout: {stdout}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "block"

        reason = output.get("reason", "")
        assert "DES_MARKERS_MISSING" in reason, (
            f"Should be blocked by enforcement (DES_MARKERS_MISSING), "
            f"not by max_turns. Got: {reason}"
        )
        assert "MAX_TURNS" not in reason, (
            f"Should NOT mention max_turns — enforcement fires first. Got: {reason}"
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

        # Mock stdin with the input data
        with patch("sys.stdin", StringIO(stdin_data)):
            # Mock stdout to capture output
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                # Call the handler directly
                exit_code = handle_pre_tool_use()
                stdout = mock_stdout.getvalue()

        # No stderr in direct calls (only in subprocess)
        stderr = ""

        return exit_code, stdout, stderr

    return invoke_hook
