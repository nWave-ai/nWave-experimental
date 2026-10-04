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
it. ``TMPDIR`` points outside the project to prove that lanes are durable,
project-local workspaces rather than temporary directories.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from des.adapters.driven.codefact.tree_scope import TreeScope


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
    """An external temp directory which must not determine the lane path."""
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
    assert worktree == root / "lanes" / "probe"
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
    assert git(root, "status", "--porcelain", "--untracked-files=all") == ""
    assert not (root / ".gitignore").exists()


def test_local_exclusion_preserves_bytes_and_does_not_hide_real_source(temp_home, root):
    exclusion = root / ".git" / "info" / "exclude"
    original = b"# local policy\r\nscratch/\r\n# no final newline"
    exclusion.parent.mkdir(parents=True, exist_ok=True)
    exclusion.write_bytes(original)
    put(root, ".gitignore", "")
    commit(root, "source.py", "def original(): pass\n", "source")
    before = TreeScope(root)
    assert before.files("*.py") == [root / "source.py"]
    assert before.health_event() is None
    worktree = opened(temp_home, root, "probe")
    sibling = opened(temp_home, root, "sibling")
    assert exclusion.read_bytes() == original + b"\n/lanes/\n"
    put(root, "lanes/real/source.py", "def real(): pass\n")
    scope = TreeScope(root)
    assert set(scope.files("*.py")) == {
        root / "source.py",
        root / "lanes/real/source.py",
    }
    assert TreeScope(worktree).files("*.py") == [worktree / "source.py"]
    assert TreeScope(sibling).files("*.py") == [sibling / "source.py"]
    assert scope.health_event() == "filtered"


def test_independent_projects_can_open_the_same_lane_name(temp_home, root, tmp_path):
    second = tmp_path / "second"
    git(tmp_path, "clone", "-q", str(root), str(second))
    assert opened(temp_home, root, "same") == root / "lanes" / "same"
    assert opened(temp_home, second, "same") == second / "lanes" / "same"


@pytest.mark.parametrize(
    "obstruction", ["directory", "target-symlink", "parent-symlink"]
)
def test_open_preserves_non_owned_paths_and_refuses_symlink_escapes(
    temp_home, root, obstruction
):
    outside = temp_home / "outside"
    outside.mkdir()
    put(outside, "keep", "precious\n")
    target = root / "lanes" / "probe"
    if obstruction == "parent-symlink":
        target.parent.symlink_to(outside, target_is_directory=True)
    else:
        target.parent.mkdir()
        if obstruction == "target-symlink":
            target.symlink_to(outside / "absent", target_is_directory=True)
        else:
            target.mkdir()
            put(target, "keep", "owned elsewhere\n")
    put(root, ".git/info/exclude", "# existing local policy\n")
    before = (root / ".git/info/exclude").read_bytes()
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")
    assert result.returncode != 0, terminal(result)
    assert (outside / "keep").read_text() == "precious\n"
    assert not (outside / "absent").exists()
    assert (root / ".git/info/exclude").read_bytes() == before
    assert git(root, "branch", "--list", "lane/probe") == ""
    if obstruction == "directory":
        assert (target / "keep").read_text() == "owned elsewhere\n"
    elif obstruction == "target-symlink":
        assert target.is_symlink()
    else:
        assert target.parent.is_symlink()


def test_open_refuses_to_ignore_tracked_project_source(temp_home, root):
    commit(root, "lanes/source.py", "def real(): pass\n", "source")
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")
    assert result.returncode != 0, terminal(result)
    assert field(result, "WHAT") == "UnsafeLanePath"
    assert not (root / "lanes/probe").exists()
    assert TreeScope(root).files("*.py") == [root / "lanes/source.py"]


