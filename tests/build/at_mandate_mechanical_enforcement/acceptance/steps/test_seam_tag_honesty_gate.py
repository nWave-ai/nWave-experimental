"""Tier A step definitions — the CM-I seam-tag-honesty gate (slice-05).

CONTRACT_SHAPE: pure-function

Driving port: the real rule entrypoint
``des.testarch.rules.seam_tag_honesty.detect`` via the production
``PythonAstAdapter``, reached through the ``SeamTagHonestyGate`` composition
service. Step bodies delegate to the service and assert against port-exposed
observables (the ``SeamHonestyOutcome`` enum, the named offending test + claim
tag); no business logic is inlined (Mandate-12 criterion 3).

Layer ~2 (in-memory pure-AST query, in-process) → example-based, no PBT
machinery (Mandate 9 v2: the only driven dependency is the in-memory Python AST
adapter, so the OR-reduction keeps it example-based here — the golden-fixture
corpus is finite and enumerable, not an unbounded domain). The "left untouched"
Then uses ``assert_state_delta`` over the inspected file's content (Mandate 8:
the universe is the port-observable file bytes, never an internal rule field).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess — the gate practises the honesty it enforces.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    EXPECTED_DISHONEST_CLAIM_TAG,
    EXPECTED_DISHONEST_TEST,
    SeamBreachKind,
    SeamCorpusKind,
    SeamHonestyOutcome,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.seam_tag_honesty_composition import (
    build_gate,
)
from tests.common.state_delta import assert_state_delta, unchanged


scenarios("../seam-tag-honesty-gate.feature")


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def gate():
    """Production composition root for the seam-tag-honesty gate."""
    return build_gate()


@pytest.fixture
def run_state() -> dict:
    """Mutable carrier for verdicts + content snapshots across Given/When/Then."""
    return {}


# --- Given -----------------------------------------------------------------


@given("the seam-tag-honesty gate")
def given_the_gate(gate, run_state):
    # Precondition only — the gate object is the SUT entry. No expected output
    # is staged here (no Fixture Theater).
    run_state["gate"] = gate


# --- When ------------------------------------------------------------------


@when("the gate judges a test that claims a real subprocess but runs in-process")
def when_judge_dishonest(run_state):
    gate = run_state["gate"]
    run_state["corpus"] = SeamCorpusKind.DISHONEST_WIRING_E2E
    run_state["snapshot_bytes"] = gate.path_for(
        SeamCorpusKind.DISHONEST_WIRING_E2E
    ).read_text(encoding="utf-8")
    run_state["verdict"] = gate.inspect(SeamCorpusKind.DISHONEST_WIRING_E2E)


@when("the gate judges a test that claims a real subprocess and genuinely spawns one")
def when_judge_honest_real_subprocess(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(SeamCorpusKind.HONEST_TAGS)


@when("the gate judges an in-process test honestly tagged as a component test")
def when_judge_honest_in_process(run_state):
    gate = run_state["gate"]
    run_state["verdict"] = gate.inspect(SeamCorpusKind.HONEST_TAGS)


# --- Then ------------------------------------------------------------------


@then("the seam-tag-honesty gate rules the file dishonest")
def then_flagged(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is SeamHonestyOutcome.FLAGGED


@then("the gate names the mislabelled test and the tag it falsely wears")
def then_names_breach(run_state):
    violations = run_state["verdict"].violations
    named = {(v.test, v.tag, v.kind) for v in violations}
    assert (
        str(EXPECTED_DISHONEST_TEST),
        EXPECTED_DISHONEST_CLAIM_TAG,
        SeamBreachKind.TAG_CLAIMS_SUBPROCESS_BUT_RUNS_IN_PROCESS.value,
    ) in named


@then("the judged test file is left untouched")
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


@then("the seam-tag-honesty gate rules the file honest")
def then_honest(run_state):
    outcome = run_state["gate"].outcome_of(run_state["verdict"])
    assert outcome is SeamHonestyOutcome.HONEST


@then("the gate raises no objection to the honest in-process component test")
def then_no_false_positive(run_state):
    # Precision half: the honest corpus carries an in-process main(argv) body —
    # the very shape that is dishonest UNDER a subprocess tag — but honestly
    # tagged @component. The breach is the TAG-vs-SPAWN mismatch, not the body
    # shape alone; so the gate must report zero violations on the honest corpus.
    assert run_state["verdict"].violations == ()
