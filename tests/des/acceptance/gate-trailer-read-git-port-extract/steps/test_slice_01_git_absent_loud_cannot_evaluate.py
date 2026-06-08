"""pytest-bdd binding: the deliver-integrity gate refuses LOUD when it cannot
read the commit-trailer history (slice-01 walking skeleton).

Driving port: the production ``des verify-integrity`` CLI, invoked as a
subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess). Step
bodies delegate to the composition root (``composition.py``); no production
module is imported-and-called at the step boundary, and no business logic lives
in a step body (Mandate-12 criterion 3: each body is a single delegation).

The ``scenarios(...)`` call binds every scenario in the ``.feature`` file via the
RELATIVE path from this steps/ module -- the proven-collecting form used by the
sibling suite oss-dormant-seam-gate. This routes the scenario @tags through
pytest-bdd's tag-to-dynamic-mark pipeline, which the project's filterwarnings
makes --strict-markers-safe. Each step decorator's literal text is unique within
this feature directory (S1 step-text-uniqueness invariant; this is the only step
file in the directory).

RED scaffold (empirically confirmed at authorship HEAD): on master
``_shipped_slices`` swallows git-absence as a silent ``return frozenset()``, so a
non-git-work-tree with a present integrity-clean ledger EXITS 0 ("All slices have
a complete trace"). The cannot-evaluate Then-steps assert exit 4 + the LOUD
``FeatureIndeterminate`` event and fail with a semantic ``AssertionError`` (the
verdict is OTHER, not CANNOT_EVALUATE) -- never a collection / import / setup
error in the test process. The ATs PASS once DELIVER lands the
CommitTrailerReadPort + GitCommitTrailerReadAdapter + the silent->loud re-point.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import TrailerReadGateComposition


scenarios("../slice-01-git-absent-loud-cannot-evaluate.feature")


@pytest.fixture
def composition() -> Iterator[TrailerReadGateComposition]:
    comp = TrailerReadGateComposition()
    yield comp
    comp.cleanup()


# --- Given -------------------------------------------------------------------


@given("a deliver project that demands slice reconciliation but is not a git work-tree")
def given_non_work_tree(composition: TrailerReadGateComposition) -> None:
    composition.given_non_work_tree_demanding_reconciliation()


@given(
    "a deliver project that demands slice reconciliation but the git binary is "
    "unavailable"
)
def given_git_binary_absent(composition: TrailerReadGateComposition) -> None:
    composition.given_git_binary_unavailable_demanding_reconciliation()


@given("a deliver project in a git work-tree carrying a recorded shipped slice")
def given_real_work_tree(composition: TrailerReadGateComposition) -> None:
    composition.given_real_work_tree_with_recorded_slice()


# --- When --------------------------------------------------------------------


@when("the operator runs des verify-integrity for that feature")
def when_runs_verify_integrity(composition: TrailerReadGateComposition) -> None:
    composition.when_operator_runs_verify_integrity()


# --- Then --------------------------------------------------------------------


@then("the gate refuses with a loud cannot-evaluate verdict")
def then_refuses_loud(composition: TrailerReadGateComposition) -> None:
    composition.then_refuses_with_loud_cannot_evaluate()


@then("the gate names the cannot-evaluate reason in the loud verdict")
def then_names_reason(composition: TrailerReadGateComposition) -> None:
    composition.then_names_cannot_evaluate_reason()


@then("the gate does not silently report the delivery as nothing-shipped")
def then_not_silent(composition: TrailerReadGateComposition) -> None:
    composition.then_does_not_silently_report_nothing_shipped()


@then("the gate does not mutate the deliver project")
def then_pure_read(composition: TrailerReadGateComposition) -> None:
    composition.then_does_not_mutate_the_deliver_project()


@then("the cannot-evaluate refusal is distinct from an unreconciled-slice verdict")
def then_distinct_from_unreconciled(composition: TrailerReadGateComposition) -> None:
    composition.then_cannot_evaluate_distinct_from_unreconciled()


@then("the gate reconciles the delivery cleanly")
def then_reconciles(composition: TrailerReadGateComposition) -> None:
    composition.then_reconciles_cleanly()
