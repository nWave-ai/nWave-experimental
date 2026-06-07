"""
Regression Tests: Agent Tool Hook Processing After Task-to-Agent Migration

PROBLEM STATEMENT:
Claude Code v2.1.63 renamed the "Task" tool to "Agent" and removed the
max_turns parameter from tool_input schema. This broke DES hooks silently:
1. PreToolUse hook matchers with "Task" stopped firing (tool_name is now "Agent")
2. max_turns validation always returned MISSING_MAX_TURNS, blocking all DES tasks

The max_turns parameter moved to maxTurns in agent definition YAML frontmatter,
already present in all 23 nWave agents.

EXPECTED BEHAVIOR:
After migration:
- PreToolUse hook processes Agent tool invocations (matcher updated)
- No max_turns validation in hook (removed from PreToolUseService)
- Valid DES prompts are ALLOWED without max_turns in tool_input
- Invalid DES prompts are still BLOCKED by template/completeness validation
- Non-DES invocations pass through as before

BUSINESS IMPACT:
Without this fix, ALL DES task invocations are silently blocked, preventing
any nWave workflow from executing.
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


def _make_incomplete_des_prompt() -> str:
    """DES prompt with markers but missing mandatory sections."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : test-project -->\n"
        "<!-- DES-STEP-ID : 01-01 -->\n"
        "Do something without proper sections"
    )


class TestAgentToolHookProcessing:
    """Regression tests for Agent tool invocations after Task-to-Agent migration.

    The key regression: DES hooks must process Agent tool invocations without
    requiring max_turns in tool_input, since Claude Code v2.1.63 moved this
    parameter to agent definition YAML frontmatter.

    All tests invoke through the driving port (handle_pre_tool_use) which is
    the actual entry point called by Claude Code hooks.
    """

    def test_agent_tool_des_invocation_allowed_without_max_turns(
        self, claude_code_hook_stdin
    ):
        """
        GIVEN a valid DES prompt with NO max_turns in tool_input (new Agent schema)
        WHEN PreToolUse hook processes the invocation
        THEN hook ALLOWS invocation with exit code 0
        AND no error mentions max_turns

        This is THE key regression test. Before the fix, every Agent tool
        invocation was blocked with MISSING_MAX_TURNS because max_turns was
        always absent from the new Agent schema.
        """
        # GIVEN: Valid DES prompt, no max_turns in tool_input (Agent schema)
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": _make_valid_des_prompt(),
                "description": "Execute step 01-01",
                # No max_turns -- Agent tool schema does not include it
            }
        }

        # WHEN: Hook processes the invocation
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Invocation is ALLOWED
        assert exit_code == 0, (
            f"Valid DES invocation without max_turns should be allowed. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        # Allow path: silent exit 0, no stdout (Claude Code protocol)
        assert stdout.strip() == "", (
            f"Allow path should produce no stdout. Got: {stdout!r}"
        )

    def test_agent_tool_non_des_invocation_passes_through(self, claude_code_hook_stdin):
        """
        GIVEN an Agent tool invocation with no DES markers and no max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook ALLOWS invocation with exit code 0

        Non-DES tasks always pass through regardless of max_turns presence.
        This behavior must be preserved after the migration.
        """
        # GIVEN: Non-DES prompt, no max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "Search for all Python files in the project",
                "description": "Quick exploration",
                # No DES markers, no max_turns
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: ALLOWED
        assert exit_code == 0, (
            f"Non-DES invocation should be allowed. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        # Allow path: silent exit 0, no stdout (Claude Code protocol)
        assert stdout.strip() == "", (
            f"Allow path should produce no stdout. Got: {stdout!r}"
        )

    def test_agent_tool_invalid_des_prompt_still_blocked(self, claude_code_hook_stdin):
        """
        GIVEN a DES prompt with markers but missing mandatory sections, no max_turns
        WHEN PreToolUse hook processes the invocation
        THEN hook BLOCKS invocation with exit code 2
        AND block reason does NOT mention max_turns

        The removal of max_turns validation must not weaken other validations.
        Template completeness checks must still catch malformed DES prompts.
        """
        # GIVEN: Incomplete DES prompt, no max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": _make_incomplete_des_prompt(),
                "description": "Execute step 01-01",
                # No max_turns
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: Invocation is BLOCKED
        assert exit_code == 2, (
            f"Incomplete DES prompt should be blocked. "
            f"Got exit code: {exit_code}, stdout: {stdout}"
        )

        output = json.loads(stdout)
        assert output.get("decision") == "block", (
            f"Decision should be 'block'. Got: {output}"
        )

        # THEN: Block reason does NOT mention max_turns
        reason = output.get("reason", "")
        assert "MAX_TURNS" not in reason and "max_turns" not in reason, (
            f"Block reason should not mention max_turns after removal. "
            f"Got reason: {reason}"
        )

    def test_agent_tool_with_legacy_max_turns_still_works(self, claude_code_hook_stdin):
        """
        GIVEN an Agent tool invocation WITH max_turns=30 in tool_input (legacy field)
        WHEN PreToolUse hook processes the invocation
        THEN hook ALLOWS invocation with exit code 0 if prompt is valid

        Backward compatibility: if a caller still includes max_turns in
        tool_input, it should be silently ignored (not extracted, not validated).
        The field is simply unused extra data in the JSON.
        """
        # GIVEN: Valid DES prompt WITH legacy max_turns
        hook_input = {
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": _make_valid_des_prompt(),
                "description": "Execute step 01-01",
                "max_turns": 30,  # Legacy field, should be ignored
            }
        }

        # WHEN: Hook processes
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        # THEN: ALLOWED (max_turns ignored, valid prompt passes)
        assert exit_code == 0, (
            f"Valid DES invocation with legacy max_turns should be allowed. "
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
