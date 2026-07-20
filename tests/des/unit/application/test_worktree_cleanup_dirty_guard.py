"""Dirty-tree guard: a worktree with uncommitted work is NEVER cleaned up.

Second half of the worktree-cleanup data-loss fix. The ancestry refinement
(``is_merged_contribution``) closes the "trunk advanced PAST a non-diverged
worktree" case, but it deliberately returns True when ``head_sha == tip`` --
so a worktree sitting EXACTLY at trunk's tip with ZERO commits of its own (the
normal starting state of every freshly-created worktree, before its first
commit) is still classified CLEANUP_DUE. When that worktree also holds
uncommitted work, an ACT-mode sweep force-removes it and the work is lost --
observed three times against this very branch during development.

The guard: uncommitted changes in a worktree make it UNSAFE to remove,
regardless of merge state. This is verified with pure in-process fake ports
(no real git, no subprocess) -- the ONLY isolation-safe way to exercise the
service, since the real ``GitWorktreeAdapter`` mutates a real repo.
"""

from __future__ import annotations

from pathlib import Path

from des.application.worktree_cleanup_service import WorktreeCleanupService
from des.domain.worktree_cleanup import (
    WorktreeCleanupVerdict,
    classify_worktree_cleanup_state,
)
from des.ports.driven_ports.git_worktree_port import (
    GitWorktreePort,
    MergeResult,
    WorktreeHandle,
)


# --- pure domain classifier (exhaustive truth table) ------------------------


def test_uncommitted_changes_block_cleanup_even_when_merged() -> None:
    verdict = classify_worktree_cleanup_state(
        worktree_registered=True, is_merged=True, has_uncommitted_changes=True
    )
    assert verdict is WorktreeCleanupVerdict.HAS_UNCOMMITTED_CHANGES


def test_merged_and_clean_is_cleanup_due() -> None:
    verdict = classify_worktree_cleanup_state(
        worktree_registered=True, is_merged=True, has_uncommitted_changes=False
    )
    assert verdict is WorktreeCleanupVerdict.CLEANUP_DUE


def test_not_merged_and_clean_is_not_yet_mergeable() -> None:
    verdict = classify_worktree_cleanup_state(
        worktree_registered=True, is_merged=False, has_uncommitted_changes=False
    )
    assert verdict is WorktreeCleanupVerdict.NOT_YET_MERGEABLE


def test_uncommitted_changes_block_cleanup_even_when_not_merged() -> None:
    verdict = classify_worktree_cleanup_state(
        worktree_registered=True, is_merged=False, has_uncommitted_changes=True
    )
    assert verdict is WorktreeCleanupVerdict.HAS_UNCOMMITTED_CHANGES


def test_unregistered_is_clean_regardless() -> None:
    verdict = classify_worktree_cleanup_state(
        worktree_registered=False, is_merged=True, has_uncommitted_changes=True
    )
    assert verdict is WorktreeCleanupVerdict.CLEAN


# --- service with pure fake ports (no real git) -----------------------------


class _FakeGitWorktree(GitWorktreePort):
    """In-memory GitWorktreePort double. Records removals; answers
    ``list_worktrees`` / ``has_uncommitted_changes`` from constructor state.
    Every mutation-lifecycle method a sweep never calls raises loudly."""

    def __init__(
        self, handles: tuple[WorktreeHandle, ...], dirty_paths: set[Path]
    ) -> None:
        self._handles = handles
        self._dirty_paths = dirty_paths
        self.removed_paths: list[Path] = []
        self.deleted_branches: list[str] = []

    def list_worktrees(self, repo: Path) -> tuple[WorktreeHandle, ...]:
        return self._handles

    def has_uncommitted_changes(self, repo: Path, path: Path) -> bool:
        return path in self._dirty_paths

    def remove_worktree(self, repo: Path, path: Path) -> None:
        self.removed_paths.append(path)

    def delete_branch(self, repo: Path, branch: str) -> None:
        self.deleted_branches.append(branch)

    def probe(self, repo: Path) -> bool:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def create_worktree_from_tip(
        self, repo: Path, branch: str, path: Path
    ) -> WorktreeHandle:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def merge_into(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> MergeResult:  # pragma: no cover - unused by sweep
        raise NotImplementedError

    def land_and_remove_integration(
        self, repo: Path, integration_branch: str
    ) -> bool:  # pragma: no cover - unused by sweep
        raise NotImplementedError


_REPO = Path("/fake/repo")
_WT = Path("/fake/repo-wt")


def _merged(_repo: Path, _head: str, _target: str) -> bool:
    return True


def _not_merged(_repo: Path, _head: str, _target: str) -> bool:
    return False


def test_service_never_removes_a_dirty_merged_worktree() -> None:
    handle = WorktreeHandle(path=_WT, branch="row4-plan", head_sha="a" * 40)
    fake = _FakeGitWorktree(handles=(handle,), dirty_paths={_WT})
    service = WorktreeCleanupService(git_worktree=fake, merge_check=_merged)

    result = service.sweep(repo=_REPO, target_branch="trunk", check_only=False)

    (entry,) = result.entries
    assert entry.verdict is WorktreeCleanupVerdict.HAS_UNCOMMITTED_CHANGES
    assert entry.removed is False
    assert fake.removed_paths == []
    assert fake.deleted_branches == []


def test_service_removes_a_clean_merged_worktree() -> None:
    handle = WorktreeHandle(path=_WT, branch="row4-plan", head_sha="a" * 40)
    fake = _FakeGitWorktree(handles=(handle,), dirty_paths=set())
    service = WorktreeCleanupService(git_worktree=fake, merge_check=_merged)

    result = service.sweep(repo=_REPO, target_branch="trunk", check_only=False)

    (entry,) = result.entries
    assert entry.verdict is WorktreeCleanupVerdict.CLEANUP_DUE
    assert entry.removed is True
    assert fake.removed_paths == [_WT]
    assert fake.deleted_branches == ["row4-plan"]
