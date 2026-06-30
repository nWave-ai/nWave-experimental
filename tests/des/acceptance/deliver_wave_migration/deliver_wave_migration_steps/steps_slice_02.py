"""Slice-02 divergence / bump / INDETERMINATE / seam step bindings (Mandate-12 c3).

Every step body is ≤2 statements and delegates to `composition` — zero inline
business logic, zero control flow. The shared `@when` + `@then PASS`/`zero-failing`
live in `steps_common` (SSOT, S1); this module declares the slice-02 Given
bindings plus the slice-specific INDETERMINATE `@then` assertions (AT-6 guardrail).
Each decorator literal is unique within this feature directory (S1) and disjoint
from slices 01/03.
"""

from __future__ import annotations

from pytest_bdd import given, then

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import DeadMechanism, PresenceClause, Verdict


# --- Given (slice-02 presence preconditions) ------------------------------


@given(
    "the real shipped DELIVER command that the undeclared-public-symbol rule "
    "lives in exists"
)
def given_surface_undeclared_symbol(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.UNDECLARED_PUBLIC_SYMBOL_REDO
    )


@given(
    "a clause asserting an undeclared or missing public symbol fails the gate and "
    "is routed to redo in-wave"
)
def given_clause_undeclared_symbol(composition) -> None:
    composition.author_presence_manifest(PresenceClause.UNDECLARED_PUBLIC_SYMBOL_REDO)


@given(
    "the real shipped DELIVER command that the design-defect bump rule lives in exists"
)
def given_surface_design_defect_bump(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.DESIGN_DEFECT_BUMP)


@given(
    "a clause asserting a named contract self-contradiction bumps to DESIGN that "
    "the human disposes"
)
def given_clause_design_defect_bump(composition) -> None:
    composition.author_presence_manifest(PresenceClause.DESIGN_DEFECT_BUMP)


@given(
    "the real shipped DELIVER command that the matches-design degrade-LOUD rule "
    "lives in exists"
)
def given_surface_indeterminate_loud(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.MATCHES_DESIGN_INDETERMINATE_LOUD
    )


@given(
    "a clause asserting the matches-design mechanism that cannot run degrades "
    "LOUD as INDETERMINATE"
)
def given_clause_indeterminate_loud_presence(composition) -> None:
    composition.author_presence_manifest(
        PresenceClause.MATCHES_DESIGN_INDETERMINATE_LOUD
    )


@given(
    "a clause asserting the matches-design seam against a surface the mechanism "
    "cannot read"
)
def given_clause_indeterminate_unreadable(composition) -> None:
    composition.author_dead_mechanism_manifest(
        PresenceClause.MATCHES_DESIGN_INDETERMINATE_LOUD, DeadMechanism.ASSET_ABSENT
    )


@given(
    "the real shipped FP-crafter agent that the language-agnostic AST seam rule "
    "lives in exists"
)
def given_surface_language_agnostic_seam(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.LANGUAGE_AGNOSTIC_AST_SEAM
    )


@given(
    "a clause asserting the public-surface inspection is resolved behind a "
    "per-language AST port"
)
def given_clause_language_agnostic_seam(composition) -> None:
    composition.author_presence_manifest(PresenceClause.LANGUAGE_AGNOSTIC_AST_SEAM)


# --- Then (slice-02 INDETERMINATE guardrail — AT-6) -----------------------


@then(
    "the gate verdict is INDETERMINATE with exit code 4 because the mechanism "
    "could not run"
)
def then_verdict_indeterminate(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(
                composition.expected_exit(Verdict.INDETERMINATE)
            )
        },
    )


@then("the verdict refuses to certify what it cannot read")
def then_verdict_refuses_to_certify(composition) -> None:
    assert "INDETERMINATE" in composition.outcome.stdout
