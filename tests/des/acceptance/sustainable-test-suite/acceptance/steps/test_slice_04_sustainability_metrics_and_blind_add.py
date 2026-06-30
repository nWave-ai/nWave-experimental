"""slice-04 step definitions — the BALANCED DENOMINATOR (A+C metrics + blind-add).

Driving port: `des validate-feature-delta --require-sustainability --with-metrics
--format=json` subprocess (Mandate-13, Layer 3 subprocess). The subprocess is the SUT; no
production module is imported at the step boundary. Each step body delegates to the
`SustainabilityMetricsDriver` composition (Mandate-12: ≤2 statements, no inline logic, no
control flow).

Active-RED: at HEAD `des validate-feature-delta` has no `--with-metrics` mode and emits no
`metrics`/`blind_add` payload, so every scenario's metric/verdict accessor raises a clean
AssertionError (MISSING_FUNCTIONALITY) — not an ImportError. DELIVER makes these GREEN by
adding the A+C metrics calculator + the git-diff cross-check adapter + the `--with-metrics`
mode — it does NOT unskip anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice_04_composition import SustainabilityMetricsDriver
from .slice_04_domain_types import BlindAddVerdict, Verdict


scenarios("../slice-04-sustainability-metrics-and-blind-add.feature")


@pytest.fixture
def metrics_driver() -> SustainabilityMetricsDriver:
    return SustainabilityMetricsDriver()


# -- Given ------------------------------------------------------------------


@given(
    "a maintainer declares consolidation work for a feature with a real net "
    "test-LOC reduction"
)
def given_consolidation_work(
    metrics_driver: SustainabilityMetricsDriver, tmp_path: Path
) -> None:
    metrics_driver.given_consolidation_work_declared(tmp_path)


@given(
    "a maintainer claims consolidation but the git diff shows a net test-LOC increase"
)
def given_blind_add(
    metrics_driver: SustainabilityMetricsDriver, tmp_path: Path
) -> None:
    metrics_driver.given_consolidate_claim_but_net_add(tmp_path)


@given(
    "a maintainer declares consolidation work where the git-diff cross-check cannot run"
)
def given_git_absent(
    metrics_driver: SustainabilityMetricsDriver, tmp_path: Path
) -> None:
    metrics_driver.given_consolidation_declared_outside_git(tmp_path)


@given("a maintainer declares a slice whose net test-LOC trend does not regress")
def given_trend_non_regressing(
    metrics_driver: SustainabilityMetricsDriver, tmp_path: Path
) -> None:
    metrics_driver.given_trend_non_regressing_consolidation(tmp_path)


@given(
    "a maintainer requests metrics on a sustainability section that supplies no "
    "evidence cells"
)
def given_no_evidence(
    metrics_driver: SustainabilityMetricsDriver, tmp_path: Path
) -> None:
    metrics_driver.given_metrics_requested_on_section_without_evidence(tmp_path)


# -- When -------------------------------------------------------------------


@when("the sustainability metrics check runs")
def when_metrics_check_runs(metrics_driver: SustainabilityMetricsDriver) -> None:
    metrics_driver.when_metrics_check_runs()


# -- Then -------------------------------------------------------------------


@then("the check reports the consolidation-delta net test-LOC evidence")
def then_reports_consolidation_delta(
    metrics_driver: SustainabilityMetricsDriver,
) -> None:
    metrics_driver.then_reports_consolidation_delta_evidence()


@then("the check reports the generic-framework-adoption-ratio evidence")
def then_reports_adoption_ratio(metrics_driver: SustainabilityMetricsDriver) -> None:
    metrics_driver.then_reports_adoption_ratio_evidence()


@then("the reported consolidation-delta net test-LOC is not positive")
def then_consolidation_delta_non_positive(
    metrics_driver: SustainabilityMetricsDriver,
) -> None:
    metrics_driver.then_consolidation_delta_is_non_positive()


@then(parsers.parse('the blind-add cross-check reports "{verdict}"'))
def then_blind_add_is(
    metrics_driver: SustainabilityMetricsDriver, verdict: str
) -> None:
    metrics_driver.then_blind_add_cross_check_is(BlindAddVerdict(verdict))


@then("the check accepts the metrics section")
def then_accepts(metrics_driver: SustainabilityMetricsDriver) -> None:
    metrics_driver.then_accepts()


@then("the check rejects the metrics section")
def then_rejects(metrics_driver: SustainabilityMetricsDriver) -> None:
    metrics_driver.then_rejects()


@then(parsers.parse('the check reports the verdict "{verdict}"'))
def then_verdict_is(metrics_driver: SustainabilityMetricsDriver, verdict: str) -> None:
    metrics_driver.then_verdict_is(Verdict(verdict))
