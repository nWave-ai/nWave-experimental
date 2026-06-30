"""pytest-bdd binding for f-rust-test-runner-adapter slice-02 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-02 SUT (cargo run-facet + RunnerRegistry + nwave-lang-rust
plugin) imported + invoked in a child interpreter over a GENUINE controlled
filesystem + FAKE-cargo executable. Step bodies delegate to the composition root
(``composition_slice_02_cargo_runner.py``); no business logic in step bodies
(Mandate-12 criterion 3). The verdict token is parsed into the typed
``RunnerVerdict`` enum, so the verdict-assertion template ranges over the typed
domain vocabulary (DSL emergence, not decorator proliferation).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never here.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``cargo_runner.py`` + ``runner_registry.py`` + ``nwave_lang_rust.py``. At HEAD the
modules are absent, so the child probe import raises ModuleNotFoundError THERE
(rc != 0, no marker); the observable effect never happens, so each Then fails with
a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02_cargo_runner import CargoRunnerComposition
from .domain_types_cargo_runner import CargoExitScenario, RunnerVerdict


scenarios("../slice-02-cargo-runner.feature")


@pytest.fixture
def cargo() -> CargoRunnerComposition:
    return CargoRunnerComposition()


# --- Given -----------------------------------------------------------------


@given("a Rust target whose cargo exits zero with all tests passing")
def given_cargo_green(cargo: CargoRunnerComposition) -> None:
    cargo.given_target_with_fake_cargo(CargoExitScenario.GREEN)


@given("a Rust target whose cargo exits non-zero after executing tests")
def given_cargo_red(cargo: CargoRunnerComposition) -> None:
    cargo.given_target_with_fake_cargo(CargoExitScenario.RED)


@given("a Rust target whose cargo exits four having run no tests")
def given_cargo_no_match(cargo: CargoRunnerComposition) -> None:
    cargo.given_target_with_fake_cargo(CargoExitScenario.NO_MATCH)


@given("a Rust target whose cargo is absent from PATH and every known location")
def given_cargo_absent(cargo: CargoRunnerComposition) -> None:
    cargo.given_target_with_cargo_absent_everywhere()


@given("the nwave-lang-rust plugin and an empty runner registry")
def given_plugin_and_empty_registry(cargo: CargoRunnerComposition) -> None:
    # No fixture state needed: the unification check builds a fresh plugin +
    # registry in the child probe (when step). This Given names the precondition
    # for Pillar-1 readability.
    pass


# --- When ------------------------------------------------------------------


@when("the cargo run-facet runs the declared command")
def when_run_facet_runs(cargo: CargoRunnerComposition) -> None:
    cargo.when_the_run_facet_runs_the_command()


@when("the plugin registers its adapters into the registry")
def when_plugin_registers(cargo: CargoRunnerComposition) -> None:
    cargo.when_the_plugin_registers_through_the_registry()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_run_verdict_is(cargo: CargoRunnerComposition, verdict: str) -> None:
    cargo.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_indeterminate_names_remediation(cargo: CargoRunnerComposition) -> None:
    cargo.then_the_indeterminate_names_the_remediation()


@then("the registry resolves the cargo-test token to the cargo run-facet")
def then_token_resolves_to_facet(cargo: CargoRunnerComposition) -> None:
    cargo.then_the_token_resolves_to_the_cargo_facet()
