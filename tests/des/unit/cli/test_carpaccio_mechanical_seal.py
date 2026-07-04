"""P1.1 — the carpaccio gate accepts the mechanical seal for assertion 5.

Evolution-plan P1.1 step (a), pinned as regression: in pytest-regression mode
the AT-review assertion is satisfied by EITHER the legacy ``ATReviewVerdict``
(unchanged) OR the mechanical pair -- a fresh ``RedObserved`` seal (P0.2)
matching the CURRENT regression-file content AND the negative-AT mandate
(P0.3, --all-critical semantics) satisfied in that same file.

Hermetic: the seal record is crafted directly in the P0.2 producer's own shape
(via its ``_seal_path`` helper, so the slug can never diverge); no pytest-in-
pytest. The observed sandbox proofs (real ``verify-red-green --record-red``
run) live in the evolution-plan evidence row; these pins freeze cases 1-4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main
from des.cli.verify_red_green import _seal_path


_FEATURE_ID = "p11-mechanical-seal-fixture"
_REGRESSION_REL = "tests/regression/test_fix.py"

# Two module-level test_* functions; one carries the negative-AT name token
# (`_rejects_`) so the P0.3 --all-critical check is satisfied.
_REGRESSION_SRC_WITH_NEGATIVE = (
    "def test_fix_applies():\n"
    "    assert True\n"
    "\n"
    "\n"
    "def test_fix_rejects_bad_input():\n"
    "    assert True\n"
)

# Same shape, ZERO negative ATs (presence-only names) -- the seal alone must
# NOT clear the slice.
_REGRESSION_SRC_PRESENCE_ONLY = (
    "def test_fix_applies():\n"
    "    assert True\n"
    "\n"
    "\n"
    "def test_fix_still_applies():\n"
    "    assert True\n"
)


def _make_repo(tmp_path: Path, regression_src: str) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        "# Feature Delta: mechanical-seal fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | Gate accepts the mechanical evidence seal | pending | | |\n",
        encoding="utf-8",
    )
    regression = repo / _REGRESSION_REL
    regression.parent.mkdir(parents=True)
    regression.write_text(regression_src, encoding="utf-8")
    return repo


def _write_red_seal(repo: Path, *, content_sha: str | None = None) -> Path:
    """Craft the RedObserved seal in the P0.2 producer's exact record shape."""
    test_file = (repo / _REGRESSION_REL).resolve()
    seal = _seal_path(repo.resolve(), test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": _REGRESSION_REL,
                "content_sha256": (
                    content_sha
                    if content_sha is not None
                    else hashlib.sha256(test_file.read_bytes()).hexdigest()
                ),
                "outcomes": {
                    "t::test_a": "fail",
                    "t::test_b": "fail",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return seal


def _write_approved_verdict(repo: Path) -> None:
    """Mint the legacy ATReviewVerdict exactly as the existing gate tests do."""
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "ATReviewVerdict",
        "schema_version": "1.0.0",
        "slice_id": "slice-01",
        "verdict": "APPROVED",
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": ["AT-1", "AT-2"],
        "at_content_hash": hashlib.sha256(
            (repo / _REGRESSION_REL).read_bytes()
        ).hexdigest(),
        "timestamp": "2026-07-03T00:00:00Z",
        "findings_summary": [],
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _run_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    exit_code = carpaccio_gate_main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            "slice-01",
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            _REGRESSION_REL,
        ]
    )
    stdout = capsys.readouterr().out
    payload: dict[str, object] = next(
        (
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ),
        {},
    )
    return exit_code, payload


def test_no_verdict_no_seal_refuses_naming_both_remedies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 1 (NEGATIVE): fail-closed refusal unchanged; how names BOTH remedies."""
    repo = _make_repo(tmp_path, _REGRESSION_SRC_WITH_NEGATIVE)
    exit_code, payload = _run_gate(repo, capsys)
    assert exit_code == 45
    assert payload.get("event") == "ATReviewGateRejected"
    assert payload.get("reason") == "absent"
    how = payload.get("how")
    assert isinstance(how, str)
    assert "ATReviewVerdict" in how  # remedy (a): the legacy reviewer verdict
    assert "verify-red-green" in how  # remedy (b): the mechanical pair...
    assert "verify-negative-at" in how  # ...both halves named


def test_fresh_seal_plus_negative_at_clears_with_mechanical_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 2 (POSITIVE-mechanical): seal + negative AT clear without a verdict."""
    repo = _make_repo(tmp_path, _REGRESSION_SRC_WITH_NEGATIVE)
    _write_red_seal(repo)
    exit_code, payload = _run_gate(repo, capsys)
    assert exit_code == 0
    assert payload.get("event") == "SliceCleared"
    assert payload.get("at_evidence") == "mechanical-seal"


def test_stale_seal_refuses_tamper_semantics_preserved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 3 (STALE): a post-seal edit voids the evidence -- gate refuses."""
    repo = _make_repo(tmp_path, _REGRESSION_SRC_WITH_NEGATIVE)
    _write_red_seal(repo)
    regression = repo / _REGRESSION_REL
    regression.write_text(
        regression.read_text(encoding="utf-8") + "\n# tampered after RED\n",
        encoding="utf-8",
    )
    exit_code, payload = _run_gate(repo, capsys)
    assert exit_code == 45
    assert payload.get("event") == "ATReviewGateRejected"
    assert payload.get("at_evidence") is None


def test_legacy_verdict_still_clears_backward_compatible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 4 (LEGACY): the ATReviewVerdict path is unchanged and wins first."""
    repo = _make_repo(tmp_path, _REGRESSION_SRC_WITH_NEGATIVE)
    _write_approved_verdict(repo)
    exit_code, payload = _run_gate(repo, capsys)
    assert exit_code == 0
    assert payload.get("event") == "SliceCleared"
    assert payload.get("at_evidence") == "reviewer-verdict"


def test_seal_without_negative_at_never_clears(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The mechanical pair is a PAIR: a fresh seal alone (presence-only ATs,
    zero negative) must not substitute for the verdict."""
    repo = _make_repo(tmp_path, _REGRESSION_SRC_PRESENCE_ONLY)
    _write_red_seal(repo)
    exit_code, payload = _run_gate(repo, capsys)
    assert exit_code == 45
    assert payload.get("event") == "ATReviewGateRejected"
