"""Step definitions -- slice-01: git-stash guard PreToolUse hook on Bash.

fix-crafter-stash-structural-mitigation slice-01. Layer 3 (subprocess + FS
acceptance + Claude Code hook protocol simulation): the production hook script
`scripts/hooks/git_stash_guard.py` is the driving port.

The only driven ports are:
  - the real filesystem (tmp_path target: `.nwave/des/logs/audit-{today}.log`),
  - the real environment (`NWAVE_GIT_STASH_ALLOW` kill-switch env var, cleared
    per-test via the conftest autouse fixture; plus
    `NWAVE_GIT_STASH_GUARD_TARGET_ROOT` for test-harness parameter passing),
  - the real subprocess (`python -m scripts.hooks.git_stash_guard`, invoked
    with Claude Code hook-event JSON on stdin).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly). Three
ATs cover the slice-01 contract: walking-skeleton block path + kill-switch
audited bypass + passthrough Scenario Outline (4 safe-command examples). PBT
precluded by OR-reduction (Mandate 9 v2: real I/O on subprocess + audit log
touching real filesystem).

Step bodies delegate to `GitStashGuardFixture` (Mandate-12 criterion 3:
<=2 statements per body, final statement is a composition method call, zero
control flow in step bodies).

ADR-028 + friction #26 skip-marker: `pytestmark = pytest.mark.skip(...)` at the
file head keeps the whole slice RED-but-skipped until the DELIVER crafter
unskips one scenario at a time (Outside-In TDD outer-loop discipline). The
crafter removes the marker (or narrows it) when enabling each scenario.

RED-for-the-right-reason: the slice-01 production hook script
`scripts/hooks/git_stash_guard.py` does NOT EXIST YET (the crafter lands it in
DELIVER). When the composition fixture invokes it as a subprocess via
`python -m`, the interpreter returns a non-zero exit with stderr naming the
missing module; the AT then fires AssertionError on the first `Then` step
(`assert_block_decision_returned` or `assert_approve_decision_returned`). That
is the correct RED: the assertion fires because the slice-01 guard entry point
is unimplemented, not because of an import error or fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via `python -m scripts.hooks.git_stash_guard`
subprocess + JSON stdin. ZERO direct production imports in step composition.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import GitStashGuardFixture, HookInvocation


# ADR-028 + friction #26: the slice-01 skip marker is removed in DELIVER
# (Phase A_GREEN_ATS) -- git_stash_guard.py now exists and the ATs run GREEN.
scenarios("../slice-01-git-stash-guard.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> GitStashGuardFixture:
    """Per-test git-stash guard fixture rooted at an isolated tmp target."""
    return GitStashGuardFixture(target_root=tmp_path / "target")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured HookInvocation across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given(
    "the operator is inside a Claude Code session with the git-stash guard "
    "PreToolUse hook installed on Bash"
)
def given_hook_installed(fixture: GitStashGuardFixture) -> None:
    fixture.ensure_hook_installed()


@given(
    'the git-stash guard PreToolUse hook entry point is the script "git_stash_guard"'
)
def given_hook_entry_point(fixture: GitStashGuardFixture) -> None:
    fixture.ensure_hook_installed()


@given(
    "the hook speaks the Claude Code PreToolUse protocol — JSON stdin, "
    "JSON stdout, exit code as decision signal"
)
def given_hook_protocol(fixture: GitStashGuardFixture) -> None:
    fixture.ensure_hook_installed()


@given(
    'the hook writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format'
)
def given_audit_log_format(fixture: GitStashGuardFixture) -> None:
    fixture.ensure_hook_installed()


# --- Preconditions (kill-switch env state) ---------------------------------


@given('the operator\'s environment does NOT carry "NWAVE_GIT_STASH_ALLOW"')
def given_allow_env_absent(fixture: GitStashGuardFixture) -> None:
    fixture.clear_allow_env()


@given(
    parsers.parse(
        'the operator\'s environment carries "NWAVE_GIT_STASH_ALLOW" set to "{value}"'
    )
)
def given_allow_env_set(fixture: GitStashGuardFixture, value: str) -> None:
    fixture.set_allow_env(value)


# --- Action ----------------------------------------------------------------


@when(
    parsers.parse(
        'the Claude Code session prepares to run the Bash command "{command}"'
    )
)
def when_session_prepares_bash(fixture: GitStashGuardFixture, command: str) -> None:
    fixture.prepare_bash_event(command)


@when("the git-stash guard receives the Bash invocation event")
def when_guard_receives_event(
    fixture: GitStashGuardFixture, result_box: dict[str, object]
) -> None:
    result_box["invocation"] = fixture.invoke_git_stash_guard()


# --- Observation (Then step delegates) -------------------------------------


@then("the hook returns a block decision to Claude Code")
def then_block_decision_returned(
    fixture: GitStashGuardFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_block_decision_returned(result_box["invocation"])  # type: ignore[arg-type]


@then("the hook approves the Bash invocation")
def then_approve_decision_returned(
    fixture: GitStashGuardFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_approve_decision_returned(result_box["invocation"])  # type: ignore[arg-type]


@then(
    parsers.parse('the hook\'s decision reason names the safe alternative "{phrase}"')
)
def then_reason_names_alternative(
    fixture: GitStashGuardFixture, result_box: dict[str, object], phrase: str
) -> None:
    fixture.assert_block_reason_names_phrase(result_box["invocation"], phrase)  # type: ignore[arg-type]


@then(
    parsers.parse('the hook\'s decision reason names the bypass mechanism "{phrase}"')
)
def then_reason_names_bypass(
    fixture: GitStashGuardFixture, result_box: dict[str, object], phrase: str
) -> None:
    fixture.assert_block_reason_names_phrase(result_box["invocation"], phrase)  # type: ignore[arg-type]


@then("the Bash invocation is refused before the git stash subprocess is spawned")
def then_bash_refused_before_spawn(
    fixture: GitStashGuardFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_bash_invocation_refused_before_spawn(result_box["invocation"])  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit log gains exactly one new "{event_name}" event for this invocation'
    )
)
def then_one_new_bypass_event(
    fixture: GitStashGuardFixture, result_box: dict[str, object], event_name: str
) -> None:
    _ = event_name  # event_name is "GitStashBypassUsed" by feature design
    fixture.assert_exactly_one_new_bypass_event(result_box["invocation"])  # type: ignore[arg-type]


@then(parsers.parse('the new bypass event names the git-stash command "{command}"'))
def then_bypass_event_names_command(
    fixture: GitStashGuardFixture, result_box: dict[str, object], command: str
) -> None:
    fixture.assert_bypass_event_names_command(result_box["invocation"], command)  # type: ignore[arg-type]


@then(
    parsers.parse(
        'the audit log carries zero new "{event_name}" events for this invocation'
    )
)
def then_zero_new_bypass_events(
    fixture: GitStashGuardFixture, result_box: dict[str, object], event_name: str
) -> None:
    _ = event_name  # event_name is "GitStashBypassUsed" by feature design
    fixture.assert_zero_new_bypass_events(result_box["invocation"])  # type: ignore[arg-type]


@then("the target machine filesystem is unchanged outside transient hook logging")
def then_filesystem_unchanged_outside_hook_logs(
    fixture: GitStashGuardFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_filesystem_unchanged_outside_audit_log_and_hook_logs(
        result_box["invocation"]  # type: ignore[arg-type]
    )


# --- Unused-imports guard (ruff F401) --------------------------------------

# HookInvocation is re-exported for downstream slice authors to re-use the
# type when extending the step set; ruff will flag F401 without this line.
_TYPE_REEXPORTS = (HookInvocation,)
