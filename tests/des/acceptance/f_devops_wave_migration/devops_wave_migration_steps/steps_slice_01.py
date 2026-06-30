"""Slice-01 walking-skeleton step bindings (Mandate-12 c3: thin delegation).

Every step body is ≤2 statements and delegates to `composition`
(DevopsWaveMigrationComposition) — zero inline business logic, zero control flow.
The shared `@when` + `@then PASS`/`zero-failing` live in `steps_common` (SSOT,
S1); this module declares only the slice-01 Given bindings. Each decorator
literal is unique within this feature directory (S1).
"""

from __future__ import annotations

from pytest_bdd import given

from .domain_types import PresenceClause


# --- Given (slice-01 presence preconditions) ------------------------------


@given("the real shipped DEVOPS agent that the gate-IN consume rule lives in exists")
def given_surface_gate_in_consume(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.GATE_IN_CONSUME)


@given(
    "a clause asserting the gate-IN consumes the design pass and the outcome "
    "KPIs applicability-first"
)
def given_clause_gate_in_consume(composition) -> None:
    composition.author_presence_manifest(PresenceClause.GATE_IN_CONSUME)


@given("the real shipped DEVOPS agent that the KPI to telemetry map lives in exists")
def given_surface_kpi_telemetry(composition) -> None:
    composition.require_shipped_surface_present(PresenceClause.KPI_TELEMETRY_MAP)


@given("a clause asserting every outcome KPI maps to a concrete telemetry signal")
def given_clause_kpi_telemetry(composition) -> None:
    composition.author_presence_manifest(PresenceClause.KPI_TELEMETRY_MAP)


@given(
    "the real shipped observability skill that the second-way observability "
    "rule lives in exists"
)
def given_surface_observability(composition) -> None:
    composition.require_shipped_surface_present(
        PresenceClause.OBSERVABILITY_AROUND_KPIS
    )


@given(
    "a clause asserting second-way observability is designed around the "
    "outcome-KPI signals not generic"
)
def given_clause_observability(composition) -> None:
    composition.author_presence_manifest(PresenceClause.OBSERVABILITY_AROUND_KPIS)
