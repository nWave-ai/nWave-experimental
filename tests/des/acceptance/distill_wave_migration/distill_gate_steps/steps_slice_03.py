"""Slice-03 removal + non-regression step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition` — zero inline
business logic, zero control flow. Verdict/exit assertions go through
`assert_state_delta` over the port-exposed universe (Mandate 8). Each decorator
literal is unique within this feature directory (S1) and disjoint from
slices 01/02 (distinct Then-literals that name the absence / floor reason).

Two witnesses, one real gate port:
  • ABSENCE (ac-9-absence): registers the LEGACY marker; the gate FAILs when the
    marker is absent. Absence is the goal → the AT asserts FAIL. Present today →
    the gate PASSes → the AT (expecting FAIL) is ACTIVE-RED.
  • NON-REGRESSION (ac-9-non-regression): asserts the keystone-reconciled
    DESIGN-absent advisory floor STAYS present (gate PASS). A floor-preservation
    guard — green now, must remain green across the migration (C7/G-4).
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import FloorClause, LegacyClause, Verdict


# --- Given ----------------------------------------------------------------


@given("the real shipped DISTILL skill that the legacy prose is removed from exists")
def given_surface_legacy(composition) -> None:
    composition.require_legacy_surface_present(LegacyClause.NON_INDUCING_AT_AUTHORING)


@given("a clause registering the legacy non-inducing AT-authoring marker")
def given_clause_legacy(composition) -> None:
    composition.author_legacy_absence_manifest(LegacyClause.NON_INDUCING_AT_AUTHORING)


@given("the real shipped DISTILL skill that carries the keystone advisory floor exists")
def given_surface_floor(composition) -> None:
    composition.require_floor_surface_present(FloorClause.DESIGN_ABSENT_ADVISORY)


@given("a clause asserting the DESIGN-absent advisory floor wording is preserved")
def given_clause_floor(composition) -> None:
    composition.author_floor_manifest(FloorClause.DESIGN_ABSENT_ADVISORY)


# --- When -----------------------------------------------------------------


@when("the maintainer runs the skill-normative gate through the des dispatcher")
def when_run_gate_via_dispatcher(composition, state) -> None:
    state["before"] = snapshot(None)
    composition.run_gate_via_dispatcher()


# --- Then -----------------------------------------------------------------


@then("the gate verdict is FAIL with exit code 1 because the legacy marker is absent")
def then_verdict_fail_legacy_absent(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.FAIL))},
    )


@then("the verdict names the legacy non-inducing clause")
def then_verdict_names_legacy_clause(composition) -> None:
    assert composition.verdict_names_clause(
        LegacyClause.NON_INDUCING_AT_AUTHORING.value
    )


@then(
    "the gate verdict is PASS with exit code 0 because the advisory floor is preserved"
)
def then_verdict_pass_floor_preserved(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.PASS))},
    )
