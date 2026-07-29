"""Worktree anti-rot triage -- the Sentinel's read-only classification predicate, made real.

fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29). CORRECTED
same day, team-lead: this is NOT a new mechanism. `nWave/skills/nw-throughput/
SKILL.md`, section "Throughput Sentinel" (lines 123-129), already specifies
this predicate in prose, unimplemented until now:

    "Every pass performs worktree anti-rot triage. It inventories each linked
    worktree and its branch/head, dirty state, lock/PID evidence, owner
    receipt and recent host-log activity. A worktree becomes
    ABANDONED_CANDIDATE only when convergent evidence shows no live
    ownership/activity together with unintegrated or dirty work. The receipt
    names the evidence and offers exactly MERGE, RESUME, DEFER, or REMOVE.
    It never removes a worktree automatically; deletion remains
    human-authorized and separately verified."

This module IS that predicate. It is READ-ONLY by construction -- it returns
a `WorktreeAntiRotReceipt`, never mutates anything (no filesystem write, no
subprocess of its own -- callers pass in already-collected signals). The
removal-time GUARD (`scripts/hooks/worktree_removal_guard.py`) is a SEPARATE
component that CONSUMES the receipt to decide whether to refuse a `git
worktree remove` invocation. Keeping the two apart is not incidental: a
component that both judges AND deletes would violate the spec's own "never
removes a worktree automatically" constraint by construction.

TWO EVIDENCE CATEGORIES NAMED IN THE SPEC ARE NOT YET MECHANICALLY AVAILABLE
in this codebase, and are surfaced HONESTLY via `unavailable_evidence` rather
than silently omitted (flag the gap, don't resolve it silently -- this prose
was never executed before this module, so it may hold holes that only show
up on contact with real signals):
  - "owner receipt" -- no declared-ownership record exists for worktrees in
    this repo today. The Sentinel's broader "host receipt" concept
    (SKILL.md lines 90-96) covers agent/session CAPACITY, not per-worktree
    ownership -- a different fact.
  - "recent host-log activity" -- no host-log freshness reader exists for
    worktrees. The predecessor of this module considered raw HEAD/index
    mtime as a weak proxy and rejected it (redundant with PID+lock, adds
    false-positive noise without closing a gap those two miss) -- that
    rejection stands; a real host-log reader is a separate, larger build,
    not fabricated here to paper over the gap.

CONVERGENT EVIDENCE, NOT A SINGLE SIGNAL -- but only in ONE direction.
Per the spec + the team-lead correction: "a worktree is a candidate for
abandonment only when multiple signals agree. A single absent PID is not
enough." That binds declaring "no liveness" (CLEAN or ABANDONED_CANDIDATE):
BOTH available liveness-negative signals (no lock AND no live PID) must
agree before ruling out active use. It does NOT bind the opposite direction:
a single strong LIVE signal (an explicit lock, or a live process holding
cwd) is sufficient to classify LIVE immediately -- withholding a refusal
pending a second confirming signal would repeat the exact failure this
guard closes (one clean `git status` wrongly read as "safe").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from des.ports.driven_ports.committed_scope_port import Indeterminate


__all__ = [
    "RECOMMENDED_ACTIONS",
    "EvidenceItem",
    "ProcessMatch",
    "TriageState",
    "WorktreeAntiRotReceipt",
    "triage_worktree",
]


class TriageState(str, Enum):
    """The anti-rot classification.

    Only `ABANDONED_CANDIDATE` is named in the Sentinel prose. `LIVE` /
    `CLEAN` / `INDETERMINATE` are this predicate's own necessary completions
    of the state space (GDP-8: every property needs a definitive-true,
    definitive-false, AND a could-not-verify state -- the prose never had to
    say this explicitly because it was never executed against a real
    could-not-verify case before this module).
    """

    LIVE = "LIVE"
    CLEAN = "CLEAN"
    ABANDONED_CANDIDATE = "ABANDONED_CANDIDATE"
    INDETERMINATE = "INDETERMINATE"


#: The exactly-four actions the spec names for an ABANDONED_CANDIDATE receipt.
#: A human picks ONE; this predicate never picks for them.
RECOMMENDED_ACTIONS: tuple[str, ...] = ("MERGE", "RESUME", "DEFER", "REMOVE")

#: Evidence categories the spec names that this predicate cannot yet check
#: (see module docstring). Surfaced on EVERY receipt so a reader never
#: mistakes "not checked" for "checked and clear".
_UNAVAILABLE_EVIDENCE: tuple[str, ...] = ("owner-receipt", "recent-host-log-activity")


@dataclass(frozen=True)
class ProcessMatch:
    """One live process whose cwd resolves inside the worktree being triaged."""

    pid: int
    cwd: str


@dataclass(frozen=True)
class EvidenceItem:
    """One named fact the receipt cites (GDP-3: never withhold a computed fact)."""

    category: (
        str  # "pid" | "lock" | "dirty-state" | "unintegrated-work" | "*-indeterminate"
    )
    what: str
    why: str


@dataclass(frozen=True)
class WorktreeAntiRotReceipt:
    """The triage predicate's output. Read-only fact, never an action taken."""

    state: TriageState
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    actions: tuple[str, ...] = field(default_factory=tuple)
    unavailable_evidence: tuple[str, ...] = _UNAVAILABLE_EVIDENCE
    how: str = ""


