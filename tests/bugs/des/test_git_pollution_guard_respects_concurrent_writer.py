"""Regression AT (bugfix `fix-git-pollution-guard-clobbers-concurrent-writer`):
the autouse `_git_pollution_guard` fixture (`tests/conftest.py`) cannot tell a
test-caused corruption apart from a LEGITIMATE concurrent writer advancing a
branch ref -- e.g. the orchestrator committing on the host repo's branch while
a long guarded pytest session is running.

RCA (`docs/feature/fix-git-pollution-guard-clobbers-concurrent-writer/
feature-delta.md`): the guard's teardown diff sees a ref moved to a
DESCENDANT commit as "corruption" and `_atomic_restore_git_state` writes the
STALE snapshot ref back as a raw file write -- no reflog entry, commits
silently eaten. Empirical incidents: 2026-07-11 (`2195d6a9b` / `83d2bc38e`
restored over newer commits during WS-15 timed sweeps), prior `804328f51`
~20-min clobber loop (task #93), original class task #50.

Oracle (the fix, NOT authored here -- crafter's job in `tests/conftest.py`
`_diff_git_state` / `_atomic_restore_git_state` / `_git_pollution_guard`):
for each loose-ref diff, check ancestry (`git merge-base --is-ancestor
<before> <after>`) before treating a SHA change as corruption.

  * DESCENDANT advance (external writer's normal commit)      -> legitimate,
    excluded from the restore set and the failure diff.
  * NON-descendant clobber (reset/rewritten history)           -> unchanged
    fail-closed behavior: restored + failed, exactly as today.
  * Undeterminable ancestry (unknown SHA, unborn)               -> stays
    fail-closed (restored + failed) -- degrade toward today's behavior,
    never silent-pass a genuine clobber.

Reuse (per feature-delta Reuse Analysis): follows `tests/test_guard_fixtures.
py`'s isolated-repo fixture pattern verbatim (`_init_isolated_repo`,
`_create_initial_commit` imported, not re-implemented) -- no new harness.
`GIT_CEILING_DIRECTORIES` scopes every subprocess git call to the tmp repo,
mirroring that file's safety discipline; this repo's own `.git` is never
touched.

Driving surface: the guard's pure-function seam directly --
`_compute_git_state_snapshot` / `_diff_git_state` / `_atomic_restore_git_state`
from `tests.conftest` -- port-to-port unit testing of the detective guard's
domain logic, same pattern `tests/test_guard_fixtures.py` already
establishes. T1-T3 use a second branch, `refs/heads/concurrent`, as the
external writer's stand-in while `main` (HEAD) stays untouched -- isolating
the ref-level ancestry contract. T4-T5 (extension pass) then cover the
REALISTIC incident path the isolation deliberately excluded.

Scenarios:
  T1 POSITIVE (the bug, active-RED today) --
      `test_guard_treats_concurrent_branch_advance_as_legitimate`
  T2 NEGATIVE/invariance pin (unchanged behavior, green today AND after) --
      `test_guard_restores_and_fails_genuine_non_descendant_ref_clobber`
  T3 GUARD/invariance pin (fail-closed degrade, green today AND after) --
      `test_guard_treats_unknown_ancestry_ref_as_corruption`

Extension pass (independent examine found a REAL gap T1-T3 missed): a normal
`git commit` by a concurrent writer on the CHECKED-OUT branch moves BOTH the
branch ref (T1's seam, now ancestry-excludable) AND `HEAD_resolved` -- and
`_diff_git_state` compares `HEAD_resolved` UNCONDITIONALLY (tests/
conftest.py:704-705), so the full guard still restores+fails on a legitimate
descendant advance even once the refs seam is fixed. T1 passed the refs seam
in isolation; the 2026-07-11 incident path (writer commits on the branch
HEAD points at) also traverses the HEAD_resolved comparison. Oracle
extension, same three-way split as the refs seam: `HEAD_resolved` moved to a
DESCENDANT of the snapshot = legitimate (no "HEAD" in diff, nothing
restored); moved to a NON-descendant, or ancestry undeterminable = "HEAD"
flagged fail-closed exactly as today. HEAD's SYMBOLIC-TARGET changes
(re-pointing `ref:` to another branch / detaching) remain fail-closed and
out of scope, per the design ("HEAD symbolic target keeps today's
fail-closed behavior") -- the descendant exemption applies only to the
resolved-SHA advance a normal commit produces.

  T4 POSITIVE (the HEAD_resolved gap, active-RED today) --
      `test_guard_treats_full_commit_by_concurrent_writer_as_legitimate`
  T5 NEGATIVE/invariance pin (green today AND after; parametrized
      non-descendant reset + unknown-SHA, the T3 fail-closed symmetry) --
      `test_guard_still_flags_head_moved_off_descendant_path`
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.conftest import (
    _atomic_restore_git_state,
    _compute_git_state_snapshot,
    _diff_git_state,
)
from tests.test_guard_fixtures import _create_initial_commit, _init_isolated_repo


if TYPE_CHECKING:
    from pathlib import Path


_CONCURRENT_REF = "refs/heads/concurrent"


# ---------------------------------------------------------------------------
# Helpers (git plumbing, all scoped via GIT_CEILING_DIRECTORIES like
# tests/test_guard_fixtures.py's `_init_isolated_repo`/`_create_initial_commit`)
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


def _tree_of(repo_root: Path, ref: str) -> str:
    return _git(repo_root, "rev-parse", f"{ref}^{{tree}}")


def _commit_tree(
    repo_root: Path, tree: str, message: str, parent: str | None = None
) -> str:
    args = ["commit-tree", tree, "-m", message]
    if parent is not None:
        args += ["-p", parent]
    return _git(repo_root, *args)


def _unrelated_tree(repo_root: Path) -> str:
    """A tree with no relation to the seed commit's tree -- via plumbing
    only (`hash-object` + `mktree`), never touching the working index."""
    blob = _git(repo_root, "hash-object", "-w", "--stdin", input_text="unrelated\n")
    return _git(repo_root, "mktree", input_text=f"100644 blob {blob}\tunrelated.txt\n")


def _update_ref(repo_root: Path, ref_name: str, sha: str) -> None:
    _git(repo_root, "update-ref", ref_name, sha)


def _concurrent_ref_path(repo_root: Path) -> Path:
    return repo_root / ".git" / "refs" / "heads" / "concurrent"


def _setup_repo_with_concurrent_branch(repo_root: Path) -> str:
    """Init repo, one commit on `main`, a second loose ref `concurrent`
    pointing at the same commit -- the stand-in for the branch an external
    legitimate writer (e.g. the orchestrator) also advances while `main`
    (HEAD) stays untouched. Returns the seed commit SHA."""
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    seed = _git(repo_root, "rev-parse", "HEAD")
    _update_ref(repo_root, _CONCURRENT_REF, seed)
    return seed


# ---------------------------------------------------------------------------
# T1 -- POSITIVE (the bug): descendant advance must NOT be corruption.
# ---------------------------------------------------------------------------


def test_guard_treats_concurrent_branch_advance_as_legitimate(
    tmp_path: Path,
) -> None:
    """A DESCENDANT advance on a concurrently-written branch must not be
    flagged as corruption, and must not be restored away.

    Active-RED at HEAD: `_diff_git_state`'s refs comparison flags ANY SHA
    change on an existing loose ref, with no ancestry check -- exactly the
    2026-07-11 incident shape (`2195d6a9b` / `83d2bc38e` restored over newer
    commits).
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    seed = _setup_repo_with_concurrent_branch(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # External legitimate writer: a normal child commit on `concurrent`,
    # descendant of the snapshot -- e.g. the orchestrator committing on the
    # branch while this guarded test session runs. `main`/HEAD is untouched.
    tree = _tree_of(repo_root, seed)
    child = _commit_tree(repo_root, tree, "external legitimate advance", parent=seed)
    _update_ref(repo_root, _CONCURRENT_REF, child)

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)

    assert "refs" not in diff, (
        f"BUG: a descendant ref advance by a legitimate concurrent writer "
        f"was classified as pollution (diff={diff!r}). The guard must check "
        f"ancestry (git merge-base --is-ancestor <before> <after>) before "
        f"flagging a loose-ref SHA change -- a descendant of the snapshot is "
        f"legitimate history, not corruption. See docs/feature/"
        f"fix-git-pollution-guard-clobbers-concurrent-writer/feature-delta.md."
    )

    # Simulate the autouse guard's teardown exactly: restore only fires when
    # the diff is non-empty (tests/conftest.py:848-861).
    if diff:
        _atomic_restore_git_state(repo_root, before)

    surviving_sha = _concurrent_ref_path(repo_root).read_text().strip()
    assert surviving_sha == child, (
        f"BUG: the guard restored the concurrent writer's legitimate advance "
        f"back to the stale snapshot (found {surviving_sha!r}, expected the "
        f"surviving commit {child!r}) -- exactly the 2026-07-11 commit-eating "
        f"incident (2195d6a9b / 83d2bc38e restored over newer commits)."
    )


