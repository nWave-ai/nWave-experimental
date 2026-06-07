"""pytest-bdd binding + step vocabulary for slice-02-test-runner-port.

Mandate-12 (SSOT via Types + Services + DSL): step decorators are parameterized
templates over typed-enum parameters (from ``domain_types.py``). Mandate-12
criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), no control flow.
Business logic lives in the production adapter behind the ``run_tests`` CLI; the
composition transports envelopes; this module only names domain facts and
delegates.

S1 (step-text uniqueness): every literal step string here is distinct from
slice-01's vocabulary -- no ``@then`` shadowing across the feature dir. The
slice-02 composition is a separate root from slice-01's, so the fixture name
``runner_composition`` is also distinct.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import RunnerComposition
from .domain_types import REASON_BY_PHRASE, TARGET_HEALTH_BY_PHRASE


scenarios("../slice-02-test-runner-port.feature")


@pytest.fixture
def runner_composition() -> Iterator[RunnerComposition]:
    """The production test-runner composition root, fresh per scenario.

    Teardown removes the mkdtemp workspace the composition stages during the
    CLI subprocess call, so the suite leaves no ``/tmp`` residue.
    """
    comp = RunnerComposition()
    yield comp
    if comp._workspace is not None:
        shutil.rmtree(comp._workspace, ignore_errors=True)


# --- Given: stage the test target --------------------------------------------


@given(parsers.parse("a test target whose tests {target_health}"))
def given_target_passing(
    runner_composition: RunnerComposition, target_health: str
) -> None:
    runner_composition.given_target(TARGET_HEALTH_BY_PHRASE[target_health])


@given(parsers.parse("a test target with {target_health}"))
def given_target_with(
    runner_composition: RunnerComposition, target_health: str
) -> None:
    runner_composition.given_target(TARGET_HEALTH_BY_PHRASE[target_health])


@given(parsers.parse("a test target whose runner {target_health}"))
def given_target_runner_absent(
    runner_composition: RunnerComposition, target_health: str
) -> None:
    runner_composition.given_target(TARGET_HEALTH_BY_PHRASE[target_health])


# --- When: run the target through the test-runner port ------------------------


@when("the test-runner port runs the target")
def when_run_target(runner_composition: RunnerComposition) -> None:
    runner_composition.result = runner_composition.run_target()


# --- Then: assert on the emitted test_result.v1 (or the ABSTAIN signal) -------


@then("the emitted run result conforms to the test-result contract")
def then_emitted_conforms(runner_composition: RunnerComposition) -> None:
    assert runner_composition.emitted_is_valid_test_result() is True


@then("the emitted run result reports at least one passing test")
def then_reports_passing(runner_composition: RunnerComposition) -> None:
    assert (runner_composition.result.passed or 0) > 0


@then("the emitted run result reports no failing tests")
def then_reports_no_failing(runner_composition: RunnerComposition) -> None:
    assert runner_composition.result.failed == 0


@then("the emitted run result reports a zero exit code")
def then_reports_zero_exit(runner_composition: RunnerComposition) -> None:
    assert runner_composition.result.exit_code == 0


@then("the emitted run result reports at least one failing test")
def then_reports_failing(runner_composition: RunnerComposition) -> None:
    assert (runner_composition.result.failed or 0) > 0


@then("the emitted run result reports a nonzero exit code")
def then_reports_nonzero_exit(runner_composition: RunnerComposition) -> None:
    assert (runner_composition.result.exit_code or 0) != 0


@then("the emitted result is a fail-safe abstain")
def then_is_abstain(runner_composition: RunnerComposition) -> None:
    assert runner_composition.emitted_is_fail_safe_abstain() is True


@then(parsers.parse('the abstain reason is "{reason}"'))
def then_abstain_reason(runner_composition: RunnerComposition, reason: str) -> None:
    assert runner_composition.result.reason == REASON_BY_PHRASE[reason]


@then("no passing run result is fabricated")
def then_no_fabricated_green(runner_composition: RunnerComposition) -> None:
    assert runner_composition.no_passing_run_fabricated() is True
