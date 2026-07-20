"""Regression AT (bugfix `conftest-pollution-guard-shared-git`): the autouse
`_git_pollution_guard` fixture AND the session-scoped `guard_git_hooks` fixture
(`tests/conftest.py`) perform a DIRECT-FILE restore (`write_bytes` / `unlink`)
of `.git/{config,HEAD,refs/}` and `.git/hooks/` on the COMMON git dir whenever
their detective diff is non-empty. That restore assumes the guard is the SOLE
writer of the common `.git`.

RCA: under the swarm-parallel-delivery methodology this repo runs MANY linked
worktrees sharing ONE common `.git`. `des feature-end run` executes the full
suite (`pytest -m "unit or integration or acceptance"`) over the whole `tests/`
tree with `cwd=repo`, so the autouse guard fires per-test for the run's entire
duration. When a SIBLING worktree legitimately creates a NEW branch (a fresh
loose ref) or moves HEAD/config, the guard's diff flags it as "pollution" and
`_atomic_restore_git_state` / `_restore_hooks_dir` CLOBBER that sibling's work
via direct file write -- no reflog entry, silently eaten. The existing
`_is_descendant_ref_advance` exemption only covers a commit ON AN EXISTING
branch; new-branch creation and config/HEAD moves are NOT exempt.

Oracle (the fix, authored in `tests/conftest.py`): a pure filesystem detector
`_common_git_dir_is_shared(common_dir)` reports whether the common dir is
shared with live linked worktrees (a non-empty `worktrees/` subdir). When
SHARED, the DESTRUCTIVE restore is skipped in BOTH primitives -- degrade to
WARN-ONLY -- because a sibling worktree's legitimate change is indistinguishable
from this test's pollution and must never be clobbered. When EXCLUSIVE (a
standalone clone, no `worktrees/`), the single-writer restore behavior is
preserved UNCHANGED -- this is a safety-relaxation for the shared case only,
never a removal of protection for the normal case.

Safety: every scenario runs against a THROWAWAY standalone repo under
`tmp_path` (scoped by `GIT_CEILING_DIRECTORIES`), with the "shared" condition
SIMULATED by `mkdir .git/worktrees/<name>` -- a plain directory marker, exactly
what git writes when a linked worktree is created. No live linked worktree, and
this repo's own `.git`, is ever touched.

Reuse: follows `tests/test_guard_fixtures.py`'s isolated-repo fixture pattern
(`_init_isolated_repo`, `_create_initial_commit` imported, not re-implemented)
and `tests/bugs/des/test_git_pollution_guard_respects_concurrent_writer.py`'s
plumbing helpers -- no new harness.

Scenarios:
  D  detector unit --
     `test_common_git_dir_is_shared_detects_live_worktrees`
  T1 POSITIVE (config/HEAD/refs restore, the bug) --
     `test_atomic_restore_skips_when_common_dir_shared`
  T2 NEGATIVE/invariance pin (exclusive dir still restores) --
     `test_atomic_restore_still_restores_when_common_dir_exclusive`
  T3 POSITIVE (new-branch-by-sibling, the specific gap) --
     `test_new_branch_by_sibling_not_clobbered_when_shared`
  T4 POSITIVE (hooks restore, the sibling defect) --
     `test_restore_hooks_dir_skips_when_common_dir_shared`
  T5 NEGATIVE/invariance pin (hooks restore, exclusive dir) --
     `test_restore_hooks_dir_still_restores_when_common_dir_exclusive`
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.conftest import (
    _atomic_restore_git_state,
    _common_git_dir_is_shared,
    _compute_git_state_snapshot,
    _resolve_git_common_dir,
    _restore_hooks_dir,
    _snapshot_hooks_dir,
)
from tests.test_guard_fixtures import _create_initial_commit, _init_isolated_repo


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers (git plumbing scoped via GIT_CEILING_DIRECTORIES, mirroring
# tests/test_guard_fixtures.py + the concurrent-writer regression file).
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str, input_text: str | None = None) -> str:
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
    )
    return result.stdout.strip()


def _mark_shared(repo_root: Path, name: str = "sibling") -> None:
    """Simulate a live linked worktree by creating the `worktrees/<name>`
    entry git writes into the common dir when a worktree is added. A plain
    directory -- no live worktree, no shared state beyond this marker."""
    (repo_root / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)


def _ref_path(repo_root: Path, ref: str) -> Path:
    return repo_root / ".git" / ref


# ---------------------------------------------------------------------------
# D -- detector unit test.
# ---------------------------------------------------------------------------


def test_common_git_dir_is_shared_detects_live_worktrees(tmp_path: Path) -> None:
    """Pure detector: a standalone clone (no `worktrees/`) is EXCLUSIVE; the
    moment a linked worktree exists (`worktrees/<name>/`) it is SHARED; an
    empty `worktrees/` dir (all worktrees pruned) is EXCLUSIVE again."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    common_dir = _resolve_git_common_dir(repo_root)

    assert _common_git_dir_is_shared(common_dir) is False, (
        "A standalone clone with no worktrees/ subdir must be reported "
        "EXCLUSIVE so single-writer restore is preserved."
    )

    (common_dir / "worktrees").mkdir(exist_ok=True)
    assert _common_git_dir_is_shared(common_dir) is False, (
        "An EMPTY worktrees/ dir (all linked worktrees pruned) is exclusive."
    )

    (common_dir / "worktrees" / "sibling").mkdir()
    assert _common_git_dir_is_shared(common_dir) is True, (
        "A worktrees/<name>/ entry means a live linked worktree shares this "
        "common dir -- must be reported SHARED so destructive restore is "
        "skipped."
    )


