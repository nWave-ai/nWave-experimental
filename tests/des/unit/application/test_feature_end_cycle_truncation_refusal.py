"""Root fix: the feature-end cycle REFUSES a truncated feature before sealing.

The adversarial swarm (2026-06-29) proved `des feature-end run` was decoupled
from verify-integrity's truncation oracle: it could emit a FeatureEnd record for
a feature whose Slice-Plan declares a slice never delivered (no `.feature`), a
theater-seal that `des verify-integrity` then rejects. The cycle now runs the
same un-gameable oracle FIRST and fail-closes (no record emitted).
"""

import inspect
from pathlib import Path

from des.application.feature_end_cycle_service import (
    CycleRefusal,
    _run_feature_end_member_cycle,
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


def test_member_cycle_no_longer_re_checks_the_slice_plan_oracle_itself() -> None:
    """Regression for techdebt row duplicate-truncated-slice-plan-check:
    ``_run_feature_end_member_cycle`` must NOT independently re-run the
    undelivered-Slice-Plan oracle -- that check now lives ONLY in
    ``feature_end_batch_service._check_slice_commit_verified``, the D-5
    batch-eligibility precheck that ALWAYS runs first for every member
    (``_run_feature_end_member_cycle``'s sole production caller,
    ``run_feature_end_batch``'s member loop, is only ever reached after that
    precheck has already passed for this exact ``feature_id`` -- the second
    check was unreachable duplicate work).

    A source-level assertion (rather than a call-counting mock) is used
    because the redundant check was provably UNREACHABLE at runtime through
    the public API: the D-5 precheck refuses the WHOLE batch before the
    per-member loop -- containing this function -- ever runs for a feature
    whose Slice-Plan is undelivered, so no live call sequence can exercise
    "the duplicate fires" either before or after the fix.
    """
    source = inspect.getsource(_run_feature_end_member_cycle)
    # Checks for the CALL form (name immediately followed by an opening
    # paren) rather than the bare name -- this function's own docstring/
    # comments legitimately NAME the oracle when explaining where the check
    # now lives, without calling it.
    assert "_undelivered_slice_plan_slices(" not in source, (
        "_run_feature_end_member_cycle must not call the undelivered-slice-"
        "plan oracle itself -- that check belongs solely to the D-5 batch-"
        "eligibility precheck (feature_end_batch_service."
        "_check_slice_commit_verified), which already runs before this "
        "function's sole caller reaches it"
    )
