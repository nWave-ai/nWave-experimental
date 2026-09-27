"""Public oracle: `_git_refusal`'s Indeterminate calls never crash the CLI.

`_close` and `_shipped` in `des.cli.lane` report a Git command that refused as
`Disposition.Indeterminate` -- the integration or fast-forward already
happened, so the outcome cannot be reported as a plain repository fact.
Three call sites passed `Disposition.Indeterminate` positionally into
`_git_refusal`, whose fourth parameter, `indeterminate`, is keyword-only. That
raised `TypeError` instead of returning the closed WHAT/WHY/HOW the step
promises, for the entirely ordinary case of Git refusing to remove a worktree.

The root-into-root self-refusal case below never reaches `_git_refusal` at
all -- `_not_a_disposable_lane` refuses by path equality before any Git
command that could crash runs, so it exercises the entrypoint's guard, not
the original crash. The original crash is exercised here through a real
LOCKED lane worktree, where `git worktree remove` genuinely refuses and
`_close` must report `CleanupUnproven`/`Indeterminate` instead of raising.

This file reuses the real-CLI fixtures from
`test_lane_steps_open_and_integrate.py` (subprocess against a real temporary
Git repository) and drives call sites reachable through the public CLI:
`des lane integrate` and `des lane finalize`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


PACKAGE_PARENT = Path(__file__).parents[4] / "src"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def put(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def commit(root: Path, name: str, text: str, subject: str) -> str:
    put(root, name, text)
    git(root, "add", ".")
    git(root, "commit", "-qm", subject)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def temp_home(tmp_path: Path) -> Path:
    """The directory the step must derive its deterministic lane path inside."""
    home = tmp_path / "tmp"
    home.mkdir()
    return home


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """One real repository with one commit -- the orchestrator's live checkout."""
    repository = tmp_path / "root"
    repository.mkdir()
    git(repository, "init", "-q")
    git(repository, "config", "user.email", "a@b")
    git(repository, "config", "user.name", "a")
    commit(repository, "README.md", "x\n", "base")
    return repository


