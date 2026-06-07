"""Step bodies for oss-spine-watchdog slice-02 (bounded-block terminal N=3).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`bounded_block_fixture.<method>(...)` call (or one assertion), and contains zero
control flow (`if`/`for`/`while`/`try`). All business logic lives in
`BoundedBlockFixture` (composition_slice_02.py).

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`InterceptOutcome` (`outcome.blocked`, `outcome.names_bound`) — never Popen
handles, never the transcript JSONL bytes, never the raw ledger path (Mandate 8 —
port-exposed observables only).

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + real hook subprocess
against tmp_path, @real-io — the driven set includes a real filesystem adapter +
a real git subprocess + a real hook subprocess) → example-only. PBT machinery is
intentionally NOT imported (Mandate 11 — sad paths enumerated explicitly).

Mandate-13: ATs drive through the production G_COMMIT exit-gate driving port (the
real `handle_subagent_stop` hook subprocess) — NEVER a direct
`from des...subagent_stop_handler import _handle_g_commit_exit_gate` invocation in
test bodies. The composition fires the hook over its JSON stdin protocol.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_02 import PROGRESS_BY_PHRASE, BlockProgress


# --- Universe (Mandate 8): port-exposed observables only -----------------

INTERCEPT_UNIVERSE = frozenset(
    {
        "outcome.blocked",
        "outcome.names_bound",
    }
)


def _intercept_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the intercept observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the intercept runs.
    """
    outcome = state.get("outcome")
    return {
        "outcome.blocked": getattr(outcome, "blocked", None),
        "outcome.names_bound": getattr(outcome, "names_bound", None),
    }


# --- Given ----------------------------------------------------------------


@given("two prior identical exit-gate blocks are recorded for the slice and commit")
def given_two_prior_identical_blocks(bounded_block_fixture, state_02) -> None:
    state_02["progress"] = BlockProgress.IDENTICAL
    state_02["before"] = _intercept_snapshot(state_02)


@given(
    parsers.parse(
        "two prior exit-gate blocks are recorded then the next block arrives "
        "{progress_phrase}"
    )
)
def given_two_prior_blocks_then_progress(state_02, progress_phrase: str) -> None:
    state_02["progress"] = PROGRESS_BY_PHRASE[progress_phrase]


# --- When -----------------------------------------------------------------


@when("the spine evaluates the next exit-gate block for the same slice")
def when_spine_evaluates_next_block(bounded_block_fixture, state_02) -> None:
    bounded_block_fixture.build_blocking_commit()
    state_02["outcome"] = bounded_block_fixture.run_intercept(
        progress=state_02["progress"]
    )


@when("the spine evaluates the arriving exit-gate block")
def when_spine_evaluates_arriving_block(bounded_block_fixture, state_02) -> None:
    bounded_block_fixture.build_blocking_commit()
    state_02["outcome"] = bounded_block_fixture.run_intercept(
        progress=state_02["progress"]
    )


# --- Then -----------------------------------------------------------------


@then("the spine terminates the agent loud instead of re-firing it")
def then_spine_terminates_loud(state_02) -> None:
    after = _intercept_snapshot(state_02)
    assert_state_delta(
        before={k: state_02["before"][k] for k in INTERCEPT_UNIVERSE},
        after={k: after[k] for k in INTERCEPT_UNIVERSE},
        universe=INTERCEPT_UNIVERSE,
        expected={
            "outcome.blocked": set_to(False),
            "outcome.names_bound": set_to(True),
        },
    )


@then("the spine re-fires the agent because genuine progress reset the count")
def then_spine_refires_on_progress(state_02) -> None:
    assert state_02["outcome"].blocked is True, (
        "progress-resets discriminator: the bounded-block terminal must fire ONLY "
        "on 3 IDENTICAL blocks for the same (slice, pinned_commit_sha); genuine "
        "progress (a newly amended commit, or a different gate failure) RESETS the "
        "count, so the spine must still re-fire the agent (emit a {decision:block}) "
        "rather than terminate. A gate that terminates at the 3rd block regardless "
        f"of key would wrongly terminate here. Got blocked={state_02['outcome'].blocked}, "
        f"event={state_02['outcome'].decision_event!r}, "
        f"diagnostic={state_02['outcome'].diagnostic!r}"
    )
