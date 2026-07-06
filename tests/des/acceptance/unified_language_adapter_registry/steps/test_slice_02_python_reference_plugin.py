"""Step definitions: the Python reference plugin wires real adapters (slice-02).

unified-language-adapter-registry slice-02 (DISCUSS Slice Plan / DESIGN
slice-05a, component IDs C8-C11). Layer 3 subprocess (child-interpreter),
example-only, no PBT machinery (Mandate 9/11): each scenario pins one closed
observable; the sad path (module absent at HEAD) is the active-RED state
itself.

Step bodies delegate to `Slice02Composition`; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed accessor plus a composition
call.

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD
`scripts/install/plugins/nwave_lang_python.py` and the 3 new adapters
(C8-C10) do not exist, so every child program's import fails and each Then
fires a named semantic AssertionError. Collection imports ONLY the
composition module (which imports ONLY stdlib + the collection-safe domain
types) -- the absent production names appear nowhere at module top.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import Slice02Composition


scenarios("../slice-02-python-reference-plugin.feature")


@pytest.fixture
def composition() -> Slice02Composition:
    """Production-wired composition root driving the real slice-02 SUT."""
    return Slice02Composition()


# --- Given ---------------------------------------------------------------


@given("the maintainer has a Python codebase with a passing test suite")
def given_passing_codebase(composition: Slice02Composition, tmp_path: Path) -> None:
    composition.given_passing_python_codebase(tmp_path)


@given(
    "the Python language plugin has wired its contract-gate adapter into the registry"
)
def given_plugin_will_wire(composition: Slice02Composition) -> None:
    # No-op placeholder: the actual wiring happens as part of the When step
    # (one child process both registers AND drives the gate, proving the
    # registration is what makes the gate's routing possible -- Mandate 15
    # dormant-seam reconciliation: the AT drives the seam through the REAL
    # entry point, never a pre-armed fixture standing in for it).
    pass


@given("the maintainer has a Python codebase with a failing test suite")
def given_failing_codebase(composition: Slice02Composition, tmp_path: Path) -> None:
    composition.given_failing_python_codebase(tmp_path)


@given("a fresh unified language-adapter registry")
def given_fresh_registry(composition: Slice02Composition) -> None:
    # No-op placeholder: `when_plugin_wires_all_slots` constructs the fresh
    # `LanguageAdapterRegistry()` itself, inside the child interpreter (the
    # registry is a net-new production type -- constructing it here would
    # require importing it in THIS process, violating P1).
    pass


# --- When ------------------------------------------------------------------


@when("the maintainer runs the contract gate against the codebase")
def when_run_gate_ws(composition: Slice02Composition) -> None:
    composition.when_plugin_wires_contract_gate_adapter()


@when("the contract gate runs against the codebase with the Python adapter registered")
def when_parity_runs(composition: Slice02Composition) -> None:
    composition.when_gate_runs_registered_then_unregistered()


@when(
    "the contract gate runs again against the same codebase with no adapter registered"
)
def when_parity_second_leg_noop(composition: Slice02Composition) -> None:
    # No-op: `when_gate_runs_registered_then_unregistered` drives BOTH legs
    # (registered, then unregistered) so the two child processes share the
    # identical failing-codebase fixture without any state leaking between
    # them (each child starts with its OWN empty GLOBAL_REGISTRY).
    pass


@when("the Python plugin wires its adapters into the registry")
def when_wires_all_slots(composition: Slice02Composition) -> None:
    composition.when_plugin_wires_all_slots()


# --- Then --------------------------------------------------------------------


@then("the contract gate reports it ran through the registered Python adapter")
def then_routed_via_registered_adapter(composition: Slice02Composition) -> None:
    obs = composition.registered_run()
    assert obs.child_import_ok, (
        "driving the contract gate with the Python plugin registered must "
        "succeed end-to-end (the plugin imports, registers, and the gate "
        "runs) -- but at HEAD scripts/install/plugins/nwave_lang_python.py "
        f"does not exist, so the child process cannot even import it. "
        f"{composition.diag_registered()}"
    )
    assert obs.routed_via_registered_adapter, (
        "the contract gate's emitted ContractGateResult event must carry "
        "routed_via_registered_adapter=true once a ContractGatePort facet is "
        "registered under the resolved tool-name -- but at HEAD the "
        "registered-arm of _maybe_route_through_registered_contract_gate "
        f"emits no such marker (or the plugin is absent). {composition.diag_registered()}"
    )


@then("the contract gate reports the codebase as passing")
def then_gate_reports_passing(composition: Slice02Composition) -> None:
    obs = composition.registered_run()
    assert obs.passed is True, (
        "the contract gate must report the codebase's genuinely passing test "
        "suite as passed=true through the registered adapter -- but at HEAD "
        f"no such verdict is observable. {composition.diag_registered()}"
    )


@then("the maintainer's codebase is left unchanged by the contract-gate run")
def then_codebase_unchanged(composition: Slice02Composition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before=composition.universe_before(),
        after=composition.capture_universe(composition.passing_repo()),
        universe={"repo.exists", "repo.python_file_count"},
        expected={
            "repo.exists": unchanged(),
            "repo.python_file_count": unchanged(),
        },
    )


@then("both runs report the identical pytest verdict")
def then_parity_identical_verdict(composition: Slice02Composition) -> None:
    registered = composition.registered_run()
    unregistered = composition.unregistered_run()
    assert registered.child_import_ok, (
        "the adapter-registered parity leg must succeed end-to-end -- but at "
        "HEAD scripts/install/plugins/nwave_lang_python.py does not exist. "
        f"{composition.diag_registered()}"
    )
    assert unregistered.child_import_ok, (
        "the no-adapter (fallback) parity leg must succeed end-to-end. "
        f"{composition.diag_unregistered()}"
    )
    assert (
        registered.pytest_exit_code == unregistered.pytest_exit_code
        and registered.pytest_exit_code is not None
    ), (
        "the registered-adapter path must wrap the SAME underlying pytest "
        "invocation as the fallback path (DDD-U3: wraps existing logic "
        "verbatim, never a new algorithm) -- both runs must report the "
        "IDENTICAL pytest_exit_code on the identical failing fixture; got "
        f"registered={registered.pytest_exit_code!r} vs "
        f"unregistered={unregistered.pytest_exit_code!r}. "
        f"registered={composition.diag_registered()}; "
        f"unregistered={composition.diag_unregistered()}"
    )


@then("only the adapter-registered run reports routing through the registered adapter")
def then_parity_only_registered_routes(composition: Slice02Composition) -> None:
    registered = composition.registered_run()
    unregistered = composition.unregistered_run()
    assert registered.routed_via_registered_adapter, (
        "the adapter-registered leg must report "
        "routed_via_registered_adapter=true -- but at HEAD the plugin is "
        f"absent so no such marker is observable. {composition.diag_registered()}"
    )
    assert not unregistered.routed_via_registered_adapter, (
        "the no-adapter (fallback) leg must NEVER report "
        "routed_via_registered_adapter=true -- a target with no plugin "
        "installed must keep running today's hardcoded path unchanged. "
        f"{composition.diag_unregistered()}"
    )


@then("the registry resolves a contract-gate adapter for the plugin's runner")
def then_contract_gate_slot_resolved(composition: Slice02Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.child_import_ok, (
        "wiring a fresh registry via the Python plugin's register_adapters "
        "must succeed end-to-end -- but at HEAD "
        "scripts/install/plugins/nwave_lang_python.py does not exist. "
        f"{composition.diag_slots()}"
    )
    assert slots.contract_gate_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_contract_gate('pytest') must resolve to a real "
        f"ContractGatePort facet -- but it did not. {composition.diag_slots()}"
    )


@then("the registry resolves an environmental-e2e adapter for the plugin's runner")
def then_e2e_slot_resolved(composition: Slice02Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.environmental_e2e_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_environmental_e2e('pytest') must resolve to a real "
        f"EnvironmentalE2EPort facet -- but it did not. {composition.diag_slots()}"
    )


@then("the registry resolves a robustness-density adapter for the plugin's runner")
def then_robustness_slot_resolved(composition: Slice02Composition) -> None:
    slots = composition.slot_resolution()
    assert slots.robustness_density_resolved, (
        "after ONE register_adapters(registry) call, "
        "registry.lookup_robustness_density('pytest') must resolve to a real "
        f"RobustnessDensityPort facet -- but it did not. {composition.diag_slots()}"
    )
