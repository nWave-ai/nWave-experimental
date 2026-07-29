"""Regression AT: the feature-end walking-skeleton PASS assertion is WIRED.

RCA (fix-ws-done-gate-na-reconciliation slice-01): `WalkingSkeletonGateRan` is
a heartbeat the gate emits on ENTRY, before the verdict is known -- it is
present whether the gate PASSED or FAILED. The feature-end integrity check
(`verify_deliver_integrity._verify_atdd_pure`, mirrored in
`subagent_stop_handler._missing_feature_end_cycle_records`) used to assert
only the heartbeat was present, so a feature whose walking skeleton ran and
FAILED could still declare done. The strictly-stronger PASS record
(`WalkingSkeletonTierVerified`) already existed and the standalone
`walking_skeleton_done_gate.py` CLI already asserted it correctly -- but that
CLI had zero production callers, so its correct assertion never ran.

Wiring the PASS assertion naively (requiring `WalkingSkeletonTierVerified` on
every feature) would have been WRONG: a feature with no `@walking-skeleton`
AT and no delta-added installable root is legitimately NOT_APPLICABLE -- the
common case for non-installer features -- and never earns, and never should
earn, a `WalkingSkeletonTierVerified` record. This fix adds a DISTINCT
`WalkingSkeletonNotApplicable` marker, minted ONLY on the gate's own
mechanical `GateVerdict.NOT_APPLICABLE` decision, and reconciles it via the
shared `feature_end_na_marker_reconciles()` SSOT (the same mechanism already
governing the coverage-map and full-suite-leg legs).

This AT asserts the USER-VISIBLE property through the REAL `des verify-
integrity` entry point (`des.cli.verify_deliver_integrity.main`), the actual
feature-end path -- never an internal function call. Three cases, one ledger
substrate, one entry point:

  1. PASSED  -- `WalkingSkeletonTierVerified` present -> feature CLOSES (0).
  2. NA      -- `WalkingSkeletonNotApplicable` present (no Verified record) ->
                feature CLOSES (0).
  3. RAN-NOT-PASSED -- only the `WalkingSkeletonGateRan` heartbeat present
                (no Verified, no NA marker) -> feature is BLOCKED (1), naming
                `WalkingSkeletonTierVerified` in `missing_records`.

Every other feature-end record is seeded via the shared
`seed_required_feature_end_records` helper (`tests/des/_helpers/
feature_end_seeding.py`) so only the walking-skeleton leg varies across the
three cases -- the same reuse pattern `test_verify_deliver_integrity.py`'s
`_complete_feature_end_ledger` already uses.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_deliver_integrity import main
from tests.des._helpers.feature_end_seeding import seed_required_feature_end_records


_FEATURE_ID = "demo-ws-na-reconciliation-feature"


def _write_atdd_pure_config(project_dir: Path) -> None:
    """Write a minimal .nwave/config.yaml selecting atdd_pure mode."""
    nwave_dir = project_dir / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "config.yaml").write_text("workflow:\n  mode: atdd_pure\n")


def _verdict_argv(project_dir: Path, feature_id: str) -> list[str]:
    return [str(project_dir), "--feature-id", feature_id]


def test_feature_closes_when_walking_skeleton_passed(tmp_path: Path) -> None:
    """Case 1: `WalkingSkeletonTierVerified` present -> the feature CLOSES."""
    project_dir = tmp_path / "repo"
    _write_atdd_pure_config(project_dir)
    ledger = AtCompletionLedger(_FEATURE_ID, project_dir)
    seed_required_feature_end_records(ledger, verdict_hash="abc123")

    exit_code = main(_verdict_argv(project_dir, _FEATURE_ID))

    assert exit_code == 0, (
        "a feature whose walking skeleton PASSED (WalkingSkeletonTierVerified "
        f"present) must CLOSE (exit 0); got exit_code={exit_code!r}"
    )


def test_feature_closes_when_walking_skeleton_legitimately_not_applicable(
    tmp_path: Path,
) -> None:
    """Case 2: the NA marker reconciles the PASS record -> the feature CLOSES.

    A feature that never authored a `@walking-skeleton` AT and never added an
    installable root (the common case for non-installer features) mints the
    NA marker instead of the Verified record -- never both, never neither.
    """
    project_dir = tmp_path / "repo"
    _write_atdd_pure_config(project_dir)
    ledger = AtCompletionLedger(_FEATURE_ID, project_dir)
    seed_required_feature_end_records(
        ledger,
        verdict_hash="abc123",
        exclude={"WalkingSkeletonGateRan", "WalkingSkeletonTierVerified"},
    )
    # The gate's OWN sequence on a NOT_APPLICABLE verdict (walking_skeleton_
    # gate.py:main): the heartbeat is ALWAYS written on entry, then the NA
    # marker in place of the (never-earned) Verified record.
    ledger.append_walking_skeleton_gate_ran()
    ledger.append_walking_skeleton_not_applicable()

    exit_code = main(_verdict_argv(project_dir, _FEATURE_ID))

    assert exit_code == 0, (
        "a legitimately NOT_APPLICABLE walking skeleton (no @walking-skeleton "
        "AT, no delta-added installable root) must CLOSE (exit 0) via the "
        f"WalkingSkeletonNotApplicable reconciliation; got exit_code={exit_code!r}"
    )


def test_feature_blocked_when_walking_skeleton_ran_and_did_not_pass(
    tmp_path: Path,
) -> None:
    """Case 3: THE HOLE THIS FIX CLOSES -- ran, no PASS, no NA -> BLOCKED.

    Only the entry heartbeat (`WalkingSkeletonGateRan`) is present, exactly
    what a FAILED gate run leaves behind. Before this fix the feature-end
    check only demanded the heartbeat, so this ledger shape closed the
    feature; after this fix it is refused, naming the missing PASS record.
    """
    project_dir = tmp_path / "repo"
    _write_atdd_pure_config(project_dir)
    ledger = AtCompletionLedger(_FEATURE_ID, project_dir)
    seed_required_feature_end_records(
        ledger, verdict_hash="abc123", exclude={"WalkingSkeletonTierVerified"}
    )

    exit_code = main(_verdict_argv(project_dir, _FEATURE_ID))

    assert exit_code == 1, (
        "a walking skeleton that RAN (heartbeat present) but never PASSED "
        "(no WalkingSkeletonTierVerified, no WalkingSkeletonNotApplicable) "
        f"must BLOCK the feature (exit 1); got exit_code={exit_code!r}"
    )


def test_blocked_verdict_names_the_missing_pass_record(tmp_path: Path) -> None:
    """The block verdict is self-explaining (GDP-3): it NAMES the missing record.

    A degrade-LOUD blind refusal ("something is missing") is not acceptable --
    the JSON verdict must name `WalkingSkeletonTierVerified` specifically so a
    blocked developer knows what to fix.
    """
    project_dir = tmp_path / "repo"
    _write_atdd_pure_config(project_dir)
    ledger = AtCompletionLedger(_FEATURE_ID, project_dir)
    seed_required_feature_end_records(
        ledger, verdict_hash="abc123", exclude={"WalkingSkeletonTierVerified"}
    )

    import contextlib
    import io

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = main(_verdict_argv(project_dir, _FEATURE_ID))

    assert exit_code == 1
    payload = json.loads(captured.getvalue().strip().splitlines()[-1])
    assert payload["event"] == "FeatureEndCycleIncomplete"
    assert "WalkingSkeletonTierVerified" in payload["missing_records"], (
        "the block verdict must NAME WalkingSkeletonTierVerified as missing "
        f"(GDP-3 self-explaining rejection); got missing_records="
        f"{payload['missing_records']!r}"
    )
