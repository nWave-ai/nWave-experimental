"""Step definitions: the epic-delta tracks live progress through status flips.

discuss-epic-mode slice-05 (the linkage/status-flip MAINTENANCE procedure).

Honest mechanical-vs-prompt boundary: the status flip is performed by the
maintainer following the nw-discuss skill procedure during a discuss / feature-end
session (DESIGN slice-02/04/05 text contracts: the slice's "code" is SKILL / COMMAND
text, NO net-new ``src/des`` maintenance surface). These ATs pin the LSC contract
(LSC-1..LSC-6) on the flip OUTCOME -- the pick-up flip + link (LSC-1), the finalize
flip (LSC-2), the keystone-gate preservation via slice-01's REAL CLI, the fractal-JIT
invariant (LSC-3), and the procedure-level rejection of an illegal token (LSC-6) --
witnessed against a suite-local reference producer (a golden-file analogue of the
maintainer's flip), NOT a prose-grep of SKILL.md (presence-watcher anti-pattern).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the LSC is a finite, enumerable closed contract over the 3-token status set.

Step bodies delegate to ``MaintenanceComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call, or
a composition observation plus a single assertion.

Active-RED contract (atdd_pure): every LSC observation FAILS on the current tip and
PASSES once slice-05 lands. The maintenance procedure is undefined today, so
``run_maintenance`` applies no flip -- the observation reads ``MAINTENANCE_ABSENT``.
A deliberate missing-functionality RED (absent flip and absent LSC pins), not a test
bug. The composition imports ONLY slice-01's already-shipped CLI (the
gate-preservation leg) -- ZERO ``des.{domain,application,adapters}`` code -- so the
RED is a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .composition import GateOutResult, MaintenanceComposition, RowObservation
from .domain_types import (
    FEATURE_STATUS_BY_PHRASE,
    FeatureId,
    GateOutVerdict,
    MaintenanceAction,
    MaintenanceVerdict,
)


scenarios("../epic-mode-maintenance.feature")


@pytest.fixture
def composition(tmp_path: Path) -> MaintenanceComposition:
    """Composition root over a tmp_path repository."""
    return MaintenanceComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for observations across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("an authored epic-delta whose feature rows are all pending")
def given_authored_epic(composition: MaintenanceComposition) -> None:
    composition.open_authored_epic(composition.epic_id)


@given(parsers.parse("the maintainer picks up the feature {feature_id}"))
def given_picks_up(composition: MaintenanceComposition, feature_id: str) -> None:
    composition.target(FeatureId(feature_id), MaintenanceAction.PICK_UP)


@given(parsers.parse("the feature {feature_id} is {status_phrase}"))
def given_feature_status(
    composition: MaintenanceComposition, feature_id: str, status_phrase: str
) -> None:
    composition.seed_feature_status(
        FeatureId(feature_id), FEATURE_STATUS_BY_PHRASE[status_phrase]
    )


@given(parsers.parse("the maintainer finalizes the feature {feature_id}"))
def given_finalizes(composition: MaintenanceComposition, feature_id: str) -> None:
    composition.target(FeatureId(feature_id), MaintenanceAction.FINALIZE)


@given(parsers.parse("the maintainer proposes the illegal status token {token}"))
def given_proposes_token(composition: MaintenanceComposition, token: str) -> None:
    composition.propose_status_token(token)


# --- When --------------------------------------------------------------------


@when("the maintainer runs the maintenance on the epic-delta")
def when_run_maintenance(
    composition: MaintenanceComposition, result_box: dict[str, object]
) -> None:
    composition.run_maintenance()
    result_box["row"] = composition.observe_row()


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the picked-up row reads {status_phrase}"))
def then_picked_up_status(result_box: dict[str, object], status_phrase: str) -> None:
    """LSC-1: pick-up flips the row pending -> in-flight (forward-only, LSC-5).

    On the current tip the maintenance procedure is undefined, so the observation
    reads ``MAINTENANCE_ABSENT`` and the status stays its pre-maintenance
    ``pending`` -- this pin fails (the active-RED missing-functionality signal).
    """
    row = result_box["row"]
    assert isinstance(row, RowObservation)
    assert row.verdict is MaintenanceVerdict.APPLIED, (
        "LSC-1: the pick-up flip is applied"
    )
    assert row.status is FEATURE_STATUS_BY_PHRASE[status_phrase], (
        "LSC-1/LSC-5: the picked-up row reads in-flight (forward-only)"
    )


@then("the picked-up row carries its docs/feature link")
def then_picked_up_link(result_box: dict[str, object]) -> None:
    """LSC-1: the pick-up flip is one atomic edit -- the row also gains its link.

    The Feature cell gains its ``docs/feature/{id}/`` link AT the pick-up flip, so
    a maintainer opening the epic-delta navigates straight to the picked-up
    feature's workspace.
    """
    row = result_box["row"]
    assert isinstance(row, RowObservation)
    assert row.has_workspace_link, (
        "LSC-1: the picked-up row's Feature cell carries its docs/feature/{id}/ link"
    )


@then(parsers.parse("the finalized row reads {status_phrase}"))
def then_finalized_status(result_box: dict[str, object], status_phrase: str) -> None:
    """LSC-2: finalize flips the row in-flight -> shipped (forward-only, LSC-5)."""
    row = result_box["row"]
    assert isinstance(row, RowObservation)
    assert row.verdict is MaintenanceVerdict.APPLIED, (
        "LSC-2: the finalize flip is applied"
    )
    assert row.status is FEATURE_STATUS_BY_PHRASE[status_phrase], (
        "LSC-2/LSC-5: the finalized row reads shipped (forward-only)"
    )


@then("the flipped epic-delta still clears the keystone gate")
def then_gate_preserved(composition: MaintenanceComposition) -> None:
    """LSC-1/LSC-2 corollary: a status flip must NOT break structural validity.

    The flipped epic-delta is re-validated through slice-01's REAL CLI; it must
    still return ``accepted``. Empirically (DC-1) the validator does NOT validate
    Status cells, so a well-formed flip preserves validity. On the current tip no
    flip was applied -> EPIC_DELTA_ABSENT, and this pin fails (active-RED).
    """
    gate_out = composition.validate_gate_out()
    assert isinstance(gate_out, GateOutResult)
    assert gate_out.verdict is GateOutVerdict.ACCEPTED, (
        "LSC-1/LSC-2: the flipped epic-delta still clears the keystone gate"
    )


@then("no pending feature has a workspace")
def then_jit_invariant(
    composition: MaintenanceComposition, result_box: dict[str, object]
) -> None:
    """LSC-3 fractal JIT: a row still ``pending`` has no docs/feature workspace.

    The universe is the pending-row workspace count: only the picked-up feature
    gets a workspace; ``pending`` rows get none. On the current tip no flip ran, so
    the row-status pin above fires first -- this delta pins the no-eager-workspace
    invariant at GREEN.
    """
    assert_state_delta(
        before={"pending_workspaces.count": 0},
        after={
            "pending_workspaces.count": composition.count_pending_feature_workspaces()
        },
        universe={"pending_workspaces.count"},
        expected={"pending_workspaces.count": set_to(0)},
    )


@then("the illegal status token is rejected by the maintenance procedure")
def then_token_rejected(composition: MaintenanceComposition) -> None:
    """LSC-6: an off-set Status token is rejected at the PROCEDURE level.

    The slice-01 validator does NOT validate Status cells (DC-1) -- ``done``
    validates ``accepted`` through the keystone gate today -- so this rejection is
    the slice-05 maintenance procedure's responsibility. On the current tip the
    procedure is undefined -> ``MAINTENANCE_ABSENT`` (not ``REJECTED_BAD_TOKEN``),
    so this pin fails (active-RED).
    """
    verdict = composition.observe_token_verdict()
    assert verdict is MaintenanceVerdict.REJECTED_BAD_TOKEN, (
        "LSC-6: an illegal status token is rejected at the maintenance-procedure "
        "level (the keystone gate does not validate Status cells -- DC-1)"
    )
