"""GitWorktreeRemovalSafetyAdapter -- git implementation of
WorktreeRemovalSafetyPort (lock status, dirty state, unmerged commits).

fix-worktree-removal-liveness-guard. `git worktree list --porcelain` already
emits a `locked` line per entry; the existing `_parse_worktree_porcelain` in
`git_worktree_adapter.py` deliberately discards it ("tolerated, no state
captured") because its callers never needed lock state. Rather than widen
that shared parser's contract for one new caller (two sibling changes
extending the same parsed shape can silently break an unrelated caller's
assumption of what fields are populated), this adapter carries its OWN
narrow, single-purpose porcelain parse -- mirroring how `CommitDiffPort` /
`CommitTreePathPort` each own a narrow git read rather than widening a
shared one.

`has_unmerged_commits` reuses `is_merged_contribution` (already shipped in
`git_subprocess.py` for the worktree-cleanup sweep) rather than re-deriving
the ancestor-vs-genuine-contribution distinction. `has_dirty_state` reuses
`GitWorktreeAdapter.has_uncommitted_changes` (`adapters/driven/refactor/
git_worktree_adapter.py`, the SAME `git status --porcelain` read the
worktree-cleanup sweep already trusts) rather than re-deriving the porcelain
parse for dirty state a second time -- that method returns a bare `bool`
(its callers assume git is present), so this adapter wraps the call with the
degrade-LOUD translation `WorktreeRemovalSafetyPort` requires.

git enters here ONLY (AD-21 git-free mandate). Every git failure -- binary
absent, non-work-tree, unresolvable ref, or the worktree not being a
registered entry at all -- degrades LOUD to `Indeterminate`, never a silent
"assume safe".

FIXED (fabricated-commit-count bugfix, 2026-07-29): `has_unmerged_commits`
used to synthesize a ONE-ELEMENT tuple holding an explanation string
(`f"unmerged into {target_branch!r}"`) whenever `is_merged_contribution`
conservatively refused (a proper-ancestor worktree with zero commits of its
own) AND `git log target..head` genuinely returned nothing. The caller
counts the tuple's length and reports "N commit(s)" -- so that fabricated
placeholder was counted and printed as "1 commit(s)", a number nobody
measured. A commit-subjects LIST and a REASON-FOR-UNCERTAINTY were being
carried in the same tuple, so the caller could not tell them apart; that
conflation was the defect, the wrong sentence only its symptom. Fixed by
returning `Indeterminate` for that case -- a real, separate channel this
port already declares -- never a synthetic tuple element. This does NOT
flip `is_merged_contribution`'s conservative refuse-to-remove direction:
`INDETERMINATE` blocks removal exactly as `ABANDONED_CANDIDATE` did (see
`worktree_removal_guard.py`'s consumption rule); only the REPORTED reason
changed, from a fabricated count to the true uncertainty.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import is_merged_contribution
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.ports.driven_ports.worktree_removal_safety_port import (
    Indeterminate,
    WorktreeRemovalSafetyPort,
)
from des.runtime.spawn import SpawnTimeout, spawn


if TYPE_CHECKING:
    from des.ports.driven_ports.git_worktree_port import GitWorktreePort


# Wall-clock bound for the two local git reads this adapter makes
# (`worktree list`, `log`) -- generous for a shared box under contention but
# never unbounded (RCA fix-inherited-stdin-deadlocks-spawns: every spawn in
# `src/des/**` must carry an explicit stdin decision + bound; `spawn()` is
# the general boundary that injects `stdin=DEVNULL` and enforces this).
_GIT_READ_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class _PorcelainWorktree:
    """One `git worktree list --porcelain` block, including its lock state."""

    path: Path
    head_sha: str | None
    branch: str | None
    locked: bool


def _parse_worktree_list_porcelain(output: str) -> list[_PorcelainWorktree]:
    """Parse `git worktree list --porcelain`, capturing the `locked` line.

    Narrow, single-purpose sibling of `git_worktree_adapter._parse_worktree_
    porcelain` -- that shared parser drops `locked` by design; this adapter
    is the one caller that needs it, so it owns its own parse rather than
    widening a contract other callers already depend on staying narrow.
    """
    entries: list[_PorcelainWorktree] = []
    path: Path | None = None
    head_sha: str | None = None
    branch: str | None = None
    locked = False

    def _flush() -> None:
        if path is not None:
            entries.append(
                _PorcelainWorktree(
                    path=path, head_sha=head_sha, branch=branch, locked=locked
                )
            )

    for line in output.splitlines():
        if line.startswith("worktree "):
            _flush()
            path = Path(line[len("worktree ") :])
            head_sha = None
            branch = None
            locked = False
        elif line.startswith("HEAD "):
            head_sha = line[len("HEAD ") :]
        elif line.startswith("branch "):
            branch = line[len("branch ") :]
        elif line == "locked" or line.startswith("locked "):
            locked = True
        # detached / prunable / bare: tolerated, no state captured
    _flush()
    return entries


class GitWorktreeRemovalSafetyAdapter(WorktreeRemovalSafetyPort):
    """Reads worktree lock status, dirty state, and unmerged-commit facts out of git."""

    def __init__(self, git_worktree_port: GitWorktreePort | None = None) -> None:
        # Injected for testability; defaults to the real adapter so
        # production callers need no wiring change (Reuse Analysis: compose
        # the EXISTING GitWorktreePort implementation rather than re-deriving
        # its `git status --porcelain` read).
        self._git_worktree_port: GitWorktreePort = (
            git_worktree_port or GitWorktreeAdapter()
        )

    def _list(self, repo: Path) -> list[_PorcelainWorktree] | Indeterminate:
        try:
            result = spawn(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=_GIT_READ_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except SpawnTimeout as exc:
            return Indeterminate(f"git worktree list timed out: {exc}")
        if result.returncode != 0:
            return Indeterminate(
                f"git worktree list failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        return _parse_worktree_list_porcelain(result.stdout)

    def _find(
        self, repo: Path, worktree_path: Path
    ) -> _PorcelainWorktree | Indeterminate | None:
        entries = self._list(repo)
        if isinstance(entries, Indeterminate):
            return entries
        resolved = worktree_path.resolve()
        for entry in entries:
            try:
                if entry.path.resolve() == resolved:
                    return entry
            except OSError:
                continue
        return None

    def is_locked(self, repo: Path, worktree_path: Path) -> bool | Indeterminate:
        entry = self._find(repo, worktree_path)
        if isinstance(entry, Indeterminate):
            return entry
        if entry is None:
            return Indeterminate(
                f"{worktree_path} is not a registered worktree of {repo} "
                "-- lock status unknown"
            )
        return entry.locked

    def has_unmerged_commits(
        self, repo: Path, worktree_path: Path, target_branch: str
    ) -> tuple[str, ...] | Indeterminate:
        entry = self._find(repo, worktree_path)
        if isinstance(entry, Indeterminate):
            return entry
        if entry is None:
            return Indeterminate(
                f"{worktree_path} is not a registered worktree of {repo} "
                "-- unmerged-commit status unknown"
            )
        if entry.head_sha is None:
            return Indeterminate(
                f"{worktree_path} has no resolvable HEAD (detached/bare) "
                "-- unmerged-commit status unknown"
            )
        try:
            merged = is_merged_contribution(repo, entry.head_sha, target_branch)
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        if merged:
            return ()
        try:
            result = spawn(
                ["git", "log", "--oneline", f"{target_branch}..{entry.head_sha}"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=_GIT_READ_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except SpawnTimeout as exc:
            return Indeterminate(f"git log timed out: {exc}")
        if result.returncode != 0:
            return Indeterminate(
                f"git log failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        subjects = tuple(line for line in result.stdout.splitlines() if line)
        if subjects:
            return subjects
        # `is_merged_contribution` refused (its conservative direction) yet
        # `target_branch..head_sha` is genuinely empty: `head_sha` is a
        # PROPER ancestor sitting on `target_branch`'s own first-parent
        # mainline (case 2 of `is_merged_contribution`'s docstring --
        # "target advanced past it", not "head's own work merged onto it").
        # Without a recorded creation base (worktrees here are made by many
        # surfaces, not one) this cannot be told apart from "head's work
        # never landed at all" -- report the real uncertainty. Returning a
        # synthetic placeholder string INSIDE the commit-subjects tuple (the
        # prior behavior) let the caller count it as "1 commit(s)" -- a
        # count that was never measured, not merely a vague message.
        return Indeterminate(
            f"{worktree_path} carries no commits of its own ahead of "
            f"{target_branch!r} (it sits as a proper ancestor on that "
            "branch's own mainline) -- with no recorded creation base, "
            "'nothing to merge' cannot be told apart from 'work that never "
            "landed', so unmerged-commit status is unknown"
        )

    def has_dirty_state(self, repo: Path, worktree_path: Path) -> bool | Indeterminate:
        entry = self._find(repo, worktree_path)
        if isinstance(entry, Indeterminate):
            return entry
        if entry is None:
            return Indeterminate(
                f"{worktree_path} is not a registered worktree of {repo} "
                "-- dirty-state unknown"
            )
        try:
            return self._git_worktree_port.has_uncommitted_changes(repo, worktree_path)
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except subprocess.CalledProcessError as exc:
            return Indeterminate(
                f"git status failed (exit {exc.returncode}): "
                f"{(exc.stderr or '').strip()[:200]}"
            )


__all__ = ["GitWorktreeRemovalSafetyAdapter"]
