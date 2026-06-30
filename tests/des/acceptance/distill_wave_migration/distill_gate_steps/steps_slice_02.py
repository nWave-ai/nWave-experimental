"""Slice-02 gate-OUT coherence step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition` — zero inline
business logic, zero control flow. Verdict/exit assertions go through
`assert_state_delta` over the port-exposed universe (Mandate 8). Each decorator
literal is unique within this feature directory (S1) and disjoint from slice-01
(slice-01 says "failing induction clauses"; slice-02 says "failing coherence
clauses" — distinct Then-literals).
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import PresenceClause, Verdict


# --- Given ----------------------------------------------------------------


@given("the real shipped DISTILL skill that carries the DEVOPS-induction rule exists")
def given_surface_devops(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.DEVOPS_INDUCED_FIRST_CLASS
    )


@given(
    "a clause asserting DEVOPS-induced scenarios are first-class and trace to "
    "the DEVOPS status"
)
def given_clause_devops(composition) -> None:
    composition.author_presence_manifest(PresenceClause.DEVOPS_INDUCED_FIRST_CLASS)


@given("the real shipped DISTILL skill that carries the no-coupling rule exists")
def given_surface_no_coupling(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.NO_COUPLING_UNVERIFIED)


@given(
    "a clause asserting a port-shaped surface not yet on the contract is "
    "UNVERIFIED never a silent pass"
)
def given_clause_no_coupling(composition) -> None:
    composition.author_presence_manifest(PresenceClause.NO_COUPLING_UNVERIFIED)


@given("the real shipped DISTILL skill that carries the gate-G coherence rubric exists")
def given_surface_gate_g(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.GATE_G_REVIEW_RUBRIC)


@given(
    "a clause asserting the gate-G review-rubric witnesses design to AT "
    "coherence at gate-OUT"
)
def given_clause_gate_g(composition) -> None:
    composition.author_presence_manifest(PresenceClause.GATE_G_REVIEW_RUBRIC)


@given("the real shipped DISTILL skill that carries the degrade-loud rule exists")
def given_surface_degrade_loud(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.INDETERMINATE_DEGRADE_LOUD
    )


@given(
    "a clause asserting an unrunnable coherence mechanism is INDETERMINATE "
    "never a false green"
)
def given_clause_degrade_loud(composition) -> None:
    composition.author_presence_manifest(PresenceClause.INDETERMINATE_DEGRADE_LOUD)


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


@then("the verdict reports zero failing coherence clauses")
def then_zero_failing_coherence_clauses(composition) -> None:
    assert "0 failing" in composition.outcome.stdout
