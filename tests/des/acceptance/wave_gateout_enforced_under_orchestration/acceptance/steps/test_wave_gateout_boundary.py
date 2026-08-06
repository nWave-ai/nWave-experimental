"""pytest-bdd binding for the wave-gateout fail-closed boundary.

Drives the REAL ``handle_subagent_stop`` hook entry (Layer 3 composition) through the
production composition root with a constructed return on stdin. Step bodies delegate to
``WaveBoundaryComposition`` -- no business logic in steps (Mandate-12). The driving
primitives are REUSED from the slice-01 surface (Mandate-12 reuse).

MIXED RED/green classification (reported per scenario):
  * AT-13 (out-of-vocab wave) / AT-14 (no project id) -> ACTIVE-RED: the fail-closed
    boundary does not exist at HEAD (an unresolvable DES return is silently allowed).
    They RUN and fail for the right reason (the hook allows where it must block).
  * AT-15 (non-DES) -> GREEN-on-keystone regression-lock (the existing
    passthrough-allow).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_wave_boundary import WaveBoundaryComposition
from .domain_types import MarkerShape


_ACCEPTANCE_DIR = Path(__file__).resolve().parents[1]

scenarios(str(_ACCEPTANCE_DIR / "wave-gateout-boundary.feature"))


@pytest.fixture
def boundary(tmp_path: Path) -> WaveBoundaryComposition:
    """A fresh boundary composition rooted at a tmp work-tree per scenario."""
    return WaveBoundaryComposition(repo_dir=tmp_path)


# ---- Given -------------------------------------------------------------------


@given("a wave-agent returns under orchestration declaring an out-of-vocabulary wave")
def _given_out_of_vocab(boundary: WaveBoundaryComposition) -> None:
    boundary.given_marker_shape(MarkerShape.OUT_OF_VOCAB)
    boundary.given_return_under_orchestration()


@given(
    "a wave-agent returns under orchestration with a wave marker but no project identity"
)
def _given_no_project_id(boundary: WaveBoundaryComposition) -> None:
    boundary.given_marker_shape(MarkerShape.NO_PROJECT_ID)
    boundary.given_return_under_orchestration()


@given("an agent returns under orchestration carrying no DES wave marker at all")
def _given_non_des(boundary: WaveBoundaryComposition) -> None:
    boundary.given_marker_shape(MarkerShape.NON_DES)
    boundary.given_return_under_orchestration()


# ---- When --------------------------------------------------------------------


@when("the orchestration return is evaluated at the wave boundary")
def _when_return_evaluated(boundary: WaveBoundaryComposition) -> None:
    boundary.when_orchestration_return_evaluated()


# ---- Then --------------------------------------------------------------------


@then("the wave closure is refused")
def _then_refused(boundary: WaveBoundaryComposition) -> None:
    boundary.then_wave_closure_refused()


@then("the wave closure is allowed")
def _then_allowed(boundary: WaveBoundaryComposition) -> None:
    boundary.then_wave_closure_allowed()
