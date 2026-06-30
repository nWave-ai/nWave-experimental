"""Slice-01 walking-skeleton step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition`
(DistillWaveMigrationComposition) — zero inline business logic, zero control flow.
The verdict/exit assertions go through `assert_state_delta` over the port-exposed
universe (Mandate 8). Each decorator literal is unique within this feature
directory (S1).
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import PresenceClause, Verdict


# --- Given ----------------------------------------------------------------


@given(
    "the real shipped DISTILL skill that DISTILL consumes the design contract from exists"
)
def given_surface_induction_map(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.INDUCTION_MAP)


@given(
    "a clause asserting the DISTILL skill declares ATs are induced from the design contract"
)
def given_clause_induction_map(composition) -> None:
    composition.author_presence_manifest(PresenceClause.INDUCTION_MAP)


@given(
    "the real shipped DISTILL skill that carries the example-table correspondence exists"
)
def given_surface_example_table(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.EXAMPLE_TABLE_BIJECTION)


@given("a clause asserting every example-table row maps to exactly one scenario")
def given_clause_example_table(composition) -> None:
    composition.author_presence_manifest(PresenceClause.EXAMPLE_TABLE_BIJECTION)


@given(
    "the real shipped DISTILL skill that carries the contract-shape treatment exists"
)
def given_surface_contract_shape(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.CONTRACT_SHAPE_TREATMENT)


@given(
    "a clause asserting a declared law induces a property test and an "
    "error-encoding a sad path"
)
def given_clause_contract_shape(composition) -> None:
    composition.author_presence_manifest(PresenceClause.CONTRACT_SHAPE_TREATMENT)


@given(
    "the real shipped DISTILL skill that carries the slice-plan scaffolding rule exists"
)
def given_surface_slice_plan(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.SLICE_PLAN_ACTIVE_RED)


@given("a clause asserting ATs are scaffolded per-slice active-RED never skipped")
def given_clause_slice_plan(composition) -> None:
    composition.author_presence_manifest(PresenceClause.SLICE_PLAN_ACTIVE_RED)


# --- When -----------------------------------------------------------------


@when("the maintainer runs the skill-normative gate through the des dispatcher")
def when_run_gate_via_dispatcher(composition, state) -> None:
    state["before"] = snapshot(None)
    composition.run_gate_via_dispatcher()


# --- Then -----------------------------------------------------------------


@then("the gate verdict is PASS with exit code 0")
def then_verdict_pass(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.PASS))},
    )


@then("the verdict reports zero failing induction clauses")
def then_zero_failing_clauses(composition) -> None:
    assert "0 failing" in composition.outcome.stdout
