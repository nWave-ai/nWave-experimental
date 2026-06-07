"""Step bodies for des-spine-control-plane-ssot slice-04 (gate-composition SSOT).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
`gate_composition_fixture.<method>(...)` call (or one `assert_state_delta` /
assertion), and contains zero control flow (`if`/`for`/`while`/`try`). All
business logic lives in `GateCompositionFixture` (composition_slice_04.py).

Mandate 8: the state-mutating Then on the discriminators goes through
`assert_state_delta(before, after, universe, expected)` from
`tests.common.state_delta`. Universe entries are port-exposed observables on
`BoundaryRun` (outcome, missing_records, block_event) — never Popen handles,
never env dicts, never the parsed JSON object.

Mandate 9 v2: layer 3 (subprocess against tmp_path, @real-io — the driven set
includes a real filesystem adapter the hook reads config + feature-delta +
transcript from) -> example-only. PBT machinery is intentionally NOT imported.

Mandate 11: each feature-end boundary verdict (per flavor composition) is one
explicit named example.

Mandate-13: ATs drive through the production `subagent.stop` hook entry
(subprocess) — NEVER a direct
`from des.application.flavor_dispatcher import dispatch_lifecycle_event` or
`from des.adapters.drivers.hooks.subagent_stop_handler import
_handle_feature_end_gate` invocation in test bodies.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .domain_types_slice_04 import (
    FLAVOR_COMPOSITION_BY_PHRASE,
    PRODUCTION_REQUIRED_RECORDS,
    BoundaryOutcome,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------

BOUNDARY_UNIVERSE = frozenset(
    {
        "boundary.outcome",
        "boundary.missing_records",
        "boundary.block_event",
    }
)


def _boundary_snapshot(state: dict) -> dict:
    """Build a universe snapshot of the boundary observables. Pure function.

    Returns None sentinels for unobserved keys so the before-snapshot is
    well-defined before the hook is fired.
    """
    run = state.get("boundary_run")
    return {
        "boundary.outcome": getattr(run, "outcome", None),
        "boundary.missing_records": getattr(run, "missing_records", None),
        "boundary.block_event": getattr(run, "block_event", None),
    }


# --- Given ----------------------------------------------------------------


@given(
    parsers.parse(
        "a feature whose only slice is shipped and that runs under {composition_phrase}"
    )
)
def given_feature_end_project(
    gate_composition_fixture, state, composition_phrase: str
) -> None:
    state["project"] = gate_composition_fixture.build_feature_end_project(
        flavor_composition=FLAVOR_COMPOSITION_BY_PHRASE[composition_phrase]
    )


# --- When -----------------------------------------------------------------


@when("the feature-end crafter returns to the subagent-stop boundary")
def when_crafter_returns(gate_composition_fixture, state) -> None:
    state["before"] = _boundary_snapshot(state)
    state["boundary_run"] = gate_composition_fixture.run_subagent_stop(state["project"])


# --- Then -----------------------------------------------------------------


@then("the boundary demands exactly the shipped feature-end records")
def then_boundary_demands_production_records(state) -> None:
    after = _boundary_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in BOUNDARY_UNIVERSE},
        after={k: after[k] for k in BOUNDARY_UNIVERSE},
        universe=BOUNDARY_UNIVERSE,
        expected={
            "boundary.outcome": set_to(BoundaryOutcome.BLOCKED_MISSING_RECORDS),
            "boundary.missing_records": set_to(PRODUCTION_REQUIRED_RECORDS),
            "boundary.block_event": set_to("FeatureEndCycleIncomplete"),
        },
    )


@then("the boundary no longer demands any feature-end record")
def then_boundary_demands_no_records(gate_composition_fixture, state) -> None:
    assert gate_composition_fixture.proceeded_past_records(state["boundary_run"]), (
        "gate-composition SSOT (DDD-1): a flavor declaring an EMPTY feature-end "
        "required-records profile at the subagent.stop boundary must make the "
        "boundary STOP demanding the hardcoded six — the required-records profile "
        "is YAML-sourced, not the `_REQUIRED_FEATURE_END_RECORDS` frozenset. Today "
        "the if-ladder ignores the flavor and blocks regardless. got "
        f"outcome={state['boundary_run'].outcome!r} "
        f"missing={sorted(state['boundary_run'].missing_records)!r} "
        f"stdout={state['boundary_run'].stdout[:400]!r}"
    )


@then("the boundary demands the extra feature-end record the composition declares")
def then_boundary_demands_sentinel(gate_composition_fixture, state) -> None:
    assert gate_composition_fixture.blocked_naming_sentinel(state["boundary_run"]), (
        "gate-composition SSOT (DDD-1, `gates_fired_at(E) == yaml_composition(E)`): "
        "a flavor ADDING one required-record at the subagent.stop boundary must "
        "make the boundary block naming THAT record — proving the profile is read "
        "from the flavor YAML composition, not the hardcoded frozenset. Today the "
        "frozenset is the SSOT and the YAML-declared record never appears in "
        f"`missing`. got outcome={state['boundary_run'].outcome!r} "
        f"missing={sorted(state['boundary_run'].missing_records)!r} "
        f"stdout={state['boundary_run'].stdout[:400]!r}"
    )
