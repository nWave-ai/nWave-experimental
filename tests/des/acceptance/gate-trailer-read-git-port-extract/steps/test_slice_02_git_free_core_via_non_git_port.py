"""pytest-bdd binding: the deliver-integrity verdict is computed through a
git-FREE gate core fed by a NON-git CommitTrailerReadPort (slice-02).

Driving seam (Mandate-13 tolerable contract-AT variant -- the R3 slice-03 shape):
the gate core's PUBLIC DESIGN-INTENDED injection point
``_verify_atdd_pure(project_dir, roadmap_path, feature_id, trailer_port=<fake>)``,
substituting a FAKE non-git ``CommitTrailerReadPort`` (an in-memory double for a
driven port, Architecture-of-Reference). The slice-01 CLI subprocess black box
CANNOT prove this value because ``main()`` hardcodes the git adapter
(verify_deliver_integrity.py:645) -- no env/flag selects a non-git source. Step
bodies delegate to the composition root (``composition_slice_02.py``); no business
logic lives in a step body (Mandate-12 criterion 3: each body is a single
delegation).

The ``scenarios(...)`` call binds every scenario in the slice-02 ``.feature`` via
the RELATIVE path from this steps/ module -- the proven-collecting form used by
the sibling suite oss-dormant-seam-gate and slice-01. Each step decorator's
literal text is unique within this feature directory (S1 step-text-uniqueness
invariant): the slice-02 Given/When/Then phrasings are distinct from slice-01's
(slice-01 drives the real git adapter through the CLI; slice-02 drives the
git-free core through a non-git port).

GIT-FREEDOM PROOF: every scenario runs on a ``tmp_path`` that is NOT a git
work-tree. The verdict is derived entirely from what the fake port returns, with
zero git involvement; the When-step's universe guard pins ``git.exists`` False
throughout. NON-VACUITY: RECORDS_SHIPPED_SLICE (reconciles, exit 0) is paired with
MISSING_SHIPPED_SLICE (unreconciled, exit 1) + CANNOT_READ (Indeterminate, exit 4)
-- the verdict genuinely depends on the port's return.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import GitFreeCoreComposition


scenarios("../slice-02-git-free-core-via-non-git-port.feature")


@pytest.fixture
def git_free_core() -> Iterator[GitFreeCoreComposition]:
    comp = GitFreeCoreComposition()
    yield comp
    comp.cleanup()


# --- Given -------------------------------------------------------------------


@given("a deliver project that demands slice reconciliation in a non-git tree")
def given_non_git_tree(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.given_non_git_tree_demanding_reconciliation()


@given(
    "the commit-trailer history is supplied by a non-git source recording the "
    "shipped slice"
)
def given_source_records_shipped_slice(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.given_source_records_shipped_slice()


@given(
    "the commit-trailer history is supplied by a non-git source missing the "
    "shipped slice"
)
def given_source_missing_shipped_slice(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.given_source_missing_shipped_slice()


@given("the commit-trailer history cannot be read by the non-git source")
def given_source_cannot_read(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.given_source_cannot_read()


# --- When --------------------------------------------------------------------


@when("the operator verifies the delivery through the git-free gate core")
def when_verifies_through_git_free_core(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.when_operator_verifies_through_git_free_core()


# --- Then --------------------------------------------------------------------


@then("the gate core reconciles the delivery cleanly without consulting git")
def then_reconciles_without_git(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.then_reconciles_cleanly_without_git()


@then("the gate core does not mutate the deliver project")
def then_pure_read(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.then_does_not_mutate_the_deliver_project()


@then("the gate core leaves the delivery unreconciled")
def then_leaves_unreconciled(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.then_leaves_delivery_unreconciled()


@then("the unreconciled verdict is distinct from a cannot-evaluate refusal")
def then_unreconciled_distinct(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.then_unreconciled_distinct_from_cannot_evaluate()


@then("the gate core refuses with a loud cannot-evaluate verdict")
def then_refuses_loud(git_free_core: GitFreeCoreComposition) -> None:
    git_free_core.then_refuses_with_loud_cannot_evaluate()
