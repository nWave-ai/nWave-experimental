"""pytest-bdd binding for the slice-01 relax-false-positive scenarios.

Driving port (Mandate-13 driving-port-only, Layer 3 composition): the REAL
PreToolUseService.validate via the production composition root over a tmp
project_root with a real WaveActiveReader floor. Step bodies delegate to the
composition root (composition_slice_marker_contract_01.py); no business logic in
step bodies (Mandate-12). Every step decorator's literal is unique within this
feature directory (S1) and disjoint from the slice-04 / 07 / 07b / 07c / 07d
literals.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
exempts input_data.wave_entering=True at the :146 veto, a DES-WAVE-only entering
dispatch is blocked WAVE_MARKER_BYPASS -> AT-1a/1b fail with a semantic
AssertionError (BLOCKED where ALLOW was expected). AT-1c (markerless child
denied) is preservation-GREEN at HEAD and pins the S2 veto through DELIVER (R-A2).

SUT STATE MACHINE (C2): see the .feature header + composition docstring --
{WAVE_ENTERING(DES_WAVE_ONLY), MARKERLESS_CHILD(non-entering)} with
entering-dispatch-exempt / markerless-non-entering-child-denied transitions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_marker_contract_01 import MarkerContractRelaxComposition
from .domain_types_slice_marker_contract import WaveUnderTest


scenarios("../slice-marker-contract-01-relax-false-positive.feature")


@pytest.fixture
def relax() -> MarkerContractRelaxComposition:
    return MarkerContractRelaxComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the {wave} wave is active and this dispatch is entering it"))
def given_wave_active_entering(
    relax: MarkerContractRelaxComposition, tmp_path: Path, wave: str
) -> None:
    relax.given_wave_active_entering(tmp_path, WaveUnderTest(wave))


# CLASS-1 RE-EXPRESS (ADR-001 Amendment 2): trigger re-expressed markerless ->
# partial-context; the composition seeds a DES-* subset (no DES-VALIDATION) that
# still BLOCKs, preserving the R-A2 deletion-mutation guard.
@given("the design wave is active and a partial-context non-entering child arrives")
def given_partial_context_child_in_wave(
    relax: MarkerContractRelaxComposition, tmp_path: Path
) -> None:
    relax.given_markerless_child_in_wave(tmp_path, WaveUnderTest.DESIGN)


# --- When ------------------------------------------------------------------


@when("a DES-WAVE-only entering dispatch is checked")
def when_des_wave_only_entering_checked(
    relax: MarkerContractRelaxComposition,
) -> None:
    relax.when_des_wave_only_entering_dispatch_checked()


@when("a partial-context in-wave child dispatch is checked")
def when_partial_context_child_checked(relax: MarkerContractRelaxComposition) -> None:
    relax.when_markerless_child_dispatch_checked()


# --- Then ------------------------------------------------------------------


@then("the entering dispatch is recognized and allowed")
def then_entry_recognized_and_allowed(
    relax: MarkerContractRelaxComposition,
) -> None:
    relax.then_entry_recognized_and_allowed()


@then("the allow decision carries no bypass veto")
def then_no_bypass_block(relax: MarkerContractRelaxComposition) -> None:
    relax.then_no_bypass_block()


@then("the partial-context child dispatch is denied as a wave bypass")
def then_bypass_denied_loud(relax: MarkerContractRelaxComposition) -> None:
    relax.then_bypass_denied_loud()
