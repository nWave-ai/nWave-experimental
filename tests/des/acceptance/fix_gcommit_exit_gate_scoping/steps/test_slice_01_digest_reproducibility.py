"""Step definitions for fix-gcommit-exit-gate-scoping slice-01 (Mandate-12).

slice-01 (#2) -- the committed-scope digest must be reproducible over the
COMMITTED tree at HEAD, not the working tree. The committed-scope digest is a
NEW, DISTINCT mode (`des run-contract-gate --committed-scope-digest`), separate
from the general `--collect-only --print-digest` (working-tree, non-git-OK,
collect-then-classify -- the dogfood + backward-compat contract, untouched).

These ATs are genuine RED at HEAD: the new mode does not exist yet, so AT-1
(reproducibility) and AT-3 (git-absent refusal) fail for MISSING_FUNCTIONALITY.
AT-2 (whole-tree breadth) pins a safety property the committed-scope mode must
satisfy once delivered (the OPT-a guard: a committed test anywhere stays inside
the digest).

Step bodies delegate to `GcommitScopingComposition` -- no inline business logic
(Mandate-12 criterion 3). Domain nouns are typed via `domain_types` (criterion
1); the composition service signatures consume those typed parameters
(criterion 2).

Mandate-13: the SUT is driven exclusively through the real `des
run-contract-gate --committed-scope-digest` CLI as a Layer-3 subprocess
black-box (see composition).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import GcommitScopingComposition
from .domain_types import (
    COMMITTED_SCOPE_INDETERMINATE_EVENT,
    CommittedContent,
    CommittedSuiteShape,
    DigestOutcome,
    WorkingTreeState,
)


scenarios("../slice-01-digest-reproducibility.feature")


@pytest.fixture
def composition() -> GcommitScopingComposition:
    """The production composition root driving the real contract-gate CLI."""
    return GcommitScopingComposition()


# ===========================================================================
# Given
# ===========================================================================


@given(
    "a repository whose contract suite is fully committed at one revision",
    target_fixture="repo",
)
def _given_committed_repo(composition: GcommitScopingComposition, tmp_path):
    """Precondition: a real git repo with a fully-committed contract suite."""
    return composition.make_committed_contract_repo(tmp_path)


@given(
    "a contract tree that is not under revision control",
    target_fixture="repo",
)
def _given_non_git_tree(composition: GcommitScopingComposition, tmp_path):
    """Precondition: a contract tree with no `.git/` (the git-absent case)."""
    return composition.make_non_git_contract_dir(tmp_path)


@given(
    "a repository whose committed contract suite mixes test modules and "
    "specification files",
    target_fixture="repo",
)
def _given_committed_mixed_repo(composition: GcommitScopingComposition, tmp_path):
    """Precondition: a real git repo whose committed suite mixes `.py` + `.feature`."""
    return composition.make_committed_mixed_contract_repo(
        tmp_path, CommittedSuiteShape.MIXED_PY_AND_FEATURE
    )


# ===========================================================================
# When
# ===========================================================================


@when(
    "the operator derives the gate-scope digest over the pristine working tree",
    target_fixture="first_run",
)
def _when_derive_pristine(composition: GcommitScopingComposition, repo):
    """Drive the digest CLI with no untracked co-resident files present."""
    composition.place_working_tree(repo, WorkingTreeState.PRISTINE)
    return composition.derive_digest(repo)


@when("an untracked co-resident contract file is dropped into the working tree")
def _when_drop_coresident(composition: GcommitScopingComposition, repo):
    """Add one UNTRACKED co-resident contract file (the perturbation)."""
    composition.place_working_tree(repo, WorkingTreeState.CORESIDENT_UNTRACKED)


@when(
    "the operator derives the gate-scope digest again over the same revision",
    target_fixture="second_run",
)
def _when_derive_again_same_revision(composition: GcommitScopingComposition, repo):
    """Drive the digest CLI a second time over the same pinned revision."""
    return composition.derive_digest(repo)


@when(
    "the operator derives the gate-scope digest over the committed suite",
    target_fixture="first_run",
)
def _when_derive_committed_suite(composition: GcommitScopingComposition, repo):
    """Drive the digest CLI over the committed suite before the new commit."""
    return composition.derive_digest(repo)


@when(
    "a new contract test is committed under an unrelated part of the tree",
    target_fixture="digest_after_commit",
)
def _when_commit_unrelated_test(composition: GcommitScopingComposition, repo):
    """Commit a NEW contract test under an unrelated subdirectory (breadth)."""
    return composition.commit_new_contract_test(
        repo, CommittedContent.NEW_COMMITTED_TEST
    )


@when("the operator derives the gate-scope digest after the new commit")
def _when_derive_after_new_commit(composition: GcommitScopingComposition):
    """The digest after the new commit was captured by the prior When step."""
    assert composition.last_run is not None


@when(
    "the operator derives the gate-scope digest over that tree",
    target_fixture="first_run",
)
def _when_derive_over_non_git(composition: GcommitScopingComposition, repo):
    """Drive the digest CLI over the non-git tree (git-absent path)."""
    return composition.derive_digest(repo)


@when(
    "the operator derives the gate-scope digest over the committed mixed suite",
    target_fixture="first_run",
)
def _when_derive_over_mixed(composition: GcommitScopingComposition, repo):
    """Drive the digest CLI over the committed mixed (`.py` + `.feature`) suite."""
    return composition.derive_digest(repo)


# ===========================================================================
# Then
# ===========================================================================


@then("both derivations print the identical gate-scope digest")
def _then_identical_digest(first_run, second_run) -> None:
    assert first_run.outcome is DigestOutcome.DIGEST_PRINTED, (
        f"the first derivation did not print a digest (exit {first_run.exit_code}, "
        f"outcome {first_run.outcome.value!r})"
    )
    assert second_run.outcome is DigestOutcome.DIGEST_PRINTED, (
        f"the second derivation did not print a digest (exit "
        f"{second_run.exit_code}, outcome {second_run.outcome.value!r})"
    )
    assert first_run.digest == second_run.digest != "", (
        "the gate-scope digest CHANGED when an untracked co-resident file was "
        f"added ({first_run.digest!r} != {second_run.digest!r}) -- the digest "
        "is computed over the working tree, not the committed tree at HEAD "
        "(slice-01 not yet delivered)"
    )


@then("the second digest ignored the untracked co-resident file")
def _then_ignored_untracked(first_run, second_run) -> None:
    assert first_run.digest == second_run.digest, (
        "the untracked co-resident file moved the digest -- it was collected "
        "into the gate-scope, so the committed-tree restriction is not in "
        "effect (slice-01 not yet delivered)"
    )


@then("the digest after the new commit differs from the digest before it")
def _then_digest_moved_on_commit(first_run, digest_after_commit) -> None:
    assert first_run.outcome is DigestOutcome.DIGEST_PRINTED, (
        f"the pre-commit derivation did not print a digest (exit {first_run.exit_code})"
    )
    assert first_run.digest != digest_after_commit != "", (
        "committing a new contract test elsewhere did NOT move the digest "
        f"({first_run.digest!r} -> {digest_after_commit!r}) -- the digest no "
        "longer covers the whole committed tree (OPT-a contract-narrowing "
        "regression)"
    )


@then("the whole committed tree's contract suite is still covered by the digest")
def _then_whole_tree_covered(digest_after_commit) -> None:
    assert digest_after_commit != "", (
        "the digest after committing a tree-wide contract test is empty -- the "
        "whole-committed-tree breadth was lost"
    )


@then("the gate refuses to fingerprint a tree it cannot pin to a revision")
def _then_gate_refuses(first_run) -> None:
    # Exit-code-exact: REFUSED <=> exit 2 (the fail-closed `MalformedInput`
    # path). DIGEST_PRINTED means it silently fingerprinted the working tree
    # (today's defect); UNEXPECTED means it failed via a WRONG mode -- both are
    # caught, so the assertion never passes for the wrong reason.
    assert first_run.outcome is DigestOutcome.REFUSED, (
        f"expected a fail-closed refusal (exit 2), got outcome "
        f"{first_run.outcome.value!r} (exit {first_run.exit_code}) -- "
        + (
            "the gate silently digested the working tree of a non-git dir "
            "instead of refusing (slice-01 git-absent guard not delivered)"
            if first_run.outcome is DigestOutcome.DIGEST_PRINTED
            else "the gate failed via the WRONG mode -- not the fail-closed "
            "INDETERMINATE refusal"
        )
    )


@then("the operator is loudly told the committed suite is indeterminate")
def _then_loud_indeterminate(first_run) -> None:
    combined = first_run.stdout + first_run.stderr
    assert COMMITTED_SCOPE_INDETERMINATE_EVENT in combined, (
        "no LOUD committed-scope INDETERMINATE health event surfaced for the "
        f"non-git tree (looked for {COMMITTED_SCOPE_INDETERMINATE_EVENT!r}) -- "
        "the gate degraded SILENTLY, violating the degrade-LOUD contract "
        "(slice-01 not yet delivered)"
    )


@then("the gate prints a reproducible gate-scope digest over the committed mixed suite")
def _then_mixed_digest_printed(first_run) -> None:
    # The genuine-witness assertion: a committed `.feature` in the suite must
    # NOT break the digest. Today the committed `.feature` is passed to pytest
    # as a `--path` -> pytest exit 4 -> MalformedInput -> REFUSED (exit 2), so
    # this fires for the right reason (the masking the `.py`-only fixtures hid).
    assert first_run.outcome is DigestOutcome.DIGEST_PRINTED, (
        f"expected a printed digest (exit 0), got outcome "
        f"{first_run.outcome.value!r} (exit {first_run.exit_code}) -- the "
        "committed `.feature` was passed to pytest as a collection `--path`, "
        "which pytest cannot collect directly (exit 4), so the gate fails "
        "closed instead of fingerprinting the committed mixed suite "
        "(slice-01 `.feature`-exclusion not yet delivered)"
    )
    assert first_run.digest != "", (
        "the gate exited 0 but printed no 64-hex digest line for the committed "
        "mixed suite"
    )


@then(
    "the gate does not refuse the committed suite for a specification it cannot "
    "collect directly"
)
def _then_not_refused_for_feature(first_run) -> None:
    assert first_run.outcome is not DigestOutcome.REFUSED, (
        f"the gate REFUSED the committed mixed suite (exit {first_run.exit_code}) "
        "-- a committed `.feature` spec was passed to pytest as a collection "
        "`--path` and pytest exited 4; the digest mode must exclude `.feature` "
        "from the explicit path-set (its scenarios are collected via their bound "
        "`@scenario` `.py` modules, so no coverage is lost)"
    )
