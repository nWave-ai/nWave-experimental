"""Pure classifier: (worktree_registered, is_merged) -> WorktreeCleanupVerdict.

CREATE_NEW (parallel-work-cleans-up-after-merge-back slice-01, D-D4,
ADR-SWARM-002). No existing classifier maps a worktree's registration + merge
state to a cleanup verdict; ``evaluate_done_gate``
(``des.domain.environmental_e2e.done_gate``) is the nearest existing analog,
cited as the closed-enum-over-state PATTERN this module mirrors -- design-time
pattern reuse, not a code dependency (Reuse Analysis).

Pure function, no I/O, no mutation (principle 12). Consumed by
``WorktreeCleanupService`` as the functional core deciding what should happen
to each worktree the driven port observes -- the service supplies the
state-based facts (``list_worktrees`` registration, ``is_ancestor`` merge
check, D-D2); this module never reads git itself.
"""

from __future__ import annotations

from enum import Enum


class WorktreeCleanupVerdict(str, Enum):
    """Closed 4-value classification of one worktree's cleanup state.

    | registered | uncommitted | merged | verdict                 |
    |------------|-------------|--------|-------------------------|
    | False      | *           | *      | CLEAN                   |
    | True       | True        | *      | HAS_UNCOMMITTED_CHANGES |
    | True       | False       | True   | CLEANUP_DUE             |
    | True       | False       | False  | NOT_YET_MERGEABLE       |

    The uncommitted-changes row is checked BEFORE merge state: a worktree
    holding uncommitted work is never safe to remove, however merged its
    committed history is -- removing it would lose that work (the data-loss
    the dirty-tree guard exists to prevent).
    """

    CLEAN = "CLEAN"
    CLEANUP_DUE = "CLEANUP_DUE"
    NOT_YET_MERGEABLE = "NOT_YET_MERGEABLE"
    HAS_UNCOMMITTED_CHANGES = "HAS_UNCOMMITTED_CHANGES"


def classify_worktree_cleanup_state(
    worktree_registered: bool,
    is_merged: bool,
    has_uncommitted_changes: bool = False,
) -> WorktreeCleanupVerdict:
    """The pure fact: given registration, uncommitted-work, and confirmed-merge
    state, what verdict.

    An unregistered worktree is already CLEAN regardless (nothing left to act
    on). A registered worktree holding uncommitted work is
    HAS_UNCOMMITTED_CHANGES -- left alone whatever its merge state, because
    removing it would lose that work (a worktree at trunk's tip with zero
    commits of its own but live edits is the exact data-loss case: its
    committed history looks "merged", yet its working tree is not). A
    registered, clean, confirmed-merged worktree is CLEANUP_DUE (removal is
    safe). A registered, clean, not-yet-merged worktree is NOT_YET_MERGEABLE.

    Only CLEANUP_DUE is a removal candidate (D-D4: mutation is structurally
    reachable only for CLEANUP_DUE).
    """
    if not worktree_registered:
        return WorktreeCleanupVerdict.CLEAN
    if has_uncommitted_changes:
        return WorktreeCleanupVerdict.HAS_UNCOMMITTED_CHANGES
    if is_merged:
        return WorktreeCleanupVerdict.CLEANUP_DUE
    return WorktreeCleanupVerdict.NOT_YET_MERGEABLE


__all__ = ["WorktreeCleanupVerdict", "classify_worktree_cleanup_state"]