_HOW_LIVE = (
    "This worktree is LIVE -- do not remove it. Wait for the process to "
    "exit, or run `git worktree unlock <path>` after confirming the lock "
    "reason with its owner, then re-triage."
)

_HOW_INDETERMINATE = (
    "Liveness could not be fully established (see the *-indeterminate "
    "evidence above for which probe failed and why). Fix the underlying "
    "probe, or -- ONLY after a HUMAN has confirmed removal is safe -- use "
    "the guard's authorised override (a non-trivial justification string, "
    'audited). "Could not tell" is never treated as "safe".'
)

_HOW_ABANDONED_CANDIDATE = (
    "No liveness evidence, but unintegrated or dirty work is at stake -- "
    "this needs a HUMAN decision among exactly four actions: MERGE the work "
    "in, RESUME work on it, DEFER the decision, or REMOVE it deliberately. "
    "This predicate never picks for you and never removes automatically."
)


def triage_worktree(
    *,
    target_path: str,
    process_matches: tuple[ProcessMatch, ...] | Indeterminate,
    locked: bool | Indeterminate,
    dirty: bool | Indeterminate,
    unmerged_commits: tuple[str, ...] | Indeterminate,
) -> WorktreeAntiRotReceipt:
    """Classify one worktree from its already-collected signals.

    `process_matches` + `locked` are the liveness axis ("lock/PID evidence"
    in the spec); `dirty` + `unmerged_commits` are the at-risk-work axis
    ("dirty state" + "branch/head" unintegrated work). ANY single live
    finding -> LIVE. No live finding but ANY axis could not be verified ->
    INDETERMINATE (the honest "not enough convergent evidence to call it
    clean" answer). Both liveness signals agree there is no life AND at
    least one at-risk finding exists -> ABANDONED_CANDIDATE. Both liveness
    signals agree there is no life AND nothing is at risk -> CLEAN (not
    "abandoned" at all -- there is nothing to decide).
    """
    live_evidence: list[EvidenceItem] = []
    atrisk_evidence: list[EvidenceItem] = []
    indeterminate_evidence: list[EvidenceItem] = []

    if isinstance(process_matches, Indeterminate):
        indeterminate_evidence.append(
            EvidenceItem(
                category="pid-indeterminate",
                what=f"process liveness for {target_path!r} could not be verified",
                why=process_matches.reason,
            )
        )
    elif process_matches:
        who = ", ".join(f"PID {m.pid} (cwd={m.cwd})" for m in process_matches)
        live_evidence.append(
            EvidenceItem(
                category="pid",
                what=f"{len(process_matches)} live process(es) hold a cwd inside "
                f"{target_path!r}: {who}",
                why="removing a worktree a process is currently working in "
                "corrupts that process's view mid-run (the incident this "
                "predicate closes: a pytest run crashed with FileNotFoundError "
                "on its own cwd when this exact removal happened).",
            )
        )

    if isinstance(locked, Indeterminate):
        indeterminate_evidence.append(
            EvidenceItem(
                category="lock-indeterminate",
                what=f"lock status for {target_path!r} could not be verified",
                why=locked.reason,
            )
        )
    elif locked:
        live_evidence.append(
            EvidenceItem(
                category="lock",
                what=f"{target_path!r} carries an explicit `git worktree lock`",
                why="a lock is a maintainer's own declaration that this "
                "worktree must not be touched yet -- honour it.",
            )
        )

    if isinstance(dirty, Indeterminate):
        indeterminate_evidence.append(
            EvidenceItem(
                category="dirty-state-indeterminate",
                what=f"dirty-state for {target_path!r} could not be verified",
                why=dirty.reason,
            )
        )
    elif dirty:
        atrisk_evidence.append(
            EvidenceItem(
                category="dirty-state",
                what=f"{target_path!r} has uncommitted changes (modified, "
                "staged, or untracked)",
                why="uncommitted work is not reachable from any commit -- "
                "removing the worktree destroys it outright, with no branch "
                "left to recover it from.",
            )
        )

    if isinstance(unmerged_commits, Indeterminate):
        indeterminate_evidence.append(
            EvidenceItem(
                category="unintegrated-work-indeterminate",
                what=f"unintegrated-work status for {target_path!r} could not "
                "be verified",
                why=unmerged_commits.reason,
            )
        )
    elif unmerged_commits:
        atrisk_evidence.append(
            EvidenceItem(
                category="unintegrated-work",
                what=f"{len(unmerged_commits)} commit(s) on {target_path!r}'s "
                f"branch are not yet integrated: {'; '.join(unmerged_commits[:5])}",
                why="removing a worktree holding unintegrated work is "
                "destruction, not cleanup.",
            )
        )

    all_evidence = tuple(live_evidence + indeterminate_evidence + atrisk_evidence)

    if live_evidence:
        return WorktreeAntiRotReceipt(
            state=TriageState.LIVE, evidence=all_evidence, how=_HOW_LIVE
        )
    if indeterminate_evidence:
        return WorktreeAntiRotReceipt(
            state=TriageState.INDETERMINATE,
            evidence=all_evidence,
            how=_HOW_INDETERMINATE,
        )
    if atrisk_evidence:
        return WorktreeAntiRotReceipt(
            state=TriageState.ABANDONED_CANDIDATE,
            evidence=all_evidence,
            actions=RECOMMENDED_ACTIONS,
            how=_HOW_ABANDONED_CANDIDATE,
        )
    return WorktreeAntiRotReceipt(state=TriageState.CLEAN)
