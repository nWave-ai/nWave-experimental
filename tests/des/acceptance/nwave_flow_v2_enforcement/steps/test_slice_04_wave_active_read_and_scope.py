"""pytest-bdd binding for the wave-active read + scope scenarios (slice-04).

Driving port: the REAL ``PreToolUseService.validate`` via the production
composition root (Mandate-13 driving-port-only, Layer 3 composition). Step bodies
delegate to the composition root (``composition.py``); no production module is
imported-and-called at the step boundary, and no business logic lives in a step
body (Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each step
decorator's literal text is unique within this feature directory (S1 step-text-
uniqueness invariant) and disjoint from the walking-skeleton step file's
literals -- no literal is declared with its own body in two files.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
ships the WaveActiveReader adapter + the wave-aware ``pre_tool_use_service.py``
hinge, the production service falls through to the current no-marker -> allow()
behaviour, so the S2 scenario fails with a semantic ``AssertionError`` (the
service ALLOWED where a DENY was expected) -- never a collection / import / setup
error (pre-DELIVER fail-for-right-reason gate).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WaveActiveAnchorComposition
from .domain_types import Wave


scenarios("../slice-04-wave-active-read-and-scope.feature")


@pytest.fixture
def composition() -> WaveActiveAnchorComposition:
    return WaveActiveAnchorComposition()


# --- Given -------------------------------------------------------------------


@given("the discuss wave is active in the project")
def given_discuss_wave_active(
    composition: WaveActiveAnchorComposition, tmp_path: Path
) -> None:
    composition.given_wave_active(tmp_path, Wave.DISCUSS)


@given("no wave is active in the project")
def given_no_wave_active(
    composition: WaveActiveAnchorComposition, tmp_path: Path
) -> None:
    composition.given_no_wave_active(tmp_path)


# --- When --------------------------------------------------------------------


@when("a sub-dispatch that dropped its wave markers is checked by the gate")
def when_markerless_in_wave_checked(
    composition: WaveActiveAnchorComposition,
) -> None:
    composition.when_markerless_in_wave_dispatch_checked()


@when("a sub-dispatch carrying the wave markers is checked by the gate")
def when_marked_in_wave_checked(composition: WaveActiveAnchorComposition) -> None:
    composition.when_in_wave_dispatch_with_markers_checked()


@when("a bare non-wave dispatch is checked by the gate")
def when_bare_non_wave_checked(composition: WaveActiveAnchorComposition) -> None:
    composition.when_bare_non_wave_dispatch_checked()


# --- Then --------------------------------------------------------------------


# CLASS-1 RETARGET (ADR-001 Amendment 2): the markerless child now ALLOWs (K2
# benign passthrough). The former `denies` / `denial-names-bypass` steps are
# replaced by ALLOW + untouched. The bypass-DENY contract those steps encoded is
# preserved by the slice-01 PARTIAL-context ATs of fix-wave-marker-bypass-benign-
# passthrough (a partial-context child still DENIES loud).
@then("the gate allows the markerless sub-dispatch as benign passthrough")
def then_gate_allows_markerless(composition: WaveActiveAnchorComposition) -> None:
    composition.then_gate_allows()


@then("the gate leaves the markerless sub-dispatch completely untouched")
def then_markerless_untouched(composition: WaveActiveAnchorComposition) -> None:
    composition.then_bare_dispatch_untouched()


@then("the gate allows the sub-dispatch")
def then_gate_allows_sub_dispatch(
    composition: WaveActiveAnchorComposition,
) -> None:
    composition.then_gate_allows()


@then("the gate allows the dispatch")
def then_gate_allows_bare_dispatch(
    composition: WaveActiveAnchorComposition,
) -> None:
    composition.then_gate_allows()


@then("the gate leaves the bare dispatch completely untouched")
def then_bare_dispatch_untouched(
    composition: WaveActiveAnchorComposition,
) -> None:
    composition.then_bare_dispatch_untouched()
