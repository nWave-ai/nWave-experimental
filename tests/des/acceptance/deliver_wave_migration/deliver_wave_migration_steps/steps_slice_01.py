"""Slice-01 walking-skeleton step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition`
(DeliverWaveMigrationComposition) — zero inline business logic, zero control flow.
The shared `@when` + `@then PASS`/`zero-failing` live in `steps_common` (SSOT,
S1); this module declares only the slice-01 Given bindings. Each decorator
literal is unique within this feature directory (S1).
"""

from __future__ import annotations

from pytest_bdd import given

from .domain_types import PresenceClause


# --- Given (slice-01 presence preconditions) ------------------------------


@given("the real shipped crafter agent that the bundle-consume rule lives in exists")
def given_surface_bundle_consume(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.BUNDLE_CONSUME_IMPLEMENT_MATCHING
    )


@given(
    "a clause asserting the crafter consumes the bundle and implements matching "
    "the declared structure"
)
def given_clause_bundle_consume(composition) -> None:
    composition.author_presence_manifest(
        PresenceClause.BUNDLE_CONSUME_IMPLEMENT_MATCHING
    )


@given(
    "the real shipped DELIVER command that the matches-design public-surface rule "
    "lives in exists"
)
def given_surface_matches_design(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.MATCHES_DESIGN_PUBLIC_SURFACE
    )


@given(
    "a clause asserting the matches-design gate compares the public surface "
    "against the declared contract"
)
def given_clause_matches_design(composition) -> None:
    composition.author_presence_manifest(PresenceClause.MATCHES_DESIGN_PUBLIC_SURFACE)


@given(
    "the real shipped crafter skill that the private-refactor-freedom rule lives "
    "in exists"
)
def given_surface_private_freedom(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.PRIVATE_REFACTOR_FREEDOM)


@given(
    "a clause asserting a new private symbol or Extract-Method below the public "
    "boundary is never flagged"
)
def given_clause_private_freedom(composition) -> None:
    composition.author_presence_manifest(PresenceClause.PRIVATE_REFACTOR_FREEDOM)
