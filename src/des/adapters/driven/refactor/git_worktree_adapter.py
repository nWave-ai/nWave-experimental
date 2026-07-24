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
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.git.git_mutate import git_run
from des.adapters.driven.git.git_subprocess import git_text
from des.ports.driven_ports.git_worktree_port import (
    GitWorktreePort,
    MergeResult,
    WorktreeHandle,
)


@dataclass(frozen=True)
class _PorcelainEntry:
    """One ``git worktree list --porcelain`` block, minimally parsed.

    ``head_sha``/``branch`` are ``None`` when the block never carried the
    corresponding line (e.g. a detached-HEAD entry has no ``branch`` line).
    """

    path: Path
    head_sha: str | None
    branch: str | None


def _parse_worktree_porcelain(output: str) -> list[_PorcelainEntry]:
    """Parse ``git worktree list --porcelain`` into one entry per block.

    Shared parsing primitive behind both ``_worktree_path_for_branch`` and
    ``list_worktrees`` (parallel-work-cleans-up-after-merge-back, D-1
    generalize-not-duplicate). Tolerant of ``locked``/``prunable``/
    ``detached``/``bare`` line kinds -- they are skipped without being
    misparsed as a new ``worktree``/``branch`` pair.
    """
    entries: list[_PorcelainEntry] = []
    path: Path | None = None
    head_sha: str | None = None
    branch: str | None = None

    def _flush() -> None:
        if path is not None:
            entries.append(_PorcelainEntry(path=path, head_sha=head_sha, branch=branch))

    for line in output.splitlines():
        if line.startswith("worktree "):
            _flush()
            path = Path(line[len("worktree ") :])
            head_sha = None
            branch = None
        elif line.startswith("HEAD "):
            head_sha = line[len("HEAD ") :]
        elif line.startswith("branch "):
            branch = line[len("branch ") :]
        # detached / locked / prunable / bare: tolerated, no state captured
    _flush()
    return entries


def _porcelain_status_paths(status: str) -> list[str]:
    """The path each ``git status --porcelain`` line refers to.

    Porcelain v1 emits ``XY <path>``; a rename/copy emits ``XY <old> -> <new>``
    and the NEW path is the one that exists in the working tree, so that is the
    one reported. Paths git had to quote (whitespace / non-ASCII) are unquoted,
    so a caller can compare them against a path as the operator wrote it.
    """
    paths: list[str] = []
    for line in status.splitlines():
        entry = line[3:].strip()
        if not entry:
            continue
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1].strip()
        paths.append(entry.strip('"'))
    return paths


def _short_branch(ref: str | None) -> str | None:
    if ref is None:
        return None
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


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

# The harness's OWN telemetry directory (``AtCompletionLedger`` -- the
# ``self._ledger.append_gate_event`` call every drained item makes) writes
# ``.nwave/telemetry/...`` inside ``repo`` too -- the SAME "never git's
# business" category as the pile files above (slice-02 latent-bug fix: a
# batch's SECOND merge_into call is the first caller to ever re-run this
# dirty check after a ledger write has already landed; slice-01's single-item
# ``drain_one`` never exercised this path, since its own ledger write always
# happens strictly AFTER its one and only merge).
_HARNESS_BOOKKEEPING_DIR_PREFIX = ".nwave/"

_PROBE_BRANCH = "refactor-probe-health-check"
_PROBE_DIR_SUFFIX = "-refactor-probe"


