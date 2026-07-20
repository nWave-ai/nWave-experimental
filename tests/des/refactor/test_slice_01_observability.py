# @feature-des-refactor-fixer-swarm
# @slice-01
"""Observability ATs -- slice-01 (des-refactor-fixer-swarm), closing the 3
real-CLI EXAMINE opacity flags.

slice-01's core drain loop is 18/18 green and EXAMINE-verified, but the real
`des refactor` CLI was found MUTE where an operator needs feedback -- and one
gap violates the standing "every failure explains what/why/how" mandate. This
file pins the CLI's OWN self-reporting as observable behaviour:

1. **Silent success** -- a drain that DID work exits 0 with ZERO stdout.
2. **Silent empty/unparseable pile** -- a pile with 0 parseable items (empty,
   or a line that fails the item grammar) exits 0 with ZERO output.
3. **Opaque worktree failure** -- when `git worktree add` fails for the real
   item, the failure escapes as a raw, uncaught `subprocess.CalledProcessError`
   traceback -- no WHAT/WHY/HOW.

Layer 2 in-process (`composition.call_refactor_main_in_process`) -- the REAL
`des.cli.refactor.main` entry, no interpreter fork; subprocess-e2e stays
reserved for the ONE `@walking_skeleton` in test_slice_01_walking_skeleton.py.
`capsys` captures the CLI's OWN stdout/stderr -- the exact observable a real
operator sees on their terminal, never a harness/implementation internal.

RED-scaffold note: today's `des.cli.refactor.main` never prints anything on
success or on a probe-refused no-op, and lets a mid-drain git failure escape
as a raw exception -- every assertion below fails for that genuine reason
(MISSING_FUNCTIONALITY: the CLI does not yet report), never a collection or
import error.

covers: R-DES-REFACTOR-WS
"""

from __future__ import annotations

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# importing `des.cli.refactor` triggers `des.cli`'s package `__init__`, which
# fires the runtime freshness gate's ONE-SHOT `des.runtime.freshness.*` stderr
# event on first import in this process (des/runtime/freshness.py: "Fires at
# the import-time of `des.cli`"). Forcing that one-shot print to happen here,
# before any test's `capsys` fixture is active, keeps every test below's
# captured stdout/stderr free of freshness noise regardless of pytest
# collection/execution order.
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance


# --- Flag 1: silent success ------------------------------------------------


def test_a_successful_drain_reports_the_count_the_item_id_and_the_integration_branch(
    tmp_path, capsys
):
    """Given a pile with one item that drains and merges cleanly, When
    `des refactor` runs, Then stdout reports the count of items drained, the
    drained item's id, and the integration branch it landed on -- never a
    silent exit 0 that looks identical to nothing having happened.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    exit_code = composition.call_refactor_main_in_process(
        agent_cmd=composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0, (
        f"a successful drain must exit 0; got exit_code={exit_code}, "
        f"stderr={captured.err!r}"
    )
    assert captured.out.strip() != "", (
        "a drain that DID work must report on stdout -- got completely "
        f"empty stdout for a real, successful drain (exit_code={exit_code})"
    )
    assert "1" in captured.out, (
        f"stdout must report the COUNT of items drained; got: {captured.out!r}"
    )
    assert "TD-001" in captured.out, (
        f"stdout must name the drained item's id; got: {captured.out!r}"
    )
    assert composition.integration_branch in captured.out, (
        "stdout must name the integration branch the fix landed on; got: "
        f"{captured.out!r}"
    )


# --- Flag 2: silent empty/unparseable pile ---------------------------------


def test_a_pile_with_zero_pending_items_reports_zero_parsed_never_a_silent_exit_zero(
    tmp_path, capsys
):
    """Given a pile with zero pending items, When `des refactor` runs, Then
    stdout names that ZERO items were parsed -- never a silent exit 0 that is
    indistinguishable from "everything already drained".
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_empty_pile()

    exit_code = composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()

    assert exit_code == 0, (
        f"an empty pile must exit 0; got exit_code={exit_code}, stderr={captured.err!r}"
    )
    assert captured.out.strip() != "", (
        "an empty pile must report ZERO items parsed on stdout -- got "
        "completely empty stdout, indistinguishable from a crash or a "
        "silently-skipped run"
    )
    assert "0" in captured.out, (
        f"stdout must name the ZERO-items-parsed count; got: {captured.out!r}"
    )


