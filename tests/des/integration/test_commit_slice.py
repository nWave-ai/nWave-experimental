"""Integration test: `des commit-slice` produces a verified slice commit.

Closes the recurring gate-scope-timing defect (#67 facet-4 / AD-23 adjacent):
the committed-scope ``Gate-Scope:`` trailer must be correct BY CONSTRUCTION, so
the G_COMMIT exit gate (``run_contract_gate --verify-gate-scope``) verifies
clean with NO manual ``git commit --amend``.

The load-bearing scenario reproduces the EXACT defect: a slice that adds a NEW
test file (untracked at terminating-run time). The pre-fix producer digest --
computed before the commit, when the new file is untracked -- would have stamped
the PARENT's committed-scope digest, which the exit gate then rejects as a
mismatch. ``commit-slice`` stages -> commits -> computes the committed-scope
digest of the RESULTING HEAD (now including the new file) -> amends -> the
commit verifies clean.

Real I/O: a real tmp git work-tree, real ``git`` subprocesses, a real
``run_contract_gate --verify-gate-scope`` subprocess collection. Integration
layer (Mandate 6 -- subprocess adapter, real exit codes).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli.commit_slice import main as commit_slice_main
from des.cli.run_contract_gate import main as run_contract_gate_main


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a git work-tree with one committed test file (the slice's parent)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
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


def test_commit_slice_verifies_clean_with_new_untracked_at(
    tmp_path: Path, capsys
) -> None:
    """A slice adding a NEW (untracked) test file commits + verifies with NO amend.

    This is the acceptance proof for the gate-scope-timing fix: the committed
    commit carries the committed-scope digest of its OWN tree, so the exit gate
    verifies clean -- the manual --amend tax is eliminated.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # The slice's NEW test file -- untracked, exactly the defect trigger.
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--message",
            "feat(slice): add the new slice behaviour\n\nSlice-Id: slice-01",
        ]
    )
    out = capsys.readouterr().out
    event = _last_json_event(out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True
    assert len(event["gate_scope_digest"]) == 64

    # The commit message carries the committed-scope digest as a Gate-Scope:
    # trailer -- and ONLY that, the placeholder is gone.
    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert f"Gate-Scope: {event['gate_scope_digest']}" in message
    assert "0" * 64 not in message
    assert "Slice-Id: slice-01" in message

    # Independent re-verification: the SAME gate the G_COMMIT exit gate runs
    # accepts HEAD with NO amend in between.
    capsys.readouterr()  # drain
    verify_code = run_contract_gate_main(
        ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    )
    verify_event = _last_json_event(capsys.readouterr().out)
    assert verify_code == 0
    assert verify_event["event"] == "GateScopeVerified"


def test_commit_slice_refuses_message_with_gate_scope_trailer(
    tmp_path: Path, capsys
) -> None:
    """A --message that already carries a Gate-Scope: trailer is MalformedInput.

    The trailer is appended mechanically; a caller-supplied one would race the
    mechanical stamp. Fail closed (exit 2) before any git mutation.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "tests" / "unit" / "test_x.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--message",
            "feat(x): thing\n\nGate-Scope: " + ("a" * 64),
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "MalformedInput"


def test_commit_slice_refuses_empty_index(tmp_path: Path, capsys) -> None:
    """Nothing staged -> MalformedInput exit 2 (no empty slice commit)."""
    repo = tmp_path / "repo"
    _init_repo(repo)  # clean tree, nothing new

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--message",
            "feat(x): nothing to commit\n\nSlice-Id: slice-02",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "MalformedInput"
