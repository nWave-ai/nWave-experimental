"""pytest-bdd binding for the dormant-seam gate escapes (slice-02).

Driving port: the production ``des dormant-seam-gate`` composition-root CLI,
invoked as a subprocess black box (Mandate-13 driving-port-only, Layer 3
subprocess). Step bodies delegate to the slice-02 composition root
(``composition_slice_02.py``); no production module is imported-and-called at the
step boundary, and no business logic lives in a step body (Mandate-12: each body
is a single delegation).

The ``scenarios(...)`` call binds every scenario in the slice-02 ``.feature`` via
the RELATIVE path from this steps/ module -- the proven-collecting form. Every
step decorator's literal text is UNIQUE within this feature directory (S1
step-text-uniqueness invariant): slice-02 deliberately phrases its When / Then
literals ("escape-aware dormant-seam gate", "exits with code zero" qualified as
"the escape-aware gate exits with code zero") so they do NOT collide with
slice-01's step literals in the same directory -- no global-registry shadowing.

RED scaffold: against the shipped slice-01 production, the ``# dormant-ok``
marker is ignored (no escape record, symbol still flagged) and the indirect
attribute-call wiring is unresolved (symbol wrongly flagged), so the Then-steps
fail with a semantic ``AssertionError`` (cleared/recorded assertions unmet) --
never a collection / import / setup error (pre-DELIVER fail-for-right-reason).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import DormantSeamEscapesComposition


scenarios("../slice-02-dormant-seam-escapes.feature")


@pytest.fixture
def escapes_composition() -> DormantSeamEscapesComposition:
    return DormantSeamEscapesComposition()


# --- Given -------------------------------------------------------------------


@given("a dormant effectful seam carrying a dormant-ok owned-residue marker")
def given_marked_dormant_seam(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.given_dormant_seam_with_owned_residue_marker()


@given("a dormant effectful seam reached only by an indirect wiring call-site")
def given_indirectly_wired_seam(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.given_dormant_seam_wired_indirectly()


@given("a wired effectful seam that also carries a dormant-ok owned-residue marker")
def given_wired_marked_seam(escapes_composition: DormantSeamEscapesComposition) -> None:
    escapes_composition.given_wired_seam_with_owned_residue_marker()


@given("a dormant effectful seam with neither a call-site nor a marker")
def given_unescaped_dormant_seam(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.given_dormant_seam_without_any_escape()


# --- When --------------------------------------------------------------------


@when("the developer runs the escape-aware dormant-seam gate at GREEN-phase")
def when_runs_escape_aware_gate(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.when_developer_runs_the_gate()


# --- Then --------------------------------------------------------------------


@then("the gate no longer flags the marked seam as dormant")
def then_marker_clears_seam(escapes_composition: DormantSeamEscapesComposition) -> None:
    escapes_composition.then_marker_clears_the_seam()


@then("the gate records the clearing naming the owning residue id")
def then_clearing_recorded(escapes_composition: DormantSeamEscapesComposition) -> None:
    escapes_composition.then_clearing_is_recorded_with_owner()


@then("the gate no longer flags the indirectly-wired seam as dormant")
def then_indirect_clears_seam(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.then_indirect_call_site_clears_the_seam()


@then("the gate records no escape for the already-wired seam")
def then_no_escape_for_wired(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.then_no_escape_record_for_wired_seam()


@then("the gate still names the unescaped seam in its loud warning")
def then_unmarked_still_warns(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.then_unmarked_seam_still_warns()


@then("the escape-aware gate exits with code zero")
def then_escape_aware_exits_zero(
    escapes_composition: DormantSeamEscapesComposition,
) -> None:
    escapes_composition.then_exits_zero()
