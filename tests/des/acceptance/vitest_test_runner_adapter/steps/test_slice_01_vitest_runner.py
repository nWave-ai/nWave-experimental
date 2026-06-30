"""pytest-bdd binding for vitest-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUT (the JS/TS run-facet ``run_vitest_scope``) imported +
invoked in a child interpreter over a GENUINE controlled filesystem +
FAKE-``vitest`` executable. Step bodies delegate to the composition root
(``composition_slice_01_vitest_runner.py``); no business logic in step bodies
(Mandate-12 criterion 3). The verdict token is parsed into the typed
``RunnerVerdict`` enum, so the verdict-assertion template ranges over the typed
domain vocabulary (DSL emergence, not decorator proliferation).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never here.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``vitest_runner.py``. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect never
happens, so each Then fails with a semantic AssertionError, never a collection /
import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_vitest_runner import VitestRunnerComposition
from .domain_types_vitest_runner import RunnerVerdict, VitestExitScenario


scenarios("../slice-01-vitest-runner.feature")


@pytest.fixture
def vitest() -> VitestRunnerComposition:
    return VitestRunnerComposition()


# --- Given -----------------------------------------------------------------


@given("a JS/TS target whose vitest run exits zero with all tests passing")
def given_vitest_green(vitest: VitestRunnerComposition) -> None:
    vitest.given_target_with_fake_vitest(VitestExitScenario.GREEN)


@given("a JS/TS target whose vitest run exits non-zero after executing tests")
def given_vitest_red(vitest: VitestRunnerComposition) -> None:
    vitest.given_target_with_fake_vitest(VitestExitScenario.RED)


@given("a JS/TS target whose vitest is absent from PATH and every known location")
def given_vitest_absent(vitest: VitestRunnerComposition) -> None:
    vitest.given_target_with_vitest_absent_everywhere()


@given(
    "a JS/TS target whose vitest records the argv and working directory it is "
    "shelled with"
)
def given_vitest_records_argv(vitest: VitestRunnerComposition) -> None:
    # AC-4 drives the same GREEN fake-vitest fixture: the fake records its argv +
    # cwd to a record file the Then steps read back. GREEN keeps the probe rc clean
    # so the assertion isolates the declared-command-shelled contract.
    vitest.given_target_with_fake_vitest(VitestExitScenario.GREEN)


# --- When ------------------------------------------------------------------


@when("the vitest run-facet runs the declared command")
def when_run_facet_runs(vitest: VitestRunnerComposition) -> None:
    vitest.when_the_run_facet_runs_the_command()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_run_verdict_is(vitest: VitestRunnerComposition, verdict: str) -> None:
    vitest.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_indeterminate_names_remediation(vitest: VitestRunnerComposition) -> None:
    vitest.then_the_indeterminate_names_the_remediation()


@then("the vitest binary was invoked with the declared subcommand as-is")
def then_subcommand_shelled(vitest: VitestRunnerComposition) -> None:
    vitest.then_the_declared_subcommand_was_shelled()


@then("the vitest binary was invoked with the working directory set to the target root")
def then_cwd_target_root(vitest: VitestRunnerComposition) -> None:
    vitest.then_the_cwd_was_the_target_root()
