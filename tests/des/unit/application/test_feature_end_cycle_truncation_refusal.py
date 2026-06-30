"""Root fix: the feature-end cycle REFUSES a truncated feature before sealing.

The adversarial swarm (2026-06-29) proved `des feature-end run` was decoupled
from verify-integrity's truncation oracle: it could emit a FeatureEnd record for
a feature whose Slice-Plan declares a slice never delivered (no `.feature`), a
theater-seal that `des verify-integrity` then rejects. The cycle now runs the
same un-gameable oracle FIRST and fail-closes (no record emitted).
"""

from pathlib import Path

from des.application.feature_end_cycle_service import (
    CycleRefusal,
    run_feature_end_cycle,
)


_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | first | shipped | | j |
| slice-02 | never delivered (no .feature) | to-design | | j |
"""


def _seed_feature(tmp_path: Path, fid: str) -> Path:
    feature_dir = tmp_path / "docs" / "feature" / fid
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        _SLICE_PLAN.format(fid=fid), encoding="utf-8"
    )
    return feature_dir


def test_truncated_feature_is_refused_before_any_gate(tmp_path: Path) -> None:
    fid = "trunc-feat"
    feature_dir = _seed_feature(tmp_path, fid)

    result = run_feature_end_cycle(
        repo_root=tmp_path,
        feature_id=fid,
        feature_dir=feature_dir,
        reviewer_agent_id="nw-software-crafter-reviewer",
        verdict="APPROVED",
    )

    # Refused fail-closed BEFORE the gates: slice-02 has no `.feature`.
    assert isinstance(result, CycleRefusal)
    assert "TRUNCATED" in result.error
    assert "slice-02" in result.error
    # No FeatureEnd record was emitted (no ledger seal for a theater-truncated feature).
    ledger = tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{fid}.jsonl"
    if ledger.is_file():
        text = ledger.read_text(encoding="utf-8")
        assert "EBatchRefactorCompleted" not in text
        assert "FeatureEndReviewVerdict" not in text
