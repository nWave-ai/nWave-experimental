"""Step bodies for oss-spine-watchdog slice-01 (collection-health precheck).

Mandate-12 criterion 3: every step body is ≤2 statements, ends in a single
`collection_precheck_fixture.<method>(...)` call (or one assertion), and contains
zero control flow (`if`/`for`/`while`/`try`). All business logic lives in
`CollectionPrecheckFixture` (conftest.py).

Mandate 8: the state-mutating outcome assertion goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`PrecheckOutcome` (`outcome.exit_code`, `outcome.crash_named`,
`outcome.named_module`) — never Popen handles, never env dicts, never raw worker
bytes (Mandate 8 — port-exposed observables only).

Mandate 9 v2: layer 3 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter + a real fresh-interpreter pytest subprocess)
→ example-only. PBT machinery is intentionally NOT imported (Mandate 11 — sad
paths enumerated explicitly).

Mandate-13: ATs drive through the production COLLECTION-PRECHECK driving port
(subprocess `python -m des.cli run-contract-gate --collect-only --print-digest`)
— NEVER a direct `from des.cli.run_contract_gate import _collect_scope` invocation
in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types import (
    COLLECTABILITY_BY_PHRASE,
    OPT_OUT_BY_PHRASE,
    FreshnessOptOut,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

PRECHECK_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.crash_named",
        "outcome.named_module",
    }
)


def _precheck_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the precheck observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the precheck runs.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.crash_named": getattr(outcome, "crash_named", None),
        "outcome.named_module": getattr(outcome, "named_module", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("a project whose contract suite {collectability_phrase}"))
def given_contract_suite(
    collection_precheck_fixture, state, collectability_phrase: str
) -> None:
    state["suite"] = collection_precheck_fixture.build_contract_suite(
        collectability=COLLECTABILITY_BY_PHRASE[collectability_phrase]
    )


@given(parsers.parse("the operator runs with {opt_out_phrase}"))
def given_operator_opt_out(state, opt_out_phrase: str) -> None:
    state["opt_out"] = OPT_OUT_BY_PHRASE[opt_out_phrase]


# --- When -----------------------------------------------------------------


@when("the spine runs the collection-health precheck before the commit gate")
def when_precheck_runs(collection_precheck_fixture, state) -> None:
    state["before"] = _precheck_snapshot(state)
    state["outcome"] = collection_precheck_fixture.run_precheck(
        state["suite"],
        opt_out=state.get("opt_out", FreshnessOptOut.UNSET),
    )


# --- Then -----------------------------------------------------------------


@then("the precheck fails loud and names the broken module")
def then_precheck_fails_loud_named(state) -> None:
    after = _precheck_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in PRECHECK_UNIVERSE},
        after={k: after[k] for k in PRECHECK_UNIVERSE},
        universe=PRECHECK_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(2),
            "outcome.crash_named": set_to(True),
            "outcome.named_module": set_to(state["suite"].crashing_module_rel),
        },
    )


@then("the commit gate proceeds with no loud failure")
def then_gate_proceeds_no_loud_failure(state) -> None:
    after = _precheck_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in PRECHECK_UNIVERSE},
        after={k: after[k] for k in PRECHECK_UNIVERSE},
        universe=PRECHECK_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(0),
            "outcome.crash_named": set_to(False),
            "outcome.named_module": set_to(None),
        },
    )


@then("the spine proceeds to the commit gate without re-firing the agent")
def then_clean_precheck_yields_digest(state) -> None:
    assert state["outcome"].digest is not None, (
        "no-false-positive discriminator: a cleanly-collecting contract suite must "
        "PROCEED the precheck (exit 0 with a printed gate-scope digest), so the "
        "gate runs normally and the agent is NOT re-fired; got "
        f"exit={state['outcome'].exit_code}, digest={state['outcome'].digest!r}, "
        f"payload={state['outcome'].stdout_payload!r}"
    )
