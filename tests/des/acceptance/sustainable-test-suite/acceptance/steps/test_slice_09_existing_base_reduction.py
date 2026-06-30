"""slice-09 step definitions — EXISTING-BASE CONTINUOUS REDUCTION (DDD-16C/17C).

Driving port: `des validate-feature-delta --require-sustainability --with-metrics
--existing-base-trend [--prior-existing-base-ratio=<float>] [--corpus-root=<dir>]
--format=json` subprocess (Mandate-13, Layer 3 subprocess). The subprocess is the SUT;
no production module is imported at the step boundary. Each step body delegates to the
`ExistingBaseTrendDriver` composition (Mandate-12: ≤2 statements, no inline logic, no
control flow).

Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04 cells
+ the slice-07 consolidate-on-add leg, but accepts NO `--existing-base-trend` flag and emits
NO `existing_base_duplication_ratio` cell nor `existing_base_trend` cross-check object, so
every scenario's existing-base accessor raises a clean AssertionError (MISSING_FUNCTIONALITY)
— not an ImportError. DELIVER makes these GREEN by adding the pure
`existing_base_duplication_ratio` calc to `sustainability_metrics.py` + the CodeFactPort
step-shape leg + the `--existing-base-trend` mode + the `--prior-existing-base-ratio` /
`--corpus-root` values — it does NOT unskip anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice_09_composition import ExistingBaseTrendDriver
from .slice_09_domain_types import ExistingBaseTrendVerdict, Verdict


scenarios("../slice-09-existing-base-reduction.feature")


@pytest.fixture
def eb_driver() -> ExistingBaseTrendDriver:
    return ExistingBaseTrendDriver()


# -- Given ------------------------------------------------------------------


@given(
    "a maintainer folds an existing near-duplicate step cluster, netting the "
    "existing-base ratio below the prior"
)
def given_improved(eb_driver: ExistingBaseTrendDriver, tmp_path: Path) -> None:
    eb_driver.given_existing_base_improved_below_prior(tmp_path)


@given(
    "a maintainer's run makes the existing-base near-duplicate-step ratio rise above the prior"
)
def given_regressed(eb_driver: ExistingBaseTrendDriver, tmp_path: Path) -> None:
    eb_driver.given_existing_base_regressed_above_prior(tmp_path)


@given(
    "a maintainer declares existing-base work where the AST step-shape corpus cannot be read"
)
def given_corpus_unavailable(
    eb_driver: ExistingBaseTrendDriver, tmp_path: Path
) -> None:
    eb_driver.given_ast_corpus_unavailable(tmp_path)


@given(
    "a maintainer requests the existing-base trend check but supplies no prior committed ratio"
)
def given_no_prior(eb_driver: ExistingBaseTrendDriver, tmp_path: Path) -> None:
    eb_driver.given_existing_base_trend_without_prior(tmp_path)


# -- When -------------------------------------------------------------------


@when("the existing-base trend check runs")
def when_check_runs(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.when_existing_base_trend_check_runs()


# -- Then -------------------------------------------------------------------


@then("the check reports the existing-base near-duplicate-step ratio evidence")
def then_reports_ratio(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.then_reports_existing_base_ratio()


@then("the reported existing-base ratio is a real fraction")
def then_ratio_real_fraction(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.then_existing_base_ratio_is_a_real_fraction()


@then("the reported existing-base ratio is below the prior committed ratio")
def then_ratio_below_prior(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.then_existing_base_ratio_below_prior()


@then(parsers.parse('the existing-base trend cross-check reports "{verdict}"'))
def then_trend_is(eb_driver: ExistingBaseTrendDriver, verdict: str) -> None:
    eb_driver.then_existing_base_trend_is(ExistingBaseTrendVerdict(verdict))


@then("the check accepts the existing-base section")
def then_accepts(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.then_accepts()


@then("the check rejects the existing-base section")
def then_rejects(eb_driver: ExistingBaseTrendDriver) -> None:
    eb_driver.then_rejects()


@then(parsers.parse('the check reports the verdict "{verdict}"'))
def then_verdict_is(eb_driver: ExistingBaseTrendDriver, verdict: str) -> None:
    eb_driver.then_verdict_is(Verdict(verdict))
