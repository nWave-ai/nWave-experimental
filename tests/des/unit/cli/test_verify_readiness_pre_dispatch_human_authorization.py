"""Readiness gate — the ``at_review_verdict`` invariant under the
``rigor.human_authorization`` axis (velocity-v2, Ale 2026-07-04).

Off by default: the human two-party GO is an opt-in compliance layer, so a slice
with NO recorded ``ATReviewVerdict`` is ADVISORY-satisfied (the carpaccio
mechanical-seal + AT-completeness check attest the AT at the same dispatch.pre,
EXAMINE provides the outcome-independence downstream). On (regulated): the GO is
hard-required. A recorded APPROVED verdict always satisfies, either way.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli.verify_readiness_pre_dispatch import _check_at_review_verdict


def _write_config(repo: Path, rigor: dict[str, object] | None) -> None:
    nwave = repo / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    if rigor is not None:
        (nwave / "des-config.json").write_text(json.dumps({"rigor": rigor}))


def _record_verdict(repo: Path, feature_id: str, slice_id: str, verdict: str) -> None:
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(
            {"event": "ATReviewVerdict", "slice_id": slice_id, "verdict": verdict}
        )
        + "\n"
    )


def test_off_by_default_no_verdict_is_advisory_satisfied(tmp_path: Path) -> None:
    """No config (default OFF) + no recorded verdict -> advisory satisfied."""
    _write_config(tmp_path, rigor=None)
    result = _check_at_review_verdict(tmp_path, "feat-x", "slice-01")
    assert result.satisfied is True


def test_explicit_off_no_verdict_is_advisory_satisfied(tmp_path: Path) -> None:
    """Explicit human_authorization: false + no verdict -> advisory satisfied."""
    _write_config(tmp_path, rigor={"human_authorization": False})
    result = _check_at_review_verdict(tmp_path, "feat-x", "slice-01")
    assert result.satisfied is True


def test_on_regulated_no_verdict_is_blocked(tmp_path: Path) -> None:
    """human_authorization: true (regulated) + no verdict -> BLOCKED (require GO)."""
    _write_config(tmp_path, rigor={"human_authorization": True})
    result = _check_at_review_verdict(tmp_path, "feat-x", "slice-01")
    assert result.satisfied is False


def test_recorded_verdict_satisfies_when_on(tmp_path: Path) -> None:
    """A recorded APPROVED verdict satisfies even under human_authorization: true."""
    _write_config(tmp_path, rigor={"human_authorization": True})
    _record_verdict(tmp_path, "feat-x", "slice-01", "APPROVED")
    result = _check_at_review_verdict(tmp_path, "feat-x", "slice-01")
    assert result.satisfied is True


def test_rejected_verdict_blocked_when_on(tmp_path: Path) -> None:
    """A NEEDS_REVISION verdict does not satisfy under human_authorization: true."""
    _write_config(tmp_path, rigor={"human_authorization": True})
    _record_verdict(tmp_path, "feat-x", "slice-01", "NEEDS_REVISION")
    result = _check_at_review_verdict(tmp_path, "feat-x", "slice-01")
    assert result.satisfied is False
