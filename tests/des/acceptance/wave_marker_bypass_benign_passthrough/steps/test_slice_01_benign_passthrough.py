"""pytest-bdd binding for the corrected-guard scenarios (slice-01).

Driving port: the REAL ``PreToolUseService.validate`` via the production
composition root (Mandate-13 driving-port-only, Layer 3 composition). Step bodies
delegate to the composition root (``composition_slice_01.py``); no production
module is imported-and-called at the step boundary, and no business logic / control
flow lives in a step body (Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each step
decorator's literal text is unique within this feature directory (S1 step-text-
uniqueness invariant).

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
re-points the S2 guard from the floor-presence predicate to
``carries_partial_wave_context``, the benign markerless dispatch under an armed
floor is BLOCKED (AT-1 fails RED) and the partial-context bypass is ALLOWED
(AT-2 fails RED). AT-3/AT-4/AT-5 are preservation-GREEN regression guards. Each
RED is a semantic ``AssertionError`` -- never a collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_01 import GuardComposition
from .domain_types import DispatchShape, FloorState


scenarios("../slice-01-benign-passthrough-vs-bypass.feature")


@pytest.fixture
def composition() -> GuardComposition:
    return GuardComposition()


# --- Given -------------------------------------------------------------------


@given("a design wave floor is armed in an isolated project")
def given_design_floor_armed(composition: GuardComposition, tmp_path: Path) -> None:
    composition.given_floor(tmp_path, FloorState.DESIGN_ARMED)


@given("no wave floor is armed in an isolated project")
def given_no_floor_armed(composition: GuardComposition, tmp_path: Path) -> None:
    composition.given_floor(tmp_path, FloorState.NO_FLOOR)


@given("the dispatch is the wave-entering dispatch")
def given_wave_entering(composition: GuardComposition) -> None:
    composition.given_wave_entering()


# --- When --------------------------------------------------------------------


@when("a fully markerless prompt is checked by the gate")
def when_fully_markerless_checked(composition: GuardComposition) -> None:
    composition.when_dispatch_checked(DispatchShape.FULLY_MARKERLESS)


@when(
    "an in-wave child carrying partial wave context but missing its required "
    "marker is checked by the gate"
)
def when_partial_markers_checked(composition: GuardComposition) -> None:
    composition.when_dispatch_checked(DispatchShape.PARTIAL_MARKERS)


@when(
    "a child carrying only a wave declaration but missing its required marker "
    "is checked by the gate"
)
def when_des_wave_only_checked(composition: GuardComposition) -> None:
    composition.when_dispatch_checked(DispatchShape.DES_WAVE_ONLY)


# --- Then --------------------------------------------------------------------


@then("the gate allows the dispatch")
def then_gate_allows(composition: GuardComposition) -> None:
    composition.then_allowed()


@then("the gate leaves the benign dispatch completely untouched")
def then_benign_untouched(composition: GuardComposition) -> None:
    composition.then_left_untouched()


@then("the gate blocks the dispatch")
def then_gate_blocks(composition: GuardComposition) -> None:
    composition.then_blocked()


@then("the block names the wave-bypass so it cannot pass as a silent success")
def then_block_names_bypass(composition: GuardComposition) -> None:
    composition.then_block_names_bypass()
