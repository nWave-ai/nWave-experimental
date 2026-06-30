"""DISCUSS PO-review CONSUMER veto gate (f-declarative-gate-composition, OB-2).

``des verify-discuss-review``: the PO-review CONSUMER veto promoted to its own
catalog ``gate_id`` so the DISCUSS gate-OUT stack is the readable 2-row declared
list ``[validate-feature-delta, verify-discuss-review]`` (OB-2). Today this
consumer veto is an imperative sub-call inside ``subagent_stop_service``
(``_discuss_review_veto``); this thin gate is the declarative-composition handle
for it.

THIN WRAPPER — zero new correctness logic. It reads the latest
``DiscussReviewVerdict`` ledger record via the read-only ``DiscussReviewReader``
port, seals the feature-delta content (SHA-256 over its bytes, the §21.2 idiom),
and delegates the verdict entirely to the EXISTING pure core
``DiscussReviewGate.evaluate``. The §17 GateVerdict mapping (PASS / VETOED /
INDETERMINATE) is the pure core's; this CLI only projects it onto an exit code +
a JSON-stdout line carrying the verdict and the specific recovery the generic
iteration carries through (OB-2 parity).

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

from des.adapters.driven.logging.discuss_review_ledger_reader import (
    DiscussReviewLedgerReader,
)
from des.domain.discuss_review_gate import (
    DiscussReviewGate,
    DiscussReviewGateToken,
)
from des.domain.repo_path_resolver import resolve_repo_root as _resolve_repo_root


if TYPE_CHECKING:
    from pathlib import Path


# The per-token recovery the generic iteration carries through (OB-2 parity).
# This is the SAME tailored recovery the imperative ``_discuss_review_veto``
# branch hand-wrote (subagent_stop_service.py) — preserved verbatim so the lift
# does not regress the actionable-recovery payload.
_VETOED_RECOVERY: tuple[str, ...] = (
    "The DISCUSS PO-review returned NEEDS_REVISION -- address the reviewer's "
    "findings in docs/feature/<id>/feature-delta.md, then record a fresh "
    "APPROVED PO-review verdict whose artefact hash matches the updated "
    "feature-delta before retrying the return.",
    "If the verdict is stale (its sealed hash no longer matches the current "
    "feature-delta), re-run the PO-review against the latest feature-delta so "
    "the artefact-currency seal is current.",
)

_INDETERMINATE_RECOVERY: tuple[str, ...] = (
    "The DISCUSS PO-review verdict mechanism could not run (no APPROVED "
    "verdict recorded for this feature, or the recorded verdict is stale / of "
    "an unknown schema) -- record a current APPROVED PO-review verdict via "
    "`des record-discuss-review` whose artefact hash matches the feature-delta, "
    "then retry the discuss return.",
)


def _feature_delta_seal(repo_root: Path, feature_id: str) -> str:
    """SHA-256 hexdigest over the feature-delta artefact's exact bytes (§21.2)."""
    delta = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    return hashlib.sha256(delta.read_bytes()).hexdigest()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify-discuss-review",
        description=(
            "Verify the DISCUSS product-owner review verdict (CONSUMER veto, "
            "OB-2): a thin catalog-gate wrapper over DiscussReviewGate.evaluate. "
            "PASS (exit 0) iff an artefact-current APPROVED verdict exists; "
            "VETOED / INDETERMINATE block (exit 1) and carry the specific "
            "recovery for the generic gate-out iteration."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Verify the DISCUSS PO-review consumer veto from the command line.

    Reads the latest ``DiscussReviewVerdict`` via the ledger reader, seals the
    feature-delta, delegates the verdict to ``DiscussReviewGate.evaluate``, and
    projects it: exit 0 + ``{"verdict": "pass", ...}`` when no objection was
    found; exit 1 + ``{"verdict": "vetoed"|"indeterminate", ...,
    "recovery_suggestions": [...]}`` otherwise. Returns 1 (degrade-LOUD) when the
    feature-delta artefact is unreadable — a verdict cannot be sealed against an
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
                    "event": "DiscussReviewConsumerVeto",
                    "gate_id": "verify-discuss-review",
                    "verdict": DiscussReviewGateToken.INDETERMINATE.value,
                    "feature_id": args.feature_id,
                    "detail": f"feature-delta-unreadable: {error}",
                    "recovery_suggestions": list(_INDETERMINATE_RECOVERY),
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 1

    record = DiscussReviewLedgerReader().latest(repo_root, args.feature_id)
    review = DiscussReviewGate.evaluate(record, expected_hash)

    if review.token is DiscussReviewGateToken.PASS:
        sys.stdout.write(
            json.dumps(
                {
                    "event": "DiscussReviewConsumerVeto",
                    "gate_id": "verify-discuss-review",
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
        if review.token is DiscussReviewGateToken.VETOED
        else _INDETERMINATE_RECOVERY
    )
    sys.stdout.write(
        json.dumps(
            {
                "event": "DiscussReviewConsumerVeto",
                "gate_id": "verify-discuss-review",
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
