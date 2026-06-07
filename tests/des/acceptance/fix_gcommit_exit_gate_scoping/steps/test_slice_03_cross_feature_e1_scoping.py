"""Step definitions for fix-gcommit-exit-gate-scoping slice-03 (Mandate-12).

slice-03 (E1 cross-feature scoping) -- the G_COMMIT exit-gate completeness check
(E1, `verify_slice_commit_completeness`) must be invoked SCOPED to the committing
feature (`resolved.project_id`), so its `.feature` candidate scan no longer
collides with a CO-RESIDENT feature's `@slice-NN` tags.

These ATs are genuine RED at HEAD 6020dc76b: the hook invokes E1 with no feature
scope (`subagent_stop_handler.py:618-630`), so E1 falls back to a WHOLE-TREE
`rglob("*.feature")` -> a co-resident foreign feature B carrying the SAME
`@slice-01` value as the committing feature A is demanded inside A's commit ->
the intercept blocks with `slice-commit-completeness gate failed (e1=1, ...)`,
the reason naming `tests/feat-beta/acceptance.feature`. AT-A (cross-feature
isolation) therefore fails for MISSING_FUNCTIONALITY -- the commit is blocked on
a FOREIGN feature's file. AT-C (single certification) fails because the blocked
commit is never certified (zero records). AT-B (genuine incompleteness) pins the
anti-vacuity guard.

Step bodies delegate to `GcommitE1ScopingComposition` -- no inline business
logic (Mandate-12 criterion 3). Domain nouns are typed via
`domain_types_slice_03` (criterion 1); the composition service signatures consume
those typed parameters (criterion 2).

Mandate-13: the SUT is driven exclusively through the real `handle_subagent_stop`
SubagentStop hook as a Layer-3 composition/wiring black-box (see
`composition_slice_03`) -- the same gate the U2 G_COMMIT exit-gate runs behind.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import GcommitE1ScopingComposition, InterceptRun
from .domain_types_slice_03 import (
    CoResidentState,
    E1Outcome,
    OwnSliceState,
)


scenarios("../slice-03-cross-feature-e1-scoping.feature")


# The foreign feature's repo-relative specification path -- the file the unscoped
# whole-tree completeness scan cross-binds into the committing feature's commit.
_FOREIGN_FEATURE_SPEC = "tests/feat-beta/acceptance.feature"


@pytest.fixture
def composition() -> GcommitE1ScopingComposition:
    """The production composition root driving the real SubagentStop hook."""
    return GcommitE1ScopingComposition()


# ===========================================================================
# Given
# ===========================================================================


@given(
    "the committing feature has committed its own slice specification",
    target_fixture="repo",
)
def _given_own_slice_committed(composition: GcommitE1ScopingComposition, tmp_path):
    """Precondition: the committing feature's own slice .feature is in the commit."""
    return composition.make_two_feature_commit(tmp_path, OwnSliceState.COMMITTED)


@given(
    "the committing feature authored its own slice specification but kept it out "
    "of the commit",
    target_fixture="repo",
)
def _given_own_slice_uncommitted(composition: GcommitE1ScopingComposition, tmp_path):
    """Precondition: the committing feature's own slice .feature is NOT committed."""
    return composition.make_two_feature_commit(
        tmp_path, OwnSliceState.AUTHORED_BUT_NOT_COMMITTED
    )


@given("a second feature carrying the same slice number sits beside it on the tree")
def _given_coresident_second_feature(composition: GcommitE1ScopingComposition, repo):
    """Precondition: a co-resident foreign feature sharing the slice tag on-tree."""
    composition.place_coresident_feature(
        repo, CoResidentState.PRESENT_SHARING_SLICE_TAG
    )


# ===========================================================================
# When
# ===========================================================================


@when(
    "the exit gate checks the committing feature's slice commit",
    target_fixture="intercept",
)
def _when_exit_gate_checks(
    composition: GcommitE1ScopingComposition, repo
) -> InterceptRun:
    """Drive the real G_COMMIT SubagentStop intercept over the two-feature repo."""
    return composition.run_g_commit_intercept(repo)


# ===========================================================================
# Then
# ===========================================================================


