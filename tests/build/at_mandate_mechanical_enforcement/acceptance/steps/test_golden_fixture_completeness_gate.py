"""Tier A step definitions — the Tier-M golden-fixture-completeness meta-gate.

CONTRACT_SHAPE: bounded-change (the meta-gate reports a bounded completeness
verdict per inspected gate; the inspected gate corpus is left untouched).

Provenance: feature `at-mandate-mechanical-enforcement`, slice-11 (re-shaped to
pytest-bdd after the carpaccio entry-gate required Gherkin scenarios tagged
@slice-11; a plain parametrized pytest provided no .feature and was rejected with
`no-scenarios-for-slice`). The meta-gate DOES carry a domain story — the
methodology-maintainer's Earned-Trust self-application contract — so Gherkin is
meaningful, not ceremony, and it matches the 9 sibling gate self-ATs.

Driving port: the meta-gate's own structural filesystem walk over the OTHER
gates' golden-fixture coverage, reached through the ``GoldenFixtureCompleteness
Gate`` composition service. Step bodies delegate to the service and assert
against the port-exposed observable (the ``GateCompletenessOutcome`` enum); no
business logic is inlined (Mandate-12 criterion 3). The structural-walk logic
lives in the composition service (SSOT), not here.

Layer ~2 (in-memory pure filesystem-presence query, in-process) → example-based,
no PBT machinery (Mandate 9 v2: the only driven dependency is the local
filesystem read of a finite enumerable gate corpus, not an unbounded domain).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess — no spawn, no AST, no git, no real I/O beyond reading
directory entries. The meta-gate practises the honesty it enforces.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    GateCompletenessOutcome,
    GateCorpusKind,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.golden_fixture_completeness_composition import (
    build_gate,
)


scenarios("../golden-fixture-completeness-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the golden-fixture-completeness meta-gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the golden-fixture-completeness meta-gate")
def given_the_meta_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output is
    # staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when(
    "the meta-gate judges a gate that ships a violation fixture but no clean "
    "near-miss and no self-AT"
)
def when_judge_incomplete(run_state):
    gates = run_state["gate"].enumerate_gates(GateCorpusKind.PLANTED_INCOMPLETE)
    run_state["inspected_gates"] = gates


@when(
    "the meta-gate judges a gate that ships a violation fixture, a clean "
    "near-miss, and a self-AT"
)
def when_judge_complete(run_state):
    gates = run_state["gate"].enumerate_gates(GateCorpusKind.PLANTED_COMPLETE)
    run_state["inspected_gates"] = gates


@when("the meta-gate judges every gate the feature has shipped")
def when_judge_all_shipped(run_state):
    gates = run_state["gate"].enumerate_gates(GateCorpusKind.REAL_SHIPPED)
    run_state["inspected_gates"] = gates


# --- Then ------------------------------------------------------------------


@then("the meta-gate rules that gate incomplete")
def then_incomplete(run_state):
    gate = run_state["gate"]
    outcomes = {gate.outcome_of(g) for g in run_state["inspected_gates"]}
    assert outcomes == {GateCompletenessOutcome.INCOMPLETE}, (
        "RECALL: the meta-gate must flag a gate missing part of its golden "
        f"triad as INCOMPLETE; got {outcomes}. A vacuous meta-gate that green-"
        "lights an uncovered gate defeats the D-E self-application contract."
    )


@then("the meta-gate rules that gate complete")
def then_complete(run_state):
    gate = run_state["gate"]
    outcomes = {gate.outcome_of(g) for g in run_state["inspected_gates"]}
    assert outcomes == {GateCompletenessOutcome.COMPLETE}, (
        "PRECISION: the meta-gate must clear a gate carrying its full golden "
        f"triad as COMPLETE; got {outcomes}. A meta-gate that false-positives "
        "on a well-formed gate is unusable."
    )


@then("the meta-gate rules every shipped gate complete")
def then_all_shipped_complete(run_state):
    gate = run_state["gate"]
    incomplete = [
        g.name
        for g in run_state["inspected_gates"]
        if gate.outcome_of(g) is not GateCompletenessOutcome.COMPLETE
    ]
    assert not incomplete, (
        "PRECISION (real corpus): every shipped Tier-S gate must carry its full "
        f"golden triad (>=1 violation_ fixture, >=1 clean_ fixture, a sibling "
        f"*-gate self-AT). Gates missing part of their triad: {incomplete}"
    )


@then("the meta-gate finds at least one shipped gate to judge")
def then_corpus_non_empty(run_state):
    # Guards against the precision arm silently judging ZERO gates (an empty
    # corpus makes the all-complete Then a vacuous green — the classic vacuous-
    # suite trap). Pure filesystem presence, independent of the RED scaffold.
    assert run_state["inspected_gates"], (
        "meta-gate enumerated ZERO shipped gates -- the fixtures tree moved or "
        "the walk broke; a precision arm over an empty corpus is a vacuous green."
    )
