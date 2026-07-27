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
    """Observable identity of a created worktree (D1's witness).

    ``branch`` is ``None`` for a detached-HEAD worktree (``git worktree add
    --detach``) -- it has no branch line to report (detached-worktree-
    excluded-from-cleanup-sweep bugfix). ``create_worktree_from_tip`` always
    creates a branched worktree, so its own return value's ``branch`` is
    never ``None``; only a `list_worktrees`-enumerated entry can be."""

    path: Path
    branch: str | None
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

    @abstractmethod
    def land_and_remove_integration(self, repo: Path, integration_branch: str) -> bool:
        """Land the drained fix onto the operator's OWN branch, then remove the
        now-redundant integration branch (D5/D6 'nothing is left behind').

        The integration branch is the clean merge VEHICLE (D4), never the
        deliverable: fast-forward the operator's currently checked-out branch
        onto it so the fix becomes reachable from the maintainer's own
        ``git log`` (charter positive oracle), then delete the integration
        branch (charter negative oracle: no branch the run created survives it).

        Returns ``True`` iff the fix was landed AND the integration branch
        removed. Returns ``False`` WITHOUT deleting anything when there is no
        operator branch to land onto (detached HEAD) or the operator tree is
        dirty -- the integration branch then SURVIVES for human recovery,
        never silently dropped and never force-merged into a dirty tree. Caller
        invokes this ONLY after a CONFIRMED merge into the integration branch."""
        ...

    @abstractmethod
    def has_uncommitted_changes(self, repo: Path, path: Path) -> bool:
        """True iff the worktree at ``path`` has uncommitted work (modified,
        staged, or untracked) in its working tree.

        EXTEND (worktree-cleanup dirty-tree guard). The cleanup sweep consults
        this BEFORE removing a confirmed-merged worktree: a worktree holding
        uncommitted work must NEVER be force-removed, however merged its
        committed history is -- removing it would discard that work (the
        data-loss the guard prevents). Read LIVE, per-worktree."""
        ...

    @abstractmethod
    def list_worktrees(self, repo: Path) -> tuple[WorktreeHandle, ...]:
        """Enumerate every LINKED worktree registered against ``repo``.

        EXTEND (parallel-work-cleans-up-after-merge-back, D-1 reuse, D-D1).
        Excludes the main worktree itself. Each ``head_sha`` is read LIVE
        (current HEAD, not a creation-time snapshot) -- the cleanup gate's
        "confirmed merged" state-check depends on currency."""
        ...

    def uncommitted_paths(self, repo: Path) -> tuple[str, ...]:
        """The repo-relative paths carrying uncommitted work in ``repo``'s OWN
        working tree -- modified, staged, renamed or untracked.

        The path-RESOLVED sibling of ``has_uncommitted_changes``: that one
        collapses a whole worktree to the yes/no the cleanup guard asks; this
        one names WHICH paths, which is what an operator-facing refusal needs
        in order to say "the copy of YOUR fixer that ran was the committed
        one". A bare bool cannot carry that -- a repo is almost always dirty
        somewhere (an untracked pile file is enough), so only the per-path
        answer distinguishes "your fixer is shadowed" from "some unrelated
        file is dirty".

        Concrete (NOT abstract) so it is a safe, additive extension: every
        existing implementer -- including in-memory test doubles that never
        touch a real git tree -- inherits the empty default unchanged, exactly
        as ``is_linked_worktree`` does. The empty tuple means, and only means,
        "no uncommitted path is known here" -- never "this tree is provably
        clean" (GDP-6: absence of evidence is never reported as evidence of
        absence)."""
        return ()

    def changed_paths_since(self, repo: Path, base_sha: str) -> tuple[str, ...]:
        """Repo-relative paths that differ between ``base_sha`` and the
        CURRENT state of ``repo``'s working tree -- committed changes
        (``git diff --name-only base_sha..HEAD``) UNION uncommitted ones
        (``uncommitted_paths``), deduplicated.

        EXTEND ([[impacted-test-selector-selects-everything-and-its-premise-
        is-false]]): the drain's "after" test run needs to know what the
        dispatched agent actually touched, whether it committed the fix,
        left it uncommitted, or both -- this is that single combined view.

        Concrete (NOT abstract), same safe-additive-extension pattern as
        ``uncommitted_paths``: every existing implementer, including in-
        memory test doubles that never touch a real git tree, inherits the
        empty default unchanged. The empty tuple means only "no changed path
        is known here" -- never "nothing changed" as a positive claim."""
        return ()

    def is_linked_worktree(self, repo: Path) -> bool:
        """True iff ``repo`` is a LINKED worktree -- one whose worktree/branch/
        checkout mutations land in a ``.git`` SHARED with sibling worktrees
        (``git rev-parse --git-common-dir`` != ``--git-dir``).

        Concrete (NOT abstract) so it is a safe, additive extension: every
        existing implementer -- including in-memory test doubles that never
        touch a real shared ``.git`` -- inherits the ``False`` default
        unchanged. Only a real git-backed adapter overrides it. The drain
        service consults this BEFORE the startup worktree probe so a run
        against a linked worktree is refused before it can corrupt the
        operator's shared refs/HEAD."""
        return False
