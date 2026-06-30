"""pytest-bdd binding for wave-gateout slices 02/03/04 (wave-parametric regression-locks).

Drives the REAL ``handle_subagent_stop`` hook entry (Layer 3 composition) through the
production composition root with a WAVE-ONLY orchestration return, plus the REAL
``des record-<wave>-review`` producer CLIs (Layer 3 subprocess). Step bodies delegate
to ``WaveParametricGateoutComposition`` -- no business logic in steps (Mandate-12). The
driving primitives are REUSED from the slice-01 surface (Mandate-12 step reuse).

GREEN-on-keystone: slices 02/03/04 are regression-locks proving the single slice-01
wave-parametric route already covers the DEVOPS / DISCUSS-structural / DISCUSS-PO-review
gate-outs. They PASS on the current committed code (NOT active-RED, NOT @skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_wave_parametric import WaveParametricGateoutComposition
from .domain_types import DiscussGateRow, ReviewState, Wave


_ACCEPTANCE_DIR = Path(__file__).resolve().parents[1]

scenarios(
    str(_ACCEPTANCE_DIR / "wave-gateout-devops.feature"),
    str(_ACCEPTANCE_DIR / "wave-gateout-discuss-structural.feature"),
    str(_ACCEPTANCE_DIR / "wave-gateout-discuss-review.feature"),
)


@pytest.fixture
def parametric(tmp_path: Path) -> WaveParametricGateoutComposition:
    """A fresh wave-parametric composition rooted at a tmp work-tree per scenario."""
    return WaveParametricGateoutComposition(repo_dir=tmp_path)


# ---- Given: the orchestration return precondition (per wave) ----------------


@given(
    "a platform-architect is returning a DEVOPS deliverable under autonomous orchestration"
)
def _given_devops_returning(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_wave(Wave.DEVOPS)
    parametric.given_agent_returning_under_orchestration()


@given(
    "a product-owner is returning a DISCUSS deliverable under autonomous orchestration"
)
def _given_discuss_returning(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_wave(Wave.DISCUSS)
    parametric.given_discuss_gate_row(DiscussGateRow.STRUCTURAL)


# ---- Given: the DISCUSS slice-plan shape (structural row, slice-03) ----------


@given("the feature-delta slice plan carries no user-observable value")
def _given_infra_only_plan(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_slice_plan_value_bearing(False)
    parametric.given_agent_returning_under_orchestration()


@given("the feature-delta slice plan carries user-observable value")
def _given_value_bearing_plan(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_slice_plan_value_bearing(True)
    parametric.given_agent_returning_under_orchestration()


# ---- Given: the recorded-review precondition (per wave) ----------------------


@given("no DEVOPS review has been recorded for that deliverable")
def _given_no_devops_review(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_review_recorded(ReviewState.NONE)


@given("the reviewer has recorded an approved DEVOPS review for that deliverable")
def _given_approved_devops_review(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_review_recorded(ReviewState.APPROVED)


@given("no product-owner review has been recorded for that deliverable")
def _given_no_po_review(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_review_recorded(ReviewState.NONE)


@given("the product-owner has recorded an approved review for that deliverable")
def _given_approved_po_review(parametric: WaveParametricGateoutComposition) -> None:
    parametric.given_review_recorded(ReviewState.APPROVED)


# ---- When --------------------------------------------------------------------


@when("the orchestration return is evaluated at the wave boundary")
def _when_return_evaluated(parametric: WaveParametricGateoutComposition) -> None:
    parametric.when_orchestration_return_evaluated()


# ---- Then --------------------------------------------------------------------


@then("the wave closure is refused with a missing-devops-review reason")
def _then_refused_devops(parametric: WaveParametricGateoutComposition) -> None:
    parametric.then_wave_closure_refused_naming("review verdict", "absent")


@then("the wave closure is refused with a non-value-bearing slice-plan reason")
def _then_refused_structural(parametric: WaveParametricGateoutComposition) -> None:
    parametric.then_wave_closure_refused_naming("slice plan", "value-bearing")


@then("the wave closure is not refused on structural grounds")
def _then_not_structural(parametric: WaveParametricGateoutComposition) -> None:
    parametric.then_wave_closure_not_blocked_structurally()


@then("the wave closure is refused with a missing-review reason")
def _then_refused_po(parametric: WaveParametricGateoutComposition) -> None:
    parametric.then_wave_closure_refused_naming("absent")


@then("the wave closure is allowed")
def _then_allowed(parametric: WaveParametricGateoutComposition) -> None:
    parametric.then_wave_closure_allowed()
