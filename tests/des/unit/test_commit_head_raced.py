"""Unit tests for the F3 CommitHeadRaced detection (slice-05 revision).

slice-05 of F-DES-ATDD-PURE-HOOK-GATES -- closes deep-review Finding 3.

M9 SHA-pinning landed (`_resolve_head_sha` pins `git rev-parse HEAD` once and
passes it to E1/E2 via `--commit`). But no `CommitHeadRaced` race-detection
existed. Finding 3 requires the exit-gate CLIs
(`verify_slice_commit_completeness.py`, `run_contract_gate.py`) to re-read
`HEAD` and, if it has moved off the pinned `--commit` SHA, fail closed emitting
`{"event": "CommitHeadRaced", ...}`.

Detection is keyed on the new optional `--expected-head` argument: when present,
the CLI resolves `git rev-parse HEAD` afresh and compares. When absent, the
CLI behaves byte-for-byte as before (no race check) -- so every existing caller
is unaffected.

Port-to-port: the driving port is each CLI's `main(argv)`; the JSON stdout
payload + exit code are the observable surface; a real git repo on tmp_path is
the driven dependency.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli import run_contract_gate, verify_slice_commit_completeness


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _init_repo(repo: Path) -> str:
    """Init a repo with a slice commit; return its HEAD SHA."""
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    (repo / "at_slice-01.feature").write_text(
        "@slice-01\nFeature: f\n  Scenario: s\n    Given x\n", encoding="utf-8"
    )
    _git(repo, "add", "at_slice-01.feature")
    _git(repo, "commit", "-m", "feat: deliver slice-01\n\nSlice-Id: slice-01")
    return _git(repo, "rev-parse", "HEAD").strip()


def _move_head(repo: Path) -> str:
    """Make a second commit so HEAD moves off the pinned SHA; return new HEAD."""
    (repo / "more.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", "more.py")
    _git(repo, "commit", "-m", "chore: amend-like follow-up")
    return _git(repo, "rev-parse", "HEAD").strip()


# --- verify_slice_commit_completeness (E1) ----------------------------------


def test_e1_no_expected_head_arg_skips_race_check(tmp_path: Path, capsys) -> None:
    """Without --expected-head, E1 behaves exactly as before (no race check)."""
    head = _init_repo(tmp_path)
    code = verify_slice_commit_completeness.main(
        ["--repo", str(tmp_path), "--commit", head]
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 0
    assert payload["event"] == "SliceCommitComplete"


def test_e1_head_unmoved_passes_race_check(tmp_path: Path, capsys) -> None:
    """When HEAD still matches the pinned SHA, E1 proceeds to its verdict."""
    head = _init_repo(tmp_path)
    code = verify_slice_commit_completeness.main(
        ["--repo", str(tmp_path), "--commit", head, "--expected-head", head]
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 0
    assert payload["event"] == "SliceCommitComplete"


def test_e1_head_moved_off_pinned_sha_fails_closed(tmp_path: Path, capsys) -> None:
    """A HEAD moved off the pinned SHA is a CommitHeadRaced fail-closed block."""
    pinned = _init_repo(tmp_path)
    moved = _move_head(tmp_path)
    assert pinned != moved

    code = verify_slice_commit_completeness.main(
        ["--repo", str(tmp_path), "--commit", pinned, "--expected-head", pinned]
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 1
    assert payload["event"] == "CommitHeadRaced"
    assert payload["pinned_sha"] == pinned
    assert payload["current_sha"] == moved


# --- run_contract_gate (E2) -------------------------------------------------


def test_e2_head_moved_off_pinned_sha_fails_closed(tmp_path: Path, capsys) -> None:
    """E2 --verify-gate-scope with a raced HEAD is a CommitHeadRaced block."""
    pinned = _init_repo(tmp_path)
    moved = _move_head(tmp_path)
    assert pinned != moved

    code = run_contract_gate.main(
        [
            "--repo",
            str(tmp_path),
            "--commit",
            pinned,
            "--verify-gate-scope",
            "--expected-head",
            pinned,
        ]
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 1
    assert payload["event"] == "CommitHeadRaced"
    assert payload["pinned_sha"] == pinned
    assert payload["current_sha"] == moved


def test_e2_no_expected_head_arg_skips_race_check(tmp_path: Path, capsys) -> None:
    """Without --expected-head, E2 --verify-gate-scope runs the normal verdict."""
    head = _init_repo(tmp_path)
    # No Gate-Scope: trailer -> GateScopeUnverified (the normal absent verdict),
    # NOT a CommitHeadRaced block -- proving the race check did not fire.
    code = run_contract_gate.main(
        ["--repo", str(tmp_path), "--commit", head, "--verify-gate-scope"]
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 1
    assert payload["event"] == "GateScopeUnverified"