def test_old_registered_external_lane_can_still_integrate_and_finalize(temp_home, root):
    worktree = temp_home / "nwave-historical-lane"
    git(root, "worktree", "add", "-b", "lane/historical", str(worktree))
    tip = commit(worktree, "lanes/source.py", "def legacy(): pass\n", "legacy source")
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
        temp_home, "finalize", "--repo-root", str(root), "--worktree", str(worktree)
    )
    assert finalized.returncode == 0, terminal(finalized)
    assert not worktree.exists()
    assert git(root, "rev-parse", "HEAD") == tip
    assert (root / "lanes/source.py").read_text() == "def legacy(): pass\n"


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
    sibling = opened(temp_home, root, "sibling")
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
    assert sibling.is_dir()
    assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 2
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
    sibling = opened(temp_home, root, "sibling")
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
    assert sibling.is_dir()
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/sibling")


def test_nested_lane_is_not_removed_with_its_clean_containing_lane(temp_home, root):
    parent = opened(temp_home, root, "parent")
    child = parent / "lanes/child"
    git(parent, "worktree", "add", str(child), "-b", "lane/child")
    put(child, "in-flight.txt", "must survive\n")
    assert git(parent, "status", "--porcelain") == ""
    for step in ("integrate", "finalize"):
        result = lane(
            temp_home, step, "--repo-root", str(root), "--worktree", str(parent)
        )
        assert result.returncode != 0, terminal(result)
        assert field(result, "WHAT") == "LaneDirty"
        assert (child / "in-flight.txt").read_text() == "must survive\n"


def test_open_refuses_when_tracked_ignore_policy_overrides_local_exclusion(
    temp_home, root
):
    commit(root, ".gitignore", "!/lanes/\n", "ignore policy")
    result = lane(temp_home, "open", "--repo-root", str(root), "--name", "probe")
    assert result.returncode != 0, terminal(result)
    assert field(result, "WHAT") == "LaneNotOpened"
    assert not (root / "lanes/probe").exists()
    assert (root / ".gitignore").read_text() == "!/lanes/\n"


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
    assert not (root / "escape").exists()


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


def lanes_in(completed: subprocess.CompletedProcess[str]) -> dict[str, dict[str, str]]:
    """The per-lane blocks a `des lane status` terminal reported, keyed by path."""
    blocks: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        for label in ("LANE: ", "UNREGISTERED: "):
            if line.startswith(label):
                current = line[len(label) :]
                blocks[current] = {}
                break
        else:
            if current is not None and ": " in line:
                name, value = line.split(": ", 1)
                blocks[current][name] = value
    return blocks


def emitted_git_commands(next_step: str) -> list[list[str]]:
    """The git commands the software's own NEXT advice names, in order.

    A caller executes the advice as emitted; this consumes the producer's
    output exactly that way, so the scenarios below prove what EXECUTING the
    remediation does to the repository, never what its prose says.
    """
    commands = []
    for fragment in next_step.replace("(", " ").replace(")", " ").split(";"):
        start = fragment.find("git -C ")
        if start != -1:
            commands.append(shlex.split(fragment[start:].strip()))
    return commands


def test_status_reports_a_finished_unintegrated_lane_as_not_delivered(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, "feature.md", "work\n", "lane work")
    head_before = git(root, "rev-parse", "HEAD")
    worktrees_before = git(root, "worktree", "list", "--porcelain")

    result = lane(temp_home, "status", "--repo-root", str(root))

    assert result.returncode == 0, terminal(result)
    reported = lanes_in(result)[str(worktree)]
    assert reported["TIP"] == tip
    assert reported["INTEGRATED"].startswith("no")
    assert "des lane integrate" in reported["NEXT"]
    assert field(result, "DESTINATION-HEAD") == head_before
    # `status` observed; it merged and registered nothing.
    assert git(root, "rev-parse", "HEAD") == head_before
    assert git(root, "worktree", "list", "--porcelain") == worktrees_before


def test_status_shows_a_retained_integrated_lane_pending_cleanup(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, "feature.md", "work\n", "lane work")
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

    result = lane(temp_home, "status", "--repo-root", str(root))

    reported = lanes_in(result)[str(worktree)]
    assert reported["INTEGRATED"].startswith("yes")
    assert reported["CONTENT"] == "clean"
    assert "des lane finalize" in reported["NEXT"]
    assert worktree.is_dir()


