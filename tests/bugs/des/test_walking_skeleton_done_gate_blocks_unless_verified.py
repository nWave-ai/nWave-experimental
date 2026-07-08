"""Regression AT: the walking-skeleton done-gate blocks "feature done" unless
BOTH (a) no `walking-skeleton-unverified` marker is present, and (b) a positive
`WalkingSkeletonTierVerified` ledger record exists (RM-3).

Charter: ``docs/product/expectations/implement-walking-skeleton-done-gate/
the-done-gate-blocks-feature-done-unless-tier-verified.md``.

Drives the REAL ``des.cli.walking_skeleton_done_gate.main()`` in-process.
``main()`` is a RED scaffold today (``__SCAFFOLD__ = True``): it parses argv
then unconditionally ``raise AssertionError("Not yet implemented ...")``
(:51-53). DELIVER replaces the body with the RM-3 marker + ledger check; this
AT pins the exit-code contract (``0`` proceeds, ``1`` blocks per the module's
own docstring line 8) that must hold once it does.

Fixture representation -- REUSED from production, nothing invented for the
ledger half:
  - The positive-proof ledger record is written through the REAL
    ``des.adapters.driven.logging.at_completion_ledger.AtCompletionLedger``
    (legacy per-feature shape: ``AtCompletionLedger(feature_id, project_root)``),
    calling ``.append_walking_skeleton_tier_verified(tier_of_record="t1")`` --
    the IDENTICAL production writer
    ``WalkingSkeletonFeatureEndGate.run()`` calls on a green tier run
    (src/des/application/walking_skeleton_feature_end_gate.py:65-68), and the
    same event the parent acceptance suite's composition root reads back via
    ``positive_verification_record_present()``
    (tests/des/acceptance/walking_skeleton_production_like_gate/steps/
    composition.py:588-596, which filters
    ``AtCompletionLedger.walking_skeleton_events()`` for
    ``WALKING_SKELETON_TIER_VERIFIED``). Written to
    ``{repo_root}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.

  - The ``walking-skeleton-unverified`` MARKER has **no production writer or
    reader yet**. In the parent acceptance suite's composition root
    (``steps/composition.py``), ``write_deferral_marker`` / ``marker_present``
    / ``corrupt_marker`` / ``remove_marker_by_hand`` are ALL themselves RED
    scaffolds that ``raise AssertionError("... not yet implemented")`` --
    unlike the ledger helpers above, none of them has ever run. The ONLY
    on-disk shape documented anywhere is PROSE in that same suite's
    ``steps/domain_types.py``: ``MarkerKind.UNVERIFIED`` names the path
    ``.nwave/markers/walking-skeleton-unverified/{feature}.json``;
    ``MarkerReadState.UNPARSEABLE`` says the done-gate treats "a malformed /
    empty / unknown-``schema_version`` marker" as a BLOCK (RM-3 ST-20). No
    production module defines the payload fields beyond ``schema_version``.
    Per the task's explicit STOP instruction, this AT does NOT invent that
    schema as a confirmed contract. The one marker-present negative case
    below is fenced off as BEST-EFFORT (documented PATH convention only,
    flagged loudly) rather than asserted as gospel; the fully-grounded
    negative case needs no marker-format invention at all -- "no marker AND
    no verified record" requires writing nothing.

CLI arg contract: ``_build_parser()`` in
``src/des/cli/walking_skeleton_done_gate.py`` defines ZERO flags today (an
argparse-only-for---help scaffold -- no ``add_argument`` call at all). This AT
calls ``main()`` with a PROPOSED ``--feature-id`` / ``--repo-root`` contract,
mirroring the two closest sibling CLI conventions in this codebase:
  - ``walking_skeleton_gate.py`` -- ``--repo-root`` (default ".")
  - ``verify_deliver_integrity.py`` -- ``--feature-id``
Empirically verified today: calling ``main()`` with these flags raises
``SystemExit(2)`` ("unrecognized arguments") from argparse -- NOT the
module's own ``raise AssertionError`` -- because the flags are not wired yet;
DELIVER must add them as a prerequisite to reaching the gate's own check
logic. Both failure shapes are genuine "not-yet-implemented" signals, and
pytest reports an uncaught ``SystemExit`` raised inside a test body as FAILED
(not ERROR) exactly like an ``AssertionError`` -- confirmed by direct probe,
not assumed -- so wrapping the call in ``assert main(argv) == <code>`` keeps
every case here a semantic RED regardless of which of the two exceptions
today's scaffold raises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import walking_skeleton_done_gate


_FEATURE_ID = "demo-walking-skeleton-feature"


def _done_gate_argv(feature_id: str, repo_root: Path) -> list[str]:
    """The PROPOSED CLI contract (see module docstring) -- not yet wired."""
    return ["--feature-id", feature_id, "--repo-root", str(repo_root)]


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def _write_positive_verification_record(feature_id: str, repo_root: Path) -> None:
    """Write the RM-3 positive-proof record via the REAL production writer.

    Identical call the production ``WalkingSkeletonFeatureEndGate.run()``
    makes on a green tier run (walking_skeleton_feature_end_gate.py:65-68).
    """
    ledger = AtCompletionLedger(feature_id, repo_root)
    ledger.append_walking_skeleton_tier_verified(tier_of_record="t1")


def _write_unverified_marker_best_effort(feature_id: str, repo_root: Path) -> None:
    """BEST-EFFORT marker fixture -- PATH documented, payload schema is NOT.

    Path per ``MarkerKind.UNVERIFIED`` (parent suite's ``steps/domain_types.py``):
    ``.nwave/markers/walking-skeleton-unverified/{feature}.json``. The
    ``schema_version`` key is the only payload field named anywhere in
    production-adjacent prose (``MarkerReadState.UNPARSEABLE``); every other
    key here (``reason``) is a best-effort guess from the ``DeferralReason``
    enum vocabulary, NOT a confirmed on-disk contract -- flagged, not
    invented as gospel.
    """
    marker_dir = repo_root / ".nwave" / "markers" / "walking-skeleton-unverified"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / f"{feature_id}.json"
    marker_path.write_text(
        json.dumps({"schema_version": 1, "reason": "no-provisionable-tier"}),
        encoding="utf-8",
    )


# ===========================================================================
# POSITIVE AT -- active-RED today (main() raises; the assert below never runs)
# ===========================================================================


def test_done_gate_proceeds_when_no_marker_and_verified_record_present(
    tmp_path: Path,
) -> None:
    """Charter item 3: no marker + a positive verified record -> PROCEEDS
    (exit 0). Today ``main()`` raises before this assertion is ever reached --
    RED for the right (semantic, not-yet-implemented) reason.
    """
    repo_root = _make_repo(tmp_path)
    _write_positive_verification_record(_FEATURE_ID, repo_root)

    exit_code = walking_skeleton_done_gate.main(_done_gate_argv(_FEATURE_ID, repo_root))

    assert exit_code == 0, (
        "the done-gate must PROCEED (exit 0) when no walking-skeleton-unverified "
        f"marker is present AND a WalkingSkeletonTierVerified record exists; "
        f"got exit_code={exit_code!r}"
    )


# ===========================================================================
# NEGATIVE ATs -- the honesty/block invariants (RM-3). Active-RED today for
# the same scaffold reason; pin the BLOCK behaviour DELIVER must implement.
# ===========================================================================


@pytest.mark.negative_at
def test_done_gate_blocks_when_no_marker_and_no_verified_record(tmp_path: Path) -> None:
    """Charter item 2: no marker but NO verified record -> BLOCKED (exit 1).

    A removed/never-written marker is not proof -- nothing is written to the
    repo at all (no marker directory, no ledger record); this is the fully
    grounded negative case, needing zero marker-format invention.
    """
    repo_root = _make_repo(tmp_path)
    # Deliberately nothing written: no marker, no ledger record for the feature.

    exit_code = walking_skeleton_done_gate.main(_done_gate_argv(_FEATURE_ID, repo_root))

    assert exit_code == 1, (
        "the done-gate must BLOCK (exit 1) when no WalkingSkeletonTierVerified "
        f"record exists for the feature (a missing record is not proof); "
        f"got exit_code={exit_code!r}"
    )


@pytest.mark.negative_at
def test_done_gate_blocks_when_unverified_marker_present(tmp_path: Path) -> None:
    """Charter item 1 (BEST-EFFORT fixture, see module docstring): an
    unverified marker present -> BLOCKED (exit 1), even alongside a positive
    verified record -- the marker's presence is the reason named, and RM-3
    treats marker-absence and record-presence as two independent conditions
    that must BOTH hold before the gate proceeds.
    """
    repo_root = _make_repo(tmp_path)
    _write_positive_verification_record(_FEATURE_ID, repo_root)
    _write_unverified_marker_best_effort(_FEATURE_ID, repo_root)

    exit_code = walking_skeleton_done_gate.main(_done_gate_argv(_FEATURE_ID, repo_root))

    assert exit_code == 1, (
        "the done-gate must BLOCK (exit 1) whenever a walking-skeleton-unverified "
        f"marker is present, regardless of a verified record; got exit_code={exit_code!r}"
    )