# ---------------------------------------------------------------------------
# T1 -- POSITIVE (the bug): shared common dir => restore is a no-op.
# ---------------------------------------------------------------------------


def test_atomic_restore_skips_when_common_dir_shared(tmp_path: Path) -> None:
    """When the common `.git` is shared with live linked worktrees,
    `_atomic_restore_git_state` must NOT write/delete any ref/config/HEAD --
    a direct-file restore would silently clobber a sibling worktree's work."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    seed = _git(repo_root, "rev-parse", "HEAD")
    _git(repo_root, "update-ref", "refs/heads/concurrent", seed)

    before = _compute_git_state_snapshot(repo_root)

    # A sibling worktree shares the common dir...
    _mark_shared(repo_root)
    # ...and legitimately rewrites `concurrent` to an unrelated history (the
    # shape the guard classifies as "corruption" today).
    blob = _git(repo_root, "hash-object", "-w", "--stdin", input_text="x\n")
    tree = _git(repo_root, "mktree", input_text=f"100644 blob {blob}\tx.txt\n")
    unrelated = _git(repo_root, "commit-tree", tree, "-m", "sibling work")
    _git(repo_root, "update-ref", "refs/heads/concurrent", unrelated)

    _atomic_restore_git_state(repo_root, before)

    surviving = _ref_path(repo_root, "refs/heads/concurrent").read_text().strip()
    assert surviving == unrelated, (
        f"BUG: restore clobbered a sibling worktree's ref on a SHARED common "
        f"dir (found {surviving!r}, sibling wrote {unrelated!r}). When shared, "
        f"the destructive restore must be skipped (WARN-ONLY)."
    )


# ---------------------------------------------------------------------------
# T2 -- NEGATIVE/invariance pin: exclusive dir keeps single-writer restore.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_atomic_restore_still_restores_when_common_dir_exclusive(
    tmp_path: Path,
) -> None:
    """A standalone repo (no live worktrees) is EXCLUSIVE: the guard remains
    the sole writer and MUST still restore a genuine clobber, exactly as
    today. This is the protection-preserved half of the oracle."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    seed = _git(repo_root, "rev-parse", "HEAD")
    _git(repo_root, "update-ref", "refs/heads/concurrent", seed)

    before = _compute_git_state_snapshot(repo_root)

    blob = _git(repo_root, "hash-object", "-w", "--stdin", input_text="x\n")
    tree = _git(repo_root, "mktree", input_text=f"100644 blob {blob}\tx.txt\n")
    unrelated = _git(repo_root, "commit-tree", tree, "-m", "clobber")
    _git(repo_root, "update-ref", "refs/heads/concurrent", unrelated)

    _atomic_restore_git_state(repo_root, before)

    restored = _ref_path(repo_root, "refs/heads/concurrent").read_text().strip()
    assert restored == seed, (
        f"Protection-preserved pin violated: an EXCLUSIVE common dir must "
        f"still restore a genuine clobber to the snapshot (found {restored!r}, "
        f"expected {seed!r})."
    )