def test_status_names_dirty_untracked_and_ignored_bytes_separately(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, ".gitignore", "build/\n", "ignore policy")
    (worktree / "build").mkdir()
    (worktree / "build" / "artifact.o").write_text("compiled\n")
    put(worktree, "tracked.md", "edited\n")
    put(worktree, "stray.md", "untracked\n")

    result = lane(temp_home, "status", "--repo-root", str(root))

    reported = lanes_in(result)[str(worktree)]
    content = reported["CONTENT"]
    assert "tracked.md" in content
    assert "stray.md" in content
    assert "build/" in content
    assert reported["AVAILABILITY"] == "AVAILABLE"


def test_finalize_refuses_a_lane_whose_only_extra_bytes_are_ignored(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, ".gitignore", "build/\n", "ignore policy")
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
    (worktree / "build").mkdir()
    (worktree / "build" / "evidence.bin").write_text("must survive\n")
    plain = subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert not plain.stdout.strip()  # the trap: Git itself reports the lane clean

    result = lane(
        temp_home, "finalize", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "DELIVERY-OUTCOME") == "Refusal"
    assert field(result, "WHAT") == "LaneIgnoredContent"
    assert field(result, "HOW")
    assert worktree.is_dir()
    assert (worktree / "build" / "evidence.bin").read_text() == "must survive\n"


def test_integrate_without_keep_refuses_ignored_bytes_too(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, "feature.md", "work\n", "lane work")
    commit(worktree, ".gitignore", "build/\n", "ignore policy")
    (worktree / "build").mkdir()
    (worktree / "build" / "evidence.bin").write_text("must survive\n")

    result = lane(
        temp_home, "integrate", "--repo-root", str(root), "--worktree", str(worktree)
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "WHAT") == "LaneIgnoredContent"
    assert worktree.is_dir()
    assert (worktree / "build" / "evidence.bin").exists()
    assert git(root, "rev-parse", "--verify", "refs/heads/lane/probe") != tip


