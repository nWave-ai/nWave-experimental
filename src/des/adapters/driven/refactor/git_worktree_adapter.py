"""GitWorktreeAdapter -- GitWorktreePort implementation via git_run/git_text.

CREATE_NEW file (des-refactor-fixer-swarm slice-01). Every mutation this adapter
performs MUST route through the existing ``git_run`` seam
(``des.adapters.driven.git.git_mutate``, AD-21); every read through the existing
``git_text`` seam (``des.adapters.driven.git.git_subprocess``, AD-22) -- no
second git-subprocess helper (Reuse Analysis).

Implements worktree-from-tip (D1), the venv-hygiene + dirty-tree merge-into
guard (D4/D5), and confirmed-merge-gated cleanup (D5/D6).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.adapters.driven.git.git_mutate import git_run
from des.adapters.driven.git.git_subprocess import git_text
from des.ports.driven_ports.git_worktree_port import (
    GitWorktreePort,
    MergeResult,
    WorktreeHandle,
)


_VENV_DIR_NAME = ".venv"

# The harness's OWN per-item scratch file (the rendered prompt handed to
# agent_cmd, written into the worktree BEFORE dispatch -- see
# RefactorDrainService._dispatch_agent). It is ephemeral orchestration state,
# never a deliverable of the item's own fix -- committing it would make two
# independently-drained items' branches collide on an add/add conflict at the
# SAME path with DIFFERENT (per-item) content the moment both get merged into
# the same integration branch. It must never be staged/committed at all.
_PROMPT_SCRATCH_FILENAME = ".refactor-prompt.md"

# The harness's OWN bookkeeping files (Interface = the pile, feature-delta
# Value section) always sit uncommitted next to the repo -- they are never
# git's business and must never be mistaken for operator dirt when deciding
# whether the integration branch's tree is safe to merge into.
_PILE_BOOKKEEPING_FILENAMES = frozenset({"techdebt.md", "paidtechdebt.md"})

_PROBE_BRANCH = "refactor-probe-health-check"
_PROBE_DIR_SUFFIX = "-refactor-probe"


class GitWorktreeAdapter(GitWorktreePort):
    """Real adapter -- worktree lifecycle over ``git_run``/``git_text``."""

    def probe(self, repo: Path) -> bool:
        probe_path = repo.parent / f"{repo.name}{_PROBE_DIR_SUFFIX}"
        try:
            git_run(
                repo, "worktree", "add", "-b", _PROBE_BRANCH, str(probe_path), "HEAD"
            )
        except subprocess.CalledProcessError:
            return False
        git_run(repo, "worktree", "remove", "--force", str(probe_path))
        git_run(repo, "branch", "-D", _PROBE_BRANCH)
        return True

    def create_worktree_from_tip(
        self, repo: Path, branch: str, path: Path
    ) -> WorktreeHandle:
        head_sha = git_text(repo, "rev-parse", "HEAD").strip()
        git_run(repo, "worktree", "add", "-b", branch, str(path), "HEAD")
        return WorktreeHandle(path=path, branch=branch, head_sha=head_sha)

    def merge_into(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> MergeResult:
        source_worktree = self._worktree_path_for_branch(repo, source_branch)
        if source_worktree is not None:
            blocked = self._refuse_if_venv_staged(source_worktree)
            if blocked is not None:
                return blocked
            self._commit_pending_changes(source_worktree, source_branch)

        self._ensure_branch(repo, integration_branch)
        if self._is_dirty(repo):
            return MergeResult(merged=False, blocked_reason="MergeBlockedDirtyTree")

        self._perform_merge(repo, integration_branch, source_branch)
        return MergeResult(merged=True)

    def remove_worktree(self, repo: Path, path: Path) -> None:
        git_run(repo, "worktree", "remove", "--force", str(path))

    def delete_branch(self, repo: Path, branch: str) -> None:
        git_run(repo, "branch", "-D", branch)

    # -- internal: branch/worktree resolution --------------------------------

    def _worktree_path_for_branch(self, repo: Path, branch: str) -> Path | None:
        output = git_text(repo, "worktree", "list", "--porcelain")
        current: Path | None = None
        for line in output.splitlines():
            if line.startswith("worktree "):
                current = Path(line[len("worktree ") :])
                continue
            if line.startswith("branch ") and current is not None:
                ref = line[len("branch ") :]
                if ref in (f"refs/heads/{branch}", branch):
                    return current
        return None

    def _ensure_branch(self, repo: Path, branch: str) -> None:
        existing = git_text(repo, "branch", "--list", branch)
        if existing.strip():
            return
        git_run(repo, "branch", branch)

    # -- internal: the .venv hygiene guard (D4) ------------------------------

    def _refuse_if_venv_staged(self, worktree: Path) -> MergeResult | None:
        staged = git_text(worktree, "diff", "--name-only", "--cached")
        for path in _lines(staged):
            if _is_venv_path(path):
                return MergeResult(
                    merged=False, blocked_reason="MergeBlockedVenvStaged"
                )
        return None

    def _commit_pending_changes(self, worktree: Path, source_branch: str) -> None:
        paths = self._changed_paths_excluding_venv(worktree)
        if not paths:
            return
        git_run(worktree, "add", "--", *paths)
        git_run(worktree, "commit", "-q", "-m", f"refactor: drain {source_branch}")

    def _changed_paths_excluding_venv(self, worktree: Path) -> list[str]:
        status = git_text(worktree, "status", "--porcelain")
        return [
            path
            for path in _status_paths(status)
            if not _is_venv_path(path) and path != _PROMPT_SCRATCH_FILENAME
        ]

    # -- internal: integration-branch dirty check + merge (D5) ---------------

    def _is_dirty(self, repo: Path) -> bool:
        status = git_text(repo, "status", "--porcelain")
        return any(
            path not in _PILE_BOOKKEEPING_FILENAMES for path in _status_paths(status)
        )

    def _perform_merge(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> None:
        current = git_text(repo, "branch", "--show-current").strip()
        git_run(repo, "checkout", "-q", integration_branch)
        try:
            git_run(repo, "merge", "-q", "--no-edit", source_branch)
        finally:
            if current:
                git_run(repo, "checkout", "-q", current)


def _status_paths(porcelain_output: str) -> list[str]:
    return [line[3:].strip() for line in porcelain_output.splitlines() if line.strip()]


def _lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def _is_venv_path(path: str) -> bool:
    return path == _VENV_DIR_NAME or path.startswith(f"{_VENV_DIR_NAME}/")
