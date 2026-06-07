"""Tier A step definitions — the M2 technical-call-smell gate (slice-08).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.technical_call_smell.detect`` via the production
``PythonAstAdapter``, reached through the ``TechnicalCallSmellGate`` composition
service. Step bodies delegate to the service and assert against port-exposed
observables (the ``TechnicalCallOutcome`` enum, the named offending step +
technical callee); no business logic is inlined (Mandate-12 criterion 3).

Layer ~2 (in-memory pure-AST query, in-process) → example-based, no PBT
machinery (Mandate 9 v2: the only driven dependency is the in-memory Python AST
adapter, so the OR-reduction keeps it example-based here — the golden-fixture
corpus is finite and enumerable, not an unbounded domain). The "left untouched"
Then uses ``assert_state_delta`` over the inspected file's content (Mandate 8:
the universe is the port-observable file bytes, never an internal rule field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess — the gate practises the honesty the suite enforces.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_ASSERTION_CALLEE,
    EXPECTED_ASSERTION_STEP,
    EXPECTED_DB_CALL_STEP,
    EXPECTED_DB_CALLEE,
    EXPECTED_HTTP_CALL_STEP,
    EXPECTED_HTTP_CALLEE,
    TechnicalCallBreachKind,
    TechnicalCallCorpusKind,
    TechnicalCallOutcome,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.technical_call_smell_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../technical-call-smell-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the technical-call-smell gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the technical-call-smell gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output is
    # staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate judges a step suite whose bodies issue an HTTP call and a DB call")
def when_judge_technical_calls(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = TechnicalCallCorpusKind.TECHNICAL_CALLS
    run_state["snapshot_bytes"] = gate.path_for(
        TechnicalCallCorpusKind.TECHNICAL_CALLS
    ).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(TechnicalCallCorpusKind.TECHNICAL_CALLS)


@when("the gate judges a step suite whose assertion is driven by an HTTP call")
def when_judge_technical_assertion(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(TechnicalCallCorpusKind.TECHNICAL_ASSERTION)


@when("the gate judges a step suite that always delegates to domain services")
def when_judge_clean_domain(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(TechnicalCallCorpusKind.CLEAN_DOMAIN)


# --- Then ------------------------------------------------------------------


@then("the technical-call-smell gate rules the suite flagged")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is TechnicalCallOutcome.FLAGGED


@then("the gate names each offending step and the technical call it issues")
def then_names_both_breaches(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.callee, v.kind) for v in violations}
    breach = TechnicalCallBreachKind.TECHNICAL_CALL_IN_STEP_BODY.value
    assert (str(EXPECTED_HTTP_CALL_STEP), str(EXPECTED_HTTP_CALLEE), breach) in named
    assert (str(EXPECTED_DB_CALL_STEP), str(EXPECTED_DB_CALLEE), breach) in named


@then("the gate names the asserting step and the technical call it issues")
def then_names_assertion_breach(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.callee, v.kind) for v in violations}
    assert (
        str(EXPECTED_ASSERTION_STEP),
        str(EXPECTED_ASSERTION_CALLEE),
        TechnicalCallBreachKind.TECHNICAL_CALL_IN_STEP_BODY.value,
    ) in named


@then("the judged step suite file is left untouched")
def then_file_untouched(run_state):
    # Mandate 8: the universe is the port-observable file bytes of the inspected
    # corpus. The gate is a pure-function read; the source must be untouched.
    path = run_state["gate"].path_for(run_state["corpus"])
    after_bytes = path.read_text(encoding="utf-8")
    assert_state_delta(
        before={"corpus.source_bytes": run_state["snapshot_bytes"]},
        after={"corpus.source_bytes": after_bytes},
        universe={"corpus.source_bytes"},
        expected={"corpus.source_bytes": unchanged()},
    )


@then("the technical-call-smell gate rules the suite clean")
def then_clean(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is TechnicalCallOutcome.CLEAN


@then("the gate raises no objection to the clean domain-delegating step suite")
def then_no_false_positive(run_state):
    # Precision half / learning-hypothesis guard: the clean corpus carries the
    # near-miss traps (a ``.place``/``.judge`` domain method; a ``.status``
    # domain-outcome attribute read). The breach is a denylisted TECHNICAL callee,
    # not a domain method that happens to resemble one; so the gate must report
    # zero violations on the clean corpus.
    assert run_state["verdict"].violations == ()
