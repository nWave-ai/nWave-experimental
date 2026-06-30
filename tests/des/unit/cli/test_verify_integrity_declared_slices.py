"""Regression: reconciled_slices reports the feature's OWN declared slice-ids,
not the cross-feature git-history over-count (F-VERIFY-INTEGRITY-RECONCILED-
SLICES-OVERCOUNTS-PHANTOM, cross-tier swarm 2026-06-29)."""

from pathlib import Path

from des.cli.verify_deliver_integrity import _declared_slice_plan_slice_ids


_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | a | shipped | | j |
| slice-02 | b | shipped | | j |
"""


def _seed(tmp_path: Path, fid: str, body: str) -> None:
    d = tmp_path / "docs" / "feature" / fid
    d.mkdir(parents=True)
    (d / "feature-delta.md").write_text(body, encoding="utf-8")


def test_declared_slice_ids_are_the_feature_own_slices(tmp_path: Path) -> None:
    _seed(tmp_path, "feat", _PLAN.format(fid="feat"))
    assert _declared_slice_plan_slice_ids(tmp_path, "feat") == ["slice-01", "slice-02"]


def test_absent_slice_plan_yields_empty(tmp_path: Path) -> None:
    _seed(tmp_path, "feat", "# Feature Delta: feat\n\nno slice plan here\n")
    assert _declared_slice_plan_slice_ids(tmp_path, "feat") == []