@then("the slice commit's completeness check passes")
def _then_completeness_passes(intercept: InterceptRun) -> None:
    # E1Outcome lifts the completeness verdict out of the block reason's
    # `e1=N` token (COMPLETE <=> e1=0, or a verified ALLOW). INCOMPLETE here
    # means the unscoped whole-tree scan cross-bound the foreign feature's
    # specification into this commit; INDETERMINATE is a WRONG mode -- both
    # caught so the assertion never passes for the wrong reason.
    assert intercept.e1_outcome is E1Outcome.COMPLETE, (
        "the committing feature's slice commit was NOT found complete "
        f"(e1 outcome {intercept.e1_outcome.value!r}; block reason "
        f"{intercept.block_reason!r}) -- the completeness check ran a "
        "WHOLE-TREE scan and demanded a co-resident SECOND feature's "
        "specification inside this commit (E1 cross-feature collision; "
        "slice-03 feature scoping not yet wired into the hook)"
    )


@then("the second feature's specification was not demanded in the commit")
def _then_foreign_spec_not_demanded(intercept: InterceptRun) -> None:
    # The cross-feature collision surfaces as the foreign feature's spec path
    # named in the incomplete-completeness block reason. Its ABSENCE from the
    # reason (and a COMPLETE verdict) proves the scan was scoped to the
    # committing feature.
    reason = intercept.block_reason or ""
    assert _FOREIGN_FEATURE_SPEC not in reason, (
        "the completeness check demanded the SECOND feature's specification "
        f"({_FOREIGN_FEATURE_SPEC!r}) inside the committing feature's commit -- "
        f"its whole-tree scan cross-bound the foreign feature's @slice-01 tag "
        f"(block reason {intercept.block_reason!r}); the scan was not scoped to "
        "the committing feature (slice-03 not yet delivered)"
    )
    assert intercept.e1_outcome is E1Outcome.COMPLETE, (
        "the completeness check did not pass for the committing feature "
        f"(e1 outcome {intercept.e1_outcome.value!r})"
    )


@then(
    "the slice commit's completeness check fails for the committing feature's "
    "own missing specification"
)
def _then_own_missing_still_fails(intercept: InterceptRun) -> None:
    # Anti-vacuity guard: scoping the check to the committing feature must NOT
    # mask a genuinely incomplete commit. The committing feature authored its
    # own @slice-01 specification but kept it OUT of the commit -> the check
    # must STILL report INCOMPLETE (e1=1). A COMPLETE verdict here would mean
    # the scoping fix turned the check into an always-pass.
    assert intercept.e1_outcome is E1Outcome.INCOMPLETE, (
        "a commit that genuinely omits the committing feature's OWN slice "
        f"specification was NOT rejected (e1 outcome "
        f"{intercept.e1_outcome.value!r}; block reason {intercept.block_reason!r})"
        " -- scoping the completeness check to the committing feature must not "
        "turn a genuinely incomplete commit into an always-pass (anti-vacuity "
        "guard)"
    )


@then("the slice commit is certified exactly once for the slice")
def _then_certified_exactly_once(intercept: InterceptRun) -> None:
    # The seam discriminator. Seam A (E1-only scoping) leaves the hook the SOLE
    # author of the SliceCommitVerified record -> exactly one. The rejected
    # Seam B (passing `--feature-id`, flipping the completeness CLI into
    # verify-then-record) would run the contract check a SECOND time AND write a
    # DUPLICATE certification record -> two. At HEAD the commit is BLOCKED by the
    # cross-feature collision so it is never certified -> zero records (the RED
    # witness). After the Seam-A fix the verified commit is certified exactly
    # once.
    assert intercept.verified_record_count == 1, (
        "the verified slice commit was not certified exactly once "
        f"(SliceCommitVerified record count = {intercept.verified_record_count}) "
        "-- zero means the commit was blocked (the cross-feature collision at "
        "HEAD, or the contract half refused); two means the completeness check "
        "was scoped via the verify-then-record seam (rejected Seam B) which "
        "double-runs the contract check and writes a duplicate certification "
        "record. Seam A (E1-only scoping) certifies exactly once"
    )
