"""pytest-bdd binding + step vocabulary for slice-04-commit-gate-self-test.

Mandate-12 (SSOT via Types + Services + DSL): step decorators are parameterized
templates over typed-enum parameters (from ``domain_types.py``). Mandate-12
criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), no control flow.
Business logic lives in the production commit-gate hook + slice-01/02/03 ports
behind it; the composition transports decisions; this module only names domain
facts and delegates.

S1 (step-text uniqueness): every literal step string here is distinct from the
other slices' vocabulary -- no ``@then`` shadowing across the feature dir. The
fixture name ``commit_gate_composition`` is distinct from the other roots.

DEPENDENCY (FLAGGED): slice-04 depends on slice-02 + slice-03 being shipped; the
ATs are @skip @pending and RED today because the commit-gate hook branch +
self-test entry do not exist (driving-port-absent RED). DELIVER unskips after
02 + 03 are green.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_04 import CommitGateComposition
from .domain_types import (
    COMMIT_DECISION_BY_PHRASE,
    SLICE_HEALTH_BY_PHRASE,
    STATUS_BY_PHRASE,
)


scenarios("../slice-04-commit-gate-self-test.feature")


@pytest.fixture
def commit_gate_composition() -> CommitGateComposition:
    """The production commit-gate composition root, fresh per scenario."""
    return CommitGateComposition()


# --- Given: stage the slice + its ATs (or the self-test perturbation) ---------


@given(parsers.parse('a slice whose acceptance tests are "{slice_health}"'))
def given_slice(
    commit_gate_composition: CommitGateComposition, slice_health: str
) -> None:
    commit_gate_composition.given_slice(SLICE_HEALTH_BY_PHRASE[slice_health])


@given("the gate's own verdict core has been perturbed at its seam")
def given_core_perturbed(commit_gate_composition: CommitGateComposition) -> None:
    commit_gate_composition.given_core_perturbed()


# --- When: drive the real PreToolUse hook / the self-test ---------------------


@when("a commit of that slice is attempted through the pre-commit gate")
def when_attempt_commit(commit_gate_composition: CommitGateComposition) -> None:
    commit_gate_composition.result = commit_gate_composition.attempt_commit()


@when("the gate runs its self-test over the perturbed core")
def when_run_self_test(commit_gate_composition: CommitGateComposition) -> None:
    commit_gate_composition.result = commit_gate_composition.run_self_test()


# --- Then: assert on the gate's decision body + self-test verdict -------------


@then(parsers.parse('the commit gate decision is "{decision}"'))
def then_commit_decision(
    commit_gate_composition: CommitGateComposition, decision: str
) -> None:
    assert (
        commit_gate_composition.result.decision == COMMIT_DECISION_BY_PHRASE[decision]
    )


@then("the gate reports the theater test as the reason")
def then_reports_theater(commit_gate_composition: CommitGateComposition) -> None:
    assert commit_gate_composition.reports_theater_reason() is True


@then(parsers.parse('the gate\'s self-test verdict is "{status}"'))
def then_self_test_verdict(
    commit_gate_composition: CommitGateComposition, status: str
) -> None:
    assert commit_gate_composition.result.self_test_status == STATUS_BY_PHRASE[status]


@then("the gate denies its own commit")
def then_denies_own_commit(commit_gate_composition: CommitGateComposition) -> None:
    assert (
        commit_gate_composition.result.decision == COMMIT_DECISION_BY_PHRASE["denied"]
    )


@then(
    parsers.parse(
        'the gate\'s self-test verdict over an un-perturbed core is "{status}"'
    )
)
def then_self_test_control_verdict(
    commit_gate_composition: CommitGateComposition, status: str
) -> None:
    commit_gate_composition.run_self_test_control()
    assert commit_gate_composition.control_status == STATUS_BY_PHRASE[status]
