"""WorktreeCleanupService -- the mechanical worktree-cleanup sweep (D-D4).

CREATE_NEW (parallel-work-cleans-up-after-merge-back slice-01, ADR-SWARM-002).
``RefactorDrainService`` is the nearest existing analog -- an application-layer
service composing a ``GitWorktreePort`` through a classifier -- cited as the
composition-root SHAPE this service mirrors (port-injected, application
layer), not code it calls (Reuse Analysis).

Contract: bounded-change. Universe: every LINKED worktree currently
registered against the repo (an unbounded, operator-controlled set). Delta:
mutates (``remove_worktree``/``delete_branch``) ONLY the subset whose
``classify_worktree_cleanup_state`` verdict is ``CLEANUP_DUE`` -- itself
gated by the ``is_ancestor`` state-check (D-D2/D-D4) -- every other worktree
in the universe is read, never written. ``--check-only`` (``check_only=True``
here) narrows the whole sweep to a pure read: mutation is structurally
unreachable regardless of verdict (D-2/D-3).

The service has no workflow-controller or telemetry dependency; cleanup safety
is protected by construction through the injected Git port and classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from des.domain.worktree_cleanup import (
    WorktreeCleanupVerdict,
    classify_worktree_cleanup_state,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.git_worktree_port import GitWorktreePort, WorktreeHandle


class MergeCheck(Protocol):
    """The ``is_merged_contribution(repo, head_sha, target_ref) -> bool`` seam
    (``des.adapters.driven.git.git_subprocess.is_merged_contribution``,
    D-D2/D-D7).

    Answers "did this worktree's OWN work genuinely merge onto the target?" --
    strictly stronger than bare ``is_ancestor``, which is TRUE both for a real
    merge AND for a non-diverged worktree that trunk merely advanced past (the
    data-loss false-positive this seam exists to reject)."""

    def __call__(self, repo: Path, head_sha: str, target_ref: str) -> bool: ...


@dataclass(frozen=True)
class WorktreeCleanupEntry:
    """One worktree's outcome for one sweep -- one row of the CLI's payload.

    ``branch`` is ``None`` for a detached-HEAD worktree (detached-worktree-
    excluded-from-cleanup-sweep bugfix)."""

    path: str
    branch: str | None
    verdict: WorktreeCleanupVerdict
    removed: bool


@dataclass(frozen=True)
class WorktreeCleanupSweepResult:
    """Observable outcome of one full sweep (Mandate 8 port-exposed universe)."""

    entries: tuple[WorktreeCleanupEntry, ...]

    @property
    def has_unresolved_cleanup_due(self) -> bool:
        """True iff a CLEANUP_DUE entry survives the sweep un-removed --
        the GDP-3 refusal condition (D-2 enforcing gate)."""
        return any(
            entry.verdict is WorktreeCleanupVerdict.CLEANUP_DUE and not entry.removed
            for entry in self.entries
        )


class WorktreeCleanupService:
    """Application-layer composition root: the cleanup sweep."""

    def __init__(
        self, *, git_worktree: GitWorktreePort, merge_check: MergeCheck
    ) -> None:
        self._git_worktree = git_worktree
        self._merge_check = merge_check

    def sweep(
        self,
        *,
        repo: Path,
        target_branch: str,
        check_only: bool,
        scope_to: Path | None = None,
    ) -> WorktreeCleanupSweepResult:
        """Sweep every registered worktree (or the ONE named by ``scope_to``,
        path-keyed per DESIGN Open Question #3)."""
        handles = self._git_worktree.list_worktrees(repo)
        if scope_to is not None:
            resolved_scope = scope_to.resolve()
            handles = tuple(h for h in handles if h.path.resolve() == resolved_scope)
        entries = tuple(
            self._sweep_one(repo, target_branch, check_only, handle)
            for handle in handles
        )
        return WorktreeCleanupSweepResult(entries=entries)

    def _sweep_one(
        self,
        repo: Path,
        target_branch: str,
        check_only: bool,
        handle: WorktreeHandle,
    ) -> WorktreeCleanupEntry:
        is_merged = self._merge_check(repo, handle.head_sha, target_branch)
        has_uncommitted = self._git_worktree.has_uncommitted_changes(repo, handle.path)
        verdict = classify_worktree_cleanup_state(
            worktree_registered=True,
            is_merged=is_merged,
            has_uncommitted_changes=has_uncommitted,
        )
        removed = False
        if verdict is WorktreeCleanupVerdict.CLEANUP_DUE and not check_only:
            self._git_worktree.remove_worktree(repo, handle.path)
            if handle.branch is not None:
                self._git_worktree.delete_branch(repo, handle.branch)
            removed = True
        return WorktreeCleanupEntry(
            path=str(handle.path),
            branch=handle.branch,
            verdict=verdict,
            removed=removed,
        )


__all__ = [
    "MergeCheck",
    "WorktreeCleanupEntry",
    "WorktreeCleanupService",
    "WorktreeCleanupSweepResult",
]
