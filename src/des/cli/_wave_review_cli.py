"""The shared PRODUCER + CONSUMER halves of the per-wave review-verdict gate.

Six CLI modules (``record-{wave}-review`` and ``verify-{wave}-review`` for
DISCUSS / DESIGN / DEVOPS) were six copies of two functions. The verdict was
never among the differences -- it has lived once in ``ReviewVerdictGate`` since
the DESIGN wave reused the DISCUSS core. What was copied was the plumbing
around it: seal the feature-delta, append (or read back) the record, project the
token onto an exit code and a JSON line.

Both halves live here ONCE, parameterized by ``WaveReviewSpec``. The wave-named
modules keep their names -- the ``des`` dispatcher registry resolves them by
module path -- and are now the spec plus a one-line delegation.

PRODUCER / CONSUMER split (§22.7): the producer RECORDS what the reviewer
decided; the consumer READS that record back and decides. The agent never hands
the gate a verdict.

Stdlib-only (no third-party imports) so the modules stay bundle-safe.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.repo_path_resolver import feature_delta_path
from des.domain.repo_path_resolver import resolve_repo_root as _resolve_repo_root
from des.domain.review_verdict_gate import (
    REVIEW_APPROVED,
    REVIEW_NEEDS_REVISION,
    ReviewGateToken,
    ReviewVerdictGate,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.wave_review_spec import WaveReviewSpec
    from des.ports.driven_ports.discuss_review_reader import DiscussReviewReader


_SCHEMA_VERSION = "1.0.0"


def feature_delta_seal(repo_root: Path, feature_id: str) -> str:
    """SHA-256 hexdigest over the feature-delta artefact's exact bytes (§21.2).

    The seal idiom: the verdict binds to the artefact CONTENT it judged. Raises
    ``OSError`` when the artefact is unreadable -- a verdict cannot be sealed
    against an artefact that does not exist.
    """
    delta = feature_delta_path(repo_root, feature_id)
    return hashlib.sha256(delta.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# PRODUCER -- records what the reviewer decided
# --------------------------------------------------------------------------


def record_wave_review_verdict(
    spec: WaveReviewSpec,
    repo_root: Path,
    feature_id: str,
    verdict: str,
    reviewer_agent_id: str,
    feature_delta_hash: str,
    timestamp: str,
    findings_summary: list[object],
) -> None:
    """Append one keyless review-verdict record for ``spec``'s wave to the ledger.

    Writes BOTH outcomes (``approved`` and ``needs-revision``) -- the O-4
    both-outcomes policy. The gate must mechanically READ a veto to enforce it;
    a NEEDS_REVISION that wrote nothing would collapse into INDETERMINATE
    alongside "no review yet", defeating the veto. Earlier ledger records are
    never altered (append-only); the record carries the M7 ``seq`` +
    ``record_hash`` via ``AtCompletionLedger``.

    Post-demotion (oss-review-verdict-demotion S3): no ``hmac_sha256`` field is
    written and no signing key is resolved. The content seal
    ``feature_delta_hash`` is the whole binding.
    """
    record: dict[str, object] = {
        "event": spec.event,
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
    ledger.append_wave_review_verdict(event=spec.event, verdict_fields=verdict_fields)


def _parse_producer_args(
    spec: WaveReviewSpec, argv: list[str] | None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=spec.producer_command,
        description=(
            f"Record a keyless {spec.wave_upper} {spec.reviewer_title} review "
            "verdict (O-4 producer). BOTH approved and needs-revision are "
            f"written -- the {spec.wave_upper} gate-OUT mechanically reads the "
            "record to honor a veto."
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


def producer_main(spec: WaveReviewSpec, argv: list[str] | None = None) -> int:
    """Record a review verdict for ``spec``'s wave from the command line.

    Computes the ``feature_delta_hash`` seal itself from the feature's
    feature-delta.md bytes -- the operator supplies only the feature id, the
    verdict and the reviewer id. Returns 0 on success; 1 when the feature-delta
    artefact is unreadable.
    """
    args = _parse_producer_args(spec, argv)
    repo_root = _resolve_repo_root(args.repo_root)
    try:
        feature_delta_hash = feature_delta_seal(repo_root, args.feature_id)
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
    record_wave_review_verdict(
        spec,
        repo_root=repo_root,
        feature_id=args.feature_id,
        verdict=args.verdict,
        reviewer_agent_id=args.reviewer_agent_id,
        feature_delta_hash=feature_delta_hash,
        timestamp=timestamp,
        findings_summary=list(args.findings),
    )
    sys.stdout.write(
        json.dumps(
            {
                "event": spec.producer_event,
                "feature_id": args.feature_id,
                "verdict": args.verdict,
                "verdict_written": True,
                "feature_delta_hash": feature_delta_hash,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


# --------------------------------------------------------------------------
# CONSUMER -- reads the record back and projects the veto
# --------------------------------------------------------------------------


def _parse_verify_args(
    spec: WaveReviewSpec, argv: list[str] | None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=spec.verify_gate_id,
        description=(
            f"Verify the {spec.wave_upper} {spec.reviewer_title} review verdict "
            "(CONSUMER veto): a thin catalog-gate wrapper over "
            "ReviewVerdictGate.evaluate. PASS (exit 0) iff an artefact-current "
            "APPROVED verdict exists; VETOED / INDETERMINATE block (exit 1) and "
            "carry the specific recovery for the generic gate-out iteration."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def verify_main(
    spec: WaveReviewSpec,
    reader: DiscussReviewReader,
    argv: list[str] | None = None,
) -> int:
    """Verify ``spec``'s wave review consumer veto from the command line.

    Reads the latest verdict record via ``reader``, seals the feature-delta,
    delegates the decision to ``ReviewVerdictGate.evaluate``, and projects it:
    exit 0 + ``{"verdict": "pass", ...}`` when no objection was found; exit 1 +
    ``{"verdict": "vetoed"|"indeterminate", ..., "recovery_suggestions": [...]}``
    otherwise. Returns 1 (degrade-LOUD) when the feature-delta artefact is
    unreadable -- a verdict cannot be sealed against an absent artefact.

    Asymmetric authority (§22.0): a NEEDS_REVISION is a mechanically-honored
    VETO; an artefact-current APPROVED is "no objection found" (PASS), NEVER an
    authorizing GO.
    """
    args = _parse_verify_args(spec, argv)
    repo_root = _resolve_repo_root(args.repo_root)
    try:
        expected_hash = feature_delta_seal(repo_root, args.feature_id)
    except OSError as error:
        _emit(
            {
                "event": spec.consumer_event,
                "gate_id": spec.verify_gate_id,
                "verdict": ReviewGateToken.INDETERMINATE.value,
                "feature_id": args.feature_id,
                "detail": f"feature-delta-unreadable: {error}",
                "recovery_suggestions": list(spec.indeterminate_recovery),
            }
        )
        return 1

    record = reader.latest(repo_root, args.feature_id)
    review = ReviewVerdictGate.evaluate(record, expected_hash)

    if review.token is ReviewGateToken.PASS:
        _emit(
            {
                "event": spec.consumer_event,
                "gate_id": spec.verify_gate_id,
                "verdict": review.token.value,
                "feature_id": args.feature_id,
                "detail": review.detail,
            }
        )
        return 0

    recovery = (
        spec.vetoed_recovery
        if review.token is ReviewGateToken.VETOED
        else spec.indeterminate_recovery
    )
    _emit(
        {
            "event": spec.consumer_event,
            "gate_id": spec.verify_gate_id,
            "verdict": review.token.value,
            "feature_id": args.feature_id,
            "detail": review.detail,
            "recovery_suggestions": list(recovery),
        }
    )
    return 1
