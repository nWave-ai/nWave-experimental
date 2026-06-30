"""pytest-bdd binding for wave-gateout-enforced-under-orchestration slice-01 (WS).

Drives the REAL ``handle_subagent_stop`` hook entry (Layer 3 composition) through
the production composition root with a WAVE-ONLY orchestration return, plus the
REAL ``des record-design-review`` producer CLI (Layer 3 subprocess). Step bodies
delegate to ``WaveGateoutComposition`` -- no business logic in steps (Mandate-12).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_wave_gateout import WaveGateoutComposition
from .domain_types import ReviewState


_FEATURE = Path(__file__).resolve().parents[1] / "wave-gateout-reachability.feature"

scenarios(str(_FEATURE))


@pytest.fixture
def composition(tmp_path: Path) -> WaveGateoutComposition:
    """A fresh wave-gateout composition rooted at a tmp work-tree per scenario."""
    return WaveGateoutComposition(repo_dir=tmp_path)


# ---- Given ------------------------------------------------------------------


@given("an architect is returning a DESIGN deliverable under autonomous orchestration")
def _given_architect_returning(composition: WaveGateoutComposition) -> None:
    composition.given_architect_returning_under_orchestration()


@given("no DESIGN review has been recorded for that deliverable")
def _given_no_review(composition: WaveGateoutComposition) -> None:
    composition.given_review_recorded(ReviewState.NONE)


@given("the architect's reviewer has recorded an approved review for that deliverable")
def _given_approved_review(composition: WaveGateoutComposition) -> None:
    composition.given_review_recorded(ReviewState.APPROVED)


# ---- When -------------------------------------------------------------------


@when("the orchestration return is evaluated at the wave boundary")
def _when_return_evaluated(composition: WaveGateoutComposition) -> None:
    composition.when_orchestration_return_evaluated()


# ---- Then -------------------------------------------------------------------


@then("the wave closure is refused")
def _then_refused(composition: WaveGateoutComposition) -> None:
    composition.then_wave_closure_refused()


@then("the wave closure is refused with an unreviewed-deliverable reason")
def _then_refused_unreviewed(composition: WaveGateoutComposition) -> None:
    composition.then_wave_closure_refused_unreviewed()


@then("the wave closure is allowed")
def _then_allowed(composition: WaveGateoutComposition) -> None:
    composition.then_wave_closure_allowed()
