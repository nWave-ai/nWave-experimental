"""Step bodies for oss-spine-watchdog slice-06 (timeout-block countability).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`timeout_countability_fixture.<method>(...)` call (or one assertion), and contains
zero control flow (`if`/`for`/`while`/`try`). All business logic lives in
`TimeoutCountabilityFixture` (composition_slice_06.py).

Mandate 8: the state-mutating outcome assertion (AT-01, a durable terminal record
appended) goes through `assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`GateOutcome` (`outcome.terminated`, `outcome.blocked`) — never Popen handles, never
the transcript JSONL bytes, never the raw ledger path (Mandate 8 — port-exposed
observables only).

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + forced-timeout real
hook subprocess against tmp_path, @real-io — the driven set includes a real
filesystem adapter + a real git subprocess + a real hook subprocess) → example-only.
PBT machinery is intentionally NOT imported (Mandate 11 — sad paths enumerated
explicitly).

Mandate-13: ATs drive through the production G_COMMIT exit-gate driving port (the
real `handle_subagent_stop` hook subprocess, with the gate subprocess forced to time
out) — NEVER a direct
`from des...subagent_stop_handler import _handle_g_commit_exit_gate` invocation in
test bodies. The composition fires the hook over its JSON stdin protocol.
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_06 import TimeoutBlockHistory


# --- Universe (Mandate 8): port-exposed observables only -----------------

GATE_UNIVERSE = frozenset(
    {
        "outcome.terminated",
        "outcome.blocked",
    }
)


def _gate_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the gate observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook fires.
    """
    outcome = state.get("outcome")
    return {
        "outcome.terminated": getattr(outcome, "terminated", None),
        "outcome.blocked": getattr(outcome, "blocked", None),
    }


# --- Given ----------------------------------------------------------------


@given("two prior gate-timeout blocks are recorded for the slice and commit")
def given_two_prior_timeout_blocks(timeout_countability_fixture, state_06) -> None:
    state_06["history"] = TimeoutBlockHistory.THIRD_IDENTICAL_TIMEOUT


@given("no prior gate-timeout block is recorded for the slice and commit")
def given_no_prior_timeout_block(timeout_countability_fixture, state_06) -> None:
    state_06["history"] = TimeoutBlockHistory.FIRST_TIMEOUT_NO_PRIORS


# --- When -----------------------------------------------------------------


@when("the commit exit gate times out for the returning crafter")
def when_commit_exit_gate_times_out(timeout_countability_fixture, state_06) -> None:
    state_06["before"] = _gate_snapshot(state_06)
    state_06["outcome"] = timeout_countability_fixture.run_forced_timeout_gate(
        history=state_06["history"]
    )


# --- Then -----------------------------------------------------------------


@then(
    "the spine closes the timed-out commit gate with a durable terminal instead of "
    "re-firing the crafter"
)
def then_spine_closes_gate_with_durable_terminal(state_06) -> None:
    after = _gate_snapshot(state_06)
    assert_state_delta(
        before={k: state_06["before"][k] for k in GATE_UNIVERSE},
        after={k: after[k] for k in GATE_UNIVERSE},
        universe=GATE_UNIVERSE,
        expected={
            "outcome.terminated": set_to(True),
            "outcome.blocked": set_to(False),
        },
    )


@then("the spine re-fires the crafter because a single timeout does not terminate")
def then_spine_refires_on_single_timeout(state_06) -> None:
    assert state_06["outcome"].terminated is False, (
        "anti-vacuity discriminator: the bounded-block terminal must fire ONLY on "
        'the Nth (3rd) identical `(slice, sha, "gate-timeout")` block, NOT on any '
        "single timeout. A first timeout with no priors has a bounded-block count of "
        "0 (< N-1=2) → the gate must take the ORDINARY block path (a {decision:block} "
        "re-fire), NOT terminate. A count-blind fix that terminated EVERY timeout "
        "would wrongly terminate this first single timeout — this pin guards the fix "
        "against over-firing. Pairs with the 3rd-identical-timeout pin to bracket the "
        "contract: a fix that NEVER counts the timeout block fails the 3rd-timeout "
        "terminal pin; one that ALWAYS terminates a timeout fails THIS pin. "
        f"Got terminated={state_06['outcome'].terminated}, "
        f"blocked={state_06['outcome'].blocked}"
    )
