"""pytest-bdd binding for java-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUT (the Java run-facet ``run_java_scope`` + the
AT-discovery facet ``discover_java_ats``) imported + invoked in a child
interpreter over a GENUINE controlled filesystem + FAKE-``mvn`` executable /
real regression-file fixtures. Step bodies delegate to the composition root
(``composition_slice_01_java_runner.py``); no business logic in step bodies
(Mandate-12 criterion 3). The verdict token is parsed into the typed
``RunnerVerdict`` enum, so the verdict-assertion template ranges over the
typed domain vocabulary (DSL emergence, not decorator proliferation).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in
the child interpreter (inside the composition root's ``python -c`` probe),
never here.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``java_runner.py``. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect
never happens, so each Then fails with a semantic AssertionError, never a
collection / import error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_java_runner import JavaRunnerComposition
from .domain_types_java_runner import MavenExitScenario, RunnerVerdict


scenarios("../slice-01-java-runner.feature")


@pytest.fixture
def java() -> JavaRunnerComposition:
    return JavaRunnerComposition()


# --- Given -----------------------------------------------------------------


@given("a Java target whose mvn test exits zero with all tests passing")
def given_mvn_green(java: JavaRunnerComposition) -> None:
    java.given_target_with_fake_mvn(MavenExitScenario.GREEN)


@given("a Java target whose mvn test exits non-zero after executing tests")
def given_mvn_red(java: JavaRunnerComposition) -> None:
    java.given_target_with_fake_mvn(MavenExitScenario.RED)


@given("a Java target whose mvn is absent from PATH and every known location")
def given_mvn_absent(java: JavaRunnerComposition) -> None:
    java.given_target_with_mvn_absent_everywhere()


@given(
    "a Java target whose mvn records the argv and working directory it is shelled with"
)
def given_mvn_records_argv(java: JavaRunnerComposition) -> None:
    # AC-4 drives the same GREEN fake-mvn fixture: the fake records its argv +
    # cwd to a record file the Then steps read back. GREEN keeps the probe rc
    # clean so the assertion isolates the declared-command-shelled contract.
    java.given_target_with_fake_mvn(MavenExitScenario.GREEN)


@given(
    "a Java regression file with a plain @Test method and a @Test method "
    "annotated with @DisplayName"
)
def given_regression_file_two_tests(java: JavaRunnerComposition) -> None:
    java.given_regression_file_with_two_test_methods()


@given("a Java regression file with zero @Test methods")
def given_regression_file_zero_tests(java: JavaRunnerComposition) -> None:
    java.given_regression_file_with_zero_test_methods()


# --- When ------------------------------------------------------------------


@when("the java run-facet runs the declared command")
def when_run_facet_runs(java: JavaRunnerComposition) -> None:
    java.when_the_run_facet_runs_the_command()


@when("the java AT-discovery facet discovers the file's acceptance tests")
def when_discovery_facet_runs(java: JavaRunnerComposition) -> None:
    java.when_the_at_discovery_facet_discovers_the_ats()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_run_verdict_is(java: JavaRunnerComposition, verdict: str) -> None:
    java.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_indeterminate_names_remediation(java: JavaRunnerComposition) -> None:
    java.then_the_indeterminate_names_the_remediation()


@then("the mvn binary was invoked with the declared subcommand as-is")
def then_subcommand_shelled(java: JavaRunnerComposition) -> None:
    java.then_the_declared_subcommand_was_shelled()


@then("the mvn binary was invoked with the working directory set to the target root")
def then_cwd_target_root(java: JavaRunnerComposition) -> None:
    java.then_the_cwd_was_the_target_root()


@then(parsers.parse('the discovered AT identities are "{first_id}" and "{second_id}"'))
def then_discovered_at_ids(
    java: JavaRunnerComposition, first_id: str, second_id: str
) -> None:
    java.then_the_discovered_at_ids_are(frozenset({first_id, second_id}))


@then("the content hash seals the regression file's real bytes")
def then_content_hash_seals_real_bytes(java: JavaRunnerComposition) -> None:
    java.then_the_content_hash_seals_the_real_bytes()


@then("the discovery is refused naming the zero-test condition")
def then_discovery_refused_zero(java: JavaRunnerComposition) -> None:
    java.then_the_discovery_is_refused_naming_zero()