def test_a_pile_line_that_fails_the_item_grammar_is_named_as_skipped(tmp_path, capsys):
    """Given a pile whose only content line does NOT match the item grammar
    (a real parse-miss, not an empty file), When `des refactor` runs, Then
    stdout names that zero items parsed AND that a non-blank line was
    SKIPPED for failing the grammar -- never a silent exit 0 that looks
    identical to a genuinely empty pile.

    CORRECTED (fix-refactor-pile-grammar-undocumented, slice-01): this AT
    originally pinned `exit_code == 0` for this exact arrangement -- itself
    the GDP-3/oracle-(c) defect class ("prints a failure, exits 0") the
    fixing feature exists to close. An unparseable-content pile is a
    REFUSAL (the operator's own input could not be understood), distinct
    from a genuinely empty pile (still exit 0, see the sibling test above)
    -- so the exit code must be non-zero here. The full grammar-teaching
    contract (concrete example, named line, producing-tool-or-honesty) is
    pinned in test_slice_01_pile_grammar_refusal.py; this test keeps its
    narrower original mission (skipped-line naming) with the exit code
    corrected to match.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_with_unparseable_line(
        "- [ ] this-line-does-not-match-the-item-grammar-at-all"
    )

    exit_code = composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()

    assert exit_code != 0, (
        "a pile whose only content is unparseable is a REFUSAL, not a "
        f"quiet no-op -- got exit_code={exit_code} (expected non-zero), "
        f"stdout={captured.out!r} stderr={captured.err!r}"
    )
    combined = captured.out + captured.err
    assert combined.strip() != "", (
        "a pile whose only content line fails to parse must still report "
        "-- got completely empty stdout+stderr"
    )
    assert "0" in combined, (
        f"the refusal must name that ZERO items were parsed; got: {combined!r}"
    )
    lowered = combined.lower()
    assert any(marker in lowered for marker in ("skip", "not match", "unparseable")), (
        "the refusal must name that a non-blank line was SKIPPED for failing the "
        f"item grammar; got: {combined!r}"
    )


# --- Flag 3: opaque worktree failure (what/why/how mandate) ----------------


def test_a_worktree_creation_failure_refuses_with_what_why_how_never_a_raw_traceback(
    tmp_path, capsys
):
    """Given the branch `des refactor` will try to create for the pending
    item already exists (a real, reproducible `git worktree add -b` failure),
    When `des refactor` runs, Then it refuses naming WHAT failed (worktree
    creation), WHY (the underlying git reason), and HOW to fix it -- and
    NEVER lets a raw `subprocess.CalledProcessError` / Python traceback
    escape to the operator.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")
    composition.prepare_colliding_branch_for_item("TD-001")

    try:
        exit_code = composition.call_refactor_main_in_process(agent_cmd="true")
    except Exception as exc:
        pytest.fail(
            "des refactor must NEVER let a worktree-creation failure escape "
            f"as a raw {type(exc).__name__} -- it must refuse with a named "
            f"WHAT/WHY/HOW message instead. Escaped: {exc!r}"
        )
        return  # pragma: no cover - pytest.fail always raises

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert exit_code != 0, (
        "a worktree-creation failure must exit non-zero (a named refusal), "
        f"never the success exit code; got exit_code={exit_code}"
    )
    assert "Traceback (most recent call last)" not in combined, (
        "a worktree-creation failure must never surface as a raw Python "
        f"traceback; got: {combined!r}"
    )
    assert "CalledProcessError" not in combined, (
        "a worktree-creation failure must never surface the raw "
        f"subprocess.CalledProcessError type name; got: {combined!r}"
    )
    lowered = combined.lower()
    assert "worktree" in lowered, (
        f"the refusal must name WHAT failed (worktree creation); got: {combined!r}"
    )
    assert any(marker in lowered for marker in ("already exists", "git", "reason")), (
        f"the refusal must name WHY it failed; got: {combined!r}"
    )
    assert any(marker in lowered for marker in ("run", "repo", "expect", "fix")), (
        f"the refusal must name HOW to fix it (repo/cwd expectation); got: {combined!r}"
    )


def test_running_outside_a_usable_git_repository_refuses_at_startup_loudly(
    tmp_path, capsys
):
    """AT-12 probe-contract companion -- Given `project_root` is NOT a usable
    git repository (the D1 `GitWorktreePort.probe()` surface, Earned Trust
    principle 13), When `des refactor` starts, Then it refuses LOUD -- naming
    WHAT (the git/worktree startup probe) failed -- never a silent exit that
    is indistinguishable from "nothing to drain".
    """
    composition = RefactorSwarmComposition(tmp_path)
    # Deliberately skip init_git_repo(): project_root is a plain, non-git
    # directory -- the exact "target isn't a usable git repo" arrangement.
    composition.seed_pile_item(item_id="TD-001")

    try:
        exit_code = composition.call_refactor_main_in_process(agent_cmd="true")
    except Exception as exc:
        pytest.fail(
            "a non-git project root must never let an exception escape raw "
            f"-- it must refuse with a WHAT/WHY/HOW message instead. "
            f"Escaped: {type(exc).__name__}: {exc}"
        )
        return  # pragma: no cover - pytest.fail always raises

    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert exit_code != 0, (
        "starting des refactor outside a usable git repository must refuse "
        f"with a non-zero exit code; got exit_code={exit_code}"
    )
    assert combined.strip() != "", (
        "a startup probe refusal must be LOUD -- got completely empty "
        "stdout+stderr for a refused run"
    )
    lowered = combined.lower()
    assert any(marker in lowered for marker in ("git", "repo", "worktree")), (
        f"the refusal must name WHAT failed (the git/worktree probe); got: {combined!r}"
    )