# ---------------------------------------------------------------------------
# T2 -- NEGATIVE/invariance pin: genuine (non-descendant) clobber is
# unchanged behavior -- must stay green before AND after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_guard_restores_and_fails_genuine_non_descendant_ref_clobber(
    tmp_path: Path,
) -> None:
    """A NON-descendant ref move (rewritten/reset history) must still be
    treated as corruption -- restored, and reported in the diff -- exactly
    as today. This is the unchanged-behavior half of the oracle; a fix that
    silences it (over-broad ancestry exemption) would silently accept a
    genuine clobber.

    Green today (the pin) AND after the fix (the invariant the fix must
    preserve).
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    seed = _setup_repo_with_concurrent_branch(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Genuine clobber: `concurrent` reset to a completely UNRELATED root
    # commit -- no ancestry relation to `seed` in either direction.
    unrelated_tree = _unrelated_tree(repo_root)
    unrelated = _commit_tree(repo_root, unrelated_tree, "unrelated root")
    _update_ref(repo_root, _CONCURRENT_REF, unrelated)

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)
    assert "refs" in diff, (
        f"Unchanged-behavior pin violated: a non-descendant ref clobber must "
        f"still be classified as corruption (diff={diff!r})."
    )

    if diff:
        _atomic_restore_git_state(repo_root, before)

    restored_sha = _concurrent_ref_path(repo_root).read_text().strip()
    assert restored_sha == seed, (
        f"Unchanged-behavior pin violated: a genuine clobber must still be "
        f"restored to the snapshot (found {restored_sha!r}, expected "
        f"{seed!r})."
    )


# ---------------------------------------------------------------------------
# T3 -- GUARD/invariance pin: undeterminable ancestry degrades fail-closed.
# ---------------------------------------------------------------------------


def test_guard_treats_unknown_ancestry_ref_as_corruption(tmp_path: Path) -> None:
    """A ref pointing at an object absent from the ODB (ancestry cannot be
    established) must still be flagged as corruption -- fail-closed, never a
    silent pass. Pins the degrade-toward-today's-behavior half of the oracle
    so a future ancestry implementation cannot treat "cannot determine" as
    "assume descendant, let it through".

    Green today (unconditional flag, no ancestry check exists yet) AND after
    the fix (explicit fail-closed branch for undeterminable ancestry).
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _setup_repo_with_concurrent_branch(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Ancestry cannot be established: the ref now points at a well-formed
    # but nonexistent SHA -- a direct file write bypassing git entirely
    # (mirrors what a half-written/corrupted ref looks like on disk; `git
    # merge-base --is-ancestor` against it can only error, never resolve).
    unknown_sha = "f" * 40
    _concurrent_ref_path(repo_root).write_text(unknown_sha + "\n")

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)
    assert "refs" in diff, (
        f"Fail-closed pin violated: a ref whose ancestry cannot be "
        f"established (unknown SHA) must degrade toward corruption, never "
        f"silently pass (diff={diff!r})."
    )


