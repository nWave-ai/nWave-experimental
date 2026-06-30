"""Slice-03 removal + non-regression step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition` — zero inline
business logic, zero control flow. Verdict/exit assertions go through
`assert_state_delta` over the port-exposed universe (Mandate 8). Each decorator
literal is unique within this feature directory (S1) and disjoint from slices
01/02 (distinct Then-literals that name the absence / floor reason). The shared
`@when` lives in `steps_common` (SSOT, S1).

Two witnesses, one real gate port:
  • ABSENCE (ac-8-absence): registers the LEGACY AT-satisfaction-only marker; the
    gate FAILs when the marker is absent. Absence is the goal → the AT asserts
    FAIL. Present today → the gate PASSes → the AT (expecting FAIL) is ACTIVE-RED.
  • NON-REGRESSION (ac-8-non-regression): asserts the matches-design leg STAYS
    present (gate PASS). A floor-preservation guard — ABSENT today (migration not
    run) → gate FAIL → expects PASS → ACTIVE-RED; green when the same DELIVER
    migration lands (C9 non-regression).
"""

from __future__ import annotations

from pytest_bdd import given, then

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import FloorClause, LegacyClause, Verdict


# --- Given ----------------------------------------------------------------


@given(
    "the real shipped crafter agent that the legacy AT-satisfaction-only prose is "
    "reconciled in exists"
)
def given_surface_legacy(composition) -> None:
    composition.require_legacy_surface_present(LegacyClause.AT_SATISFACTION_ONLY)


@given("a clause registering the legacy AT-satisfaction-only marker")
def given_clause_legacy(composition) -> None:
    composition.author_legacy_absence_manifest(LegacyClause.AT_SATISFACTION_ONLY)


@given(
    "the real shipped DELIVER command that the matches-design leg floor lives in exists"
)
def given_surface_floor(composition) -> None:
    composition.require_floor_surface_present(FloorClause.MATCHES_DESIGN_PRESERVED)


@given("a clause asserting the matches-design leg is preserved")
def given_clause_floor(composition) -> None:
    composition.author_floor_manifest(FloorClause.MATCHES_DESIGN_PRESERVED)


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


@then("the verdict names the legacy AT-satisfaction-only clause")
def then_verdict_names_legacy_clause(composition) -> None:
    assert composition.verdict_names_clause(LegacyClause.AT_SATISFACTION_ONLY.value)


@then(
    "the gate verdict is PASS with exit code 0 because the matches-design leg is "
    "preserved"
)
def then_verdict_pass_floor_preserved(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.PASS))},
    )
