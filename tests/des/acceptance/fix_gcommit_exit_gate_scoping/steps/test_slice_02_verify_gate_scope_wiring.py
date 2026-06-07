"""Step definitions for fix-gcommit-exit-gate-scoping slice-02 (Mandate-12).

slice-02 (WIRING) -- the G_COMMIT exit-gate verify check
(`run_contract_gate._mode_verify_gate_scope:488`, `--verify-gate-scope`) and the
terminating Gate-Scope trailer compute (`:547`) must switch from the WORKING-TREE
`gate_scope_digest(repo)` to the committed-scope digest shipped in slice-01.

These ATs are genuine RED at HEAD 2e0e70c71: the verify check still digests the
WORKING tree, so an untracked co-resident contract file PERTURBS the fresh digest
-> `GateScopeUnverified reason=mismatch` (exit 1) in the co-resident state. AT-1
(untracked-WIP invariance) and AT-4 (mixed suite under the perturbation)
therefore fail for MISSING_FUNCTIONALITY -- the two working-tree states do NOT
verify identically. AT-2 (stale trailer) pins the preserved whole-committed-tree
witness; AT-3 (git-absent) pins the inherited LOUD refusal.

Step bodies delegate to `GcommitVerifyComposition` -- no inline business logic
(Mandate-12 criterion 3). Domain nouns are typed via `domain_types_slice_02`
(criterion 1); the composition service signatures consume those typed parameters
(criterion 2).

Mandate-13: the SUT is driven exclusively through the real `des
run-contract-gate --verify-gate-scope` CLI as a Layer-3 subprocess black-box
(see `composition_slice_02`) -- the same definition the U2 G_COMMIT exit-gate
hook invokes.
"""

from __future__ import annotations

import json

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import GcommitVerifyComposition
from .domain_types_slice_02 import (
    COMMITTED_SCOPE_INDETERMINATE_EVENT,
    CommittedSuiteShape,
    TrailerState,
    VerifyOutcome,
    WorkingTreeState,
)


scenarios("../slice-02-verify-gate-scope-wiring.feature")


def _first_event(combined: str, event_name: str) -> str:
    """Return the first single-line JSON event whose `event` field matches.

    The CLI emits one JSON object per line; this isolates the named verdict
    event from any freshness / health chatter lines so the assertion reads its
    structured `reason` field rather than substring-matching the raw stream.
    """
    for line in combined.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event_name:
            return line
    raise AssertionError(
        f"no {event_name!r} JSON event found in the verify output; "
        f"combined stream was:\n{combined}"
    )


@pytest.fixture
def composition() -> GcommitVerifyComposition:
    """The production composition root driving the real verify-gate-scope CLI."""
    return GcommitVerifyComposition()


# ===========================================================================
# Given
# ===========================================================================


@given(
    "a commit whose Gate-Scope trailer pins its committed contract suite",
    target_fixture="repo",
)
def _given_commit_matching_trailer(composition: GcommitVerifyComposition, tmp_path):
    """Precondition: a commit whose trailer pins its own committed-scope digest."""
    return composition.make_commit_pinning_its_committed_suite(
        tmp_path, TrailerState.MATCHING
    )


@given(
    "a commit whose Gate-Scope trailer pins a stale committed contract suite",
    target_fixture="repo",
)
def _given_commit_stale_trailer(composition: GcommitVerifyComposition, tmp_path):
    """Precondition: a commit whose committed tree moved past its pinned trailer."""
    return composition.make_commit_pinning_its_committed_suite(
        tmp_path, TrailerState.STALE
    )


@given(
    "a Gate-Scope trailer to verify against a tree that is not under revision control",
    target_fixture="repo",
)
def _given_non_git_target(composition: GcommitVerifyComposition, tmp_path):
    """Precondition: a contract tree with no `.git/` (the git-absent case)."""
    return composition.make_non_git_trailer_target(tmp_path)


@given(
    "a commit whose Gate-Scope trailer pins a committed suite of tests and "
    "specifications",
    target_fixture="repo",
)
def _given_commit_mixed_suite(composition: GcommitVerifyComposition, tmp_path):
    """Precondition: a commit pinning a committed `.py` + `.feature` mixed suite."""
    return composition.make_commit_pinning_committed_mixed_suite(
        tmp_path, CommittedSuiteShape.MIXED_PY_AND_FEATURE
    )


# ===========================================================================
# When
# ===========================================================================


@when(
    "the exit gate verifies that commit over the pristine working tree",
    target_fixture="first_run",
)
def _when_verify_pristine(composition: GcommitVerifyComposition, repo):
    """Drive the verify check with no untracked co-resident files present."""
    composition.place_working_tree(repo, WorkingTreeState.PRISTINE)
    return composition.verify_gate_scope(repo)


@when(
    "the exit gate verifies that commit over the committed mixed suite",
    target_fixture="first_run",
)
def _when_verify_mixed(composition: GcommitVerifyComposition, repo):
    """Drive the verify check over the committed `.py` + `.feature` mixed suite."""
    composition.place_working_tree(repo, WorkingTreeState.PRISTINE)
    return composition.verify_gate_scope(repo)


@when("an untracked co-resident contract file is dropped beside the commit")
def _when_drop_coresident(composition: GcommitVerifyComposition, repo):
    """Add one UNTRACKED co-resident contract file (the perturbation)."""
    composition.place_working_tree(repo, WorkingTreeState.CORESIDENT_UNTRACKED)


@when(
    "the exit gate verifies that same commit again",
    target_fixture="second_run",
)
def _when_verify_again(composition: GcommitVerifyComposition, repo):
    """Drive the verify check a second time over the same pinned commit."""
    return composition.verify_gate_scope(repo)