def test_require_integrated_passes_only_on_destination_history(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    commit(worktree, "feature.md", "work\n", "lane work")
    head_before = git(root, "rev-parse", "HEAD")
    unintegrated = lane(
        temp_home,
        "status",
        "--repo-root",
        str(root),
        "--require-integrated",
        str(worktree),
    )

    assert unintegrated.returncode != 0, terminal(unintegrated)
    assert field(unintegrated, "DELIVERY-OUTCOME") == "Refusal"
    assert field(unintegrated, "WHAT") == "LaneNotIntegrated"
    assert "des lane integrate" in field(unintegrated, "HOW")
    assert git(root, "rev-parse", "HEAD") == head_before  # the assertion never merges

    retained = lane(
        temp_home,
        "integrate",
        "--repo-root",
        str(root),
        "--worktree",
        str(worktree),
        "--keep-worktree",
    )
    assert retained.returncode == 0, terminal(retained)
    (worktree / "build").mkdir()
    (worktree / "build" / "artifact.o").write_text("ignored\n")

    satisfied = lane(
        temp_home,
        "status",
        "--repo-root",
        str(root),
        "--require-integrated",
        str(worktree),
    )

    # Content is not this assertion's business: a retained integrated lane
    # holding ignored bytes is still integrated; removal guards that alone.
    assert satisfied.returncode == 0, terminal(satisfied)
    assert "REQUIRE-INTEGRATED: satisfied" in satisfied.stdout

    stranger = temp_home / "never-a-lane"
    stranger.mkdir()
    unregistered = lane(
        temp_home,
        "status",
        "--repo-root",
        str(root),
        "--require-integrated",
        str(stranger),
    )

    assert unregistered.returncode != 0, terminal(unregistered)
    assert field(unregistered, "WHAT") == "LaneNotRegistered"


def test_status_reports_a_missing_registration_that_consumes_no_disk(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    shutil.rmtree(worktree)

    result = lane(temp_home, "status", "--repo-root", str(root))

    assert result.returncode == 0, terminal(result)
    reported = lanes_in(result)[str(worktree)]
    assert reported["AVAILABILITY"].startswith("MISSING")
    assert reported["CONTENT"].startswith("unobservable")
    assert not worktree.exists()
    # The remediation's real property -- sibling registrations survive, the
    # tip stays anchored -- is proven by EXECUTING the emitted advice in the
    # two scenarios below, not by quoting its wording here.


def test_status_reports_a_lanes_directory_entry_no_lane_registered(temp_home, root):
    stray = root / "lanes" / "stray"
    stray.mkdir(parents=True)
    (stray / "leftover.txt").write_text("unowned bytes\n")

    result = lane(temp_home, "status", "--repo-root", str(root))

    assert result.returncode == 0, terminal(result)
    reported = lanes_in(result)
    assert str(stray) in reported  # named where it belongs: an UNREGISTERED row
    # No per-lane block claims the stray: it has no branch, tip, ancestry,
    # content or availability -- no registration, so no lane facts at all.
    unowned = reported[str(stray)]
    assert not {"TIP", "BRANCH", "INTEGRATED", "CONTENT", "AVAILABILITY"} & set(unowned)


def test_status_reports_a_locked_lane_as_worktree_active(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    git(root, "worktree", "lock", str(worktree))

    result = lane(temp_home, "status", "--repo-root", str(root))

    reported = lanes_in(result)[str(worktree)]
    assert reported["AVAILABILITY"].startswith("LOCKED")
    assert "worktree unlock" in reported["NEXT"]


def test_status_measures_reachability_against_an_explicit_destination(temp_home, root):
    worktree = opened(temp_home, root, "probe")
    tip = commit(worktree, "feature.md", "work\n", "lane work")

    against_head = lane(temp_home, "status", "--repo-root", str(root))
    assert lanes_in(against_head)[str(worktree)]["INTEGRATED"].startswith("no")

    against_tip = lane(
        temp_home, "status", "--repo-root", str(root), "--destination", tip
    )
    assert against_tip.returncode == 0, terminal(against_tip)
    assert lanes_in(against_tip)[str(worktree)]["INTEGRATED"].startswith("yes")


def test_require_integrated_reports_every_named_failure_in_one_pass(temp_home, root):
    first = opened(temp_home, root, "aa")
    second = opened(temp_home, root, "bb")
    commit(first, "a.md", "a\n", "a work")
    commit(second, "b.md", "b\n", "b work")

    result = lane(
        temp_home,
        "status",
        "--repo-root",
        str(root),
        "--require-integrated",
        str(first),
        "--require-integrated",
        str(second),
    )

    # One pass, all N independent defects: a refusal naming only lanes/aa
    # while lanes/bb is invisible fails the standing reject-all-at-once
    # falsifier -- the second run must never surface what the first saw.
    assert result.returncode != 0, terminal(result)
    assert field(result, "WHAT") == "LaneNotIntegrated"
    why = field(result, "WHY")
    assert "2 named lanes refuse" in why
    assert "(1)" in why and "(2)" in why
    assert str(first) in why and str(second) in why
    how = field(result, "HOW")
    assert f"--worktree {first}" in how and f"--worktree {second}" in how


def test_require_integrated_numbers_mixed_independent_failures(temp_home, root):
    unfinished = opened(temp_home, root, "aa")
    commit(unfinished, "a.md", "a\n", "a work")
    stranger = temp_home / "never-a-lane"
    stranger.mkdir()

    result = lane(
        temp_home,
        "status",
        "--repo-root",
        str(root),
        "--require-integrated",
        str(stranger),
        "--require-integrated",
        str(unfinished),
    )

    assert result.returncode != 0, terminal(result)
    assert field(result, "WHAT") == "RequirementsRefused"
    why = field(result, "WHY")
    assert "2 named lanes refuse" in why
    assert "(1)" in why and "(2)" in why
    assert str(stranger) in why and str(unfinished) in why


def test_branch_backed_missing_lane_remediation_preserves_siblings(temp_home, root):
    remedy = opened(temp_home, root, "remedy")
    remedy_tip = commit(remedy, "work.md", "work\n", "remedy work")
    shutil.rmtree(remedy)
    sibling = opened(temp_home, root, "sibling")
    sibling_tip = commit(sibling, "sib.md", "sib\n", "sibling work")
    git(root, "branch", "unrelated", sibling_tip)

    result = lane(temp_home, "status", "--repo-root", str(root))
    commands = emitted_git_commands(lanes_in(result)[str(remedy)]["NEXT"])
    assert commands, "the software named no executable remediation"
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True)

    # Executing the emitted remediation preserved every registration it did
    # not name, its anchored sibling work, and an unrelated branch -- and
    # ended with the remedy workspace live again on its anchoring branch.
    registry = git(root, "worktree", "list", "--porcelain")
    assert str(sibling) in registry
    assert git(root, "rev-parse", "refs/heads/lane/sibling") == sibling_tip
    assert git(root, "rev-parse", "refs/heads/unrelated") == sibling_tip
    assert git(root, "rev-parse", "refs/heads/lane/remedy") == remedy_tip
    assert git(remedy, "rev-parse", "HEAD") == remedy_tip


def test_detached_missing_lane_remediation_anchors_the_tip_before_any_loss(
    temp_home, root
):
    base = git(root, "rev-parse", "HEAD")
    remedy = root / "lanes" / "detached"
    git(root, "worktree", "add", "--detach", str(remedy), base)
    git(remedy, "config", "user.email", "a@b")
    git(remedy, "config", "user.name", "a")
    orphan_tip = commit(remedy, "orphan.md", "work\n", "orphan work")
    shutil.rmtree(remedy)
    sibling = opened(temp_home, root, "sibling")
    sibling_tip = commit(sibling, "sib.md", "sib\n", "sibling work")
    # The pre-state the old prune advice destroyed: a detached tip held by no
    # ref at all, one command away from gc-eligibility.
    assert git(root, "branch", "--all", "--contains", orphan_tip) == ""

    result = lane(temp_home, "status", "--repo-root", str(root))
    commands = emitted_git_commands(lanes_in(result)[str(remedy)]["NEXT"])
    assert commands, "the software named no executable remediation"
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True)

    # The executed remediation anchored the tip into a recoverable branch
    # BEFORE anything was cleared, then brought the workspace back live on
    # that branch -- and lost no sibling registration or work.
    assert git(root, "rev-parse", "refs/heads/recover/detached") == orphan_tip
    registry = git(root, "worktree", "list", "--porcelain")
    assert str(sibling) in registry
    assert git(root, "rev-parse", "refs/heads/lane/sibling") == sibling_tip
    assert str(remedy) in registry
    assert git(remedy, "rev-parse", "HEAD") == orphan_tip


def test_dangling_symlink_registration_degrades_itself_and_keeps_the_inventory(
    temp_home, root
):
    healthy = opened(temp_home, root, "healthy")
    broken = opened(temp_home, root, "broken")
    shutil.rmtree(broken)
    broken.symlink_to(temp_home / "nowhere")

    result = lane(temp_home, "status", "--repo-root", str(root))

    # One dangling registration must not discard the healthy lane's
    # measured rows: Git itself is healthy, so GitUnavailable is a lie.
    assert result.returncode == 0, terminal(result)
    broken_row = lanes_in(result)[str(broken)]
    assert broken_row["AVAILABILITY"].startswith("MISSING")
    assert "dangling symlink" in broken_row["CONTENT"]
    healthy_row = lanes_in(result)[str(healthy)]
    assert healthy_row["CONTENT"] == "clean"
    assert healthy_row["AVAILABILITY"] == "AVAILABLE"


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads through mode 000, the defect cannot fire"
)
def test_unreadable_lane_degrades_its_content_and_keeps_the_inventory(temp_home, root):
    healthy = opened(temp_home, root, "healthy")
    unreadable = opened(temp_home, root, "unreadable")
    unreadable.chmod(0o000)
    try:
        result = lane(temp_home, "status", "--repo-root", str(root))
    finally:
        unreadable.chmod(0o755)

    assert result.returncode == 0, terminal(result)
    degraded = lanes_in(result)[str(unreadable)]
    assert degraded["CONTENT"].startswith("unobservable")
    assert "git status failed" in degraded["CONTENT"]
    assert lanes_in(result)[str(healthy)]["CONTENT"] == "clean"
