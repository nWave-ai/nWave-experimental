"""Public blast-radius observations must distinguish measured deltas from unknown impact."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from tests.cli_resolve import resolve_des_cli_cmd


# Canonical default thresholds (feature-delta "Canonical default thresholds"
# table) -- slice-01's OWN reduced files+lines-only tier rule reads these
# same two numbers; slice-02 wires the full `DESConfig` cascade around them.
SMALL_MAX_FILES = 2
SMALL_MAX_LINES = 10


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_git_repo(root: Path) -> None:
    """A real git work-tree with two small tracked files at HEAD."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    (root / "module_a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "module_b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


def _init_git_repo_data_only(root: Path) -> None:
    """Use opaque inputs so unsupported consumer analysis cannot hide behind omission."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    (root / "note_a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "note_b.txt").write_text("beta\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


def _last_json_line(stdout: str) -> dict:
    """The last `{...}`-shaped stdout line, parsed. Mirrors the
    `_last_json_event` precedent in `tests/des/integration/test_commit_slice.py`
    -- `des` prefixes real invocations with an unrelated freshness-autoskip
    event line the AT must skip past."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def _invoke_in_process(
    repo_root: Path, argv: list[str], capsys
) -> tuple[int, str, dict | None]:
    """Drive `des.cli.blast_radius.main(argv)` IN-PROCESS (P3 lazy import).

    Returns (exit_code, stderr, parsed-stdout-JSON-or-None).
    """
    from des.cli.blast_radius import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    payload: dict | None = None
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    if json_lines:
        payload = json.loads(json_lines[-1])
    return exit_code, captured.err, payload


# --- @walking_skeleton -- the ONE subprocess-E2E for the whole feature ----


def test_blast_radius_reports_real_git_measures_without_fabricating_consumers(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change"""
    # Venv-first resolution (row5 pattern, generalized): never bare
    # `shutil.which("des")`, which is shadowable by a stale global `des`
    # earlier on PATH -- see `tests/cli_resolve.py::resolve_des_cli_cmd`.
    des_cmd = resolve_des_cli_cmd("des", "des.cli.__main__")

    repo = tmp_path / "repo"
    _init_git_repo_data_only(repo)
    # Uncommitted, small edit across the two tracked files -- 2 files
    # touched (<= SMALL_MAX_FILES), 4 lines added total (<= SMALL_MAX_LINES).
    with (repo / "note_a.txt").open("a", encoding="utf-8") as handle:
        handle.write("second line\nthird line\n")
    with (repo / "note_b.txt").open("a", encoding="utf-8") as handle:
        handle.write("second line\nthird line\n")

    completed = subprocess.run(
        [
            *des_cmd,
            "blast-radius",
            "--repo",
            str(repo),
            "--paths",
            "note_a.txt",
            "note_b.txt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        f"expected a clean measurement, got exit={completed.returncode} "
        f"stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["files"] == 2
    assert payload["measures"]["lines_changed"] == 4
    assert payload["measures"]["consumer_counts"] == {
        "note_a.txt": None,
        "note_b.txt": None,
    }


# --- in-process: the files+lines-only S/M classification ------------------


@pytest.mark.parametrize(
    "case",
    ["too_many_files", "too_many_lines"],
)
def test_blast_radius_escalates_to_medium_tier_beyond_small_thresholds(
    tmp_path: Path, capsys, case: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A change that exceeds either the small-files or small-lines threshold
    is measured M, not silently S -- regardless of WHICH signal tripped it.

    NOTE: deliberately no shared docstring content across the two
    parametrize cases beyond this fixed contract text (pytest-pspec renders
    the JUnit testcase name from the docstring verbatim, without the
    parametrize id -- a distinguishing case-specific assertion below, not
    the docstring, is what proves each branch independently).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    if case == "too_many_files":
        # 3 named paths > SMALL_MAX_FILES=2, each with a trivial diff.
        for name in ("m1.py", "m2.py", "m3.py"):
            (repo / name).write_text("x = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed three files")
        with (repo / "m1.py").open("a", encoding="utf-8") as handle:
            handle.write("y = 2\n")
        paths = ["m1.py", "m2.py", "m3.py"]
        expected_files = 3
    else:
        # 1 named path (<= SMALL_MAX_FILES) but > SMALL_MAX_LINES lines
        # added in one uncommitted edit.
        big_edit = "".join(f"line_{i} = {i}\n" for i in range(SMALL_MAX_LINES + 2))
        with (repo / "module_a.py").open("a", encoding="utf-8") as handle:
            handle.write(big_edit)
        paths = ["module_a.py"]
        expected_files = 1

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", *paths], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["tier"] == "M"
    assert payload["measures"]["files"] == expected_files
    if case == "too_many_files":
        assert payload["measures"]["files"] > SMALL_MAX_FILES
    else:
        assert payload["measures"]["lines_changed"] > SMALL_MAX_LINES


# --- error paths (>= 40% of this module's scenarios) -----------------------


def test_blast_radius_rejects_a_nonexistent_path_instead_of_reporting_small(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A typo'd `--paths` entry that names no real file must be refused loudly
    -- never silently measured as a 0-line, 0-file S-tier change (the exact
    vacuous-truth footgun the orchestrator flagged for this slice).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    exit_code, _stderr, payload = _invoke_in_process(
        repo,
        ["--repo", str(repo), "--paths", "does-not-exist.py"],
        capsys,
    )

    assert exit_code == 2
    assert payload is not None
    assert payload["event"] != "BlastRadiusMeasured"
    assert "tier" not in payload
    assert "measures" not in payload
    assert any("does-not-exist.py" in reason for reason in payload["reasons"])


def test_blast_radius_requires_a_paths_argument(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    Omitting `--paths` entirely (slice-01's only supported input mode) is a
    usage error, not a silently-empty measurement.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    exit_code, stderr, payload = _invoke_in_process(repo, ["--repo", str(repo)], capsys)

    assert exit_code == 2
    assert payload is None or payload.get("event") != "BlastRadiusMeasured"
    assert "paths" in stderr.lower()


def test_blast_radius_degrades_lines_changed_to_null_outside_a_git_worktree(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A `--repo` that is not a git work-tree cannot honestly produce a
    `lines_changed` count -- the measurement degrades to `null` (never a
    fabricated 0) and the tier honestly escalates to M (S is unreachable
    without a real line count), naming the cause in `reasons`.
    """
    repo = tmp_path / "plain_dir"
    repo.mkdir(parents=True)
    (repo / "module_a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    # Deliberately NOT `git init`-ed.

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["lines_changed"] is None
    assert payload["measures"]["files"] == 1
    assert payload["tier"] == "M", (
        "an indeterminate lines_changed must never resolve to S -- an "
        "unknown blast radius is treated as the worse case, never silently "
        "smaller (GDP-6)"
    )
    assert any("git" in reason.lower() for reason in payload["reasons"]), (
        "the degrade cause (not a git work-tree) must be named, not silent"
    )
