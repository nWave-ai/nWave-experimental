"""Prose-delivered record producer (DDD-5 -- PRODUCER half).

carpaccio-in-order-honest-non-at-attestation slice-01. A principle-b prose slice
authors NO acceptance tests, so it never earns a ``SliceCommitVerified`` record
and the in-order gate wedges its successor. After the prose slice is doc-review
APPROVED, this producer mints ONE honest ``SliceProseDelivered`` record from that
verdict, appended to the AT-completion ledger
``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.

The record carries the honest attestation fields (``attested=true``,
``at_verified=false``, ``reason="prose_attested_by_doc_review"``,
``verdict=APPROVED``) and the doc-review reference. The kind stays semantically
DISTINCT from ``SliceCommitVerified`` -- minting a verified record for a prose
slice would be theater (the honesty invariant, DDD-8). The
``carpaccio_intercept`` in-order gate is the CONSUMER that reads this record via
``AtCompletionLedger.prose_delivered_slices()`` (DDD-1/-3); this module is the
PRODUCER that writes it.

Stdlib-only (no third-party imports) so the module is bundle-safe -- the SHAPE of
``at_review_verdict.py`` (its sibling producer in this package).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.repo_path_resolver import (
    resolve_repo_root as _resolve_repo_root,
)


if TYPE_CHECKING:
    from pathlib import Path


__all__ = [
    "main",
    "record_prose_delivered",
]

_SCHEMA_VERSION = "1.0.0"
_VERDICT = "APPROVED"
_REASON = "prose_attested_by_doc_review"


def record_prose_delivered(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    reviewer_agent_id: str,
    doc_review_ref: str,
    timestamp: str,
) -> None:
    """Append one keyless SliceProseDelivered record to the AT-completion ledger.

    Writes a single JSONL line carrying the honest attestation fields (DDD-2):
    the doc-review APPROVED verdict is the attestation, so ``attested`` is True,
    ``at_verified`` is False (no acceptance tests were run), ``reason`` is
    ``prose_attested_by_doc_review`` and ``terminal`` is False. Routed through
    the M7 ``append_prose_delivered`` API so the record carries the same ``seq``
    + ``record_hash`` every gate event carries; earlier ledger records are never
    altered (append-only).
    """
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo_root)
    verdict_fields = {
        "schema_version": _SCHEMA_VERSION,
        "reviewer_agent_id": reviewer_agent_id,
        "verdict": _VERDICT,
        "doc_review_ref": doc_review_ref,
        "timestamp": timestamp,
        "attested": True,
        "at_verified": False,
        "reason": _REASON,
        "terminal": False,
    }
    ledger.append_prose_delivered(slice_id=slice_id, verdict_fields=verdict_fields)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="record_prose_delivered",
        description=(
            "Record a prose-delivered verdict (DDD-5 producer). Mints a keyless "
            "SliceProseDelivered record from a doc-review APPROVED outcome so an "
            "honest prose slice (no acceptance tests) un-wedges its successor."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--verdict", required=True, choices=["APPROVED"])
    parser.add_argument("--reviewer-agent-id", required=True)
    parser.add_argument("--doc-review-ref", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Record a prose-delivered verdict from the command line.

    The operator supplies the feature id, slice id, reviewer id and the
    doc-review reference; the producer mints one honest ``SliceProseDelivered``
    record and emits a machine-readable JSON event on stdout. Returns 0 on
    success.
    """
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    record_prose_delivered(
        repo_root=repo_root,
        feature_id=args.feature_id,
        slice_id=args.slice_id,
        reviewer_agent_id=args.reviewer_agent_id,
        doc_review_ref=args.doc_review_ref,
        timestamp=timestamp,
    )
    event_line = (
        json.dumps(
            {
                "event": "SliceProseDeliveredCLI",
                "feature_id": args.feature_id,
                "slice_id": args.slice_id,
                "verdict": args.verdict,
                "doc_review_ref": args.doc_review_ref,
            },
            sort_keys=True,
        )
        + "\n"
    )
    sys.stdout.write(event_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
