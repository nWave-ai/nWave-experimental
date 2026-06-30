"""pytest-bdd binding for the refined-guard marker-form scenarios (slice-03).

ADR-001 Amendment 1. Driving port: the REAL ``PreToolUseService.validate`` via the
production composition root (Mandate-13 driving-port-only, Layer 3 composition).
Step bodies delegate to the composition root (``composition_slice_03.py``); no
production module is imported-and-called at the step boundary, and no business
logic / control flow lives in a step body (Mandate-12: each body is a single
delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each step
decorator's literal text is unique within this feature directory (S1 step-text-
uniqueness invariant) and disjoint from the slice-01 literals.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
re-points ``carries_partial_wave_context``'s exclusion from ``not is_des_task`` to
``not carries_des_validation``, a plain-line `DES-VALIDATION: required` child under
an armed floor is BLOCKED WAVE_MARKER_BYPASS (AT-8 fails RED -- it asserts the
bypass does NOT fire). AT-9 (neither-form partial) is preservation-GREEN. Each RED
is a semantic ``AssertionError`` -- never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import MarkerFormComposition
from .domain_types import DispatchShape, FloorState


scenarios("../slice-03-plain-line-des-validation.feature")


@pytest.fixture
def marker_form() -> MarkerFormComposition:
    return MarkerFormComposition()


# --- Given -------------------------------------------------------------------


@given("a design wave floor is armed in an isolated project for the marker-form check")
def given_design_floor_armed_marker_form(
    marker_form: MarkerFormComposition, tmp_path: Path
) -> None:
    marker_form.given_floor(tmp_path, FloorState.DESIGN_ARMED)


# --- When --------------------------------------------------------------------


@when("an in-wave child carrying a plain-line required marker is checked by the gate")
def when_plain_line_validation_checked(marker_form: MarkerFormComposition) -> None:
    marker_form.when_dispatch_checked(DispatchShape.PLAIN_LINE_DES_VALIDATION)


@when(
    "an in-wave child carrying partial markers but neither required-marker form "
    "is checked by the gate"
)
def when_neither_validation_form_checked(marker_form: MarkerFormComposition) -> None:
    marker_form.when_dispatch_checked(DispatchShape.NEITHER_VALIDATION_FORM)


# --- Then --------------------------------------------------------------------


@then("the gate does not block the dispatch as a wave-bypass")
def then_not_blocked_as_bypass(marker_form: MarkerFormComposition) -> None:
    marker_form.then_not_blocked_as_bypass()


@then("the gate blocks the dispatch as a wave-bypass")
def then_blocked_as_bypass(marker_form: MarkerFormComposition) -> None:
    marker_form.then_blocked_as_bypass()


@then("the bypass block names the wave-bypass so it cannot pass as a silent success")
def then_bypass_block_names_bypass(marker_form: MarkerFormComposition) -> None:
    marker_form.then_block_names_bypass()
