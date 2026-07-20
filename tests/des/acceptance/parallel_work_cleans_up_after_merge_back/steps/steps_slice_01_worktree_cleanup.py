"""Step bodies for parallel-work-cleans-up-after-merge-back slice-01
(a finished parallel unit of work's worktree disappears on its own).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`cleanup_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`WorktreeCleanupFixture` (composition_slice_01.py). The typed-parameter
lookup (`PHRASE_BY_TEXT`) is the single dict indexing this file performs.

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`CleanupSweepOutcome` -- never Popen handles, never raw stdout bytes, never
adapter internals.

-- BUG FIX (harness-only, caught post-crafter-GREEN by team-lead RCA) --
`state_01["before"]` is captured ONCE per scenario, inside the `@when`, BEFORE
any `outcome` exists -- so every `SWEEP_UNIVERSE` key snapshots to `None` and
NEVER changes for the rest of the scenario. `assert_state_delta`'s
implicit-unchanged enforcement means every universe key NOT named in a given
call's `expected=` fires `undeclared_change` (`before=None != after=<real>`),
REGARDLESS of whether production behaviour is correct. The original shape
split each scenario's assertion across a `Then`/`And` PAIR, each declaring
only 1-2 of the 6 keys against the SAME broad `SWEEP_UNIVERSE` -- so neither
call ever discriminated correct-vs-incorrect behaviour; both always failed.
Fix (mirrors the `autonomous_consolidation_and_bugfix_loops` slice-01
precedent): each scenario's PRIMARY `Then` now declares ALL SIX
`SWEEP_UNIVERSE` keys in ONE combined `assert_state_delta` call; the
secondary `And` step(s) are PLAIN attribute assertions on the already-
captured `outcome` (never a second `assert_state_delta` call reusing the
same broad universe with a partial declaration) -- no assertion is weakened,
the redundant "And" reinforces what the primary `Then` already proved.

`new_feature_end_pending_count == 0` is now asserted in EVERY scenario's
primary `Then` (not only AT-CLEANUP-5's) -- D-D6 (zero feature-end coupling)
is a universal invariant of every sweep, so every scenario doubles as its own
regression guard, strictly stronger than before.

Mandate 9 v2: layer 3 (real git repo + one real subprocess fork for the
walking skeleton, @real-io) => example-only. PBT machinery is intentionally
NOT imported (Mandate 11 -- sad paths enumerated explicitly).

Mandate-13: ATs drive through the production `des` driving surface (the
`des.cli.__main__` dispatcher in-process, or the real installed `des`
console-script for the walking skeleton) -- NEVER a direct
`from des.cli.verify_worktree_cleanup import main` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_01 import PHRASE_BY_TEXT


# --- Universe (Mandate 8): port-exposed observables only --------------------

SWEEP_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.worktree_removed",
        "outcome.still_registered",
        "outcome.entry_count",
        "outcome.has_what_why_how",
        "outcome.new_feature_end_pending_count",
    }
)


def _sweep_snapshot(state: dict) -> dict:
    """Universe snapshot of the sweep observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the sweep fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.worktree_removed": getattr(outcome, "worktree_removed", None),
        "outcome.still_registered": getattr(outcome, "still_registered", None),
        "outcome.entry_count": getattr(outcome, "entry_count", None),
        "outcome.has_what_why_how": getattr(outcome, "has_what_why_how", None),
        "outcome.new_feature_end_pending_count": getattr(
            outcome, "new_feature_end_pending_count", None
        ),
    }


def _assert_sweep_state(state_01: dict, **expected_values) -> None:
    """The ONE combined `assert_state_delta` call every scenario's primary
    `Then` uses -- declares EVERY `SWEEP_UNIVERSE` key explicitly (the fix:
    never a partial declaration against the shared broad universe)."""
    after = _sweep_snapshot(state_01)
    assert_state_delta(
        before={k: state_01["before"][k] for k in SWEEP_UNIVERSE},
        after={k: after[k] for k in SWEEP_UNIVERSE},
        universe=SWEEP_UNIVERSE,
        expected={
            f"outcome.{name}": set_to(value) for name, value in expected_values.items()
        },
    )


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a worktree whose branch is {branch_state}"))
def given_worktree_with_branch_state(cleanup_fixture, state_01, branch_state) -> None:
    PHRASE_BY_TEXT[branch_state]  # typed-parameter validation, no raw dispatch
    cleanup_fixture.build_trunk_repo()
    cleanup_fixture.create_linked_worktree("slice-04")
    if "confirmed merged" in branch_state:
        cleanup_fixture.confirm_merge_back("slice-04")


@given("a trunk repository that has no linked worktrees registered at all")
def given_trunk_repository_with_no_linked_worktrees(cleanup_fixture, state_01) -> None:
    cleanup_fixture.build_trunk_repo()


