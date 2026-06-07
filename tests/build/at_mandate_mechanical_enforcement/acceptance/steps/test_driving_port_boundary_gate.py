"""Tier A step definitions — the M1 driving-port-boundary gate (slice-01).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.driving_port_boundary.detect`` via the production
``PythonAstAdapter``, reached through the ``DrivingPortBoundaryGate``
composition service. Step bodies delegate to the service and assert against
port-exposed observables (the ``BoundaryOutcome`` enum, the named offending
function + module); no business logic is inlined (Mandate-12 criterion 3).

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
    EXPECTED_OFFENDING_FUNCTION,
    EXPECTED_OFFENDING_MODULE,
    BoundaryOutcome,
    CorpusKind,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.driving_port_boundary_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../driving-port-boundary-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the driving-port-boundary gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the driving-port-boundary gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output
    # is staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when(
    "the gate inspects a step suite that reaches for a driven adapter inside an action"
)
def when_inspect_violation(run_state):
    gate = run_state["gate"]
    run_state["before_content"] = CorpusKind.PLANTED_VIOLATION
    run_state["snapshot_bytes"] = gate.path_for(CorpusKind.PLANTED_VIOLATION).read_text(
        encoding="utf-8"
    )
    run_state["verdict"] = gate.inspect(CorpusKind.PLANTED_VIOLATION)


@when("the gate inspects a step suite that enters only through the driving port")
def when_inspect_clean(run_state):
    gate = run_state["gate"]
    run_state["before_content"] = CorpusKind.CLEAN
    run_state["snapshot_bytes"] = gate.path_for(CorpusKind.CLEAN).read_text(
        encoding="utf-8"
    )
    run_state["verdict"] = gate.inspect(CorpusKind.CLEAN)


# --- Then ------------------------------------------------------------------


@then("the gate reports the suite as flagged")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is BoundaryOutcome.FLAGGED


@then("the gate names the offending action and the driven adapter it reached for")
def then_names_offender(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.module) for v in violations}
    assert (
        str(EXPECTED_OFFENDING_FUNCTION),
        str(EXPECTED_OFFENDING_MODULE),
    ) in named


@then("the inspected step suite is left unchanged")
def then_suite_unchanged(run_state):
    # Mandate 8: the universe is the port-observable file bytes of the inspected
    # corpus. The gate is a pure-function read; the source must be untouched.
    corpus = run_state["before_content"]
    path = run_state["gate"].path_for(corpus)
    after_bytes = path.read_text(encoding="utf-8")
    assert_state_delta(
        before={"corpus.source_bytes": run_state["snapshot_bytes"]},
        after={"corpus.source_bytes": after_bytes},
        universe={"corpus.source_bytes"},
        expected={"corpus.source_bytes": unchanged()},
    )


@then("the gate reports the suite as clean")
def then_clean(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is BoundaryOutcome.CLEAN


@then("the gate raises no objection to setup that touches an adapter outside an action")
def then_no_false_positive_on_setup(run_state):
    # Precision half: the clean corpus carries a module-level driven-adapter
    # import AND a @given-body driven-adapter import. Neither is a @when action,
    # so the gate must report zero violations.
    assert run_state["verdict"].violations == ()
