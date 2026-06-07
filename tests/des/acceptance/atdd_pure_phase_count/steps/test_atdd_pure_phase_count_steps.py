"""Step definitions for the atdd_pure 3-phase-count reduction ATs.

Mandate-12: step bodies delegate to the composition root
(`PhaseModelComposition`) and assert on the port-exposed report — no business
logic, no phase-set derivation, in the bodies.

Mandate-13: the only production surface touched is the driving-port wrapper in
`composition.py`, which runs the real `python -m des.cli.phases` subprocess.
NO direct import of `des.domain.atdd_pure_phases.ATDDPurePhase` (the SUT).

Mandate-8: this is a Layer-3 subprocess driving-port AT; the report is the
port-exposed observable. Assertions use the typed `PhaseReport` accessors over
port-exposed names (phases / transitions / count), never internal enum fields.
Layer-3 may use traditional assertions per Mandate 8.

The `scenarios(...)` binding lives here so pytest's `python_files = test_*.py`
discovery collects the generated scenario test functions (mirrors the sibling
`atdd_pure_dispatch_markers` suite).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then

from tests.des.acceptance.atdd_pure_phase_count.steps.composition import (
    PhaseModelComposition,
    PhaseReport,
)


scenarios("../atdd_pure_phase_count_reduction.feature")


@pytest.fixture
def composition() -> PhaseModelComposition:
    return PhaseModelComposition()


@pytest.fixture
def report_box() -> dict[str, PhaseReport]:
    """Carrier for the report produced by the When step."""
    return {}


@given("the operator asks the spine to report its delivery phases")
def _ask_for_report(composition, report_box) -> None:
    report_box["report"] = composition.report_phase_model()


@then("the spine reports exactly three delivery phases")
def _then_count_three(report_box) -> None:
    assert report_box["report"].count == 3


@then(parsers.parse('the reported phases are exactly the canonical set "{names}"'))
def _then_phases_exact_canonical(report_box, names: str) -> None:
    expected = {p.strip() for p in names.split(",")}
    assert set(report_box["report"].phases) == expected


@then(parsers.parse('none of the retired phases "{names}" appears in the report'))
def _then_no_retired(report_box, names: str) -> None:
    retired = {p.strip() for p in names.split(",")}
    assert retired.isdisjoint(set(report_box["report"].phases))


@then(
    parsers.parse(
        'the spine reports the legal transition from "{source}" to "{target}"'
    )
)
def _then_has_transition(report_box, source: str, target: str) -> None:
    assert report_box["report"].has_transition(source, target)


@then(
    parsers.parse('the spine reports no transition out of the retired phase "{source}"')
)
def _then_no_transition_from(report_box, source: str) -> None:
    assert not report_box["report"].has_any_transition_from(source)
