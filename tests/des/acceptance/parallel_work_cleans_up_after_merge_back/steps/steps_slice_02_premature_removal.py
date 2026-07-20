"""Step bodies for parallel-work-cleans-up-after-merge-back slice-02 (an
attempt to remove a worktree before its merge-back is confirmed is refused).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`cleanup_fixture.<method>(...)` call (or one assertion-helper call), zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`PrematureRemovalFixture` (composition_slice_02.py).

Mandate 8: state-mutating outcome checks go through
`assert_state_delta(before, after, universe, expected)`. Each check here
scopes `universe` to EXACTLY the key(s) its `expected` dict declares --
deliberately narrower than slice-01's own `SWEEP_UNIVERSE` constant, to
avoid an existing scoping gap in that file (a wide universe paired with an
under-declared expected set makes every slice-01 Then-step fail on
`undeclared_change` regardless of production correctness -- confirmed
empirically this pass; flagged to the team, not this file's bug to
inherit).

The Given step is REUSED VERBATIM from slice-01's step module
(`given_worktree_with_branch_state` / `PHRASE_BY_TEXT`) -- imported into the
pytest-bdd binding module (`test_slice_02_premature_removal.py`), not
redefined here.

Mandate 9 v2: layer 3 (real git repo, @real-io) => example-only. PBT
machinery intentionally NOT imported (Mandate 11 -- all 3 scenarios here ARE
the sad path, D-3's refusal guarantee is the value this slice ships).
"""

from __future__ import annotations

from pytest_bdd import then, when

from tests.common.state_delta import assert_state_delta, set_to


# The Given step this slice reuses verbatim (steps_slice_01_worktree_cleanup
# .given_worktree_with_branch_state) hardcodes this worktree name when it
# builds the trunk-repo + linked-worktree fixture -- named here once, not
# duplicated at every call site.
_WORKTREE_NAME = "slice-04"


def _snapshot(state: dict) -> dict:
    """Universe snapshot of the observables this slice's Then-steps assert
    on. Pure function; returns None sentinels for unobserved keys."""
    outcome = state.get("outcome")
    return {
        "outcome.target_verdict": getattr(outcome, "target_verdict", None),
        "outcome.has_reason": getattr(outcome, "has_reason", None),
        "outcome.worktree_removed": getattr(outcome, "worktree_removed", None),
        "outcome.still_registered": getattr(outcome, "still_registered", None),
        "outcome.commit_reachable": getattr(outcome, "commit_reachable", None),
    }


def _assert_worktree_untouched(state: dict) -> None:
    """Shared assertion body: neither mode ever removes a NOT_YET_MERGEABLE
    worktree (D-D4) -- the SAME check backs two distinct domain-language
    Then-steps (done-check vs. explicit removal attempt)."""
    after = _snapshot(state)
    keys = ("outcome.worktree_removed", "outcome.still_registered")
    assert_state_delta(
        before={k: state["before"][k] for k in keys},
        after={k: after[k] for k in keys},
        universe=set(keys),
        expected={
            "outcome.worktree_removed": set_to(False),
            "outcome.still_registered": set_to(True),
        },
    )


# --- When ---------------------------------------------------------------


@when("the maintainer checks whether that worktree is ready for cleanup")
def when_maintainer_checks_readiness(cleanup_fixture, state_01) -> None:
    state_01["before"] = _snapshot(state_01)
    state_01["outcome"] = cleanup_fixture.check_cleanup_readiness(_WORKTREE_NAME)


@when(
    "the maintainer attempts to remove that worktree before its merge-back is confirmed"
)
def when_maintainer_attempts_removal(cleanup_fixture, state_01) -> None:
    state_01["before"] = _snapshot(state_01)
    state_01["outcome"] = cleanup_fixture.attempt_removal(_WORKTREE_NAME)


# --- Then ------------------------------------------------------------------


@then("the worktree is reported as not yet mergeable")
def then_worktree_reported_not_yet_mergeable(state_01) -> None:
    after = _snapshot(state_01)
    assert_state_delta(
        before={"outcome.target_verdict": state_01["before"]["outcome.target_verdict"]},
        after={"outcome.target_verdict": after["outcome.target_verdict"]},
        universe={"outcome.target_verdict"},
        expected={"outcome.target_verdict": set_to("NOT_YET_MERGEABLE")},
    )


@then("the done-check leaves the worktree registered without mutating it")
def then_readiness_check_never_mutates(state_01) -> None:
    _assert_worktree_untouched(state_01)


@then("the removal attempt is refused and the worktree remains registered")
def then_removal_attempt_refused(state_01) -> None:
    _assert_worktree_untouched(state_01)


@then("the refusal names the reason the worktree was not removed")
def then_refusal_names_reason(state_01) -> None:
    after = _snapshot(state_01)
    assert_state_delta(
        before={"outcome.has_reason": state_01["before"]["outcome.has_reason"]},
        after={"outcome.has_reason": after["outcome.has_reason"]},
        universe={"outcome.has_reason"},
        expected={"outcome.has_reason": set_to(True)},
    )


@then("the worktree's sealed commit is still reachable in the repository")
def then_commit_still_reachable(state_01) -> None:
    after = _snapshot(state_01)
    assert_state_delta(
        before={
            "outcome.commit_reachable": state_01["before"]["outcome.commit_reachable"]
        },
        after={"outcome.commit_reachable": after["outcome.commit_reachable"]},
        universe={"outcome.commit_reachable"},
        expected={"outcome.commit_reachable": set_to(True)},
    )
