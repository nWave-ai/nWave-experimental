"""Tier A step definitions — the M8 universe-bound-assertion gate (slice-03).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.assert_state_delta.detect`` via the production
``PythonAstAdapter``, reached through the ``UniverseBoundAssertionGate``
composition service. Step bodies delegate to the service and assert against
port-exposed observables (the ``GuardOutcome`` enum, the named offending test +
breach kind + leaked private field); no business logic is inlined (Mandate-12
criterion 3).

Layer ~2 (in-memory pure-AST query, in-process) → example-based, no PBT
machinery (Mandate 9 v2: the only driven dependency is the in-memory Python AST
adapter, so the OR-reduction keeps it example-based here — the golden-fixture
corpus is finite and enumerable, not an unbounded domain). The "left unchanged"
Then uses ``assert_state_delta`` over the inspected file's content (Mandate 8:
the universe is the port-observable file bytes, never an internal rule field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_LEAKED_PRIVATE_FIELD,
    EXPECTED_LEAKING_TEST,
    EXPECTED_UNGUARDED_TEST,
    BreachKind,
    GuardCorpusKind,
    GuardOutcome,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.universe_bound_assertion_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../universe-bound-assertion-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the universe-bound-assertion gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the universe-bound-assertion gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output
    # is staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate inspects a state-mutating test that never calls the universe guard")
def when_inspect_missing_guard(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = GuardCorpusKind.MISSING_GUARD
    run_state["snapshot_bytes"] = gate.path_for(
        GuardCorpusKind.MISSING_GUARD
    ).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(GuardCorpusKind.MISSING_GUARD)


@when("the gate inspects a state-mutating test whose universe names a private field")
def when_inspect_private_leak(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = GuardCorpusKind.PRIVATE_LEAK
    run_state["verdict"] = gate.inspect(GuardCorpusKind.PRIVATE_LEAK)


@when("the gate inspects a suite that guards every mutation over port-observable names")
def when_inspect_clean(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = GuardCorpusKind.CLEAN
    run_state["verdict"] = gate.inspect(GuardCorpusKind.CLEAN)


# --- Then ------------------------------------------------------------------


@then("the universe-guard gate reports the suite as flagged")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is GuardOutcome.FLAGGED


@then("the gate names the unguarded test as a missing-guard breach")
def then_names_missing_guard(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.kind) for v in violations}
    assert (
        str(EXPECTED_UNGUARDED_TEST),
        BreachKind.MISSING_ASSERT.value,
    ) in named


@then("the inspected test suite is left unchanged")
def then_suite_unchanged(run_state):
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


@then("the gate names the test and the private field leaked into the universe")
def then_names_private_leak(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.kind, v.detail) for v in violations}
    assert (
        str(EXPECTED_LEAKING_TEST),
        BreachKind.PRIVATE_UNIVERSE_LEAK.value,
        EXPECTED_LEAKED_PRIVATE_FIELD,
    ) in named


@then("the universe-guard gate reports the suite as clean")
def then_clean(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is GuardOutcome.CLEAN


@then("the gate raises no objection to a read-only test that carries no guard")
def then_no_false_positive(run_state):
    # Precision half: the clean corpus carries a state-mutating test that guards
    # correctly over port-observable names AND a read-only (unmarked) test with no
    # guard. Neither is a breach — a query test needs no universe guard — so the
    # gate must report zero violations.
    assert run_state["verdict"].violations == ()
