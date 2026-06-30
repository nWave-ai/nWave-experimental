"""slice-03 step definitions — the sustainability CONTENT GATE.

Driving port: `des validate-feature-delta --require-sustainability --format=json`
subprocess (Mandate-13, Layer 3 subprocess). The subprocess is the SUT; no production
module is imported at the step boundary. Each step body delegates to the
`SustainabilityGateDriver` composition (Mandate-12: ≤2 statements, no inline logic, no
control flow).

Active-RED: at HEAD `des validate-feature-delta` has no `--require-sustainability` mode,
so the subprocess emits no JSON verdict; every scenario asserts a post-implementation
verdict token and so fails with a clean AssertionError (MISSING_FUNCTIONALITY). DELIVER
makes these GREEN by adding `validate_sustainability_content` + the
`--require-sustainability` mode — it does NOT unskip anything.

SCOPE (HARD): the `blind-add-detected` verdict (git-diff cross-check) is slice-04/05, not
here — slice-03 is git-free section-content validation only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .slice_03_composition import SustainabilityGateDriver
from .slice_03_domain_types import Verdict


scenarios("../slice-03-sustainability-content-gate.feature")


@pytest.fixture
def gate_driver() -> SustainabilityGateDriver:
    return SustainabilityGateDriver()


# -- Given ------------------------------------------------------------------


@given(
    "a maintainer authors a feature-delta whose sustainability section is well formed"
)
def given_well_formed(gate_driver: SustainabilityGateDriver, tmp_path: Path) -> None:
    gate_driver.given_well_formed_section(tmp_path)


@given("a maintainer authors a feature-delta that omits the sustainability section")
def given_no_section(gate_driver: SustainabilityGateDriver, tmp_path: Path) -> None:
    gate_driver.given_no_section(tmp_path)


@given(
    "a maintainer authors a feature-delta whose sustainability section has the "
    "wrong columns"
)
def given_wrong_columns(gate_driver: SustainabilityGateDriver, tmp_path: Path) -> None:
    gate_driver.given_wrong_columns_section(tmp_path)


@given(
    "a maintainer authors a feature-delta with a CREATE_NEW row whose justification "
    "is empty"
)
def given_unjustified(gate_driver: SustainabilityGateDriver, tmp_path: Path) -> None:
    gate_driver.given_unjustified_create_new_section(tmp_path)


@given("a maintainer authors a feature-delta carrying the methodology-exempt marker")
def given_exempt(gate_driver: SustainabilityGateDriver, tmp_path: Path) -> None:
    gate_driver.given_methodology_exempt_section(tmp_path)


# -- When -------------------------------------------------------------------


@when("the sustainability content check runs")
def when_content_check_runs(gate_driver: SustainabilityGateDriver) -> None:
    gate_driver.when_content_check_runs()


# -- Then -------------------------------------------------------------------


@then("the check accepts the sustainability section")
def then_accepts(gate_driver: SustainabilityGateDriver) -> None:
    gate_driver.then_accepts()


@then("the check rejects the sustainability section")
def then_rejects(gate_driver: SustainabilityGateDriver) -> None:
    gate_driver.then_rejects()


@then(parsers.parse('the check reports the verdict "{verdict}"'))
def then_verdict_is(gate_driver: SustainabilityGateDriver, verdict: str) -> None:
    gate_driver.then_verdict_is(Verdict(verdict))