# ---------------------------------------------------------------------------
# T3 -- POSITIVE (the specific gap): NEW-branch creation by a sibling.
# ---------------------------------------------------------------------------


def test_new_branch_by_sibling_not_clobbered_when_shared(tmp_path: Path) -> None:
    """The exact gap the `_is_descendant_ref_advance` exemption misses: a
    sibling worktree creating a brand-NEW branch (a fresh loose ref, not a
    descendant advance of an existing one). On a SHARED common dir the guard
    must NOT delete it in the restore's pass-2 deletion sweep."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    seed = _git(repo_root, "rev-parse", "HEAD")

    before = _compute_git_state_snapshot(repo_root)

    _mark_shared(repo_root)
    # Sibling creates a NEW branch -- a loose ref absent from the snapshot.
    _git(repo_root, "update-ref", "refs/heads/sibling-feature", seed)

    _atomic_restore_git_state(repo_root, before)

    new_ref = _ref_path(repo_root, "refs/heads/sibling-feature")
    assert new_ref.is_file(), (
        "BUG: restore deleted a NEW branch a sibling worktree created on a "
        "SHARED common dir. New-branch creation is not a descendant advance, "
        "so the existing ancestry exemption never covered it -- the shared "
        "gate must skip the whole destructive restore."
    )
    assert new_ref.read_text().strip() == seed


# ---------------------------------------------------------------------------
# T4 -- POSITIVE (sibling defect): hooks restore skipped when shared.
# ---------------------------------------------------------------------------


def test_restore_hooks_dir_skips_when_common_dir_shared(tmp_path: Path) -> None:
    """`_restore_hooks_dir` writes/deletes files under the common `.git/hooks/`
    on the same sole-writer assumption. On a SHARED common dir it must skip the
    destructive restore so a sibling worktree's hooks are not clobbered."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    common_dir = _resolve_git_common_dir(repo_root)
    hooks_dir = common_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "pre-commit").write_bytes(b"#!/bin/sh\noriginal\n")

    snapshot = _snapshot_hooks_dir(hooks_dir)

    _mark_shared(repo_root)
    # Sibling adds a hook; guard would delete it in the deletion pass.
    (hooks_dir / "pre-push").write_bytes(b"#!/bin/sh\nsibling\n")

    _restore_hooks_dir(hooks_dir, snapshot)

    assert (hooks_dir / "pre-push").is_file(), (
        "BUG: hooks restore deleted a sibling worktree's hook on a SHARED "
        "common dir. When shared, the destructive hooks restore must be "
        "skipped (WARN-ONLY)."
    )


# ---------------------------------------------------------------------------
# T5 -- NEGATIVE/invariance pin: hooks restore preserved when exclusive.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_restore_hooks_dir_still_restores_when_common_dir_exclusive(
    tmp_path: Path,
) -> None:
    """An EXCLUSIVE common dir keeps the unconditional hooks restore: a file
    that appeared during the session is still deleted, matching today."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    common_dir = _resolve_git_common_dir(repo_root)
    hooks_dir = common_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "pre-commit").write_bytes(b"#!/bin/sh\noriginal\n")

    snapshot = _snapshot_hooks_dir(hooks_dir)

    # No _mark_shared: the dir stays exclusive.
    (hooks_dir / "rogue").write_bytes(b"#!/bin/sh\nrogue\n")

    _restore_hooks_dir(hooks_dir, snapshot)

    assert not (hooks_dir / "rogue").is_file(), (
        "Protection-preserved pin violated: an EXCLUSIVE common dir must still "
        "delete a file that appeared during the session."
    )
    assert (hooks_dir / "pre-commit").read_bytes() == b"#!/bin/sh\noriginal\n"
