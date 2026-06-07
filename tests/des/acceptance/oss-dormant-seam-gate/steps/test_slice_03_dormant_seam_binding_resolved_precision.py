"""pytest-bdd binding for the dormant-seam gate binding-resolved precision (slice-03).

Driving port: the production ``des dormant-seam-gate`` composition-root CLI,
invoked as a subprocess black box (Mandate-13 driving-port-only, Layer 3
subprocess). Step bodies delegate to the slice-03 composition root
(``composition_slice_03.py``); no production module is imported-and-called at the
step boundary, and no business logic lives in a step body (Mandate-12: each body
is a single delegation).

The ``scenarios(...)`` call binds every scenario in the slice-03 ``.feature`` via
the RELATIVE path from this steps/ module -- the proven-collecting form. Every
step decorator's literal text is UNIQUE within this feature directory (S1
step-text-uniqueness invariant): slice-03 phrases its Given / When / Then literals
("binding-resolving dormant-seam gate", the entry-point / name-collision Givens, the
"binding-resolving gate exits with code zero" Then) so they do NOT collide with
slice-01's or slice-02's step literals in the same directory -- no global-registry
shadowing.

RED scaffold: against the shipped slice-02 production, the pyproject entry-point
group is NOT resolved (the dispatched symbol is wrongly flagged dormant), so the
entry-point Then-step fails with a semantic ``AssertionError`` (the cleared
assertion is unmet) -- never a collection / import / setup error
(pre-DELIVER fail-for-right-reason). The name-collision scenario may be
GREEN-on-arrival (slice-02 already keys on module-qualified identity) and stands
as the no-false-negation regression guard; the unregistered-recall control is the
KPI-1 non-vacuity pole.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import DormantSeamPrecisionComposition


scenarios("../slice-03-dormant-seam-binding-resolved-precision.feature")


@pytest.fixture
def precision_composition() -> DormantSeamPrecisionComposition:
    return DormantSeamPrecisionComposition()


# --- Given -------------------------------------------------------------------


@given(
    "a dormant effectful seam wired only by a nwave.lang.adapter entry-point registration"
)
def given_entry_point_dispatched_seam(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.given_entry_point_dispatched_seam()


@given(
    "two same-named effectful seams in different modules where production calls only one"
)
def given_name_collision_seams(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.given_name_collision_one_wired_one_dormant()


@given(
    "a dormant effectful seam with neither a call-site nor an entry-point registration"
)
def given_unregistered_dormant_seam(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.given_genuinely_dormant_unregistered_seam()


# --- When --------------------------------------------------------------------


@when("the developer runs the binding-resolving dormant-seam gate at GREEN-phase")
def when_runs_binding_resolving_gate(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.when_developer_runs_the_gate()


# --- Then --------------------------------------------------------------------


@then("the gate resolves the entry-point wiring and clears the dispatched seam")
def then_entry_point_cleared(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.then_entry_point_seam_cleared()


@then(
    "the gate flags the uncalled namesake and clears the called namesake by module identity"
)
def then_namesakes_distinguished(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.then_dormant_namesake_flagged_wired_namesake_cleared()


@then("the gate names the uncalled namesake in its loud warning")
def then_uncalled_namesake_named(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.then_dormant_namesake_named_in_warning()


@then("the gate still names the unregistered seam in its loud warning")
def then_unregistered_still_warns(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.then_unregistered_seam_still_warns()


@then("the binding-resolving gate exits with code zero")
def then_binding_resolving_exits_zero(
    precision_composition: DormantSeamPrecisionComposition,
) -> None:
    precision_composition.then_exits_zero()
