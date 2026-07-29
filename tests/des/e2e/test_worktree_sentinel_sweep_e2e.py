"""End-to-end proof for the Sentinel's worktree sweep enumerator.

Sibling of `tests/hooks/test_worktree_removal_guard_end_to_end.py`, same
shape: a REAL git repo with REAL linked worktrees, the REAL `GitWorktreeAdapter`
enumerator, and the REAL `collect_worktree_triage_receipt` collector (default,
not stubbed) -- so this is the walking-skeleton proof that `sweep_worktrees`
correctly wires the ALREADY-EXISTING enumerator port + collector + predicate
together, not a re-test of any of their own unit-level contracts.

Three linked worktrees, three different real states in ONE sweep pass:
  - a LIVE process holding its cwd inside one worktree,
  - unmerged commits at risk in a second,
  - nothing at all in a third (CLEAN).

The claim under test is the dispatch's own minimum bar: a LIVE worktree must
never be reported as abandoned, and the sweep must report the WHOLE
population in one pass, not an invented subset.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.worktree_sentinel_sweep import sweep_worktrees
from des.domain.worktree_anti_rot_triage import TriageState


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _init_trunk(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "seed")


@pytest.fixture
def three_linked_worktrees(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    _init_trunk(repo)

    live_wt = tmp_path / "wt-live"
    _git(repo, "worktree", "add", "-b", "lane-live", str(live_wt), "HEAD")
    _git(repo, "merge", "-q", "--no-edit", "lane-live")  # merged: only /proc marks it

    abandoned_wt = tmp_path / "wt-abandoned"
    _git(repo, "worktree", "add", "-b", "lane-abandoned", str(abandoned_wt), "HEAD")
    (abandoned_wt / "wip.txt").write_text("wip", encoding="utf-8")
    _git(abandoned_wt, "add", "-A")
    _git(abandoned_wt, "commit", "-q", "-m", "unmerged lane work")

    clean_wt = tmp_path / "wt-clean"
    _git(repo, "worktree", "add", "-b", "lane-clean", str(clean_wt), "HEAD")
    _git(repo, "merge", "-q", "--no-edit", "lane-clean")

    return repo, live_wt, abandoned_wt, clean_wt


def test_sweep_reports_all_three_states_correctly_in_one_pass(
    three_linked_worktrees: tuple[Path, Path, Path, Path],
) -> None:
    repo, live_wt, abandoned_wt, clean_wt = three_linked_worktrees

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], cwd=live_wt
    )
    try:
        # Real /proc scanning can lag the fork by a beat -- poll like the
        # guard's own e2e test does, never a fixed sleep.
        deadline = time.monotonic() + 5
        report = None
        while time.monotonic() < deadline:
            report = sweep_worktrees(
                repo=repo,
                worktree_port=GitWorktreeAdapter(),
                target_branch="master",
            )
            live_entry = next(
                (
                    e
                    for e in report.entries
                    if e.handle.path.resolve() == live_wt.resolve()
                ),
                None,
            )
            if live_entry is not None and live_entry.receipt.state is TriageState.LIVE:
                break
            time.sleep(0.1)
    finally:
        proc.kill()
        proc.wait()

    assert report is not None
    # The full population: nothing invented, nothing dropped.
    swept_paths = {e.handle.path.resolve() for e in report.entries}
    assert swept_paths == {
        live_wt.resolve(),
        abandoned_wt.resolve(),
        clean_wt.resolve(),
    }

    by_path = {e.handle.path.resolve(): e.receipt for e in report.entries}

    # The claim the dispatch demanded: LIVE, never ABANDONED_CANDIDATE.
    assert by_path[live_wt.resolve()].state is TriageState.LIVE
    assert str(proc.pid) in by_path[live_wt.resolve()].evidence[0].what

    assert by_path[abandoned_wt.resolve()].state is TriageState.ABANDONED_CANDIDATE
    assert by_path[clean_wt.resolve()].state is TriageState.CLEAN


def test_sweep_after_the_live_process_exits_reclassifies_without_a_second_run(
    three_linked_worktrees: tuple[Path, Path, Path, Path],
) -> None:
    """Same worktree, two sweeps, the live process gone in between -- proves
    the sweep reads LIVE state, never caches a stale verdict."""
    repo, live_wt, _abandoned_wt, _clean_wt = three_linked_worktrees

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], cwd=live_wt
    )
    try:
        deadline = time.monotonic() + 5
        saw_live = False
        while time.monotonic() < deadline:
            report = sweep_worktrees(
                repo=repo, worktree_port=GitWorktreeAdapter(), target_branch="master"
            )
            entry = next(
                e
                for e in report.entries
                if e.handle.path.resolve() == live_wt.resolve()
            )
            if entry.receipt.state is TriageState.LIVE:
                saw_live = True
                break
            time.sleep(0.1)
        assert saw_live
    finally:
        proc.kill()
        proc.wait()

    report_after = sweep_worktrees(
        repo=repo, worktree_port=GitWorktreeAdapter(), target_branch="master"
    )
    entry_after = next(
        e for e in report_after.entries if e.handle.path.resolve() == live_wt.resolve()
    )
    assert entry_after.receipt.state is TriageState.CLEAN
