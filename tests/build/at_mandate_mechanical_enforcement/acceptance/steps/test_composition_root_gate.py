"""Tier A step definitions — the P3 composition-root gate (slice-09).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.composition_root.detect`` via the production
``PythonAstAdapter``, reached through the ``CompositionRootGate`` composition
service. Step bodies delegate to the service and assert against port-exposed
observables (the ``CompositionOutcome`` enum, the named offending step +
hand-wired collaborator type); no business logic is inlined (Mandate-12
criterion 3).

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

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.composition_root_composition import (
    build_gate,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_HAND_WIRED_STEP,
    EXPECTED_HAND_WIRED_TYPE,
    CompositionBreachKind,
    CompositionCorpusKind,
    CompositionOutcome,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../composition-root-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the composition-root gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the composition-root gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output is
    # staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate judges a step suite whose body hand-wires the system-under-test")
def when_judge_hand_wired(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = CompositionCorpusKind.HAND_WIRED_SUT
    run_state["snapshot_bytes"] = gate.path_for(
        CompositionCorpusKind.HAND_WIRED_SUT
    ).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(CompositionCorpusKind.HAND_WIRED_SUT)


@when(
    "the gate judges a step suite that builds the system through the composition root"
)
def when_judge_composition_root(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(CompositionCorpusKind.COMPOSITION_ROOT)


# --- Then ------------------------------------------------------------------


@then("the composition-root gate rules the suite flagged")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is CompositionOutcome.FLAGGED


@then("the gate names the offending step and the collaborator type it hand-wires")
def then_names_breach(run_state):
    violations = run_state["verdict"].violations
    named = {(v.function, v.constructed, v.kind) for v in violations}
    breach = CompositionBreachKind.HAND_WIRED_SUT_IN_STEP_BODY.value
    assert (
        str(EXPECTED_HAND_WIRED_STEP),
        str(EXPECTED_HAND_WIRED_TYPE),
        breach,
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


@then("the composition-root gate rules the suite clean")
def then_clean(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is CompositionOutcome.CLEAN


@then("the gate raises no objection to the clean composition-root step suite")
def then_no_false_positive(run_state):
    # Precision half / learning-hypothesis guard: the clean corpus carries the
    # near-miss traps (a domain VALUE-OBJECT construction that is NOT a SUT
    # collaborator; an attribute read on the composed app). The breach is a
    # hand-wired SUT-collaborator construction with no composition-root entry
    # call, not a value-object construction or a composition-root call; so the
    # gate must report zero violations on the clean corpus.
    assert run_state["verdict"].violations == ()
