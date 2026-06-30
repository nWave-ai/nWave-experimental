"""slice-07 step definitions — CONSOLIDATE-ON-ADD (add-AND-improve, DDD-4/5/6).

Driving port: `des validate-feature-delta --require-sustainability --with-metrics
--add-only-baseline-loc=<N> --format=json` subprocess (Mandate-13, Layer 3 subprocess).
The subprocess is the SUT; no production module is imported at the step boundary. Each
step body delegates to the `ConsolidateOnAddDriver` composition (Mandate-12: ≤2
statements, no inline logic, no control flow).

Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04
cells + the blind_add cross-check but emits NO `consolidate_on_add` leg and accepts NO
`--add-only-baseline-loc` argument, so every scenario's consolidate-on-add accessor raises
a clean AssertionError (MISSING_FUNCTIONALITY) — not an ImportError. DELIVER makes these
GREEN by adding the pure `consolidate_on_add_gain` calc to `sustainability_metrics.py` +
the `--add-only-baseline-loc` mode — it does NOT unskip anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice_07_composition import ConsolidateOnAddDriver
from .slice_07_domain_types import ConsolidateOnAddVerdict, Verdict


scenarios("../slice-07-consolidate-on-add.feature")


@pytest.fixture
def coa_driver() -> ConsolidateOnAddDriver:
    return ConsolidateOnAddDriver()


# -- Given ------------------------------------------------------------------


@given(
    "a maintainer adds a slice and also consolidates, netting below the add-only baseline"
)
def given_add_and_improve(coa_driver: ConsolidateOnAddDriver, tmp_path: Path) -> None:
    coa_driver.given_add_and_improve_below_baseline(tmp_path)


@given("a maintainer claims add-AND-improve but the run only added the same scope")
def given_only_added(coa_driver: ConsolidateOnAddDriver, tmp_path: Path) -> None:
    coa_driver.given_declares_add_and_improve_but_only_added(tmp_path)


@given(
    "a maintainer requests the add-AND-improve check but supplies no add-only baseline"
)
def given_no_baseline(coa_driver: ConsolidateOnAddDriver, tmp_path: Path) -> None:
    coa_driver.given_consolidate_on_add_without_baseline(tmp_path)


@given(
    "a maintainer requests consolidate-on-add on a section that supplies no evidence cells"
)
def given_no_evidence(coa_driver: ConsolidateOnAddDriver, tmp_path: Path) -> None:
    coa_driver.given_metrics_on_section_without_evidence(tmp_path)


# -- When -------------------------------------------------------------------


@when("the consolidate-on-add check runs")
def when_check_runs(coa_driver: ConsolidateOnAddDriver) -> None:
    coa_driver.when_consolidate_on_add_check_runs()


# -- Then -------------------------------------------------------------------


@then("the check reports the consolidate-on-add gain evidence")
def then_reports_gain(coa_driver: ConsolidateOnAddDriver) -> None:
    coa_driver.then_reports_consolidate_on_add_gain()


@then("the reported consolidate-on-add gain is not positive")
def then_gain_non_positive(coa_driver: ConsolidateOnAddDriver) -> None:
    coa_driver.then_consolidate_on_add_gain_is_non_positive()


@then(parsers.parse('the consolidate-on-add cross-check reports "{verdict}"'))
def then_cross_check_is(coa_driver: ConsolidateOnAddDriver, verdict: str) -> None:
    coa_driver.then_consolidate_on_add_cross_check_is(ConsolidateOnAddVerdict(verdict))


@then("the check accepts the consolidate-on-add section")
def then_accepts(coa_driver: ConsolidateOnAddDriver) -> None:
    coa_driver.then_accepts()


@then("the check rejects the consolidate-on-add section")
def then_rejects(coa_driver: ConsolidateOnAddDriver) -> None:
    coa_driver.then_rejects()


@then(parsers.parse('the check reports the verdict "{verdict}"'))
def then_verdict_is(coa_driver: ConsolidateOnAddDriver, verdict: str) -> None:
    coa_driver.then_verdict_is(Verdict(verdict))
