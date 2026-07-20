"""DISTILL-interim wire-contract extension for slice-02 (premature-removal
refusal) -- charter
`removing-a-worktree-before-its-merge-is-confirmed-is-refused.md`,
feature-delta Slice Plan row slice-02, Locked Decision D-3, ADR-SWARM-002.

REUSES slice-01's `nwave.worktree_cleanup.v1` envelope as its base (D-D4:
"zero new plumbing" for the STRUCTURAL refusal mechanism -- `remove_worktree`
/`delete_branch` are already unreachable for a NOT_YET_MERGEABLE entry).
This file adds THREE observables slice-01's own `CleanupSweepOutcome` never
needed:

- `target_verdict` -- the SCOPED entry's own verdict string (`NOT_YET_MERGEABLE`
  expected here);
- `has_reason` -- the charter's own oracle demands the refusal come "with a
  message naming that the merge-back has not happened yet", not merely a
  terse enum code. Pins a small, additive DISTILL-interim wire-contract
  extension (mirrors slice-01's own DISTILL-interim pin, same precedent):
  when a sweep is SCOPED to ONE worktree via `--worktree` (a maintainer's
  explicit removal attempt, per this charter's own Preconditions) and that
  entry's verdict is `NOT_YET_MERGEABLE`, the entry gains an additional
  `"reason"` string key (GDP-3 self-explaining, presence-checked -- exact
  wording not pinned, mirrors slice-01's own `has_what_why_how` presence-only
  pattern):
      {"path": <str>, "branch": <str>, "verdict": "NOT_YET_MERGEABLE",
       "removed": false, "reason": <str>}
  This is genuinely NEW plumbing (a small CLI-layer presentation addition,
  `verify_worktree_cleanup.py` only -- no domain/application/port change),
  distinct from D-D4's STRUCTURAL "zero new plumbing" claim about the
  removal-gating mechanism itself, which stays untouched;
- a direct-git commit-reachability read (the charter's own oracle names
  `git log`/reachability as the observation surface, independent of the
  CLI's own payload).
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain_types_slice_01 import CleanupSweepOutcome


@dataclass(frozen=True)
class PrematureRemovalOutcome(CleanupSweepOutcome):
    """Extends slice-01's `CleanupSweepOutcome` (Mandate 8 Universe) with the
    three observables slice-02's refusal oracle needs. Every inherited field
    keeps its slice-01 meaning unchanged.
    """

    target_verdict: str | None = None
    has_reason: bool = False
    commit_reachable: bool | None = None


__all__ = ["PrematureRemovalOutcome"]