@when("the exit gate verifies that commit", target_fixture="first_run")
def _when_verify_commit(composition: GcommitVerifyComposition, repo):
    """Drive the verify check once over the pinned commit."""
    return composition.verify_gate_scope(repo)


# ===========================================================================
# Then
# ===========================================================================


@then("both verifications return the identical verified verdict")
def _then_identical_verified(first_run, second_run) -> None:
    assert first_run.outcome is VerifyOutcome.VERIFIED, (
        f"the first verification did not verify (exit {first_run.exit_code}, "
        f"outcome {first_run.outcome.value!r})"
    )
    assert second_run.outcome is VerifyOutcome.VERIFIED, (
        "the verify verdict CHANGED when an untracked co-resident file was added "
        f"(exit {second_run.exit_code}, outcome {second_run.outcome.value!r}) -- "
        "the verify check digests the WORKING tree (`:488`), not the committed "
        "tree at the pinned revision, so the untracked file perturbed the fresh "
        "digest -> mismatch (slice-02 committed-scope wiring not yet delivered)"
    )


@then("the second verification ignored the untracked co-resident file")
def _then_ignored_untracked(first_run, second_run) -> None:
    assert first_run.outcome is second_run.outcome is VerifyOutcome.VERIFIED, (
        "the untracked co-resident file changed the verify verdict "
        f"({first_run.outcome.value!r} -> {second_run.outcome.value!r}) -- it was "
        "collected into the fresh working-tree digest, so the committed-tree "
        "restriction is not in effect on the verify check (slice-02 not yet "
        "delivered)"
    )


@then("the verify check reports the commit's scope as unverified")
def _then_reports_unverified(first_run) -> None:
    # Exit-code-exact: UNVERIFIED <=> exit 1. VERIFIED would mean the verify
    # check stopped witnessing the committed tree (OPT-a narrowing); REFUSED /
    # UNEXPECTED are WRONG modes -- all caught so the assertion never passes for
    # the wrong reason.
    assert first_run.outcome is VerifyOutcome.UNVERIFIED, (
        "a commit whose trailer no longer matches its committed contract suite "
        f"was NOT reported unverified (exit {first_run.exit_code}, outcome "
        f"{first_run.outcome.value!r}) -- the verify check stopped witnessing the "
        "whole committed tree (OPT-a contract-narrowing regression)"
    )


@then(
    "the whole committed tree's contract suite is still witnessed by the verify check"
)
def _then_whole_tree_witnessed(first_run) -> None:
    # Assert reason=="mismatch" specifically, NOT just the GateScopeUnverified
    # substring: the absent-trailer path ALSO emits GateScopeUnverified (with
    # reason="absent") and returns BEFORE the fresh digest is ever compared, so a
    # substring-only check is vacuous w.r.t. the slice-02 digest-source contract.
    # reason="mismatch" is reachable ONLY when a PRESENT trailer is compared
    # against a freshly-computed digest and they differ -- the genuine
    # committed-tree regression witness.
    combined = first_run.stdout + first_run.stderr
    payload = json.loads(_first_event(combined, "GateScopeUnverified"))
    assert payload.get("reason") == "mismatch", (
        "the verify check did not surface reason='mismatch' for a commit whose "
        "PRESENT trailer no longer matches its committed tree (got reason="
        f"{payload.get('reason')!r}) -- the committed-tree regression witness was "
        "lost, or the verdict fired via the absent-trailer path (a vacuous pass "
        "independent of the digest source the slice-02 fix changes)"
    )


@then("the verify check refuses to fingerprint a tree it cannot pin to a revision")
def _then_verify_refuses(first_run) -> None:
    # Exit-code-exact: REFUSED <=> exit 2 (the fail-closed committed-scope
    # INDETERMINATE path). VERIFIED / UNVERIFIED would mean it silently digested
    # the working tree of a non-git dir; UNEXPECTED is a WRONG mode.
    assert first_run.outcome is VerifyOutcome.REFUSED, (
        f"expected a fail-closed refusal (exit 2), got outcome "
        f"{first_run.outcome.value!r} (exit {first_run.exit_code}) -- the verify "
        "check did not refuse a tree it cannot pin to a committed revision "
        "(slice-02 must inherit the committed-scope git-absent LOUD refusal)"
    )


@then("the operator is loudly told the committed suite is indeterminate")
def _then_loud_indeterminate(first_run) -> None:
    combined = first_run.stdout + first_run.stderr
    assert COMMITTED_SCOPE_INDETERMINATE_EVENT in combined, (
        "no LOUD committed-scope INDETERMINATE health event surfaced for the "
        f"non-git tree (looked for {COMMITTED_SCOPE_INDETERMINATE_EVENT!r}) -- "
        "the verify check degraded SILENTLY instead of inheriting the "
        "committed-scope degrade-LOUD contract (slice-02 not yet delivered)"
    )


@then(
    "the verify check does not refuse the commit for a specification it cannot "
    "collect directly"
)
def _then_not_refused_for_feature(first_run, second_run) -> None:
    assert second_run.outcome is not VerifyOutcome.REFUSED, (
        f"the verify check REFUSED a commit pinning a committed mixed suite (exit "
        f"{second_run.exit_code}) -- a committed `.feature` spec was passed to "
        "pytest as a collection `--path` and pytest exited 4; the committed-scope "
        "wiring must exclude `.feature` from the explicit path-set (its scenarios "
        "are collected via their bound `@scenario` `.py` modules, so no coverage "
        "is lost)"
    )
