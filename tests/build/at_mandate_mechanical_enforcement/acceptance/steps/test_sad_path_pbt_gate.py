"""Tier A step definitions — the M11 integration-sad-path gate (slice-07).

CONTRACT_SHAPE: pure-function (PBT-layer scenarios) + bounded-change
(failure-mode-coverage scenario — see the per-scenario @contract-shape tags).

Driving port: the real rule entrypoints
``des.testarch.rules.sad_path_pbt.detect`` (PBT-layer half) and
``des.testarch.rules.sad_path_pbt.detect_failure_mode_coverage`` (coverage half)
via the production ``PythonAstAdapter``, reached through the ``SadPathPbtGate``
composition service. Step bodies delegate to the service and assert against
port-exposed observables (the ``SadPathOutcome`` enum, the named offending
construct + breach kind); no business logic is inlined (Mandate-12 criterion 3).

Layer ~2 (in-memory pure-AST/YAML query, in-process) → example-based, no PBT
machinery (Mandate 9 v2 / Mandate 11: the only driven dependency is the in-memory
Python AST adapter, so the OR-reduction keeps it example-based here — the
golden-fixture corpus is finite and enumerable, not an unbounded domain; and the
gate UNDER TEST is itself the M11 enforcer, so the suite practises what it
enforces). The "left untouched" Then uses ``assert_state_delta`` over the
inspected file's content (Mandate 8: the universe is the port-observable file
bytes, never an internal rule field).

RED scaffold (ADR-025): the rule entrypoints raise ``AssertionError``
("implementation missing" — DELIVER greens them). The ATs collect and fail for
the right reason (semantic AssertionError, not import/collection error).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess — the gate practises the honesty it enforces.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_STRANDED_PBT_CONSTRUCT,
    EXPECTED_UNCOVERED_FAILURE_MODE,
    SadPathBreachKind,
    SadPathCorpusKind,
    SadPathOutcome,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.sad_path_pbt_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../sad-path-pbt-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the integration-sad-path gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the integration-sad-path gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output is
    # staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate weighs a property-based sad path placed at a too-deep layer")
def when_weigh_pbt_stranded(run_state):
    gate = run_state["gate"]
    corpus = SadPathCorpusKind.PBT_STRANDED_AT_LAYER_3PLUS
    run_state["corpus"] = corpus
    run_state["snapshot_bytes"] = gate.path_for(corpus).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(corpus)


@when("the gate weighs enumerated example sad paths placed at a too-deep layer")
def when_weigh_example_at_depth(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(SadPathCorpusKind.EXAMPLE_AT_LAYER_3PLUS)
    run_state["home_verdict"] = gate.inspect(SadPathCorpusKind.PBT_AT_HOME_LAYER)
    run_state["adversarial_verdict"] = gate.inspect(SadPathCorpusKind.R6_ADVERSARIAL)


@when("the gate cross-checks a manifest declaring a failure mode no test covers")
def when_cross_check_uncovered(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.cross_check_coverage(
        SadPathCorpusKind.UNCOVERED_FAILURE_MODE
    )
    run_state["covered_verdict"] = gate.cross_check_coverage(
        SadPathCorpusKind.COVERED_FAILURE_MODE
    )


# --- Then ------------------------------------------------------------------


@then("the integration-sad-path gate rules the file out of discipline")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is SadPathOutcome.FLAGGED


@then("the gate names the stranded property sad path as a wrong-layer breach")
def then_names_stranded(run_state):
    violations = run_state["verdict"].violations
    named = {(v.offender, v.kind) for v in violations}
    assert (
        str(EXPECTED_STRANDED_PBT_CONSTRUCT),
        SadPathBreachKind.PBT_IN_LAYER3_SAD_PATH.value,
    ) in named


@then("the weighed sad-path file is left untouched")
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


@then("the integration-sad-path gate rules the file within discipline")
def then_within_discipline(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is SadPathOutcome.CLEAN


@then("the gate raises no objection to a property sad path kept at its home layer")
def then_home_layer_clean(run_state):
    # Precision half: a @given sad-path test at its home layer (1-2) is COMPLIANT
    # — the forbidden zone is layers 3+ only. The gate must report zero
    # violations on the home-layer corpus.
    assert run_state["home_verdict"].violations == ()


@then("the gate survives an adversarial sad-path file without crashing")
def then_adversarial_survived(run_state):
    # R6 self-dogfood: the gate's own parser is the SUT. An unclassifiable
    # parser shape (indirect parametrize source) must produce a deterministic
    # verdict — no @given/stateful construct present, so no PBT-layer breach —
    # WITHOUT the rule crashing. Reaching this assertion proves no exception
    # escaped the cross-check.
    assert run_state["adversarial_verdict"].violations == ()


@then("the integration-sad-path gate rules the failure-mode coverage incomplete")
def then_coverage_incomplete(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is SadPathOutcome.FLAGGED


@then("the gate names the uncovered failure mode")
def then_names_uncovered_mode(run_state):
    violations = run_state["verdict"].violations
    named = {(v.offender, v.kind) for v in violations}
    assert (
        str(EXPECTED_UNCOVERED_FAILURE_MODE),
        SadPathBreachKind.UNCOVERED_FAILURE_MODE.value,
    ) in named


@then("the gate raises no objection to a manifest whose every failure mode is covered")
def then_covered_manifest_clean(run_state):
    # Coverage-half precision: every declared failure mode has a covering named
    # test, so the gate must report zero violations on the covered manifest.
    assert run_state["covered_verdict"].violations == ()
