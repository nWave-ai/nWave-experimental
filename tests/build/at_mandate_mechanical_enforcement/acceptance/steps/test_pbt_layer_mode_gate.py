"""Tier A step definitions — the M9/9-v2 PBT-layer-mode gate (slice-04).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.pbt_layer_mode.detect`` via the production
``PythonAstAdapter``, reached through the ``PbtLayerModeGate`` composition
service. Step bodies delegate to the service and assert against port-exposed
observables (the ``PbtLayerOutcome`` enum, the named offending construct +
breach kind); no business logic is inlined (Mandate-12 criterion 3).

Layer ~2 (in-memory pure-AST query, in-process) → example-based, no PBT
machinery (Mandate 9 v2: the only driven dependency is the in-memory Python AST
adapter, so the OR-reduction keeps it example-based here — the golden-fixture
corpus is finite and enumerable, not an unbounded domain). The "left untouched"
Then uses ``assert_state_delta`` over the inspected file's content (Mandate 8:
the universe is the port-observable file bytes, never an internal rule field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_GIVEN_CONSTRUCT,
    EXPECTED_STATE_MACHINE_CONSTRUCT,
    PbtBreachKind,
    PbtCorpusKind,
    PbtLayerOutcome,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.pbt_layer_mode_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../pbt-layer-mode-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the PBT-layer-mode gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the PBT-layer-mode gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output
    # is staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate weighs a property test placed at a too-deep layer")
def when_weigh_given_at_layer(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = PbtCorpusKind.GIVEN_AT_LAYER_3PLUS
    run_state["snapshot_bytes"] = gate.path_for(
        PbtCorpusKind.GIVEN_AT_LAYER_3PLUS
    ).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(PbtCorpusKind.GIVEN_AT_LAYER_3PLUS)


@when("the gate weighs a state-machine model placed at a too-deep layer")
def when_weigh_state_machine_at_layer(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = PbtCorpusKind.STATE_MACHINE_AT_LAYER_3PLUS
    run_state["verdict"] = gate.inspect(PbtCorpusKind.STATE_MACHINE_AT_LAYER_3PLUS)


@when("the gate weighs property tests kept at their home layer")
def when_weigh_clean(run_state):
    gate = run_state["gate"]
    run_state["verdict_home"] = gate.inspect(PbtCorpusKind.CLEAN_PBT_AT_LAYER_1_2)
    run_state["verdict_example"] = gate.inspect(
        PbtCorpusKind.CLEAN_EXAMPLE_AT_LAYER_3PLUS
    )


# --- Then ------------------------------------------------------------------


@then("the PBT-layer-mode gate rules the file out of discipline")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is PbtLayerOutcome.FLAGGED


@then("the gate names the stranded property test as a wrong-layer breach")
def then_names_given_breach(run_state):
    violations = run_state["verdict"].violations
    named = {(v.construct, v.kind) for v in violations}
    assert (
        str(EXPECTED_GIVEN_CONSTRUCT),
        PbtBreachKind.GIVEN_AT_LAYER_3PLUS.value,
    ) in named


@then("the weighed test file is left untouched")
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


@then("the gate names the stranded state-machine model as a wrong-layer breach")
def then_names_state_machine_breach(run_state):
    violations = run_state["verdict"].violations
    named = {(v.construct, v.kind) for v in violations}
    assert (
        str(EXPECTED_STATE_MACHINE_CONSTRUCT),
        PbtBreachKind.STATE_MACHINE_AT_LAYER_3PLUS.value,
    ) in named


@then("the PBT-layer-mode gate rules the file within discipline")
def then_clean(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict_home"])
    assert outcome is PbtLayerOutcome.CLEAN


@then("the gate raises no objection to an example-based test placed at a deep layer")
def then_no_false_positive(run_state):
    # Precision half: the home-layer corpus carries legitimate PBT at layers 1-2
    # (its home), AND the deep-layer corpus carries an example-based test with the
    # textual near-miss trap (a "given"/"hypothesis" mention, no real construct).
    # Neither is a breach — so the gate must report zero violations on both.
    assert run_state["verdict_home"].violations == ()
    assert run_state["verdict_example"].violations == ()
