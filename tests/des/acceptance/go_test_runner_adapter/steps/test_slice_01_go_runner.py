"""pytest-bdd binding for go-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUT (the Go run-facet ``run_go_scope``) imported + invoked in a
child interpreter over a GENUINE controlled filesystem + FAKE-``go`` executable.
Step bodies delegate to the composition root
(``composition_slice_01_go_runner.py``); no business logic in step bodies
(Mandate-12 criterion 3). The verdict token is parsed into the typed
``RunnerVerdict`` enum, so the verdict-assertion template ranges over the typed
domain vocabulary (DSL emergence, not decorator proliferation).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never here.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``go_runner.py``. At HEAD the module is absent, so the child probe import raises
ModuleNotFoundError THERE (rc != 0, no marker); the observable effect never
happens, so each Then fails with a semantic AssertionError, never a collection /
import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_go_runner import GoRunnerComposition
from .domain_types_go_runner import GoExitScenario, RunnerVerdict


scenarios("../slice-01-go-runner.feature")


@pytest.fixture
def go() -> GoRunnerComposition:
    return GoRunnerComposition()


# --- Given -----------------------------------------------------------------


@given("a Go target whose go test exits zero with all tests passing")
def given_go_green(go: GoRunnerComposition) -> None:
    go.given_target_with_fake_go(GoExitScenario.GREEN)


@given("a Go target whose go test exits non-zero after executing tests")
def given_go_red(go: GoRunnerComposition) -> None:
    go.given_target_with_fake_go(GoExitScenario.RED)


@given("a Go target whose go is absent from PATH and every known location")
def given_go_absent(go: GoRunnerComposition) -> None:
    go.given_target_with_go_absent_everywhere()


@given("a Go target whose go records the argv and working directory it is shelled with")
def given_go_records_argv(go: GoRunnerComposition) -> None:
    # AC-4 drives the same GREEN fake-go fixture: the fake records its argv + cwd
    # to a record file the Then steps read back. GREEN keeps the probe rc clean so
    # the assertion isolates the declared-command-shelled contract.
    go.given_target_with_fake_go(GoExitScenario.GREEN)


# --- When ------------------------------------------------------------------


@when("the go run-facet runs the declared command")
def when_run_facet_runs(go: GoRunnerComposition) -> None:
    go.when_the_run_facet_runs_the_command()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_run_verdict_is(go: GoRunnerComposition, verdict: str) -> None:
    go.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_indeterminate_names_remediation(go: GoRunnerComposition) -> None:
    go.then_the_indeterminate_names_the_remediation()


@then("the go binary was invoked with the declared subcommand as-is")
def then_subcommand_shelled(go: GoRunnerComposition) -> None:
    go.then_the_declared_subcommand_was_shelled()


@then("the go binary was invoked with the working directory set to the target root")
def then_cwd_target_root(go: GoRunnerComposition) -> None:
    go.then_the_cwd_was_the_target_root()
