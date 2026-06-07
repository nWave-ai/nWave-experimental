"""Step definitions: slice-01 — the agent-prose SLIM-crafter contract audit.

slice-01 of F-CRAFTER-SLIM-ATD-EXPERT (DDD-1 + DDD-7 walking-skeleton-first).

Three ATs, example-only at layer 3 (filesystem read against live project
assets — Mandate 9/11). Step bodies delegate to
``CrafterSurfaceAuditComposition``; no inline logic (Mandate-12 criterion 3).

RED contract (verified empirically before authoring — see
``docs/feature/fix-crafter-slim-atd-expert/distill/red-classification.md``):
  * AT-01a (OOP crafter): RED on master — 2 loophole hits at L48 + L106, 0
    escalation hits. Fail-for-right-reason: assertion fails because the
    contract is unmet (MISSING_FUNCTIONALITY).
  * AT-01b (FP crafter): PASS on master — regression guard. The FP-crafter
    surface is already-clean (L42 / L54 / L182 / L226 forbid test
    authoring). Documented as REGRESSION_GUARD in red-classification.md.
  * AT-01c (nw-execute classic template): RED on master — 1 loophole hit
    at L119, 0 escalation hits. Fail-for-right-reason: assertion fails
    because the loophole text is present and the escalation contract is
    missing (MISSING_FUNCTIONALITY).

DELIVER (slice-01 GREEN) makes the surface SLIM-compliant by:
  1. Removing the loophole prose from L48 + L106 of ``nw-software-crafter.md``
     and adding the AT_INSUFFICIENT_FOR_GREEN escalation contract.
  2. Rewriting ``nw-execute`` SKILL.md L110-119 per the DESIGN diff.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from .composition import AuditOutcome, CrafterSurfaceAuditComposition
from .domain_types import (
    SURFACE_BY_PHRASE,
    CrafterSurface,
    EscalationToken,
)


scenarios("../slice-01-agent-prose-slim-contract.feature")


import pytest


@pytest.fixture
def composition() -> CrafterSurfaceAuditComposition:
    """Production-wired SLIM-crafter-contract audit composition."""
    return CrafterSurfaceAuditComposition()


@pytest.fixture
def outcome_box() -> dict[str, AuditOutcome]:
    """Carrier for the audit outcome."""
    return {}


@pytest.fixture
def surface_box() -> dict[str, CrafterSurface]:
    """Carrier for the Given-set surface."""
    return {}


# --- Given -------------------------------------------------------------------


@given(parsers.parse("{surface_phrase}"))
def given_surface(
    surface_phrase: str,
    surface_box: dict[str, CrafterSurface],
) -> None:
    surface_box["surface"] = SURFACE_BY_PHRASE[surface_phrase]


# --- When --------------------------------------------------------------------


@when("the SLIM-crafter contract audit runs against that surface")
def when_audit_runs(
    composition: CrafterSurfaceAuditComposition,
    surface_box: dict[str, CrafterSurface],
    outcome_box: dict[str, AuditOutcome],
) -> None:
    outcome_box["outcome"] = composition.audit_surface(surface_box["surface"])


# --- Then --------------------------------------------------------------------


@then("no loophole phrase appears in the audited surface")
def then_no_loophole(outcome_box: dict[str, AuditOutcome]) -> None:
    outcome = outcome_box["outcome"]
    offending = {
        phrase.value: count
        for phrase, count in outcome.loophole_hits.items()
        if count > 0
    }
    assert offending == {}, (
        f"SLIM-crafter contract violated on surface "
        f"{outcome.surface.value} ({outcome.asset_path}) — "
        f"loophole phrases still present: {offending}. "
        "Expected zero hits for every loophole phrase. The DELIVER step "
        "for slice-01 must remove these phrases and replace them with the "
        "AT_INSUFFICIENT_FOR_GREEN escalation contract."
    )


@then("the AT_INSUFFICIENT_FOR_GREEN escalation token appears in the audited surface")
def then_escalation_token_present(outcome_box: dict[str, AuditOutcome]) -> None:
    outcome = outcome_box["outcome"]
    hits = outcome.escalation_hits[EscalationToken.AT_INSUFFICIENT_FOR_GREEN]
    assert hits >= 1, (
        f"SLIM-crafter contract violated on surface "
        f"{outcome.surface.value} ({outcome.asset_path}) — "
        f"AT_INSUFFICIENT_FOR_GREEN escalation token not found "
        f"(hits={hits}). The DELIVER step for slice-01 must add the "
        "escalation contract per ADR-031 §Decision."
    )


@then("the nw-acceptance-designer route token appears in the audited surface")
def then_route_token_present(outcome_box: dict[str, AuditOutcome]) -> None:
    outcome = outcome_box["outcome"]
    hits = outcome.escalation_hits[EscalationToken.ROUTE_NW_ACCEPTANCE_DESIGNER]
    assert hits >= 1, (
        f"SLIM-crafter contract violated on surface "
        f"{outcome.surface.value} ({outcome.asset_path}) — "
        f"nw-acceptance-designer route token not found "
        f"(hits={hits}). The escalation route MUST name the routing target."
    )
