"""des.cli.walking_skeleton_done_gate -- the "feature done" block check.

Feature `implement-walking-skeleton-done-gate`, slice-01. Replaces the RED
scaffold DISTILL authored for feature `walking-skeleton-production-like-gate`
(ADR-025 / Mandate 7) with the RM-3 done-gate body.

Contract (DESIGN / Fail-Mode D + Done-gate block): blocks "feature done"
(exit 1) unless BOTH hold for the feature:
  (a) no `walking-skeleton-unverified` marker is present (an unparseable
      marker counts as present -> block, RM-3 ST-20), AND
  (b) a positive `WalkingSkeletonTierVerified` ledger record exists, OR the
      feature carries the `WalkingSkeletonNotApplicable` NA marker (RM-3 --
      a hand-`rm` of the unverified marker satisfies (a) but not (b); a
      legitimately-NA feature -- no `@walking-skeleton` AT, no delta-added
      installable root -- never earns and never should earn a Verified
      record, so its mechanical NA marker reconciles (b) instead;
      fix-ws-done-gate-na-reconciliation slice-01).

RM-4 (an unsettled `walking-skeleton-tier-debt` record blocking an
OS-sensitive feature) is OUT of this slice -- a follow.

Degrade-LOUD: an unreadable/corrupt AT-completion ledger blocks (never a
silent proceed) and names the integrity violation + a repair pointer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    WALKING_SKELETON_NOT_APPLICABLE,
    WALKING_SKELETON_TIER_VERIFIED,
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.cli._repo_root_arg import add_repo_root_argument


_MARKER_SUBDIR = Path(".nwave") / "markers" / "walking-skeleton-unverified"


def _build_parser() -> argparse.ArgumentParser:
    """Build the done-gate CLI argument parser.

    Mirrors the two closest sibling CLI conventions: `--repo-root` (default
    ".") from `walking_skeleton_gate.py`, `--feature-id` (required) from
    `verify_deliver_integrity.py`.
    """
    parser = argparse.ArgumentParser(
        prog="des walking-skeleton-done-gate",
        description=(
            "Block 'feature done' unless the walking-skeleton tier was "
            "verified: no walking-skeleton-unverified marker present AND a "
            "WalkingSkeletonTierVerified ledger record exists (RM-3)."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="The feature id under the done-gate check.",
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        default=".",
        help="The repository root holding the .nwave/ marker + ledger substrate.",
    )
    return parser


def _marker_path(repo_root: Path, feature_id: str) -> Path:
    """The conventional path for the feature's unverified-marker file."""
    return repo_root / _MARKER_SUBDIR / f"{feature_id}.json"


def _marker_present(repo_root: Path, feature_id: str) -> tuple[bool, str | None]:
    """Whether the unverified marker is present, plus a parse-detail note.

    RM-3 ST-20: presence BLOCKS regardless of parseability -- a malformed,
    empty, or unknown-`schema_version` marker still counts as present. The
    returned detail names WHY for the self-explaining verdict; it never
    changes the block decision (`True` either way once the file exists).
    """
    marker_path = _marker_path(repo_root, feature_id)
    if not marker_path.is_file():
        return False, None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True, "unparseable"
    if not isinstance(payload, dict) or "schema_version" not in payload:
        return True, "unknown-schema_version"
    return True, "parseable"


def _emit(verdict: str, feature_id: str, reason: str, how: str | None = None) -> None:
    """Print the done-gate's self-explaining single-line JSON verdict."""
    payload: dict[str, object] = {
        "event": "WalkingSkeletonDoneGateVerdict",
        "verdict": verdict,
        "feature_id": feature_id,
        "reason": reason,
    }
    if how is not None:
        payload["how"] = how
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    """Entry point -- the RM-3 walking-skeleton done-gate block check."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    feature_id = str(args.feature_id)
    repo_root = Path(args.repo_root).resolve()

    marker_present, marker_detail = _marker_present(repo_root, feature_id)
    if marker_present:
        _emit(
            "block",
            feature_id,
            f"walking-skeleton-unverified marker present for feature "
            f"'{feature_id}' ({marker_detail})",
            how=(
                "the marker blocks 'feature done' until it is cleared AND a "
                "WalkingSkeletonTierVerified record exists; run "
                f"`des walking-skeleton-gate --feature-dir docs/feature/"
                f"{feature_id}/ --repo-root {repo_root}` to verify the tier "
                "-- a PASS clears the marker's deferral."
            ),
        )
        return 1

    try:
        recorded_events = AtCompletionLedger(
            feature_id, repo_root
        ).walking_skeleton_events()
    except LedgerIntegrityViolation as exc:
        _emit(
            "block",
            feature_id,
            f"AT-completion ledger integrity violation ({exc.detail}): {exc}",
            how=f"see {exc.repair_instructions} for recovery steps, then re-run this gate.",
        )
        return 1

    if (
        WALKING_SKELETON_TIER_VERIFIED not in recorded_events
        and WALKING_SKELETON_NOT_APPLICABLE not in recorded_events
    ):
        _emit(
            "block",
            feature_id,
            f"no WalkingSkeletonTierVerified record (nor a "
            f"WalkingSkeletonNotApplicable NA marker) found for feature "
            f"'{feature_id}' in the AT-completion ledger (a missing record "
            "is not proof)",
            how=(
                "run `des walking-skeleton-gate --feature-dir docs/feature/"
                f"{feature_id}/ --repo-root {repo_root}` until it PASSes or "
                "mechanically decides NOT_APPLICABLE; either run appends the "
                "record this gate requires."
            ),
        )
        return 1

    _emit(
        "proceed",
        feature_id,
        f"no unverified marker present and a WalkingSkeletonTierVerified "
        f"record (or its WalkingSkeletonNotApplicable NA marker) exists for "
        f"feature '{feature_id}'",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
