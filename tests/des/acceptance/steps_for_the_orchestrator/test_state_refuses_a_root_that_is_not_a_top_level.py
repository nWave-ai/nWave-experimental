"""`des state --repo-root` refuses a path that is not a repository top level.

ADR-DES-003 §4: the refusal is the existing class-A `InvalidRepositoryRoot`,
0 turns, WHAT / WHY / HOW, and its NEXT re-invokes `des state` -- never `des po`.

"The check does not run git" is measured, not trusted: the marker-only
repositories below carry `.git/HEAD` (or a `.git` file whose `gitdir:` target
carries HEAD) and NOTHING else, so git itself would call them no repository.
A check that asked git could not name their top level; only the marker read can.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    nexts,
)


def _refusal(step, turns: Path, path: Path) -> dict[str, str]:
    code, stdout, stderr = step("state", "--repo-root", str(path))
    rows = block(stdout, stderr)
    assert code == 1, stdout + stderr
    assert rows["DELIVERY-OUTCOME"] == "Refusal", stdout
    assert rows["WHAT"] == "InvalidRepositoryRoot", stdout
    assert rows["TURNS-BOUGHT"] == "0", stdout
    assert asked(turns) == []
    named = nexts(stdout)
    assert named, stdout
    assert all("des po" not in item for item in named), named
    assert all(item.startswith("des state --repo-root") for item in named), named
    return rows


def test_a_subdirectory_of_a_real_repository_names_its_top_level(
    step, root: Path, turns: Path
):
    inner = root / "nWave" / "agents"
    rows = _refusal(step, turns, inner)
    top, sub = root.resolve(), inner.resolve()
    assert rows["WHY"] == (
        f"{sub} is not a repository top level; "
        f"the repository top level above it is {top}"
    )
    assert rows["HOW"] == f"pass the repository top level {top} as --repo-root"


def test_the_nearest_marker_above_is_named_without_git(
    step, tmp_path: Path, turns: Path
):
    top = tmp_path / "marker-only"
    (top / ".git").mkdir(parents=True)
    (top / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    deep = top / "a" / "b"
    deep.mkdir(parents=True)
    rows = _refusal(step, turns, deep)
    assert rows["WHY"] == (
        f"{deep.resolve()} is not a repository top level; "
        f"the repository top level above it is {top.resolve()}"
    )
    assert rows["HOW"] == (
        f"pass the repository top level {top.resolve()} as --repo-root"
    )


def test_a_gitdir_file_marker_above_is_named(step, tmp_path: Path, turns: Path):
    store = tmp_path / "store"
    store.mkdir()
    (store / "HEAD").write_text("ref: refs/heads/main\n")
    top = tmp_path / "linked"
    top.mkdir()
    (top / ".git").write_text(f"gitdir: {store}\n")
    inner = top / "src"
    inner.mkdir()
    rows = _refusal(step, turns, inner)
    assert rows["WHY"] == (
        f"{inner.resolve()} is not a repository top level; "
        f"the repository top level above it is {top.resolve()}"
    )


def test_a_directory_outside_any_repository_names_no_top_level(
    step, tmp_path: Path, turns: Path
):
    # A directory merely NAMED .git, without HEAD, is not a repository.
    hollow = tmp_path / "hollow"
    (hollow / ".git").mkdir(parents=True)
    outside = hollow / "plain"
    outside.mkdir()
    rows = _refusal(step, turns, outside)
    assert rows["WHY"] == (
        f"{outside.resolve()} is not a repository top level and is inside no repository"
    )
    assert rows["HOW"] == "pass the top level of the repository to read"
    # The hollow .git holder must never be NAMED as a top level.
    assert "the repository top level above it is" not in rows["WHY"]
    assert f"is {hollow.resolve()}" not in rows["WHY"]
    assert f"top level {hollow.resolve()}" not in rows["HOW"]
