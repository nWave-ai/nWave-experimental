"""sweep_worktrees -- the Sentinel's enumerator over the anti-rot triage predicate.

CREATE_NEW (sentinel-sweep-enumerator, team-lead dispatch 2026-07-29). Closes
the GDP-1 gap named in `docs/mikado/EXECUTION-SSOT-des-optimization.md`
section SENTINEL: `des.domain.worktree_anti_rot_triage.triage_worktree` had
exactly ONE caller in the whole tree -- `scripts/hooks/worktree_removal_
guard.py`, which triages a worktree only AT THE MOMENT someone tries to
remove it (the latest possible intercept point). Nobody swept the linked-
worktree SET periodically (the earliest possible point), despite `nWave/
skills/nw-throughput/SKILL.md` claiming every Sentinel pass "inventories
each linked worktree" -- that sentence had no producer until this module.

REUSE, not reinvention (GDP-4, and the corollary this very incident names:
"a predicate without an enumerator forces every caller to invent its own
population, and an invented population is usually wrong"):

- The POPULATION comes from `GitWorktreePort.list_worktrees`, an EXISTING,
  already-tested port+adapter built for the refactor-drain cleanup sweep
  (`des.adapters.driven.refactor.git_worktree_adapter.GitWorktreeAdapter`).
  This module does NOT re-parse `git worktree list --porcelain` itself.
- The per-worktree SIGNAL COLLECTION + triage call comes from
  `des.application.worktree_triage_collector.collect_worktree_triage_receipt`
  -- the SAME function `worktree_removal_guard.py` uses (extracted from it
  in this same change). This module does NOT re-derive the four-signal
  collection.
- The CLASSIFICATION decision comes from `triage_worktree` itself, untouched.

READ-ONLY BY CONSTRUCTION: `sweep_worktrees` returns a `WorktreeSweepReport`
-- a snapshot of receipts -- and never mutates, merges, or removes anything.
Deletion stays human-authorized (the removal guard's job), never this
sweep's; a sweep that could delete would be a different, more dangerous tool.

NO ENTRY IS EVER DROPPED OR COLLAPSED (GDP-8 arity corollary, the reason
this module exists at all): every handle `list_worktrees` returns gets
exactly one `WorktreeSweepEntry`, whatever state its receipt carries --
`LIVE`, `CLEAN`, `ABANDONED_CANDIDATE`, or `INDETERMINATE`. An enumerator
that silently filtered out the states it found inconvenient would recreate,
one layer up, the exact "invented, wrong population" defect this module was
built to close.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.application.worktree_triage_collector import collect_worktree_triage_receipt


if TYPE_CHECKING:
    from des.domain.worktree_anti_rot_triage import TriageState, WorktreeAntiRotReceipt
    from des.ports.driven_ports.git_worktree_port import GitWorktreePort, WorktreeHandle


#: The signature `collect_worktree_triage_receipt` and every test double for
#: it must satisfy -- injected so tests can substitute a stub without faking
#: `/proc` or a real git tree (see `worktree_triage_collector` for the real
#: implementation this defaults to).
TriageCollector = Callable[[Path, Path, "str | None"], "WorktreeAntiRotReceipt"]


@dataclass(frozen=True)
class WorktreeSweepEntry:
    """One linked worktree's identity paired with its triage receipt."""

    handle: WorktreeHandle
    receipt: WorktreeAntiRotReceipt


@dataclass(frozen=True)
class WorktreeSweepReport:
    """The whole sweep's result: every linked worktree registered against the
    repo, each triaged exactly once. Never partial, never re-derived by a
    caller -- this IS the inventory the Sentinel skill's prose promised."""

    entries: tuple[WorktreeSweepEntry, ...]

    def by_state(self, state: TriageState) -> tuple[WorktreeSweepEntry, ...]:
        """Filter for reporting/routing -- does not change what was swept."""
        return tuple(entry for entry in self.entries if entry.receipt.state is state)


def sweep_worktrees(
    repo: Path,
    worktree_port: GitWorktreePort,
    target_branch: str | None,
    collect_receipt: TriageCollector = collect_worktree_triage_receipt,
) -> WorktreeSweepReport:
    """Enumerate every linked worktree registered against `repo` and triage
    each one.

    `target_branch` is passed through to `collect_receipt` for EVERY entry:
    the unmerged-commits axis always asks "unintegrated relative to WHAT"
    against the same one reference branch across the whole sweep, never a
    different one per worktree. Pass `None` when no reference branch could
    be resolved -- every entry then carries an Indeterminate unmerged-commits
    signal rather than a silently wrong "assume merged" for the whole sweep.

    `collect_receipt` defaults to the real, `/proc`+git-backed collector;
    tests inject a stub here instead of faking `/proc` or a git tree.
    """
    handles = worktree_port.list_worktrees(repo)
    entries = tuple(
        WorktreeSweepEntry(
            handle=handle,
            receipt=collect_receipt(repo, handle.path, target_branch),
        )
        for handle in handles
    )
    return WorktreeSweepReport(entries=entries)


__all__ = [
    "TriageCollector",
    "WorktreeSweepEntry",
    "WorktreeSweepReport",
    "sweep_worktrees",
]