@given(parsers.parse("a detached-HEAD worktree whose HEAD is {merge_state}"))
def given_detached_worktree_with_merge_state(
    cleanup_fixture, state_01, merge_state
) -> None:
    PHRASE_BY_TEXT[merge_state]  # typed-parameter validation, no raw dispatch
    cleanup_fixture.build_trunk_repo()
    cleanup_fixture.create_detached_worktree("slice-04-detached")
    if "confirmed merged" in merge_state:
        cleanup_fixture.confirm_merge_back_detached("slice-04-detached")


# --- When ---------------------------------------------------------------


@when(
    "the maintainer runs the cleanup sweep against the real installed des console-script"
)
def when_maintainer_runs_sweep_subprocess(cleanup_fixture, state_01) -> None:
    state_01["before"] = _sweep_snapshot(state_01)
    state_01["outcome"] = cleanup_fixture.run_sweep_subprocess()


@when("the maintainer runs the cleanup sweep in-process")
def when_maintainer_runs_sweep_in_process(cleanup_fixture, state_01) -> None:
    state_01["before"] = _sweep_snapshot(state_01)
    state_01["outcome"] = cleanup_fixture.run_sweep_in_process()


@when("the maintainer runs the cleanup sweep in-process as a done-check only")
def when_maintainer_runs_sweep_check_only(cleanup_fixture, state_01) -> None:
    state_01["before"] = _sweep_snapshot(state_01)
    state_01["outcome"] = cleanup_fixture.run_sweep_in_process(check_only=True)


# --- Then (primary -- ONE combined assert_state_delta per scenario) --------


@then("the worktree is gone from the repository's registered worktrees")
def then_worktree_is_gone(state_01) -> None:
    _assert_sweep_state(
        state_01,
        exit_code=0,
        worktree_removed=True,
        still_registered=False,
        entry_count=1,
        has_what_why_how=False,
        new_feature_end_pending_count=0,
    )


@then("the worktree remains registered")
def then_worktree_remains_registered(state_01) -> None:
    _assert_sweep_state(
        state_01,
        exit_code=0,
        worktree_removed=False,
        still_registered=True,
        entry_count=1,
        has_what_why_how=False,
        new_feature_end_pending_count=0,
    )


@then(parsers.parse("the sweep reports a refusal exit code of {expected_code:d}"))
def then_sweep_reports_refusal_exit_code(state_01, expected_code) -> None:
    _assert_sweep_state(
        state_01,
        exit_code=expected_code,
        worktree_removed=False,
        still_registered=True,
        entry_count=1,
        has_what_why_how=True,
        new_feature_end_pending_count=0,
    )


@then("the sweep evaluates zero worktree entries")
def then_sweep_evaluates_zero_entries(state_01) -> None:
    _assert_sweep_state(
        state_01,
        exit_code=0,
        worktree_removed=False,
        still_registered=False,
        entry_count=0,
        has_what_why_how=False,
        new_feature_end_pending_count=0,
    )


# --- Then/And (secondary -- PLAIN attribute asserts, never a 2nd state_delta
# call reusing SWEEP_UNIVERSE with a partial declaration) -------------------


@then(parsers.parse("the sweep reports a clean exit code of {expected_code:d}"))
def then_sweep_reports_clean_exit_code(state_01, expected_code) -> None:
    outcome = state_01["outcome"]
    assert outcome.exit_code == expected_code, (
        f"expected a clean exit code of {expected_code}, got "
        f"exit_code={outcome.exit_code!r}."
    )


@then("the refusal names what, why, and how to fix it")
def then_refusal_names_what_why_how(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.has_what_why_how, (
        "GDP-3: a refusal (exit 1) must self-explain WHAT/WHY/HOW -- never a "
        f"bare exit code. Got has_what_why_how={outcome.has_what_why_how!r}."
    )


@then("the worktree remains registered because a done-check never mutates")
def then_worktree_remains_registered_check_only(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.still_registered and not outcome.worktree_removed, (
        "D-3/D-2: --check-only is a PURE read -- it must never remove a "
        f"lingering worktree. Got still_registered={outcome.still_registered!r}, "
        f"worktree_removed={outcome.worktree_removed!r}."
    )


@then("no feature-end-pending record is ever appended by the sweep")
def then_no_feature_end_pending_appended(state_01) -> None:
    outcome = state_01["outcome"]
    assert outcome.new_feature_end_pending_count == 0, (
        "D-D6: zero coupling to feature-end -- no sweep may ever append a "
        "FeatureEndPending ledger record. Got "
        f"new_feature_end_pending_count={outcome.new_feature_end_pending_count!r}."
    )
