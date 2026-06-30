"""Slice-02 gate-OUT / skip / security step bindings (Mandate-12 c3: thin delegation).

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


@given("the real shipped DEVOPS agent that the explicit N/A skip rule lives in exists")
def given_surface_na_skip(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.EXPLICIT_NA_SKIP)


@given(
    "a clause asserting a no-delta feature records an explicit N/A skip the "
    "advisory notifies without blocking"
)
def given_clause_na_skip(composition) -> None:
    composition.author_presence_manifest(PresenceClause.EXPLICIT_NA_SKIP)


@given(
    "the real shipped DEVOPS agent that the un-instrumentable KPI rule lives in exists"
)
def given_surface_uninstrumentable(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.UNINSTRUMENTABLE_KPI_REDO
    )


@given(
    "a clause asserting an un-instrumentable KPI fails the gate and is routed "
    "to redo in-wave"
)
def given_clause_uninstrumentable(composition) -> None:
    composition.author_presence_manifest(PresenceClause.UNINSTRUMENTABLE_KPI_REDO)


@given(
    "the real shipped observability skill that the security-gate seam rule "
    "lives in exists"
)
def given_surface_security_seam(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.SECURITY_SEAM_DEGRADE_LOUD
    )


@given(
    "a clause asserting the security gate resolves the toolchain behind a "
    "per-language port and degrades loud"
)
def given_clause_security_seam(composition) -> None:
    composition.author_presence_manifest(PresenceClause.SECURITY_SEAM_DEGRADE_LOUD)


@given(
    "a clause asserting the security-gate seam against a surface the mechanism "
    "cannot read"
)
def given_clause_security_seam_unreadable(composition) -> None:
    composition.author_dead_mechanism_manifest(
        PresenceClause.SECURITY_SEAM_DEGRADE_LOUD, DeadMechanism.ASSET_ABSENT
    )


@given("the real shipped DEVOPS agent that the Tier-B advisory wording lives in exists")
def given_surface_tier_b_advisory(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.TIER_B_ADVISORY_WORDING)


@given(
    "a clause asserting the Tier-B advisory literal notice names the skip and "
    "proposes nw-devops and proceeds"
)
def given_clause_tier_b_advisory(composition) -> None:
    composition.author_presence_manifest(PresenceClause.TIER_B_ADVISORY_WORDING)


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
