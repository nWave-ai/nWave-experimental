"""Step definitions: the TypeScript plugin mirrors slice-02 for the TS toolchain (slice-03).

unified-language-adapter-registry slice-03 (DISCUSS Slice Plan / DESIGN
slice-07, component IDs C12-C13). Layer 3 subprocess (child-interpreter),
example-only, no PBT machinery (Mandate 9/11): each scenario pins one closed
observable; the sad path (module absent at HEAD) is the active-RED state
itself.

Step bodies delegate to `Slice03Composition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed accessor plus a composition
call.

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD
`scripts/install/plugins/nwave_lang_typescript.py` and the 3 new TS adapters
(C13) do not exist, so every child program's import fails and each Then fires
a named semantic AssertionError. Collection imports ONLY the composition
module (which imports ONLY stdlib + the collection-safe domain types shared
with slice-02) -- the absent production names appear nowhere at module top.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03_typescript_plugin import Slice03Composition


scenarios("../slice-03-typescript-plugin.feature")


@pytest.fixture
def composition() -> Slice03Composition:
    """Production-wired composition root driving the real slice-03 SUT."""
    return Slice03Composition()


# --- Given -------------------------------------------------------------------


@given("the maintainer has a TypeScript codebase with a passing vitest suite")
def given_passing_codebase(composition: Slice03Composition, tmp_path: Path) -> None:
    composition.given_passing_typescript_codebase(tmp_path)


@given(
    "the TypeScript language plugin has wired its contract-gate adapter into "
    "the registry"
)
def given_plugin_will_wire(composition: Slice03Composition) -> None:
    # No-op placeholder: the actual wiring happens as part of the When step
    # (one child process both registers AND drives the gate, proving the
    # registration is what makes the gate's routing possible -- Mandate 15
    # dormant-seam reconciliation: the AT drives the seam through the REAL
    # entry point, never a pre-armed fixture standing in for it). Mirrors
    # slice-02's identical placeholder.
    pass


@given("a fresh unified language-adapter registry")
def given_fresh_registry(composition: Slice03Composition) -> None:
    # No-op placeholder: `when_plugin_wires_all_slots` constructs the fresh
    # `LanguageAdapterRegistry()` itself, inside the child interpreter (the
    # registry is a net-new production type -- constructing it here would
    # require importing it in THIS process, violating P1). Mirrors slice-02.
    pass


# --- When ----------------------------------------------------------------------


@when("the maintainer runs the contract gate against the codebase")
def when_run_gate_ws(composition: Slice03Composition) -> None:
    composition.when_plugin_wires_contract_gate_adapter()


@when("the TypeScript plugin wires its adapters into the registry")
def when_wires_all_slots(composition: Slice03Composition) -> None:
    composition.when_plugin_wires_all_slots()


# --- Then ----------------------------------------------------------------------


@then("the contract gate reports it ran through the registered TypeScript adapter")
def then_routed_via_registered_adapter(composition: Slice03Composition) -> None:
    obs = composition.registered_run()
    assert obs.child_import_ok, (
        "driving the contract gate with the TypeScript plugin registered "
        "must succeed end-to-end (the plugin imports, registers, and the "
        "gate runs) -- but at HEAD "
        "scripts/install/plugins/nwave_lang_typescript.py does not exist, "
        f"so the child process cannot even import it. {composition.diag_registered()}"
    )
    assert obs.routed_via_registered_adapter, (
        "the contract gate's emitted ContractGateResult event must carry "
        "routed_via_registered_adapter=true once a ContractGatePort facet is "
        "registered under the resolved tool-name 'vitest' -- but at HEAD the "
        "registered-arm of _maybe_route_through_registered_contract_gate "
        f"emits no such marker (or the plugin is absent). {composition.diag_registered()}"
    )


@then("the contract gate reports the codebase as passing")
def then_gate_reports_passing(composition: Slice03Composition) -> None:
    obs = composition.registered_run()
    assert obs.passed is True, (
        "the contract gate must report the TypeScript codebase's genuinely "
        "passing vitest suite as passed=true through the registered TS "
        f"adapter -- but at HEAD no such verdict is observable. "
        f"{composition.diag_registered()}"
    )


@then("the maintainer's codebase is left unchanged by the contract-gate run")
def then_codebase_unchanged(composition: Slice03Composition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before=composition.universe_before(),
        after=composition.capture_universe(composition.passing_repo()),
        universe={"repo.exists", "repo.typescript_file_count"},
        expected={
            "repo.exists": unchanged(),
            "repo.typescript_file_count": unchanged(),
        },
    )


@then("the registry resolves a contract-gate adapter for the plugin's runner")
def then_contract_gate_slot_resolved(composition: Slice03Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.child_import_ok, (
        "wiring a fresh registry via the TypeScript plugin's "
        "register_adapters must succeed end-to-end -- but at HEAD "
        "scripts/install/plugins/nwave_lang_typescript.py does not exist. "
        f"{composition.diag_slots()}"
    )
    assert slots.contract_gate_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_contract_gate('vitest') must resolve to a real "
        f"ContractGatePort facet -- but it did not. {composition.diag_slots()}"
    )


@then("the registry resolves an environmental-e2e adapter for the plugin's runner")
def then_e2e_slot_resolved(composition: Slice03Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.environmental_e2e_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_environmental_e2e('vitest') must resolve to a real "
        f"EnvironmentalE2EPort facet -- but it did not. {composition.diag_slots()}"
    )


@then("the registry resolves a robustness-density adapter for the plugin's runner")
def then_robustness_slot_resolved(composition: Slice03Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.robustness_density_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_robustness_density('vitest') must resolve to a real "
        f"RobustnessDensityPort facet -- but it did not. {composition.diag_slots()}"
    )
