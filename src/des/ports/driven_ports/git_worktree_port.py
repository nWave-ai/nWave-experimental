"""GitWorktreePort -- driven port for the fixer-swarm's worktree lifecycle.

CREATE_NEW (des-refactor-fixer-swarm, ADR-SWARM-001). No existing worktree-
lifecycle Port/ABC exists; ``CommitVerifier`` is the nearest existing git-domain
port but covers only Step-Id-trailer commit verification (Reuse Analysis).

Every mutation the implementing adapter performs MUST route through the existing
``git_run``/``git_text`` seams (AD-21/AD-22 single-seam mandate) -- this port
only declares the SHAPE the drain lifecycle needs (D1 worktree-from-tip, D4/D5
merge-into-a-clean-branch, D5/D6 confirmed-merge-gated cleanup).

Pure interface -- no behavior to scaffold. The concrete adapter
(``des.adapters.driven.refactor.git_worktree_adapter.GitWorktreeAdapter``)
carries the Mandate-7 RED scaffold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class WorktreeHandle:
    """Observable identity of a created worktree (D1's witness)."""

    path: Path
    branch: str
    head_sha: str


@dataclass(frozen=True)
class MergeResult:
    """Observable outcome of a merge-into-integration-branch attempt (D4/D5)."""

    merged: bool
    blocked_reason: str | None = None


class GitWorktreePort(ABC):
    """Driven port: the worktree-from-tip / merge-into-clean / cleanup lifecycle."""

    @abstractmethod
    def probe(self, repo: Path) -> bool:
        """Earned-Trust startup probe (principle 13): create+remove a throwaway
        worktree in ``repo`` before any real item drains. A probe failure MUST
        refuse the harness's start (``health.startup.refused``), never a silent
        per-item failure later."""
        ...

    @abstractmethod
    def create_worktree_from_tip(
        self, repo: Path, branch: str, path: Path
    ) -> WorktreeHandle:
        """Cut a worktree from the CURRENT branch tip (D1) -- never a stale
        ancestor, never the Agent-tool ``isolation: worktree`` mode."""
        ...

    @abstractmethod
    def merge_into(
        self, repo: Path, integration_branch: str, source_branch: str
    ) -> MergeResult:
        """Merge ``source_branch`` into the DEDICATED clean ``integration_branch``
        (D4/D5). Refuses with a named ``MergeBlockedDirtyTree`` reason when the
        integration branch's tree is dirty -- never a silent skip, never a
        corrupting 3-way attempt."""
        ...

    @abstractmethod
    def remove_worktree(self, repo: Path, path: Path) -> None:
        """``git worktree remove`` (never ``rm -rf``, which leaves a dangling
        ``.git/worktrees`` registration). Caller invokes this ONLY after a
        CONFIRMED merge (D5/D6)."""
        ...

    @abstractmethod
    def delete_branch(self, repo: Path, branch: str) -> None:
        """Delete the item's branch. Caller invokes this ONLY after a CONFIRMED
        merge -- an unmerged branch is NEVER deleted (D5/D6)."""
        ...
