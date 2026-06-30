"""DESIGN review verdict producer (f-design-devops-review-gate slice-01 PRODUCER).

``des record-design-review``: after the solution-architect-reviewer judges the
DESIGN artefact, this producer RECORDS the outcome as a ``DesignReviewVerdict``
record appended to the per-feature AT-completion ledger
``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``. The DESIGN gate-OUT consumer
(``des verify-design-review``) reads it back via the ledger reader +
``ReviewVerdictGate.evaluate`` -- the agent NEVER hands the gate a verdict, it
only triggers the RECORDING (§22.7).

O-4 both-outcomes (reused verbatim from the DISCUSS producer): this producer
writes a record for BOTH ``approved`` AND ``needs-revision`` -- the gate must
mechanically READ a veto to enforce it; a NEEDS_REVISION that wrote nothing
would collapse into INDETERMINATE alongside "no review yet", defeating the veto.

The record carries the keyless content seal ``feature_delta_hash`` (SHA-256
hexdigest over the feature-delta artefact's exact bytes -- the §21.2 idiom) plus
the reviewer identity and the verdict. No signing key is needed or resolved.

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.logging.design_review_ledger_reader import (
    DESIGN_REVIEW_EVENT,
)
from des.domain.repo_path_resolver import resolve_repo_root as _resolve_repo_root
from des.domain.review_verdict_gate import REVIEW_APPROVED, REVIEW_NEEDS_REVISION


if TYPE_CHECKING:
    from pathlib import Path


_SCHEMA_VERSION = "1.0.0"


def record_design_review_verdict(
    repo_root: Path,
    feature_id: str,
    verdict: str,
    reviewer_agent_id: str,
    feature_delta_hash: str,
    timestamp: str,
    findings_summary: list[object],
) -> None:
    """Append one keyless DesignReviewVerdict record to the ledger.

    Writes BOTH outcomes (``approved`` and ``needs-revision``) -- the O-4
    both-outcomes policy. Earlier ledger records are never altered (append-only);
    the record carries the M7 ``seq`` + ``record_hash`` via
    ``AtCompletionLedger.append_design_review_verdict``.
    """
    record: dict[str, object] = {
        "event": DESIGN_REVIEW_EVENT,
        "schema_version": _SCHEMA_VERSION,
        "feature_id": feature_id,
        "verdict": verdict,
        "reviewer_agent_id": reviewer_agent_id,
        "feature_delta_hash": feature_delta_hash,
        "timestamp": timestamp,
        "findings_summary": list(findings_summary),
    }

    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo_root)
    verdict_fields = {key: value for key, value in record.items() if key != "event"}
    ledger.append_design_review_verdict(verdict_fields=verdict_fields)


def _feature_delta_seal(repo_root: Path, feature_id: str) -> str:
    """SHA-256 hexdigest over the feature-delta artefact's exact bytes as written.

    The §21.2 seal idiom: the verdict binds to the artefact CONTENT it judged.
    Raises ``OSError`` when the artefact is unreadable -- a verdict cannot be
    sealed against an artefact that does not exist.
    """
    delta = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    return hashlib.sha256(delta.read_bytes()).hexdigest()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="record-design-review",
        description=(
            "Record a keyless DESIGN solution-architect review verdict (O-4 "
            "producer). BOTH approved and needs-revision are written -- the "
            "DESIGN gate-OUT mechanically reads the record to honor a veto."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument(
        "--verdict",
        required=True,
        choices=[REVIEW_APPROVED, REVIEW_NEEDS_REVISION],
    )
    parser.add_argument("--reviewer-agent-id", required=True)
    parser.add_argument("--findings", nargs="*", default=[])
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Record a DESIGN review verdict from the command line.

    Computes the ``feature_delta_hash`` seal itself from the feature's
    feature-delta.md bytes -- the operator supplies only the feature id, the
    verdict and the reviewer id. Returns 0 on success; 1 when the feature-delta
    artefact is unreadable.
    """
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    try:
        feature_delta_hash = _feature_delta_seal(repo_root, args.feature_id)
    except OSError as error:
        sys.stderr.write(
            f"FeatureDeltaNotReadable: cannot seal the verdict -- {error}\n"
        )
        return 1
    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    record_design_review_verdict(
        repo_root=repo_root,
        feature_id=args.feature_id,
        verdict=args.verdict,
        reviewer_agent_id=args.reviewer_agent_id,
        feature_delta_hash=feature_delta_hash,
        timestamp=timestamp,
        findings_summary=list(args.findings),
    )
    event_line = (
        json.dumps(
            {
                "event": "DesignReviewVerdictCLI",
                "feature_id": args.feature_id,
                "verdict": args.verdict,
                "verdict_written": True,
                "feature_delta_hash": feature_delta_hash,
            },
            sort_keys=True,
        )
        + "\n"
    )
    sys.stdout.write(event_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