def lane(temp_home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real `des lane ...` with `TMPDIR` pointed at the test's own dir."""
    environment = {
        **os.environ,
        "PYTHONPATH": str(PACKAGE_PARENT),
        "TMPDIR": str(temp_home),
    }
    environment.pop("PYTHONSTARTUP", None)
    return subprocess.run(
        [sys.executable, "-m", "des.cli", "lane", *args],
        text=True,
        capture_output=True,
        env=environment,
        timeout=180,
        check=False,
    )


def field(completed: subprocess.CompletedProcess[str], label: str) -> str:
    """The one value the terminal reported under `label`, wherever it wrote it."""
    prefix = f"{label}: "
    lines = [
        line[len(prefix) :]
        for line in (completed.stdout + "\n" + completed.stderr).splitlines()
        if line.startswith(prefix)
    ]
    assert len(lines) == 1, f"{label} in:\n{completed.stdout}{completed.stderr}"
    return lines[0]


def terminal(completed: subprocess.CompletedProcess[str]) -> str:
    return completed.stdout + completed.stderr


@pytest.mark.parametrize("step", ["integrate", "finalize"])
def test_entrypoint_refuses_root_into_root_instead_of_crashing(
    temp_home: Path, root: Path, step: str
) -> None:
    """Neither public entrypoint may attempt to close the destination on itself.

    `root` is passed as BOTH `--repo-root` and `--worktree`: the destination
    workspace named as the lane to integrate or finalize.  The guard is path
    equality against the destination, not a claim that Git would refuse a
    "main worktree" -- the destination can itself be a linked worktree, so the
    step must never assert that fact.  Snapshotting HEAD, status and the
    worktree list proves the refusal happens before either entrypoint
    mutates anything.
    """
    head_before = git(root, "rev-parse", "HEAD")
    status_before = git(root, "status", "--porcelain")
    worktrees_before = git(root, "worktree", "list", "--porcelain")

    result = lane(
        temp_home,
        step,
        "--repo-root",
        str(root),
        "--worktree",
        str(root),
    )

    assert result.returncode != 0, terminal(result)
    # The defect crashed with a bare Python traceback; the fix must return the
    # step's own closed vocabulary instead.
    assert "Traceback" not in terminal(result), terminal(result)
    assert "TypeError" not in terminal(result), terminal(result)
    # The root is not a disposable lane, so this is a plain, anticipated
    # refusal -- never Indeterminate -- because the step never attempts
    # `worktree remove` on it in the first place.
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "NotALane"
    assert str(root) in field(result, "WHY")
    assert "destination workspace" in field(result, "WHY")
    # The WHY must not assert a Git-refusal or main-worktree fact that does
    # not hold for every destination (the destination can itself be linked).
    assert "main working tree" not in field(result, "WHY")
    assert field(result, "HOW")
    # HOW must not tell the operator to remove the repository's own
    # destination workspace; it must point at choosing an actual (disposable)
    # lane worktree instead.
    assert "remove it" not in field(result, "HOW")
    assert str(root) in field(result, "HOW")
    # Nothing about the repository moved: the step refused before mutating.
    assert git(root, "rev-parse", "HEAD") == head_before
    assert git(root, "status", "--porcelain") == status_before
    assert git(root, "worktree", "list", "--porcelain") == worktrees_before


def test_finalize_still_succeeds_on_an_ordinary_clean_lane(
    temp_home: Path, root: Path
) -> None:
    """Regression guard: the fix must not disturb the native-success path."""
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")
    assert result.returncode == 0, terminal(result)
    worktree = Path(field(result, "WORKTREE"))
    git(root, "rev-parse", "HEAD")

    integrated = lane(
        temp_home,
        "integrate",
        "--repo-root",
        str(root),
        "--worktree",
        str(worktree),
        "--keep-worktree",
    )
    assert integrated.returncode == 0, terminal(integrated)

    finalized = lane(
        temp_home,
        "finalize",
        "--repo-root",
        str(root),
        "--worktree",
        str(worktree),
    )

    assert finalized.returncode == 0, terminal(finalized)
    assert field(finalized, "DELIVERY-OUTCOME") == "Success"
    assert field(finalized, "REMOVED") == str(worktree)
    assert not worktree.exists()
    assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 1


@pytest.mark.parametrize("step", ["integrate", "finalize"])
def test_locked_worktree_refuses_cleanup_instead_of_crashing(
    temp_home: Path, root: Path, step: str
) -> None:
    """`_close`'s original crash site, driven for real: Git refuses a LOCKED remove.

    A locked worktree is the one ordinary condition where `git worktree
    remove` genuinely refuses -- Git will not force past a lock. `_close`
    must report the refusal as `CleanupUnproven`/`Indeterminate`, never crash
    with the positional-argument `TypeError` this suite guards against, and
    the locked lane must survive untouched.
    """
    opened = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")
    assert opened.returncode == 0, terminal(opened)
    worktree = Path(field(opened, "WORKTREE"))
    commit(worktree, "work.txt", "y\n", "lane work")

    if step == "finalize":
        integrated = lane(
            temp_home,
            "integrate",
            "--repo-root",
            str(root),
            "--worktree",
            str(worktree),
            "--keep-worktree",
        )
        assert integrated.returncode == 0, terminal(integrated)

    tip_before = git(worktree, "rev-parse", "HEAD")
    git(root, "worktree", "lock", str(worktree))
    try:
        result = lane(
            temp_home, step, "--repo-root", str(root), "--worktree", str(worktree)
        )

        assert "Traceback" not in terminal(result), terminal(result)
        assert "TypeError" not in terminal(result), terminal(result)
        assert field(result, "DELIVERY-OUTCOME") == "Indeterminate"
        assert field(result, "WHAT") == "CleanupUnproven"
        assert str(worktree) in field(result, "WHY")
        assert field(result, "HOW")

        # The locked lane survives, and the destination is unchanged by the
        # refused cleanup step itself.
        assert worktree.exists()
        assert git(worktree, "rev-parse", "HEAD") == tip_before
        assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 2
    finally:
        git(root, "worktree", "unlock", str(worktree))


@pytest.mark.parametrize("step", ["integrate", "finalize"])
def test_entrypoint_refuses_linked_worktree_destination_into_itself(
    temp_home: Path, root: Path, step: str
) -> None:
    """The self-refusal guard also holds when the destination is a LINKED worktree.

    `_not_a_disposable_lane` refuses by path equality against `--repo-root`,
    not by asking Git which worktree is "main" -- so it must refuse just as
    surely when `--repo-root` itself names a linked (non-main) worktree
    passed as its own `--worktree`.
    """
    linked = root.parent / "linked"
    git(root, "worktree", "add", "-b", "linked-dest", str(linked))
    try:
        head_before = git(linked, "rev-parse", "HEAD")
        worktrees_before = git(root, "worktree", "list", "--porcelain")

        result = lane(
            temp_home,
            step,
            "--repo-root",
            str(linked),
            "--worktree",
            str(linked),
        )

        assert result.returncode != 0, terminal(result)
        assert "Traceback" not in terminal(result), terminal(result)
        assert field(result, "DELIVERY-OUTCOME") == "Refusal"
        assert field(result, "WHAT") == "NotALane"
        assert str(linked) in field(result, "WHY")
        assert "destination workspace" in field(result, "WHY")

        assert git(linked, "rev-parse", "HEAD") == head_before
        assert git(root, "worktree", "list", "--porcelain") == worktrees_before
    finally:
        git(root, "worktree", "remove", str(linked))
