"""Unit tests for `classify_sentinel` -- the Throughput Sentinel's scheduling
predicate (lane/sentinel-tool).

Each of the three defects the scratchpad prototype (`lyra-sentinel.py`)
actually produced becomes ONE test here, written so it would have caught the
defect: for the first two, the test ALSO calls the existing, already-shipped
production predicate (`triage_worktree`, `worktree_anti_rot_triage.py`) on
the exact same signals and asserts it gets the SAME wrong answer the
scratchpad script did -- proving the defect is not a strawman, but a live
gap in the currently-merged code that `classify_sentinel` closes by adding
the two axes `triage_worktree` does not have. `classify_sentinel` is then
asserted to get it right.
"""

from __future__ import annotations

from des.domain.worktree_anti_rot_triage import (
    EvidenceItem,
    TriageState,
    WorktreeAntiRotReceipt,
    triage_worktree,
)
from des.domain.worktree_sentinel_verdict import (
    RECENT_ACTIVITY_SECONDS,
    SentinelState,
    classify_sentinel,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


def test_defect_1_recent_activity_with_no_owner_and_no_process_is_owned_not_abandoned() -> (
    None
):
    """Defect #1: the scratchpad script collected HEAD/index mtime and never
    used it in the verdict -- it classified `ABANDONED_CANDIDATE` five
    worktrees whose lanes had been dispatched minutes earlier.

    Signals: a dirty worktree (work present), zero live processes, zero
    lock, unmerged commits present (so the reused anti-rot receipt alone
    says ABANDONED_CANDIDATE -- proven below against `triage_worktree`
    itself), but HEAD/index was touched 5 minutes ago. No declared owner
    either. `classify_sentinel` must read the recent activity and call this
    OWNED.
    """
    anti_rot = triage_worktree(
        target_path="/fake/wt-live-but-undeclared",
        process_matches=(),  # no live process -- the exact blind spot
        locked=False,
        dirty=True,
        unmerged_commits=("feat: work in progress",),
    )
    # Prove the gap is real and current: the EXISTING, shipped predicate,
    # given only the signals it has today, calls this ABANDONED_CANDIDATE.
    assert anti_rot.state is TriageState.ABANDONED_CANDIDATE

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=300,  # 5 minutes ago -- well under the hour floor
    )

    assert verdict.state is SentinelState.OWNED
    assert verdict.state is not SentinelState.ABANDONED_CANDIDATE


def test_defect_2_declared_ownership_outranks_zero_live_processes() -> None:
    """Defect #2: `live=0` was reported for a worktree with 132 changed files
    and an index touched 0 minutes earlier -- writes were happening with no
    detectable owner, because process presence only detects an agent during
    the seconds it happens to be running a command, not the far larger
    fraction of its life spent waiting on the model between tool calls.

    Signals here deliberately give NO activity corroboration either (stale
    activity age), isolating the claim to declared ownership ALONE: even
    with zero live processes, zero lock, and STALE activity, a declared
    owner must still be OWNED. The existing predicate has no ownership axis
    at all, so on the same dirty+unmerged signals it calls this
    ABANDONED_CANDIDATE too.
    """
    anti_rot = triage_worktree(
        target_path="/fake/wt-declared-but-quiet",
        process_matches=(),
        locked=False,
        dirty=True,
        unmerged_commits=("feat: still working",),
    )
    assert anti_rot.state is TriageState.ABANDONED_CANDIDATE

    verdict = classify_sentinel(
        declared_owned=True,
        declared_how="lane-owner marker present",
        anti_rot=anti_rot,
        activity_age_seconds=2 * RECENT_ACTIVITY_SECONDS,  # 2h, well past stale
    )

    assert verdict.state is SentinelState.OWNED
    assert verdict.offers == ()


def test_declared_owner_beats_live_evidence_too_and_names_the_declaration() -> None:
    """Declared ownership is the DECIDING axis -- it does not merely tie with
    live evidence, it is checked first and names itself in the evidence."""
    anti_rot = WorktreeAntiRotReceipt(state=TriageState.CLEAN)

    verdict = classify_sentinel(
        declared_owned=True,
        declared_how="--owned 'my-lane' (normalized match: 'mylane')",
        anti_rot=anti_rot,
        activity_age_seconds=Indeterminate("not read -- declared ownership decides"),
    )

    assert verdict.state is SentinelState.OWNED
    assert any(e.category == "declared-owner" for e in verdict.evidence)


