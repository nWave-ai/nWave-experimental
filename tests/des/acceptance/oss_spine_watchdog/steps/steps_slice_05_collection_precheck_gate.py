"""Step bodies for oss-spine-watchdog slice-05 (collection-precheck gate-wiring).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`collection_precheck_gate_fixture.<method>(...)` call (or one assertion), and
contains zero control flow (`if`/`for`/`while`/`try`). All business logic lives in
`CollectionPrecheckGateFixture` (composition_slice_05.py).

Mandate 8: the state-mutating outcome assertion (AT-01, a durable terminal record
appended) goes through `assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`GateOutcome` — never Popen handles, never the transcript JSONL bytes, never the raw
ledger path (Mandate 8 — port-exposed observables only).

Mandate 9 v2: layer 3/4 (real git repo + real ledger JSONL + real collection-precheck
subprocess + real hook subprocess against tmp_path, @real-io — the driven set includes
a real filesystem adapter + a real git subprocess + a real hook subprocess) →
example-only. PBT machinery is intentionally NOT imported (Mandate 11 — sad paths
enumerated explicitly).

Mandate-13: ATs drive through the production SubagentStop driving port (the real
`handle_subagent_stop` G_COMMIT exit-gate hook subprocess) — NEVER a direct
`from des...subagent_stop_handler import _handle_g_commit_exit_gate` invocation in
test bodies. The composition fires the hook over its JSON stdin protocol. This is the
AT-tier fix BLOCKER-1 demands: assert the GATE INVOKES the precheck (terminates on a
real collection crash), NOT that the `--collect-only` probe in isolation names a
module (slice-01's wrong tier).
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_05 import SuiteCollectability


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


@given("a committed slice whose contract suite crashes on collection")
def given_committed_slice_crashes_on_collection(
    collection_precheck_gate_fixture, state_05
) -> None:
    state_05["collectability"] = SuiteCollectability.COLLECTION_CRASHES


@given(
    "a committed slice whose contract suite collects cleanly but still fails the commit gate"
)
def given_committed_slice_collects_clean_but_fails_gate(
    collection_precheck_gate_fixture, state_05
) -> None:
    state_05["collectability"] = SuiteCollectability.COLLECTS_CLEAN


# --- When -----------------------------------------------------------------


@when("the spine runs the commit exit gate on the returning crafter")
def when_spine_runs_commit_exit_gate(
    collection_precheck_gate_fixture, state_05
) -> None:
    state_05["before"] = _gate_snapshot(state_05)
    state_05["outcome"] = collection_precheck_gate_fixture.run_g_commit_gate(
        collectability=state_05["collectability"]
    )


# --- Then -----------------------------------------------------------------


@then(
    "the spine closes the commit gate with a durable terminal instead of re-firing the crafter"
)
def then_spine_closes_gate_with_durable_terminal(state_05) -> None:
    after = _gate_snapshot(state_05)
    assert_state_delta(
        before={k: state_05["before"][k] for k in GATE_UNIVERSE},
        after={k: after[k] for k in GATE_UNIVERSE},
        universe=GATE_UNIVERSE,
        expected={
            "outcome.terminated": set_to(True),
            "outcome.blocked": set_to(False),
        },
    )


@then("the spine names the collection crash and does not re-fire the crafter")
def then_spine_names_crash_and_does_not_refire(state_05) -> None:
    assert state_05["outcome"].blocked is False, (
        "BLOCKER-1 (R-69-D): the collection precheck must be WIRED INTO the gate. A "
        "real collection crash on the live spine must TERMINATE the commit exit gate "
        "(a non-block return → the harness reaches a Stop), NOT re-fire the crafter. "
        "Today `_handle_g_commit_exit_gate` runs NO precheck before E2 (grep "
        "`collect-only|precheck` in the handler = 0) — slice-01 shipped the probe but "
        "the gate never calls it ('walking-skeleton value half-delivered'). So the "
        "crash flows into E2 → exit non-zero → the block branch → `{decision:block}` "
        "→ the harness RE-FIRES the agent forever (the exact #68 loop the "
        "walking-skeleton exists to kill, NOT killed on the production hot path). "
        "GREEN once the EXTEND runs `run_contract_gate --collect-only` (no-skip, D-7) "
        "BEFORE E2 and terminates via the slice-04 shared "
        "`_emit_terminating_indeterminate` on exit 2. "
        f"Got blocked={state_05['outcome'].blocked}, "
        f"terminated={state_05['outcome'].terminated}"
    )


@then("the spine blocks the commit gate without firing the collection terminal")
def then_spine_blocks_without_collection_terminal(state_05) -> None:
    assert state_05["outcome"].terminated is False, (
        "anti-vacuity discriminator (the divergence pair): the collection terminal "
        "must fire ONLY on a COLLECTION CRASH (exit 2), NOT on any gate failure. A "
        "cleanly-collecting commit that fails E1/E2 for an ORDINARY reason (no "
        "`Gate-Scope:` trailer → E2 exit 1) must take the ORDINARY block path — the "
        "precheck sees exit 0 and lets the gate proceed to E1/E2. A collection-blind "
        "precheck that terminated EVERY commit would wrongly collection-terminate "
        "this clean commit (a durable terminal record written here) — this pin guards "
        "the wiring against over-firing. Pairs with the crash pin to bracket the "
        "contract: a precheck that NEVER terminates fails the crash pin; one that "
        "ALWAYS terminates fails THIS pin. "
        f"Got terminated={state_05['outcome'].terminated}, "
        f"blocked={state_05['outcome'].blocked}"
    )
