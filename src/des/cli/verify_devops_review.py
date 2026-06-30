"""DEVOPS review CONSUMER veto gate (f-design-devops-review-gate slice-02, seam-2).

``des verify-devops-review``: the DEVOPS gate-OUT CONSUMER veto -- the consumer
half of the per-wave review-verdict gate, carried to DEVOPS from the DESIGN
parity (this feature). Wired into the DEVOPS gate-out stack
(``nWave/waves/devops.yaml``) so a DEVOPS return is REFUSED unless an
artefact-current approved verdict exists.

THE SSOT-REUSE PROOF (brief §8 slice-02): a verbatim thin mirror of the DESIGN
consumer parameterized to ``wave="devops"`` -- ZERO new correctness logic. It
reads the latest ``DevopsReviewVerdict`` ledger record via the read-only ledger
reader, seals the feature-delta content (SHA-256 over its bytes, the §21.2
idiom), and delegates the verdict entirely to the SAME wave-parametric pure core
``ReviewVerdictGate.evaluate`` the DESIGN wave uses. The §17 GateVerdict mapping
(PASS / VETOED / INDETERMINATE) is the pure core's; this CLI only projects it
onto an exit code + a JSON-stdout line carrying the verdict and the recovery.

Asymmetric authority (§22.0): a NEEDS_REVISION is a mechanically-honored VETO; an
artefact-current APPROVED is "no objection found" (PASS), NEVER an authorizing
GO. Absent / stale / schema-unknown -> INDETERMINATE degrade-LOUD (§17), never a
silent pass.

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import TYPE_CHECKING

from des.adapters.driven.logging.devops_review_ledger_reader import (
    DevopsReviewLedgerReader,
)
from des.domain.repo_path_resolver import resolve_repo_root as _resolve_repo_root
from des.domain.review_verdict_gate import ReviewGateToken, ReviewVerdictGate


if TYPE_CHECKING:
    from pathlib import Path


# The per-token recovery the generic iteration carries through. Mirrors the
# DESIGN consumer's tailored recovery, re-spelled for the DEVOPS wave.
_VETOED_RECOVERY: tuple[str, ...] = (
    "The DEVOPS platform-architect-review returned NEEDS_REVISION -- address "
    "the reviewer's findings in docs/feature/<id>/feature-delta.md, then record "
    "a fresh APPROVED platform-architect-review verdict whose artefact hash "
    "matches the updated feature-delta before retrying the return.",
    "If the verdict is stale (its sealed hash no longer matches the current "
    "feature-delta), re-run the platform-architect-review against the latest "
    "feature-delta so the artefact-currency seal is current.",
)

_INDETERMINATE_RECOVERY: tuple[str, ...] = (
    "The DEVOPS platform-architect-review verdict mechanism could not run (no "
    "APPROVED verdict recorded for this feature, or the recorded verdict is "
    "stale / of an unknown schema) -- record a current APPROVED "
    "platform-architect-review verdict via `des record-devops-review` whose "
    "artefact hash matches the feature-delta, then retry the devops return.",
)


def _feature_delta_seal(repo_root: Path, feature_id: str) -> str:
    """SHA-256 hexdigest over the feature-delta artefact's exact bytes (§21.2)."""
    delta = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    return hashlib.sha256(delta.read_bytes()).hexdigest()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify-devops-review",
        description=(
            "Verify the DEVOPS platform-architect review verdict (CONSUMER "
            "veto): a thin catalog-gate wrapper over ReviewVerdictGate.evaluate. "
            "PASS (exit 0) iff an artefact-current APPROVED verdict exists; "
            "VETOED / INDETERMINATE block (exit 1) and carry the specific "
            "recovery for the generic gate-out iteration."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Verify the DEVOPS platform-architect-review consumer veto from the CLI.

    Reads the latest ``DevopsReviewVerdict`` via the ledger reader, seals the
    feature-delta, delegates the verdict to ``ReviewVerdictGate.evaluate``, and
    projects it: exit 0 + ``{"verdict": "pass", ...}`` when no objection was
    found; exit 1 + ``{"verdict": "vetoed"|"indeterminate", ...,
    "recovery_suggestions": [...]}`` otherwise. Returns 1 (degrade-LOUD) when the
    feature-delta artefact is unreadable -- a verdict cannot be sealed against an
    absent artefact.
    """
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    try:
        expected_hash = _feature_delta_seal(repo_root, args.feature_id)
    except OSError as error:
        sys.stdout.write(
            json.dumps(
                {
                    "event": "DevopsReviewConsumerVeto",
                    "gate_id": "verify-devops-review",
                    "verdict": ReviewGateToken.INDETERMINATE.value,
                    "feature_id": args.feature_id,
                    "detail": f"feature-delta-unreadable: {error}",
                    "recovery_suggestions": list(_INDETERMINATE_RECOVERY),
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 1

    record = DevopsReviewLedgerReader().latest(repo_root, args.feature_id)
    review = ReviewVerdictGate.evaluate(record, expected_hash)

    if review.token is ReviewGateToken.PASS:
        sys.stdout.write(
            json.dumps(
                {
                    "event": "DevopsReviewConsumerVeto",
                    "gate_id": "verify-devops-review",
                    "verdict": review.token.value,
                    "feature_id": args.feature_id,
                    "detail": review.detail,
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    recovery = (
        _VETOED_RECOVERY
        if review.token is ReviewGateToken.VETOED
        else _INDETERMINATE_RECOVERY
    )
    sys.stdout.write(
        json.dumps(
            {
                "event": "DevopsReviewConsumerVeto",
                "gate_id": "verify-devops-review",
                "verdict": review.token.value,
                "feature_id": args.feature_id,
                "detail": review.detail,
                "recovery_suggestions": list(recovery),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