class GitWorktreeAdapter(GitWorktreePort):
    """Real adapter -- worktree lifecycle over ``git_run``/``git_text``."""

    def is_linked_worktree(self, repo: Path) -> bool:
        """True iff ``repo`` is a linked worktree sharing a common ``.git``.

        A linked worktree resolves ``git rev-parse --git-common-dir`` to a
        DIFFERENT path than ``--git-dir`` (the main checkout resolves both to
        the same ``.git``). Paths are compared resolved-absolute so a relative
        ``--git-dir`` (git prints ``.git`` for the main checkout) never spoofs
        a mismatch. Degrades to ``False`` when ``repo`` is not a git repo at
        all -- ``git rev-parse`` then exits non-zero and ``git_text`` raises;
        that case is a separate, existing refusal (the git-repo startup probe),
        not a linked worktree."""
        try:
            git_dir = git_text(repo, "rev-parse", "--absolute-git-dir").strip()
            common_dir = git_text(
                repo, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).strip()
        except subprocess.CalledProcessError:
            return False
        if not git_dir or not common_dir:
            return False
        return Path(git_dir).resolve() != Path(common_dir).resolve()

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

    def land_and_remove_integration(self, repo: Path, integration_branch: str) -> bool:
        operator_branch = git_text(repo, "branch", "--show-current").strip()
        if not operator_branch or operator_branch == integration_branch:
            # Detached HEAD (no branch to land onto), or the operator is
            # standing ON the integration branch itself: keep it for recovery,
            # never land onto / delete the branch we are on.
            return False
        if self._is_dirty(repo):
            # Never fast-forward the operator's live working tree while it is
            # dirty (D4's own rationale) -- keep the integration branch for
            # human recovery instead of forcing the land.
            return False
        git_run(repo, "merge", "-q", "--no-edit", integration_branch)
        git_run(repo, "branch", "-d", integration_branch)
        return True

    def has_uncommitted_changes(self, repo: Path, path: Path) -> bool:
        """True iff ``path``'s working tree has any uncommitted change.

        Reads ``git status --porcelain`` rooted at the worktree itself (never
        ``repo``): modified, staged, AND untracked entries all count -- the
        dirty-tree guard errs toward PRESERVING work, so any non-empty status
        blocks the worktree's removal."""
        return bool(git_text(path, "status", "--porcelain").strip())

    def uncommitted_paths(self, repo: Path) -> tuple[str, ...]:
        """Every repo-relative path ``git status --porcelain`` reports as dirty.

        The SAME single read ``has_uncommitted_changes`` performs, kept
        path-resolved instead of collapsed to a bool (see the port's docstring
        for why the refusal path needs the paths themselves).

        Degrades to the port's own empty "nothing known here" default when git
        cannot answer at all -- ``repo`` is not a repository, or no ``git``
        exists on this target machine (the git-free mandate: git is an
        optional driven-adapter capability, never a hard requirement). A
        refusal that could not run the detection still renders its generic
        explanation; it never claims a clean tree it did not observe."""
        try:
            status = git_text(repo, "status", "--porcelain")
        except (subprocess.CalledProcessError, OSError):
            return ()
        return tuple(_porcelain_status_paths(status))

    def list_worktrees(self, repo: Path) -> tuple[WorktreeHandle, ...]:
        """Enumerate every LINKED worktree registered against ``repo``.

        EXTEND (parallel-work-cleans-up-after-merge-back, D-1 reuse):
        generalizes ``_worktree_path_for_branch``'s porcelain parsing into a
        public, full-enumeration read over the SAME seam. Only the main
        worktree is excluded -- a detached-HEAD entry IS included
        (detached-worktree-excluded-from-cleanup-sweep bugfix): the
        cleanup gate classifies merge state via ``head_sha`` ancestry
        (``WorktreeCleanupService._sweep_one``), never ``branch``
        presence, so there is no reason to drop it from the scan.

        Main-worktree identity is derived from GIT'S OWN reported order --
        ``git worktree list`` always lists the main worktree FIRST,
        regardless of ``repo``'s own path -- never from ``repo.resolve()``
        path-equality. This matters when ``repo`` IS a linked worktree
        (e.g. a crafter running from inside its own ephemeral worktree):
        path-equality would have wrongly excluded ``repo`` itself (mistaken
        for "main") while including the REAL main repository as a sweep
        candidate -- a corrected latent defect, safety-relevant now that a
        caller may pass a linked worktree as ``repo``."""
        output = git_text(repo, "worktree", "list", "--porcelain")
        parsed = _parse_worktree_porcelain(output)
        if not parsed:
            return ()
        main_path = parsed[0].path.resolve()
        return tuple(
            WorktreeHandle(
                path=entry.path,
                branch=_short_branch(entry.branch),
                head_sha=entry.head_sha,
            )
            for entry in parsed
            if entry.path.resolve() != main_path and entry.head_sha is not None
        )

    # -- internal: branch/worktree resolution --------------------------------

    def _worktree_path_for_branch(self, repo: Path, branch: str) -> Path | None:
        output = git_text(repo, "worktree", "list", "--porcelain")
        for entry in _parse_worktree_porcelain(output):
            if entry.branch is None:
                continue
            if entry.branch in (f"refs/heads/{branch}", branch):
                return entry.path
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
            not _is_harness_bookkeeping_path(path) for path in _status_paths(status)
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


def _is_harness_bookkeeping_path(path: str) -> bool:
    return path in _PILE_BOOKKEEPING_FILENAMES or path.startswith(
        _HARNESS_BOOKKEEPING_DIR_PREFIX
    )
