"""pytest-bdd binding for f-nonbypassable-attestation slice-03 (slice-plan shipped).

Driving surface (Mandate-13, Layer-3 composition): the REAL done-gate
``verify_deliver_integrity.main``. Step bodies delegate to the composition root;
no business logic in step bodies (Mandate-12). S1: the done-gate verbs "declares
the feature done" / "clears the feature" / "refuses with a definite failure" are
imported from the shared SSOT (one registration, no shadow). Only the
slice-03-UNIQUE steps live below; the ``attestation`` fixture lives in conftest.

Active-RED scaffold (atdd_pure -- NOT @skip):
  * CT-6 (pending-slice refusal) is RED until DELIVER folds the slice-plan
    all-shipped assertion into verify_deliver_integrity -- at HEAD a one-pending
    plan CLEARS (exit 0) where a definite FAIL is expected.
  * CT-7 (git-absent INDETERMINATE) witnesses the ALREADY-SHIPPED degrade-LOUD
    contract (AD-21/24, CONSUMED unchanged per AT-A4) -- a regression pin, green
    at HEAD; included so the done-gate's two INDETERMINATE causes (git-absent vs
    bypass-debt) stay discriminable.
Failures are semantic AssertionErrors, never collection / import / setup errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then

from .domain_types_nonbypassable import SlicePlanStatus


if TYPE_CHECKING:
    from .composition_nonbypassable import AttestationComposition


# S1: shared done-gate verbs live ONCE in conftest.py. Only the slice-03-UNIQUE
# steps live below.


scenarios("../slice-03-slice-plan-shipped.feature")


# --- Given (slice-03 unique) -----------------------------------------------


@given("a complete feature whose slice plan has a pending slice")
def given_plan_with_pending(
    attestation: AttestationComposition, tmp_path: Path
) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_and_slice_plan(
        (SlicePlanStatus.SHIPPED, SlicePlanStatus.PENDING)
    )


@given("a complete feature whose slice plan is entirely shipped")
def given_plan_all_shipped(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_and_slice_plan(
        (SlicePlanStatus.SHIPPED, SlicePlanStatus.SHIPPED)
    )


@given("a complete feature whose slice plan declares no slices")
def given_plan_empty(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_and_empty_slice_plan()


@given("a complete feature on a target that is not a git work-tree")
def given_non_worktree(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_on_non_worktree()


# --- Then (slice-03 unique cause-discriminators) ---------------------------


@then("the refusal names the pending slice")
def then_names_pending_slice(attestation: AttestationComposition) -> None:
    attestation.then_cause_names("pending")


# S1: "the done-gate cannot certify the feature" (the shared INDETERMINATE verb)
# is declared ONCE in conftest.py -- not duplicated here.


@then("the refusal names the unreadable work-tree")
def then_names_unreadable_worktree(attestation: AttestationComposition) -> None:
    attestation.then_cause_names("work-tree")
