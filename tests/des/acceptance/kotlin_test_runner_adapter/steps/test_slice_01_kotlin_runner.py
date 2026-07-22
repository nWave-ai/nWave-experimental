"""pytest-bdd binding for kotlin-test-runner-adapter slice-01 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
production slice-01 SUTs (the Kotlin run-facet ``run_kotlin_scope``, the
AT-discovery facet ``discover_kotlin_ats``, and the routing registry
``resolve()``) imported + invoked in a child interpreter over a GENUINE
controlled filesystem + FAKE-``gradlew`` executable. Step bodies delegate to the
composition root (``composition_slice_01_kotlin_runner.py``); no business logic
in step bodies (Mandate-12 criterion 3).

ZERO ``des.adapters.*`` import in THIS process: the SUT is only imported in the
child interpreter (inside the composition root's ``python -c`` probe), never
here.

Active-RED scaffold (atdd_pure -- NOT @skip): AC-1..5 RED until DELIVER ships
``kotlin_runner.py``. At HEAD the module is absent, so the child probe import
raises ModuleNotFoundError THERE (rc != 0, no marker); the observable effect
never happens, so each Then fails with a semantic AssertionError, never a
collection / import error. AC-6 (the resolve() routing row) is LIVE-GREEN at
HEAD -- it is authored directly by this feature, never gated behind
kotlin_runner.py.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_01_kotlin_runner import (
    _TWO_AT_KOTLIN_EXPECTED_IDS,
    KotlinRunnerComposition,
)
from .domain_types_kotlin_runner import GradleExitScenario, RunnerVerdict


scenarios("../slice-01-kotlin-runner.feature")


@pytest.fixture
def kotlin() -> KotlinRunnerComposition:
    return KotlinRunnerComposition()


# --- Given -------------------------------------------------------------------


@given("a Kotlin target whose gradlew test exits zero with all tests passing")
def given_kotlin_green(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_target_with_fake_gradlew(GradleExitScenario.GREEN)


@given("a Kotlin target whose gradlew test exits non-zero after executing tests")
def given_kotlin_red(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_target_with_fake_gradlew(GradleExitScenario.RED)


@given("a Kotlin target whose gradlew is absent from PATH and every known location")
def given_kotlin_gradlew_absent(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_target_with_gradlew_absent_everywhere()


@given("a Kotlin regression file declaring two @Test functions")
def given_kotlin_regression_two_tests(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_kotlin_regression_file_with_two_tests()


@given("a Kotlin regression file declaring zero @Test functions")
def given_kotlin_regression_zero_tests(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_kotlin_regression_file_with_zero_tests()


@given("a target carrying only a build.gradle.kts manifest")
def given_gradle_kts_only_target(kotlin: KotlinRunnerComposition) -> None:
    kotlin.given_target_with_only_build_gradle_kts()


# --- When ----------------------------------------------------------------


@when("the Kotlin run-facet runs the declared command")
def when_kotlin_run_facet_runs(kotlin: KotlinRunnerComposition) -> None:
    kotlin.when_the_run_facet_runs_the_command()


@when("the Kotlin AT-discovery facet discovers the file's acceptance tests")
def when_kotlin_at_discovery_runs(kotlin: KotlinRunnerComposition) -> None:
    kotlin.when_the_at_discovery_facet_discovers_ats()


@when("the target's test runner is resolved")
def when_target_runner_resolved(kotlin: KotlinRunnerComposition) -> None:
    kotlin.when_the_target_runner_is_resolved()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the run verdict is {verdict}"))
def then_kotlin_run_verdict_is(kotlin: KotlinRunnerComposition, verdict: str) -> None:
    kotlin.then_the_verdict_is(RunnerVerdict(verdict))


@then("the indeterminate result names the remediation")
def then_kotlin_indeterminate_names_remediation(
    kotlin: KotlinRunnerComposition,
) -> None:
    kotlin.then_the_indeterminate_names_the_remediation()


@then("the discovered AT identities match the declared @Test functions")
def then_kotlin_discovered_ids_match(kotlin: KotlinRunnerComposition) -> None:
    kotlin.then_the_discovered_at_ids_match(_TWO_AT_KOTLIN_EXPECTED_IDS)


@then("the discovery result carries a content seal over the regression file's bytes")
def then_kotlin_discovery_content_seal(kotlin: KotlinRunnerComposition) -> None:
    kotlin.then_the_discovery_carries_a_content_seal()


@then("the discovery degrades to a loud indeterminate naming the malformed file")
def then_kotlin_discovery_degrades_loud(kotlin: KotlinRunnerComposition) -> None:
    kotlin.then_the_discovery_degrades_loud_naming_the_malformed_file()


@then(parsers.parse("the resolved runner is {runner}"))
def then_kotlin_resolved_runner_is(
    kotlin: KotlinRunnerComposition, runner: str
) -> None:
    kotlin.then_the_resolved_runner_is(runner)
