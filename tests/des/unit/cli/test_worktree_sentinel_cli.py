"""CLI wiring test for `des sentinel` (lane/sentinel-tool).

REAL git repo, REAL linked worktrees, REAL `/proc` capacity read -- proves
the full wire-up (sweep -> declared-ownership resolution -> activity read
-> classify_sentinel -> JSON+human-summary emission), not a re-test of any
one layer's own unit contract (those live in
`tests/des/unit/domain/test_worktree_sentinel_verdict.py`,
`tests/des/unit/application/test_worktree_activity_signal.py`, and
`tests/des/unit/application/test_capacity_snapshot.py`).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _backdate_activity(worktree: Path, *, age_seconds: float) -> None:
    """Push a linked worktree's HEAD/index mtime into the past -- a freshly
    `git worktree add`-ed + committed worktree is, correctly, RECENTLY
    active (that is the point of the activity axis), so a fixture meaning
    to exercise the STALE/ABANDONED_CANDIDATE path must backdate it rather
    than rely on wall-clock elapsed-since-setup."""
    gitfile = worktree / ".git"
    gitdir = Path(gitfile.read_text(encoding="utf-8").split("gitdir:", 1)[1].strip())
    past = time.time() - age_seconds
    for name in ("HEAD", "index"):
        target = gitdir / name
        if target.exists():
            os.utime(target, (past, past))


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
def repo_with_three_worktrees(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    _init_trunk(repo)

    # 1. Abandoned candidate: dirty + unmerged, no marker, not declared, and
    #    STALE (backdated -- a just-created worktree is correctly OWNED by
    #    recent activity, so this is what distinguishes a genuine candidate).
    abandoned = tmp_path / "wt-abandoned"
    _git(repo, "worktree", "add", "-b", "lane-abandoned", str(abandoned), "HEAD")
    (abandoned / "wip.txt").write_text("wip", encoding="utf-8")
    _git(abandoned, "add", "-A")
    _git(abandoned, "commit", "-q", "-m", "unmerged lane work")
    _backdate_activity(abandoned, age_seconds=48 * 3600)

    # 2. Declared-owned via marker file, otherwise identical to #1 (dirty +
    #    unmerged) -- proves declared ownership overrides the at-risk-work
    #    reading, not merely a worktree with nothing to lose.
    marker_owned = tmp_path / "wt-markerowned"
    _git(repo, "worktree", "add", "-b", "lane-markerowned", str(marker_owned), "HEAD")
    (marker_owned / "wip.txt").write_text("wip", encoding="utf-8")
    _git(marker_owned, "add", "-A")
    _git(marker_owned, "commit", "-q", "-m", "unmerged lane work")
    marker_dir = marker_owned / ".nwave"
    marker_dir.mkdir()
    (marker_dir / "lane-owner.json").write_text(
        json.dumps({"owner": "test-orchestrator"}), encoding="utf-8"
    )

    # 3. Declared-owned via --owned flag (a `wt-`-prefixed token matching a
    #    bare-normalized worktree basename -- the defect #3 shape).
    flag_owned = tmp_path / "flagowned"
    _git(repo, "worktree", "add", "-b", "lane-flagowned", str(flag_owned), "HEAD")
    (flag_owned / "wip.txt").write_text("wip", encoding="utf-8")
    _git(flag_owned, "add", "-A")
    _git(flag_owned, "commit", "-q", "-m", "unmerged lane work")

    return repo, abandoned, marker_owned, flag_owned


def test_sentinel_cli_classifies_all_three_worktrees_correctly(
    repo_with_three_worktrees: tuple[Path, Path, Path, Path], capsys
) -> None:
    from des.cli.worktree_sentinel import main

    repo, abandoned, marker_owned, flag_owned = repo_with_three_worktrees

    exit_code = main(
        [
            "--repo",
            str(repo),
            "--target-branch",
            "master",
            "--owned",
            "wt-flagowned",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out.strip().splitlines()[0])
    assert payload["event"] == "WorktreeSentinelReport"

    by_path = {row["path"]: row for row in payload["worktrees"]}
    assert by_path[str(abandoned)]["state"] == "ABANDONED_CANDIDATE"
    assert set(by_path[str(abandoned)]["offers"]) == {
        "MERGE",
        "RESUME",
        "DEFER",
        "REMOVE",
    }
    assert by_path[str(marker_owned)]["state"] == "OWNED"
    assert by_path[str(flag_owned)]["state"] == "OWNED"

    # Capacity snapshot present with the right keys -- exact values are
    # environment-dependent and not asserted.
    capacity = payload["capacity"]
    assert set(capacity) == {
        "nproc",
        "load_avg",
        "mem_available_kb",
        "real_pytest_count",
    }


def test_sentinel_cli_never_mutates_or_removes_the_abandoned_worktree(
    repo_with_three_worktrees: tuple[Path, Path, Path, Path], capsys
) -> None:
    from des.cli.worktree_sentinel import main

    repo, abandoned, _marker_owned, _flag_owned = repo_with_three_worktrees

    main(["--repo", str(repo), "--target-branch", "master"])

    assert abandoned.exists()
    assert (abandoned / "wip.txt").exists()


def test_sentinel_cli_exits_zero_even_with_a_candidate_present(
    repo_with_three_worktrees: tuple[Path, Path, Path, Path], capsys
) -> None:
    """Advisory, GDP-6: informs, never blocks."""
    from des.cli.worktree_sentinel import main

    repo, *_ = repo_with_three_worktrees

    exit_code = main(["--repo", str(repo), "--target-branch", "master"])

    assert exit_code == 0
