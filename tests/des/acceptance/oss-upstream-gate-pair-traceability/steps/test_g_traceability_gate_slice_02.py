"""pytest-bdd binding for the traceability-gate report-quality slice (slice-02).

Driving port: the production ``handle_subagent_stop`` SubagentStop hook over its
real JSON stdin protocol as a subprocess (Mandate-13 driving-port-only, Layer 3/4
wiring_e2e) -- identical surface to slice-01. Step bodies delegate to the
slice-02 composition root (``composition_slice_02.py``, a subclass of the
slice-01 ``TraceabilityGateComposition`` that REUSES every given_/when_ method
and adds only the two slice-02 Then-assertions). No production gate module is
imported-and-called at the step boundary; no business logic lives in a step body
(Mandate-12).

STEP-REGISTRY SCOPE (S1 step-text uniqueness): pytest-bdd resolves step
decorators per binding-module via this file's ``scenarios(...)`` call. This module
owns its own step registry; the ``Given``/``When`` literals it re-binds to the
slice-02 composition do NOT collide with the slice-01 module's identically-worded
steps (each ``test_g_*.py`` module is an independent step namespace). The two
slice-02 ``Then`` literals are NEW and unique. Verified empirically by the
mandatory --co collection proof: BOTH slice-01's 3 scenarios and slice-02's 2
scenarios collect EXIT=0 under the canonical --strict-markers addopts.

PILLAR-2 chained narrative: the slice-02 ``Given`` IS the slice-01 ``Given`` (same
step method, same wording -> same composition behaviour) and the ``When`` IS the
slice-01 ``When``; only the ``Then`` tightens to the report/ledger outcomes. The
reuse is by step-method inheritance, not copy-pasted fixtures.

RED scaffold: until DELIVER (slice-02) tightens the warning to resolve
ID->summary and adds the ``append_gate_event`` call, the two Then-steps fail with
a semantic ``AssertionError`` (summary absent / no DecisionTableTraceabilityWarned
record) -- never a collection / import / setup error (pre-DELIVER
fail-for-right-reason gate).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import TraceabilityReportComposition


# Relative-string binding -- IDENTICAL pattern to slice-01 (proven to route the
# scenario @tags through pytest-bdd's strict-markers-safe dynamic-mark pipeline).
scenarios("../g-traceability-gate-slice-02.feature")


@pytest.fixture
def composition() -> TraceabilityReportComposition:
    return TraceabilityReportComposition()


# --- Given (REUSED slice-01 vocabulary, re-bound to slice-02 composition) -----


@given("a feature whose decision-table declares a clause with no witnessing test")
def given_clause_with_no_witnessing_test(
    composition: TraceabilityReportComposition,
) -> None:
    composition.given_clause_with_no_witnessing_test()


# --- When (REUSED slice-01 vocabulary) ---------------------------------------


@when("the acceptance designer returns and the DISTILL-exit gate evaluates the feature")
def when_distill_exit_gate_evaluates(
    composition: TraceabilityReportComposition,
) -> None:
    composition.when_distill_exit_gate_evaluates()


# --- Then (NEW slice-02 outcomes) --------------------------------------------


@then("the warning names the unwitnessed clause together with its summary on one line")
def then_warning_resolves_clause_to_summary(
    composition: TraceabilityReportComposition,
) -> None:
    composition.then_warning_resolves_clause_to_summary()


@then("the audit ledger records the traceability warning verdict for the feature")
def then_ledger_records_traceability_verdict(
    composition: TraceabilityReportComposition,
) -> None:
    composition.then_ledger_records_traceability_verdict()


# Reuse the slice-01 non-halting outcome step (DT-10 scenario asserts proceed too,
# Pillar-2: the warn+allow surface carries through). Re-bound here to slice-02
# composition (inherited method) so this module's registry is self-contained.
@then("the gate lets the feature proceed to DELIVER")
def then_lets_feature_proceed(composition: TraceabilityReportComposition) -> None:
    composition.then_lets_feature_proceed()
