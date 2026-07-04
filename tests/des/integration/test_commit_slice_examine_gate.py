"""Integration test: the commit-time examine-verdict gate (evolution-plan P1.2).

``des commit-slice`` mechanically requires a slice to have been EXAMINED (a
human-intent charter walked through the real surface by ``nw-user-examiner``,
verdict recorded via ``des record-examine-verdict``) before it may commit --
replacing the per-slice code-reading C_REVIEWER_AUDIT with execution-
observation. The gate is ARMED only when a charter exists for the feature
under ``docs/product/expectations/{feature_id}/*.md`` (or the operator opts in
via ``NWAVE_EXAMINE_GATE_OPT_IN=1``), so the pre-existing commit-slice test
suite (no charters, no opt-in) stays green -- see
``test_commit_slice_no_charter_leaves_gate_unarmed`` below for the explicit
backward-compat pin.

Real I/O: a real tmp git work-tree, real ``git`` subprocesses -- mirrors
``tests/des/integration/test_commit_slice.py``'s harness.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import main as record_examine_verdict_main


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a git work-tree with one committed base file (the slice's parent)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def _write_charter(repo: Path, feature_id: str, slice_id: str, body: str) -> str:
    """Write a charter under the User-Examiner convention; return its repo-relative path."""
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / f"{slice_id}.md"
    charter_file.write_text(body, encoding="utf-8")
    return str(charter_file.relative_to(repo))


def _record_examine_verdict(
    repo: Path,
    feature_id: str,
    slice_id: str,
    charter_relpath: str,
    verdict: str,
    capsys,
) -> None:
    exit_code = record_examine_verdict_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--slice",
            slice_id,
            "--charter",
            charter_relpath,
            "--verdict",
            verdict,
            "--observations",
            f"observed during {slice_id} walkthrough",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    capsys.readouterr()  # drain -- the producer's own JSON is not under test here
    assert exit_code == 0


def _add_new_slice_file(repo: Path, name: str) -> None:
    (repo / "tests" / "unit" / name).write_text(
        "def test_slice():\n    assert True\n", encoding="utf-8"
    )


def test_commit_refused_when_examine_verdict_is_fail(tmp_path: Path, capsys) -> None:
    """NEGATIVE: a recorded FAIL examine-verdict refuses the commit exit 1."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, "# Charter\n\nWalk the checkout flow.\n"
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "FAIL", capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 1
    assert event["event"] == "ExamineVerdictRefused"
    assert event["slice_id"] == slice_id
    assert "what" in event and "why" in event and "how" in event


def test_commit_refused_when_no_verdict_recorded(tmp_path: Path, capsys) -> None:
    """NEGATIVE: charter exists (gate ARMED) but NO verdict recorded -> exit 2."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    _write_charter(repo, feature_id, slice_id, "# Charter\n\nWalk the checkout flow.\n")
    # No des record-examine-verdict call at all.

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictMissing"
    assert event["slice_id"] == slice_id
    assert "record-examine-verdict" in event["how"]


def test_commit_refused_when_pass_verdict_charter_changed_after(
    tmp_path: Path, capsys
) -> None:
    """NEGATIVE: PASS recorded, then charter bytes CHANGE -> stale-seal void, refused."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, "# Charter\n\nORIGINAL body.\n"
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)

    # Mutate the charter AFTER the exam -- the recorded charter_seal is now stale.
    (repo / charter).write_text("# Charter\n\nTAMPERED body.\n", encoding="utf-8")

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictStale"
    assert event["slice_id"] == slice_id


def test_commit_proceeds_when_pass_verdict_seal_matches(tmp_path: Path, capsys) -> None:
    """POSITIVE: PASS verdict + matching seal -> commit proceeds to SliceCommitted."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, "# Charter\n\nWalk the checkout flow.\n"
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True


def test_commit_refused_when_verdict_is_indeterminate(tmp_path: Path, capsys) -> None:
    """INDETERMINATE verdict refuses LOUD (exit 2) -- never a silent pass."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, "# Charter\n\nWalk the checkout flow.\n"
    )
    _record_examine_verdict(
        repo, feature_id, slice_id, charter, "INDETERMINATE", capsys
    )

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictIndeterminate"
    assert event["slice_id"] == slice_id


def test_commit_slice_no_charter_leaves_gate_unarmed(tmp_path: Path, capsys) -> None:
    """BACKWARD-COMPAT: no charter for the feature -> gate not armed -> unchanged.

    No docs/product/expectations/ directory, no NWAVE_EXAMINE_GATE_OPT_IN, no
    ExamineVerdict recorded -- the pre-existing commit-slice path is completely
    unaffected: the slice commits + verifies exactly as before P1.2.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-no-charter", "slice-01"

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True
