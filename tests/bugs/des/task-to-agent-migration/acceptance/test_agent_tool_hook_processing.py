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
- Validation steps fire in correct order: enforcement -> completeness ->
  template validation -> allow

BUSINESS IMPACT:
Without this fix, ALL DES task invocations are silently blocked, preventing
any nWave workflow from executing.

Track WS-15 P2 collapse (2026-07-12): migration stable since 2026-06-20
(22 days, no follow-up bug citing this migration). Per skill 3.5 this file
merges the former test_agent_tool_hook_processing.py (4 tests) and
test_enforcement_ordering_without_max_turns.py (3 tests) -- one case
(valid DES prompt, no max_turns -> allowed) was byte-identical between the
two files -- into 1 single-iteration test (skill 3.2 dict-iteration)
reporting every violation at once via the case table below.
"""

import json

import pytest


DES_MARKERS_MISSING = "DES_MARKERS_MISSING"
_MAX_TURNS_TOKENS = ("MAX_TURNS", "max_turns")


def _make_valid_des_prompt() -> str:
    """Build a DES prompt the spine still ALLOWS, with all mandatory sections.

    The mode marker is load-bearing since the classic removal (aa46b6c03): an
    absent mode is a declared REFUSAL (DISPATCH_MODE_UNRESOLVED), not a legacy
    fallback, so a markerless envelope never reaches the allow branch. This
    fixture is about the Task->Agent hook pipeline, not about mode selection,
    so it carries the marker rather than encoding a request the product has
    deliberately stopped serving.
    """
    return """<!-- DES-VALIDATION : required -->
<!-- DES-MODE : refactor -->
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


# Each case: (id, tool_input, expected_exit_code, expected_decision,
#             reason_contains, reason_excludes)
# expected_decision is None for the allow path (silent exit 0, no stdout).
HOOK_BEHAVIOR_CASES = [
    (
        "des_valid_no_max_turns_allowed",
        {
            "subagent_type": "Explore",
            "prompt": _make_valid_des_prompt(),
            "description": "Execute step 01-01",
        },
        0,
        None,
        None,
        _MAX_TURNS_TOKENS,
    ),
    (
        "non_des_invocation_passes_through",
        {
            "subagent_type": "Explore",
            "prompt": "Search for all Python files in the project",
            "description": "Quick exploration",
        },
        0,
        None,
        None,
        _MAX_TURNS_TOKENS,
    ),
    (
        "invalid_des_prompt_still_blocked",
        {
            "subagent_type": "Explore",
            "prompt": _make_incomplete_des_prompt(),
            "description": "Execute step 01-01",
        },
        2,
        "block",
        None,
        _MAX_TURNS_TOKENS,
    ),
    (
        "legacy_max_turns_ignored_still_allowed",
        {
            "subagent_type": "Explore",
            "prompt": _make_valid_des_prompt(),
            "description": "Execute step 01-01",
            "max_turns": 30,  # Legacy field, should be ignored
        },
        0,
        None,
        None,
        _MAX_TURNS_TOKENS,
    ),
    (
        "enforcement_fires_before_completeness",
        {
            "subagent_type": "Explore",
            "prompt": "Execute step 02-03 for the authentication feature",
        },
        2,
        "block",
        DES_MARKERS_MISSING,
        _MAX_TURNS_TOKENS,
    ),
    (
        "completeness_check_runs_for_des_tasks",
        {
            "subagent_type": "Explore",
            "prompt": (
                "<!-- DES-VALIDATION : required -->\n"
                "<!-- DES-PROJECT-ID : test-project -->\n"
                "<!-- DES-STEP-ID : 01-01 -->\n"
                "Do something without proper template sections"
            ),
        },
        2,
        "block",
        None,
        _MAX_TURNS_TOKENS,
    ),
]


def test_agent_tool_hook_pipeline_matches_task_to_agent_baseline(
    claude_code_hook_stdin,
) -> None:
    """Every case in HOOK_BEHAVIOR_CASES must match its expected allow/block
    decision after the Task-to-Agent migration (matcher rename + max_turns
    removal from PreToolUseService).

    Iterates the table once; failure message lists every case that
    regressed (id + expected vs actual), so a single failure is as
    diagnosable as the pre-collapse 6-test version (one case --
    "valid DES prompt, no max_turns -> allowed" -- was duplicated
    byte-for-byte across the two pre-collapse files and is represented
    once here, per behavior-counting, not test-counting).
    """
    violations: list[str] = []

    for (
        case_id,
        tool_input,
        expected_exit_code,
        expected_decision,
        reason_contains,
        reason_excludes,
    ) in HOOK_BEHAVIOR_CASES:
        hook_input = {"tool_input": tool_input}
        exit_code, stdout, _stderr = claude_code_hook_stdin(
            "pre-task", json.dumps(hook_input)
        )

        if exit_code != expected_exit_code:
            violations.append(
                f"{case_id}: expected exit_code {expected_exit_code}, "
                f"got {exit_code} (stdout={stdout!r})"
            )
            continue

        if expected_decision is None:
            if stdout.strip() != "":
                violations.append(
                    f"{case_id}: allow path should produce no stdout, got {stdout!r}"
                )
            continue

        output = json.loads(stdout)
        actual_decision = output.get("decision")
        if actual_decision != expected_decision:
            violations.append(
                f"{case_id}: expected decision {expected_decision!r}, "
                f"got {actual_decision!r}"
            )

        reason = output.get("reason", "")
        if reason_contains and reason_contains not in reason:
            violations.append(
                f"{case_id}: reason should contain {reason_contains!r}, got {reason!r}"
            )
        for token in reason_excludes:
            if token in reason:
                violations.append(
                    f"{case_id}: reason should not mention {token!r} "
                    f"(max_turns was removed), got {reason!r}"
                )

    assert not violations, (
        "Agent-tool hook pipeline drifted from the Task->Agent migration "
        "baseline:\n  " + "\n  ".join(violations)
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
    import os
    from io import StringIO
    from unittest.mock import patch

    def invoke_hook(command: str, stdin_data: str) -> tuple[int, str, str]:
        """Invoke hook adapter function directly with mocked I/O.

        Runs WHILE chdir'd into the fixture's isolated ``tmp_path``: the
        production ``PreToolUseService`` sources its wave floor off
        ``resolve_nwave_root()`` (``DES_PROJECT_DIR`` env var if set, else
        ``Path.cwd()``), so the hook's decision must be a function of the floor
        in this injected root, NOT the ambient working-tree floor armed by
        whatever branch the suite runs on. ``DES_PROJECT_DIR`` is mirrored to
        ``tmp_path`` alongside the chdir so resolution honours the injected
        root even under an autouse fixture (e.g. ``tests/conftest.py``'s
        ``_isolate_nwave_root``) that has already pinned ``DES_PROJECT_DIR`` to
        a different per-test isolation root. Previous CWD/env are restored
        afterward.
        """
        from des.adapters.drivers.hooks.claude_code_hook_adapter import (
            handle_pre_tool_use,
        )

        prev_cwd = os.getcwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        os.chdir(tmp_path)
        os.environ["DES_PROJECT_DIR"] = str(tmp_path)
        try:
            # Mock stdin with the input data
            with patch("sys.stdin", StringIO(stdin_data)):
                # Mock stdout to capture output
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    # Call the handler directly
                    exit_code = handle_pre_tool_use()
                    stdout = mock_stdout.getvalue()
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env

        # No stderr in direct calls (only in subprocess)
        stderr = ""

        return exit_code, stdout, stderr

    return invoke_hook
