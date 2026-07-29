"""End-to-end acceptance tests for scripts/hooks/worktree_removal_guard.py.

Real subprocess invocation of the hook (`python -m scripts.hooks.
worktree_removal_guard`) with a crafted Claude Code PreToolUse/Bash event on
stdin, against a REAL git repo + a REAL linked worktree. This is the
walking-skeleton proof the task demanded: the guard REFUSES a `git worktree
remove` while a real process's cwd is inside the target, and PASSES once
nothing is alive there -- observed by mutating the live-process fixture and
watching the verdict flip, not by inspecting source.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _run_hook(
    command: str, cwd: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    event = json.dumps({"tool_input": {"command": command}, "cwd": str(cwd)})
    full_env = dict(os.environ)
    full_env["PYTHONPATH"] = (
        str(_REPO_ROOT / "src") + os.pathsep + full_env.get("PYTHONPATH", "")
    )
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, "-m", "scripts.hooks.worktree_removal_guard"],
        cwd=_REPO_ROOT,
        input=event,
        capture_output=True,
        text=True,
        env=full_env,
    )
    return result.returncode, result.stdout


@pytest.fixture
def repo_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    _init_trunk(repo)
    wt = tmp_path / "wt-lane"
    _git(repo, "worktree", "add", "-b", "lane", str(wt), "HEAD")
    _git(repo, "merge", "-q", "--no-edit", "lane")  # lane is fully merged by default
    return repo, wt


def test_allows_removal_when_nothing_is_live(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    repo, wt = repo_and_worktree
    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 0
    assert stdout == ""


def test_refuses_removal_while_a_process_holds_cwd_inside_the_worktree(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    """The walking-skeleton proof: mutate production (spawn a live process in
    the target) and observe the guard flip from ALLOW to REFUSE -- naming
    the PID, exactly the incident this guard closes."""
    repo, wt = repo_and_worktree
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], cwd=wt
    )
    try:
        deadline = time.monotonic() + 5
        exit_code, stdout = 0, ""
        while time.monotonic() < deadline:
            exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
            if exit_code == 2:
                break
            time.sleep(0.1)
        assert exit_code == 2
        assert "REFUSED" in stdout
        assert "LIVE" in stdout
        assert str(proc.pid) in stdout
    finally:
        proc.kill()
        proc.wait()

    # Once the process is gone, the SAME command is allowed.
    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 0
    assert stdout == ""


def test_refuses_removal_of_a_locked_worktree(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    repo, wt = repo_and_worktree
    _git(repo, "worktree", "lock", str(wt))
    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 2
    assert "LIVE" in stdout
    assert "carries an explicit" in stdout
    assert "lock" in stdout.lower()


def test_refuses_removal_of_a_worktree_with_unmerged_commits(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    """No liveness evidence, but unintegrated work is at stake ->
    ABANDONED_CANDIDATE, blocked pending a human MERGE/RESUME/DEFER/REMOVE pick."""
    repo, wt = repo_and_worktree
    (wt / "wip.txt").write_text("wip", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "unmerged lane work")

    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 2
    assert "ABANDONED_CANDIDATE" in stdout
    assert "unmerged lane work" in stdout
    assert "MERGE, RESUME, DEFER, REMOVE" in stdout


def test_refuses_removal_of_a_worktree_with_uncommitted_changes(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    """Dirty-state alone (no unmerged COMMITS -- the branch is fully merged)
    still blocks: uncommitted work is destroyed outright by removal, and
    this is the Sentinel's OWN distinct "dirty state" evidence category."""
    repo, wt = repo_and_worktree
    (wt / "untracked.txt").write_text("uncommitted", encoding="utf-8")

    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 2
    assert "ABANDONED_CANDIDATE" in stdout
    assert "uncommitted changes" in stdout


def test_block_reason_names_unavailable_evidence_categories(
    repo_and_worktree: tuple[Path, Path],
) -> None:
    """GDP-3: the refusal never withholds what it could NOT check either --
    owner-receipt and recent-host-log-activity are spec-named but not yet
    mechanically available, and every receipt says so explicitly."""
    repo, wt = repo_and_worktree
    _git(repo, "worktree", "lock", str(wt))
    exit_code, stdout = _run_hook(f"git worktree remove {wt}", repo)
    assert exit_code == 2
    assert "owner-receipt" in stdout
    assert "recent-host-log-activity" in stdout


def test_bare_env_flag_does_not_bypass(repo_and_worktree: tuple[Path, Path]) -> None:
    """A bare truthy flag (not a prose justification) must NOT bypass."""
    repo, wt = repo_and_worktree
    _git(repo, "worktree", "lock", str(wt))
    exit_code, _stdout = _run_hook(
        f"git worktree remove {wt}", repo, env={"NWAVE_WORKTREE_REMOVE_REASON": "1"}
    )
    assert exit_code == 2


def test_prose_reason_bypasses_and_is_audited(
    repo_and_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, wt = repo_and_worktree
    _git(repo, "worktree", "lock", str(wt))
    reason = "Ale confirmed via chat this lane is dead, safe to remove now"
    exit_code, stdout = _run_hook(
        f"git worktree remove {wt}",
        repo,
        env={
            "NWAVE_WORKTREE_REMOVE_REASON": reason,
            "NWAVE_WORKTREE_GUARD_TARGET_ROOT": str(tmp_path),
        },
    )
    assert exit_code == 0
    assert stdout == ""

    audit_dir = tmp_path / ".nwave" / "des" / "logs"
    logs = list(audit_dir.glob("audit-*.log"))
    assert len(logs) == 1
    lines = logs[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "WorktreeRemovalBypassUsed"
    assert event["reason"] == reason


def test_unrelated_command_is_ignored(repo_and_worktree: tuple[Path, Path]) -> None:
    repo, _wt = repo_and_worktree
    exit_code, stdout = _run_hook("git status", repo)
    assert exit_code == 0
    assert stdout == ""