# ---------------------------------------------------------------------------
# Extension pass -- the HEAD_resolved seam (examine-found gap).
# ---------------------------------------------------------------------------


def _main_ref_path(repo_root: Path) -> Path:
    return repo_root / ".git" / "refs" / "heads" / "main"


# --- T4 -- POSITIVE (the gap): a full `git commit` moves the branch ref AND
# --- HEAD_resolved; both movements are the same legitimate descendant advance.


def test_guard_treats_full_commit_by_concurrent_writer_as_legitimate(
    tmp_path: Path,
) -> None:
    """The REALISTIC incident path: an external writer lands a normal `git
    commit` on the CHECKED-OUT branch (`main`, the branch HEAD points at)
    while the guarded test runs. This advances `refs/heads/main` to a
    descendant AND moves `HEAD_resolved` to the same descendant SHA -- one
    legitimate event seen through two snapshot fields. The full diff must be
    EMPTY: no "refs", no "HEAD", nothing restored.

    Active-RED at HEAD: `_diff_git_state` compares `HEAD_resolved`
    unconditionally (tests/conftest.py:704-705), so even with the refs seam
    ancestry-fixed the guard still reports ["HEAD"] and the teardown
    restores+fails -- the exact 2026-07-11 commit-eating shape T1 could not
    see because it kept HEAD off the advanced branch.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    seed = _git(repo_root, "rev-parse", "HEAD")

    before = _compute_git_state_snapshot(repo_root)

    # External legitimate writer: a REAL `git commit` on the checked-out
    # branch -- the same subprocess path `tests/test_guard_fixtures.py::
    # test_guard_detects_head_corruption` uses, but here the commit
    # represents the orchestrator's legitimate work, not test pollution.
    (repo_root / "external.txt").write_text("legitimate concurrent work\n")
    _git(repo_root, "add", "external.txt")
    _git(repo_root, "commit", "-m", "feat: external legitimate advance")
    child = _git(repo_root, "rev-parse", "HEAD")
    assert child != seed, "Setup failure: the external commit did not land."

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)

    assert diff == [], (
        f"BUG: a normal commit by a legitimate concurrent writer on the "
        f"checked-out branch was classified as corruption (diff={diff!r}). "
        f"Both movements it causes -- refs/heads/main and HEAD_resolved -- "
        f"advance to a DESCENDANT of the snapshot ({seed[:9]} -> "
        f"{child[:9]}); the ancestry exemption must cover the HEAD_resolved "
        f"comparison too, or the full guard keeps restoring+failing on the "
        f"2026-07-11 incident path even with the refs seam fixed."
    )

    # Simulate the autouse teardown exactly: restore fires only on a
    # non-empty diff (tests/conftest.py:848-861).
    if diff:
        _atomic_restore_git_state(repo_root, before)

    surviving_sha = _main_ref_path(repo_root).read_text().strip()
    assert surviving_sha == child, (
        f"BUG: the guard restored the branch ref over the concurrent "
        f"writer's commit (found {surviving_sha!r}, expected {child!r}) -- "
        f"the commit-eating observable (2195d6a9b / 83d2bc38e restored over "
        f"newer commits, 2026-07-11)."
    )


# --- T5 -- NEGATIVE/invariance pin: HEAD_resolved moved OFF the descendant
# --- path stays fail-closed (non-descendant reset + unknown-SHA symmetry).


@pytest.mark.negative_at
@pytest.mark.parametrize("mutation", ["non_descendant_reset", "unknown_sha"])
def test_guard_still_flags_head_moved_off_descendant_path(
    tmp_path: Path, mutation: str
) -> None:
    """`HEAD_resolved` moved to a NON-descendant (branch reset to an
    unrelated root -- a genuine clobber, e.g. rewritten history) or to an
    SHA whose ancestry cannot be established (unknown object -- the T3
    fail-closed symmetry on the HEAD path) must STILL be flagged as "HEAD"
    corruption, exactly as today. A fix that exempts every HEAD_resolved
    change (instead of only descendant advances) would silently accept a
    genuine HEAD clobber.

    Green today (unconditional flag) AND after the fix (fail-closed branch
    for non-descendant / undeterminable ancestry).
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    if mutation == "non_descendant_reset":
        # Genuine clobber: the checked-out branch reset to an unrelated
        # root commit -- HEAD_resolved now points off the snapshot's
        # history entirely.
        unrelated = _commit_tree(
            repo_root, _unrelated_tree(repo_root), "unrelated root"
        )
        _update_ref(repo_root, "refs/heads/main", unrelated)
    else:
        # Ancestry undeterminable: direct file write of a well-formed but
        # nonexistent SHA into the checked-out branch's loose ref --
        # HEAD_resolved reads it, but no ancestry query can resolve it.
        _main_ref_path(repo_root).write_text("f" * 40 + "\n")

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)
    assert "HEAD" in diff, (
        f"Unchanged-behavior pin violated ({mutation}): HEAD_resolved moved "
        f"off the descendant path must still be classified as HEAD "
        f"corruption, never exempted (diff={diff!r})."
    )
