"""WorktreeRemovalSafetyPort -- driven port over git-observable evidence for
the worktree anti-rot triage predicate (lock status, dirty state, unmerged
commits).

fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29). Three of the
Sentinel's five named evidence categories (`nWave/skills/nw-throughput/
SKILL.md` "Throughput Sentinel") are git facts, not OS facts: (a) has this
worktree been explicitly `git worktree lock`ed ("lock/PID evidence") -- the
mechanism a lane in the source incident already reached for, unprompted,
AFTER the damage; (b) does the worktree carry uncommitted changes ("dirty
state"); and (c) does the worktree's branch carry commits the target branch
does not have yet ("branch/head" + unintegrated work). All three need git;
per `feedback_target_machine_independence_2026_05_15` (AD-21) the triage
predicate (`des.domain.worktree_anti_rot_triage`) stays git-free and git
enters ONLY behind this read-only driven port, degrading LOUD
(`Indeterminate`, reused from `committed_scope_port`) -- never silent.

Mirrors `CommitDiffPort`: abstract port here, real
adapter in `adapters/driven/git/`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["Indeterminate", "WorktreeRemovalSafetyPort"]


class WorktreeRemovalSafetyPort(ABC):
    """Driven, read-only port over one worktree's git-observable removal safety."""

    @abstractmethod
    def is_locked(self, repo: Path, worktree_path: Path) -> bool | Indeterminate:
        """True iff `worktree_path` carries an explicit `git worktree lock`.

        Reuses the mechanism that already exists rather than inventing a
        parallel one. Indeterminate when git is absent, `repo` is not a
        work tree, or `worktree_path` is not a registered worktree of `repo`.
        """
        ...

    @abstractmethod
    def has_unmerged_commits(
        self, repo: Path, worktree_path: Path, target_branch: str
    ) -> tuple[str, ...] | Indeterminate:
        """The worktree branch's commit subjects NOT yet merged into `target_branch`.

        An empty tuple means fully merged. Indeterminate when git is
        absent, either ref is unresolvable, or `worktree_path` is not a
        registered worktree of `repo`.
        """
        ...

    @abstractmethod
    def has_dirty_state(self, repo: Path, worktree_path: Path) -> bool | Indeterminate:
        """True iff `worktree_path`'s working tree carries uncommitted changes.

        The Sentinel's "dirty state" evidence category -- distinct from
        unmerged COMMITS: a worktree can be fully merged and still hold
        staged/unstaged/untracked work that was never committed at all, and
        that work is unrecoverable once the worktree is removed. Indeterminate
        when git is absent or `worktree_path` is not a work tree.
        """
        ...
