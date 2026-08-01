"""classify_sentinel -- the SCHEDULING-decision predicate over a worktree.

lane/sentinel-tool (team-lead dispatch 2026-07-30). Promotes the Throughput
Sentinel from an unversioned scratchpad script
(`/tmp/.../scratchpad/lyra-sentinel.py`) into tested, versioned production
code, closing three defects that scratch script produced in one afternoon:

  1. Collected an activity signal (HEAD/index mtime) and did not use it in
     the verdict -- classified `ABANDONED_CANDIDATE` five worktrees whose
     lanes were dispatched minutes earlier. Deducing absence from silence.
  2. Reported zero owners for a worktree with 132 changed files and an
     index touched 0 minutes earlier -- an LLM agent has no process for
     most of its life (it is waiting on the model between tool calls), so
     process-liveness is STRUCTURALLY incapable of establishing ownership.
  3. A declared-owner comparison that could not fire (name-normalization
     bug, `wt-wt-charterarm`) -- a fix that cannot fire, inside the patch
     meant to end that class.

REUSE, NOT REINVENTION (GDP-4). This module does NOT re-derive the
PID/lock/dirty/unmerged-commits evidence -- `des.domain.
worktree_anti_rot_triage.triage_worktree` (2026-07-29, already production,
already wired into `scripts/hooks/worktree_removal_guard.py` and the
periodic `worktree_sentinel_sweep`) already collects and classifies exactly
that evidence into `TriageState.{LIVE,CLEAN,ABANDONED_CANDIDATE,
INDETERMINATE}`. That module's OWN docstring names the two axes it cannot
supply -- "owner-receipt" and "recent-host-log-activity" -- as
`unavailable_evidence`, and its rejection of HEAD/index mtime as a signal
("redundant with PID+lock, adds false-positive noise") is the exact
reasoning defect #1 above falsifies with a concrete counterexample. This
module supplies the two missing axes ON TOP of the existing receipt,
without touching `triage_worktree` or its caller (the removal guard has a
narrower job -- "is it safe to `git worktree remove` RIGHT NOW" -- where a
lock or PID hit alone is sufficient grounds to refuse; changing its
semantics is out of this lane's scope and belongs to whoever owns that
gate).

WHY DECLARED OWNERSHIP OUTRANKS EVERY PHYSICAL SIGNAL. A dispatched-and-
unreleased lane is OWNED even while it shows zero live processes and zero
recent writes (the agent may be thinking, between tool calls, for minutes).
The physical signals (`TriageState.LIVE`, recent activity) exist to
CORROBORATE ownership for a lane that was never declared -- never to
override a declaration. See `worktree_activity_signal.py` for how ownership
is declared (a marker file the dispatching tool writes, `--owned` as a
manual fallback) and how a candidate name is matched against it (the
normalization that fixes defect #3).

Exactly three states reach the aggregate (GDP-8 arity corollary): a signal
this predicate cannot read is named `UNDECIDABLE`, never silently folded
into `ABANDONED_CANDIDATE` (that would repeat defect #1's "absence from
silence" mistake in the other direction) and never silently folded into
`OWNED` (that would hide a genuinely quiet, unowned worktree).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from des.domain.worktree_anti_rot_triage import (
    RECOMMENDED_ACTIONS,
    EvidenceItem,
    TriageState,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from des.domain.worktree_anti_rot_triage import WorktreeAntiRotReceipt


__all__ = [
    "RECENT_ACTIVITY_SECONDS",
    "SentinelState",
    "SentinelVerdict",
    "classify_sentinel",
]


class SentinelState(str, Enum):
    """The scheduling-relevant classification. Exactly three; see module
    docstring for why the third (`UNDECIDABLE`) must reach the aggregate."""

    OWNED = "OWNED"
    ABANDONED_CANDIDATE = "ABANDONED_CANDIDATE"
    UNDECIDABLE = "UNDECIDABLE"


#: A worktree touched within the hour is active, therefore not silence.
#: Mirrors the prototype's `RECENT` threshold (measured 2026-07-30 against
#: the dispatched lanes defect #1 misclassified).
RECENT_ACTIVITY_SECONDS = 3600


@dataclass(frozen=True)
class SentinelVerdict:
    """The Sentinel's per-worktree scheduling verdict. Read-only fact --
    this predicate never removes, merges, or dispatches anything."""

    state: SentinelState
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    offers: tuple[str, ...] = field(default_factory=tuple)
    how: str = ""


_HOW_OWNED_DECLARED = (
    "OWNED by declaration -- a dispatched-and-unreleased lane, regardless "
    "of what any physical signal shows. No action needed."
)
_HOW_OWNED_LIVE = "OWNED by live process/lock evidence. No action needed."
_HOW_OWNED_ACTIVE = (
    "OWNED by recent write activity -- HEAD or the index was touched "
    "within the last hour, even with zero declared owner and zero live "
    "process. No action needed."
)
_HOW_UNDECIDABLE = (
    "A required signal could not be read (see the evidence above for "
    "which probe failed and why). Do not infer absence from an unreadable "
    "signal -- fix the probe, or get a human read before deciding."
)
_HOW_ABANDONED_AT_RISK = (
    "No declared owner, no live process/lock, no recent activity, and "
    "unintegrated or dirty work is at stake -- this needs a HUMAN decision "
    "among exactly four actions: MERGE the work in, RESUME work on it, "
    "DEFER the decision, or REMOVE it deliberately. This predicate never "
    "picks for you and never removes automatically."
)
_HOW_ABANDONED_CLEAN = (
    "No declared owner, no live process/lock, no recent activity, and "
    "nothing at risk (no dirty state, no unmerged commits) -- REMOVE is "
    "the only action that applies, and it still requires a human to run it."
)


def classify_sentinel(
    *,
    declared_owned: bool,
    declared_how: str,
    anti_rot: WorktreeAntiRotReceipt,
    activity_age_seconds: int | Indeterminate,
) -> SentinelVerdict:
    """Classify one worktree's scheduling state from its already-collected
    signals.

    `declared_owned` + `declared_how` are the DECIDING axis (defect #2/#3).
    `anti_rot` is the EXISTING, reused receipt from `triage_worktree`
    (PID/lock/dirty/unmerged-commits). `activity_age_seconds` is the SECOND
    liveness axis this predicate adds (defect #1) -- seconds since HEAD or
    the index was last touched, or `Indeterminate` when that could not be
    read.

    Precedence, in order: declared ownership, then live process/lock
    evidence, then an unreadable signal (-> UNDECIDABLE, never guessed),
    then recent activity, then the at-risk/clean split of whatever remains.
    Each step is a single `if`, not a scoring function, so the precedence
    order is legible from the source rather than derived from weights.
    """
    if declared_owned:
        evidence = (
            EvidenceItem(
                category="declared-owner",
                what=f"declared owned: {declared_how}",
                why="declared ownership outranks every physical signal -- "
                "a dispatched-and-unreleased lane is OWNED even while it "
                "shows zero live processes and zero recent writes.",
            ),
            *anti_rot.evidence,
        )
        return SentinelVerdict(
            state=SentinelState.OWNED, evidence=evidence, how=_HOW_OWNED_DECLARED
        )

    if anti_rot.state is TriageState.LIVE:
        return SentinelVerdict(
            state=SentinelState.OWNED,
            evidence=anti_rot.evidence,
            how=_HOW_OWNED_LIVE,
        )

    indeterminate_evidence: list[EvidenceItem] = list(anti_rot.evidence)
    activity_unreadable = isinstance(activity_age_seconds, Indeterminate)
    if activity_unreadable:
        assert isinstance(activity_age_seconds, Indeterminate)  # narrow for mypy
        indeterminate_evidence.append(
            EvidenceItem(
                category="activity-indeterminate",
                what="HEAD/index touch-age could not be read",
                why=activity_age_seconds.reason,
            )
        )
    if activity_unreadable or anti_rot.state is TriageState.INDETERMINATE:
        return SentinelVerdict(
            state=SentinelState.UNDECIDABLE,
            evidence=tuple(indeterminate_evidence),
            how=_HOW_UNDECIDABLE,
        )

    assert isinstance(activity_age_seconds, int)  # narrowed: not Indeterminate above
    if activity_age_seconds < RECENT_ACTIVITY_SECONDS:
        evidence = (
            EvidenceItem(
                category="activity",
                what=f"HEAD or index touched {activity_age_seconds}s ago",
                why="recent write activity, even with zero declared owner "
                "and zero live process, is not silence -- an LLM agent has "
                "no process for most of its life (waiting on the model "
                "between tool calls), so process-cwd liveness alone cannot "
                "establish ownership.",
            ),
            *anti_rot.evidence,
        )
        return SentinelVerdict(
            state=SentinelState.OWNED, evidence=evidence, how=_HOW_OWNED_ACTIVE
        )

    stale_evidence = EvidenceItem(
        category="activity",
        what=f"HEAD/index quiet for {activity_age_seconds}s",
        why="no recent write activity to corroborate an undeclared owner.",
    )

    if anti_rot.state is TriageState.ABANDONED_CANDIDATE:
        return SentinelVerdict(
            state=SentinelState.ABANDONED_CANDIDATE,
            evidence=(stale_evidence, *anti_rot.evidence),
            offers=RECOMMENDED_ACTIONS,
            how=_HOW_ABANDONED_AT_RISK,
        )

    # anti_rot.state is CLEAN: no declared owner, no live/lock evidence, no
    # recent activity, and (per triage_worktree's own contract) nothing at
    # risk either -- still an ABANDONED_CANDIDATE (the third state must not
    # silently swallow "nothing to lose"), but the only sane offer is REMOVE.
    return SentinelVerdict(
        state=SentinelState.ABANDONED_CANDIDATE,
        evidence=(
            stale_evidence,
            EvidenceItem(
                category="clean-and-quiet",
                what="no dirty state and no unmerged commits",
                why="nothing at risk -- REMOVE is the only action that applies.",
            ),
        ),
        offers=("REMOVE",),
        how=_HOW_ABANDONED_CLEAN,
    )