def test_live_process_or_lock_evidence_is_owned_without_a_declaration() -> None:
    """A genuinely live/locked worktree the orchestrator forgot to declare
    must still read OWNED -- the physical LIVE signal corroborates ownership
    on its own; it is not degraded to UNDECIDABLE for lacking a marker."""
    anti_rot = WorktreeAntiRotReceipt(
        state=TriageState.LIVE,
        evidence=(EvidenceItem(category="pid", what="PID 4242 holds cwd", why="live"),),
        how="do not remove",
    )

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=Indeterminate("irrelevant -- LIVE decides first"),
    )

    assert verdict.state is SentinelState.OWNED


def test_an_unreadable_activity_signal_is_undecidable_never_guessed_as_abandoned() -> (
    None
):
    """GDP-8 arity corollary: a signal this predicate cannot read must be
    named UNDECIDABLE, never silently folded into ABANDONED_CANDIDATE (that
    would repeat defect #1's 'absence from silence' mistake in the other
    direction) and never folded into OWNED (that would hide a genuinely
    quiet, unowned worktree)."""
    anti_rot = triage_worktree(
        target_path="/fake/wt-unreadable-activity",
        process_matches=(),
        locked=False,
        dirty=True,
        unmerged_commits=(),
    )

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=Indeterminate("could not stat HEAD/index"),
    )

    assert verdict.state is SentinelState.UNDECIDABLE
    assert verdict.state is not SentinelState.ABANDONED_CANDIDATE
    assert verdict.state is not SentinelState.OWNED
    assert any(e.category == "activity-indeterminate" for e in verdict.evidence)


def test_an_indeterminate_anti_rot_receipt_is_also_undecidable() -> None:
    """The reused receipt's own INDETERMINATE state (e.g. `/proc` unreadable)
    must propagate to UNDECIDABLE too, even when activity WAS readable --
    one unresolved axis is enough to withhold a confident verdict."""
    anti_rot = triage_worktree(
        target_path="/fake/wt-proc-unreadable",
        process_matches=Indeterminate("permission denied reading /proc"),
        locked=False,
        dirty=True,
        unmerged_commits=(),
    )
    assert anti_rot.state is TriageState.INDETERMINATE

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=10,  # readable and recent -- still not enough
    )

    assert verdict.state is SentinelState.UNDECIDABLE


def test_no_owner_no_activity_no_risk_is_abandoned_candidate_with_remove_only() -> None:
    """A clean (no dirty state, no unmerged commits), quiet, undeclared
    worktree has nothing to merge or resume -- it is still an
    ABANDONED_CANDIDATE (the third state must not silently swallow 'nothing
    to lose'), but the only sane offer is REMOVE, not the full four-action
    menu."""
    anti_rot = WorktreeAntiRotReceipt(state=TriageState.CLEAN)

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=2 * RECENT_ACTIVITY_SECONDS,
    )

    assert verdict.state is SentinelState.ABANDONED_CANDIDATE
    assert verdict.offers == ("REMOVE",)


def test_no_owner_no_activity_at_risk_work_offers_all_four_actions() -> None:
    """Convergent evidence (no ownership AND no recent activity AND
    unintegrated-or-dirty work) is the ABANDONED_CANDIDATE contract's core
    positive case -- offers exactly the four named actions, unconditionally,
    a human picks one."""
    anti_rot = triage_worktree(
        target_path="/fake/wt-truly-abandoned",
        process_matches=(),
        locked=False,
        dirty=True,
        unmerged_commits=("old work",),
    )

    verdict = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=48 * 3600,  # 2 days, past the 36h anti-rot horizon
    )

    assert verdict.state is SentinelState.ABANDONED_CANDIDATE
    assert verdict.offers == ("MERGE", "RESUME", "DEFER", "REMOVE")


def test_activity_boundary_is_inclusive_at_the_recent_threshold() -> None:
    """Exactly `RECENT_ACTIVITY_SECONDS` old is NOT recent (the threshold is
    an upper-exclusive bound on 'recent'); one second younger is."""
    anti_rot = WorktreeAntiRotReceipt(state=TriageState.CLEAN)

    at_threshold = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=RECENT_ACTIVITY_SECONDS,
    )
    just_under = classify_sentinel(
        declared_owned=False,
        declared_how="",
        anti_rot=anti_rot,
        activity_age_seconds=RECENT_ACTIVITY_SECONDS - 1,
    )

    assert at_threshold.state is SentinelState.ABANDONED_CANDIDATE
    assert just_under.state is SentinelState.OWNED
