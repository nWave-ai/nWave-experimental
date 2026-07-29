"""Integration test: the examine-verdict gate (E3) is enforced on the
``des verify-slice-commit`` verify-then-record path too -- not only ``des
commit-slice``.

Regression for the bypass Ale flagged 2026-07-05: the atdd_pure per-slice
G_COMMIT flow uses ``git commit`` + ``des verify-slice-commit``, which recorded
``SliceCommitVerified`` WITHOUT the examine gate that only ``des commit-slice``
enforced (``check_examine_verdict`` was wired into commit-slice alone). EXAMINE
is the true Definition of DONE -- these pin that the verify-then-record exit
gate now runs E3 (``check_examine_verdict``) after E1+E2 and before recording.

E2 (the feature-scoped contract-gate subprocess) is monkeypatched to PASS so
each test isolates the NEW E3 leg; E1 is exercised for real (a committed
``.feature`` AT file). Real tmp git work-tree, real ``git`` subprocesses.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli import verify_slice_commit_completeness as vscc
from des.cli.record_examine_verdict import main as record_examine_verdict_main
from tests.charter_fixtures import filled_charter


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _write_charter(repo: Path, feature_id: str, slice_id: str) -> str:
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / f"{slice_id}.md"
    charter_file.write_text(filled_charter("Walk the real surface."), encoding="utf-8")
    return str(charter_file.relative_to(repo))


def _commit_slice_with_feature_file(repo: Path, feature_id: str, slice_id: str) -> None:
    """Commit a `@slice-NN`-tagged `.feature` AT file so E1 completeness passes."""
    feat_dir = repo / "tests" / "acceptance" / feature_id.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{slice_id}.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: the slice's behaviour\n\n"
        f"  @{slice_id}\n"
        "  Scenario: the slice does its thing\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"feat(slice): behaviour\n\nSlice-Id: {slice_id}")


def _record_examine_verdict(
    repo: Path, feature_id: str, slice_id: str, charter: str, verdict: str, capsys
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
            charter,
            "--verdict",
            verdict,
            "--observations",
            f"observed during {slice_id} walkthrough",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    capsys.readouterr()  # drain the producer's own JSON -- not under test here
    assert exit_code == 0


def _last_json_event(stdout: str) -> dict:
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    return json.loads(json_lines[-1])


def test_verify_slice_commit_refuses_missing_examine_when_armed(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """ARMED (a charter exists) + NO examine verdict -> E3 refuses; NO record."""
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)  # E2 passes
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-vscc-examine", "slice-01"
    _write_charter(repo, feature_id, slice_id)
    _commit_slice_with_feature_file(repo, feature_id, slice_id)
    capsys.readouterr()

    exit_code = vscc.main(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictMissing"
    assert event["refused_half"] == "E3"
    assert event["slice_id"] == slice_id
    assert "record-examine-verdict" in event["how"]


def test_verify_slice_commit_clears_with_pass_examine(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """ARMED + a fresh PASS examine verdict -> E3 clears -> SliceCommitVerified."""
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-vscc-examine", "slice-01"
    charter = _write_charter(repo, feature_id, slice_id)
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)
    _commit_slice_with_feature_file(repo, feature_id, slice_id)
    capsys.readouterr()

    exit_code = vscc.main(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitVerified"


def test_verify_slice_commit_unarmed_without_charter(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """No charter -> gate UNARMED -> clears without examine.

    Backward-compat pin AND the prefactoring/refactoring exemption: a
    behaviour-preserving slice carries no charter, so the examine gate does not
    apply and green-to-green (E1+E2) suffices.
    """
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-vscc-noexamine", "slice-01"
    _commit_slice_with_feature_file(repo, feature_id, slice_id)
    capsys.readouterr()

    exit_code = vscc.main(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitVerified"
