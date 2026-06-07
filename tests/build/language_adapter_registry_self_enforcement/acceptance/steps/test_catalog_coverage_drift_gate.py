"""Tier A step definitions — the catalog coverage-drift cross-check (slice-02).

CONTRACT_SHAPE: unbounded-preservation

language-adapter-registry-self-enforcement, slice-02 (DISTILL, per-slice JIT). The
catalog coverage-drift cross-check (C4): the catalog's hand-authored declared coverage
(``supported-languages`` + ``ports``) is cross-checked against the DISCOVERED plugins'
actual coverage (the registered plugins' ``target_language`` + covered-port set).
Hand-drift -> RED.

Driving port: the pure ``detect_catalog_coverage_drift`` entrypoint
(``des.testarch.rules.registry_conformance``), reached through the
``CatalogCoverageDriftService`` composition. Step bodies delegate to the service and
assert against port-exposed observables (the ``CoverageDriftOutcome`` enum, the named
drifted language); no business logic is inlined (Mandate-12 criterion 3).

Recall/precision golden-fixture shape (mirroring slice-01):

  * RECALL scenario — drives the cross-check against the FROZEN declared-over-discovered
    snapshot (which permanently carries a declared-but-undiscovered language). Asserts
    FLAGGED + the named planted drifted language. Green forever once the cross-check
    exists.
  * PRECISION (frozen) scenario — drives the cross-check against the FROZEN matched-
    coverage snapshot. Asserts CONFORMANT — the fail-closed precision bar.
  * PRECISION-LIVE scenario — drives the cross-check against the real catalog YAML
    declared coverage vs a LIGHT live ``target_language`` discovery. At HEAD the catalog
    over-declares (python/typescript/go vs the single inert registered fixture), so the
    cross-check MUST report FLAGGED. THIS is the scenario that flips RED->GREEN exactly
    when A_GREEN implements C4 (reverting C4 re-REDs it).

Layer ~2 (in-memory introspection of the testarch substrate + a light registry read,
in-process) -> example-based, no PBT machinery (Mandate 9 v2: a finite enumerable
declared-vs-discovered set cross-check, not an unbounded generated domain). The cross-
check reads are pure-function queries that mutate no state — the verdict is the port-
exposed observable, so the Then steps assert directly on it (no ``assert_state_delta``
universe to declare; nothing is mutated — Mandate-8 layer-1-3 universe-guard applies to
STATE-MUTATING steps only).

RED-for-right-reason (ADR-025 / Mandate-7): each When step drives the production
``detect_catalog_coverage_drift`` function, a RED scaffold raising ``AssertionError``
until A_GREEN implements it. All three scenarios RED now; the recall + frozen-precision
scenarios go GREEN when the cross-check is implemented; the precision-live scenario goes
GREEN at the same time (the real catalog genuinely over-declares against the discovered
plugins). The failures are semantic ``AssertionError`` from the missing cross-check body
— NOT collection / import / skip errors.

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from des.testarch.rules.registry_conformance import PORT_OUTSIDE_CATALOG_BREACH
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.coverage_drift.declared_over_discovered_snapshot import (
    PLANTED_DRIFTED_LANGUAGE,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.coverage_drift.port_outside_catalog_snapshot import (
    PLANTED_OUT_OF_CATALOG_PORT,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.coverage_drift_composition import (
    build_service,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.coverage_drift_domain_types import (
    CoverageDriftOutcome,
)


scenarios("../catalog-coverage-drift-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def service():
    """Production composition root for the catalog coverage-drift cross-check."""
    return build_service()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for the coverage-drift verdict across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the catalog coverage-drift cross-check")
def given_the_cross_check(service, run_state):
    # Precondition only — the coverage-drift service is the SUT entry. No expected
    # output is staged here (no Fixture Theater).
    run_state["service"] = service


# --- When ------------------------------------------------------------------


@when(
    "the maintainer checks the frozen snapshot where the catalog over-declares a language"
)
def when_check_declared_over_discovered_snapshot(run_state):
    run_state["verdict"] = run_state[
        "service"
    ].drift_of_declared_over_discovered_snapshot()


@when(
    "the maintainer checks the frozen snapshot where declared coverage matches discovered coverage"
)
def when_check_matched_coverage_snapshot(run_state):
    run_state["verdict"] = run_state["service"].drift_of_matched_coverage_snapshot()


@when(
    "the maintainer checks the frozen snapshot where a discovered port falls outside the catalog"
)
def when_check_port_outside_catalog_snapshot(run_state):
    run_state["verdict"] = run_state["service"].drift_of_port_outside_catalog_snapshot()


@when("the maintainer checks the real catalog against the discovered plugins")
def when_check_live_catalog(run_state):
    run_state["verdict"] = run_state["service"].drift_of_live_catalog()


# --- Then (recall) ---------------------------------------------------------


@then("the cross-check flags a coverage drift in the snapshot")
def then_flags_drift_in_snapshot(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is CoverageDriftOutcome.FLAGGED


@then("the cross-check names the declared language the registry does not provide")
def then_names_drifted_language(run_state):
    named = {violation.detail for violation in run_state["verdict"].violations}
    assert PLANTED_DRIFTED_LANGUAGE in named


@then("the cross-check names the discovered port that falls outside the catalog")
def then_names_out_of_catalog_port(run_state):
    named_port_breaches = {
        violation.detail
        for violation in run_state["verdict"].violations
        if violation.kind == PORT_OUTSIDE_CATALOG_BREACH
    }
    assert PLANTED_OUT_OF_CATALOG_PORT in named_port_breaches


# --- Then (precision) ------------------------------------------------------


@then(
    "the cross-check reports the catalog coverage as matching the discovered coverage"
)
def then_conformant(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is CoverageDriftOutcome.CONFORMANT


# --- Then (precision-live) -------------------------------------------------


@then("the cross-check flags a coverage drift in the real catalog")
def then_flags_drift_in_live_catalog(run_state):
    outcome = run_state["service"].outcome_of(run_state["verdict"])
    assert outcome is CoverageDriftOutcome.FLAGGED
