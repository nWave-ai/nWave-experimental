"""des emit-feature-end -- the orchestrator-run feature-end record emitter.

slice-01 of oss-feature-end-emit-cli (the R2 walking-skeleton). Closes
F-ATDD-PURE-FEATURE-END-CYCLE-UNWIRED (backlog.md:738): the two feature-end
records that, today, have NO emitter on a folded orchestrator-run cycle --
``EBatchRefactorCompleted`` and ``FeatureEndReviewVerdict`` -- so the done-gate
(``des verify-integrity``) can certify a genuine terminal instead of
fail-closing on records nothing produces.

WHAT THIS COMMAND IS
--------------------
A thin CLI over the EXISTING tamper-evident ledger writer
(``AtCompletionLedger.append_feature_end_event`` -- the verdict_hash is hashed
into the record_hash, so a forged verdict is detectable). It mirrors the
``des verify-slice-commit`` shape (``--repo`` / ``--feature-id``) and is
registered in ``des.cli.__main__:_REGISTRY`` + the gate catalog 1:1 mirror
(slice-04's AD-26 lesson). It adds NO sequencer/engine and NO new domain type
(DDD-1/DDD-4): the OSS spine is hook-only and this is the interim
orchestrator-run emitter.

ONE record per invocation (DDD-2, composable):

  --record EBatchRefactorCompleted   the E_BATCH_REFACTOR cycle ran. Carries NO
                                     hash; supplying --verdict-hash is REFUSED.
  --record FeatureEndReviewVerdict   the deep review ran. REQUIRES --verdict-hash
                                     (a real signed reviewer HMAC); its absence
                                     is REFUSED.

ANTI-THEATER INVARIANT (DDD-3, load-bearing -- the raison d'etre, per
``feedback_earned_trust_mechanical_evidence_not_llm_verdict``): a
``FeatureEndReviewVerdict`` WITHOUT a bound signed ``--verdict-hash`` is REFUSED
(non-zero exit, no record). The CLU takes the hash from a real deep-review
signing -- it NEVER mints one. The refusal is THIS command's own input check,
not a dispatcher miss.

Exit codes:
    0 = the requested feature-end record was appended.
    2 = the request was REFUSED (anti-theater invariant violated -- a verdict
        with no signed hash, or a hash supplied for the hash-less batch record);
        no record was appended.

Reference: docs/feature/oss-feature-end-emit-cli/feature-delta.md (DDD-1..4).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    EBATCH_REFACTOR_COMPLETED,
    FEATURE_END_REVIEW_VERDICT,
    AtCompletionLedger,
)
from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument


# The two feature-end record kinds one emit may write (DDD-2). The CLI accepts
# the ledger's own event-name constants verbatim so the records it appends are
# byte-identical to the ones the hook-side emitter writes (no parallel naming).
_RECORD_CHOICES = (EBATCH_REFACTOR_COMPLETED, FEATURE_END_REVIEW_VERDICT)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des emit-feature-end",
        description=(
            "Emit one feature-end completion-ledger record (EBatchRefactorCompleted "
            "or FeatureEndReviewVerdict) to the tamper-evident AT-completion ledger. "
            "A FeatureEndReviewVerdict REQUIRES a signed --verdict-hash; without one "
            "it is REFUSED (anti-theater)."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo",
        required=True,
        help="Path to the project root holding the .nwave/ ledger substrate.",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="The kebab-case feature identifier the record is scoped to.",
    )
    parser.add_argument(
        "--record",
        required=True,
        choices=_RECORD_CHOICES,
        help="The feature-end record kind to emit (one per invocation).",
    )
    parser.add_argument(
        "--verdict-hash",
        default=None,
        help="The signed reviewer verdict hash. REQUIRED for FeatureEndReviewVerdict; "
        "must NOT be supplied for EBatchRefactorCompleted.",
    )
    return parser


def _refusal(record: str, error: str) -> dict[str, object]:
    """The REFUSED payload for an anti-theater invariant violation (no record)."""
    return {"event": "EmitRefused", "record": record, "error": error}


def main(argv: list[str] | None = None) -> int:
    """Emit one feature-end record, or REFUSE on an anti-theater violation."""
    args = _build_parser().parse_args(argv)

    if args.record == FEATURE_END_REVIEW_VERDICT and args.verdict_hash is None:
        _emit(
            _refusal(
                args.record,
                "FeatureEndReviewVerdict requires a signed --verdict-hash; a "
                "verdict with no bound hash is refused (anti-theater).",
            )
        )
        return 2

    if args.record == EBATCH_REFACTOR_COMPLETED and args.verdict_hash is not None:
        # DDD-2/DDD-3 anti-theater symmetry: the verdict hash is verdict-only.
        # Binding one to the hash-less batch record would let a forged hash ride
        # on a record the done-gate reads as unsigned -- the exact theater the
        # feature prevents. NOTE: the slice-01 AT contract does NOT yet exercise
        # this branch (escalated AT_GAP_IN_DELIVERY_SCOPE for AT-4); the
        # behaviour is DESIGN-mandated, kept for spec fidelity pending the AT.
        _emit(
            _refusal(
                args.record,
                "EBatchRefactorCompleted carries no verdict hash; --verdict-hash "
                "is verdict-only and must not be supplied here.",
            )
        )
        return 2

    ledger = AtCompletionLedger(args.feature_id, Path(args.repo))
    record = ledger.append_feature_end_event(
        args.record,
        args.verdict_hash,
        feature_id=args.feature_id,
    )
    _emit(
        {
            "event": "FeatureEndRecordEmitted",
            "record": args.record,
            "feature_id": args.feature_id,
            "seq": record["seq"],
        }
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
