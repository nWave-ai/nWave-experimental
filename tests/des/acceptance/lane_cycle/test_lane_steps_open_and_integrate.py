"""Public oracle: the invocable lane steps, driven through the real CLI.

THE ONE FILE OF THIS DIRECTORY THAT OUTLIVED `des dispatch`. Its nine scenarios
drive `des lane`, which ADR-DES-003 Section 14 keeps untouched; the other eight
files drove the composed run and were retired with it. The directory's name is
therefore owed a rename to what it now holds.

An orchestrator working in lanes around the delivery steps opens and closes them
by hand -- `git worktree add`, `git merge --ff-only`, `git worktree remove`,
`git branch -d` -- and the repository's own CLAUDE.md pointed at two `des`
subcommands that no longer exist, so the instruction taught a contract the CLI
could not honour.  ADR-SSOT-002 Section 4b prescribes instead that each step is
a command invoked alone, returning one closed outcome plus the canonical next
step as DATA it does not execute.

Every scenario here runs the real `des` CLI as a real subprocess against a real
temporary Git repository, because that is exactly how the orchestrator reaches
it.  `TMPDIR` is redirected into the test's own directory so the deterministic
lane path the step derives can never collide with a live lane on the box.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


PACKAGE_PARENT = Path(__file__).parents[4] / "src"

#: A path under `nWave/` is a shipped asset, so a delta touching it leaves the
#: installed projection behind the checkout.  One scenario asserts the step says
#: so on its `NEXT` line, and another asserts it says the opposite.
SHIPPED_ASSET = "nWave/skills/probe/SKILL.md"
PRIVATE_FILE = "docs/internal/probe.md"


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


def opened(temp_home: Path, root: Path, name: str) -> Path:
    """One lane, open and reported -- the precondition every close scenario needs."""
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", name)
    assert result.returncode == 0, terminal(result)
    return Path(field(result, "WORKTREE"))


def test_open_creates_the_lane_and_reports_where_it_put_it(temp_home, root):
    base = git(root, "rev-parse", "HEAD")

    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")

    assert result.returncode == 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Success"
    worktree = Path(field(result, "WORKTREE"))
    # DETERMINISTIC, and reported: a caller never has to guess the path, and a
    # second `open` of the same name lands on the same place and so refuses.
    assert worktree == temp_home / "nwave-probe-lane"
    assert worktree.is_dir()
    assert field(result, "BRANCH") == "lane/probe"
    assert field(result, "BASE") == base
    assert git(worktree, "rev-parse", "HEAD") == base
    assert git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "lane/probe"
    # The canonical next step is DATA carrying its exact invocation form, and
    # the step executed none of it -- the lane holds no delivery of its own.
    assert f"des po --repo-root {worktree}" in field(result, "NEXT")
    assert f"des state --repo-root {worktree}" in field(result, "NEXT")
    # The retired command is named nowhere. Keyed on the INVOCATION form, not on
    # the bare word: the lane path itself may contain it.
    assert "des dispatch" not in field(result, "NEXT")
    assert field(result, "HOW-TO-INVOKE")


def test_open_refuses_a_name_whose_lane_already_exists_without_touching_it(
    temp_home, root
):
    worktree = opened(temp_home, root, "probe")
    put(worktree, "held.txt", "work in flight\n")

    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "LaneExists"
    assert str(worktree) in field(result, "WHY")
    assert field(result, "HOW")
    # Nothing was overwritten: the in-flight file and the branch both survive.
    assert (worktree / "held.txt").read_text() == "work in flight\n"
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe")


def test_integrate_advances_the_root_and_closes_the_lane(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode == 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Success"
    assert field(result, "INTEGRATED") == tip
    assert field(result, "REMOVED") == str(worktree)
    assert field(result, "BRANCH-REMOVED") == "lane/probe"
    # The root MOVED, and its working tree moved with it: an operator's live
    # checkout that advanced its ref but not its files would read as a tree
    # full of reverse-diff modifications it never made.
    assert git(root, "rev-parse", "HEAD") == tip
    assert (root / PRIVATE_FILE).read_text() == "note\n"
    assert git(root, "status", "--porcelain") == ""
    assert not worktree.exists()
    assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 1
    branches = git(root, "branch", "--list", "lane/probe")
    assert branches == "", branches
    # This delta touches no shipped asset, so no reinstallation is owed.
    assert "no step is owed" in field(result, "NEXT")


def test_integrate_names_the_reinstallation_when_the_delta_ships(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, SHIPPED_ASSET, "# probe\n", "feat(probe): ship a skill")

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode == 0, terminal(result)
    step = field(result, "NEXT")
    assert "install_nwave.py" in step, step
    assert SHIPPED_ASSET in step, step


def test_integrate_keep_worktree_retains_the_registered_lane_after_fast_forward(
    temp_home, root
):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")

    result = lane(
        temp_home,
        "integrate",
        "--repo-root",
        str(root),
        "--worktree",
        str(worktree),
        "--keep-worktree",
    )

    assert result.returncode == 0, terminal(result)
    assert field(result, "INTEGRATED") == tip
    assert field(result, "RETAINED") == str(worktree)
    assert field(result, "BRANCH-RETAINED") == "lane/probe"
    assert git(root, "rev-parse", "HEAD") == tip
    assert worktree.is_dir()
    assert str(worktree) in git(root, "worktree", "list", "--porcelain")
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe") == tip


def test_finalize_removes_retained_lane_after_destination_records_evolution(
    temp_home, root
):
    worktree = opened(temp_home, root, "probe")
    lane_tip = commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")
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
    evolution_tip = commit(
        root,
        "docs/evolution/2026-09-09-probe.md",
        "# Probe evolution\n",
        "docs(evolution): record probe",
    )

    finalized = lane(
        temp_home, "finalize", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert finalized.returncode == 0, terminal(finalized)
    assert field(finalized, "REMOVED") == str(worktree)
    assert field(finalized, "BRANCH-REMOVED") == "lane/probe"
    assert field(finalized, "NEXT") == "no step is owed"
    assert git(root, "rev-parse", "HEAD") == evolution_tip
    assert git(root, "merge-base", "--is-ancestor", lane_tip, evolution_tip) == ""
    assert not worktree.exists()
    assert git(root, "branch", "--list", "lane/probe") == ""


def test_finalize_refuses_unmerged_then_dirty_lane_without_losing_bytes(
    temp_home, root
):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")
    head = git(root, "rev-parse", "HEAD")

    unmerged = lane(
        temp_home, "finalize", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert unmerged.returncode != 0, terminal(unmerged)
    assert field(unmerged, "WHAT") == "LaneNotIntegrated"
    assert worktree.is_dir()
    assert git(worktree, "rev-parse", "HEAD") == tip
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe") == tip

    put(worktree, "uncommitted.txt", "in flight\n")
    dirty = lane(
        temp_home, "finalize", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert dirty.returncode != 0, terminal(dirty)
    assert field(dirty, "WHAT") == "LaneDirty"
    assert "uncommitted.txt" in field(dirty, "WHY")
    assert worktree.is_dir()
    assert (worktree / "uncommitted.txt").read_text() == "in flight\n"
    assert git(worktree, "rev-parse", "HEAD") == tip
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe") == tip


def test_integrate_refuses_a_dirty_lane_and_loses_nothing(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    head = git(root, "rev-parse", "HEAD")
    commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")
    put(worktree, "uncommitted.txt", "in flight\n")

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "LaneDirty"
    # The refusal NAMES what it saw, so the operator repairs the right file.
    assert "uncommitted.txt" in field(result, "WHY")
    assert worktree.is_dir()
    assert (worktree / "uncommitted.txt").read_text() == "in flight\n"
    assert git(root, "rev-parse", "HEAD") == head

    # GDP-3/GDP-4: the HOW is executed here, in this test, exactly as written.
    # A HOW nobody has run is a sentence, not a repair.
    how = field(result, "HOW")
    assert "commit" in how and "re-run" in how, how
    tip = commit(worktree, "uncommitted.txt", "in flight\n", "docs(probe): keep it")

    repaired = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert repaired.returncode == 0, terminal(repaired)
    assert git(root, "rev-parse", "HEAD") == tip
    assert not worktree.exists()


def test_integrate_refuses_when_the_root_moved_past_the_lane_base(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, PRIVATE_FILE, "note\n", "docs(probe): a note")
    moved = commit(root, "other.md", "elsewhere\n", "docs(other): trunk moved")

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "IntegrationStale"
    assert field(result, "HOW")
    # NOTHING was written: not the ref, not the lane, not the branch.
    assert git(root, "rev-parse", "HEAD") == moved
    assert worktree.is_dir()
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe")


def test_integrate_refuses_a_path_that_is_not_a_lane_of_this_root(temp_home, root):
    stranger = temp_home / "not-a-lane"
    stranger.mkdir()

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(stranger)
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "LaneNotRegistered"
    assert field(result, "HOW")


def test_open_refuses_a_name_that_is_not_one_path_segment(temp_home, root):
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "../escape")

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "InvalidLaneName"
    assert field(result, "HOW")
    assert not (temp_home / "nwave-../escape-lane").exists()


def test_all_lane_steps_are_advertised_by_the_cli_that_carries_them(temp_home):
    environment = {**os.environ, "PYTHONPATH": str(PACKAGE_PARENT)}
    environment.pop("PYTHONSTARTUP", None)
    listed = subprocess.run(
        [sys.executable, "-m", "des.cli", "--help"],
        text=True,
        capture_output=True,
        env=environment,
        timeout=180,
        check=False,
    )

    assert "lane" in listed.stdout, listed.stdout + listed.stderr
    lane_help = lane(temp_home, "--help")
    assert "finalize" in lane_help.stdout, terminal(lane_help)
