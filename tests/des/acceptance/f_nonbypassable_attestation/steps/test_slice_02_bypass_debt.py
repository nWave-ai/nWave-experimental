"""pytest-bdd binding for f-nonbypassable-attestation slice-02 (bypass-debt).

Driving surfaces (Mandate-13):
  * Layer-3 subprocess: the REAL spine-ledger pre-commit hook (the WRITE side).
  * Layer-3 composition: the REAL done-gate verify_deliver_integrity.main (READ).

Step bodies delegate to the composition root; no business logic in step bodies
(Mandate-12). S1: the done-gate verbs "declares the feature done" / "clears the
feature" are imported from the shared SSOT (one registration, no shadow). Only
the slice-02-UNIQUE steps live below; the `attestation` fixture lives in conftest.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER extends the spine
hook to write SliceCommitBypassed on --no-verify and the done-gate to read it as
INDETERMINATE-debt. Failures are semantic AssertionErrors.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when

from .domain_types_nonbypassable import BypassDebtState, CommitKind


if TYPE_CHECKING:
    from .composition_nonbypassable import AttestationComposition


# S1: shared done-gate verbs ("declares the feature done" / "clears the feature")
# live ONCE in conftest.py. Only the slice-02-UNIQUE steps live below.


scenarios("../slice-02-bypass-debt.feature")


# --- Given (slice-02 unique) -----------------------------------------------


@given("a git work-tree with the spine hook in scope")
def given_git_worktree(attestation: AttestationComposition, tmp_path: Path) -> None:
    # A real work-tree DURING an in-flight feature: a single telemetry ledger is
    # present, so the spine hook resolves the feature-id via the sanctioned
    # single-ledger rule (never a hard-coded probe id). Both the --no-verify WRITE
    # scenario and the verified-commit no-debt scenario share this precondition.
    attestation.use_project_root(tmp_path)
    attestation.init_git_repo()
    attestation.seed_single_in_flight_ledger()


@given("a git work-tree with a no-verify commit ready")
def given_git_worktree_no_verify_ready(
    attestation: AttestationComposition, tmp_path: Path
) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_git_worktree_with_no_verify_command()


@given("a complete feature whose ledger carries an unreconciled bypass-debt")
def given_unreconciled_debt(
    attestation: AttestationComposition, tmp_path: Path
) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_with_bypass_debt(BypassDebtState.UNRECONCILED)


@given("a complete feature whose bypass-debt has been reverified")
def given_reconciled_debt(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_ledger_with_bypass_debt(BypassDebtState.RECONCILED)


# --- When (slice-02 unique) ------------------------------------------------


@when("the developer commits the slice with git commit --no-verify")
def when_commit_no_verify(attestation: AttestationComposition) -> None:
    attestation.when_slice_commit_issued(CommitKind.NO_VERIFY)


@when("the developer commits the slice with git commit")
def when_commit_verified(attestation: AttestationComposition) -> None:
    attestation.when_slice_commit_issued(CommitKind.VERIFIED)


# --- Then (slice-02 unique) ------------------------------------------------


@then("a bypass-debt record is written for that slice")
def then_bypass_recorded(attestation: AttestationComposition) -> None:
    attestation.then_bypass_debt_recorded_for("slice-99")


@then("the bypass is never silent")
def then_never_silent(attestation: AttestationComposition) -> None:
    attestation.then_bypass_debt_recorded_for("slice-99")


@then("no bypass-debt record is written")
def then_no_bypass_recorded(attestation: AttestationComposition) -> None:
    attestation.then_no_bypass_debt_recorded()


# S1: "the done-gate cannot certify the feature" is the SHARED INDETERMINATE verb
# (recurs in slice-02 + slice-03) -- declared ONCE in conftest.py (the pytest-bdd
# shared-step SSOT), not duplicated here.


@then("the refusal names the unreconciled bypass-debt")
def then_names_bypass_debt(attestation: AttestationComposition) -> None:
    attestation.then_cause_names("SliceCommitBypassed")
