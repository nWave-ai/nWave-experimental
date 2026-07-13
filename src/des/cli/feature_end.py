"""des feature-end -- the consolidated feature-end command namespace (DDD-7).

slice-02 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03). The single
``des feature-end <verb>`` entry point under the one ``des.cli.__main__``
dispatcher, consolidating the feature-end surface (AD-26 1:1 catalog mirror,
``single_entry_point`` contract). Today it carries one verb:

  des feature-end sign --repo . --feature-id <id> --reviewer-agent-id <agent>
                       --verdict {APPROVED|REJECTED} [--finding <text> ...]

``sign`` is a THIN SHIM (DDD-7): it parses args + marshals I/O + invokes the
platform-agnostic ``feature_end_sign_service.sign_feature_end_review`` use-case
and prints the result. ZERO decision logic lives here -- the same use-case is
the one the eventual SubagentStop hook shim will invoke cross-platform.

The standalone ``des emit-feature-end`` top-level entry (slice-01) stays
reachable verbatim -- the round-trip that feeds this signer's hash to the
emitter goes through that entry, so ``des feature-end --help`` advertising
``sign`` plus the preserved emitter together satisfy the consolidated-surface
back-compat contract.

ANTI-THEATER (DDD-5): on a non-real verdict (no/empty agent, unknown/missing
verdict) the use-case REFUSES; this shim prints the structured
``{"event": "SignRefused", ...}`` payload (the same shape slice-01's
``EmitRefused`` carries) and exits non-zero -- a real input-check refusal,
never a silently minted hash, never a vacuous dispatcher miss.

Exit codes:
    0 = a genuine verdict hash was produced over the real deep-review verdict.
    2 = the request was REFUSED (anti-theater invariant violated); no hash.

Reference: docs/feature/oss-feature-end-emit-cli/feature-delta.md (DDD-5..7).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.application.feature_end_cycle_service import (
    CycleIndeterminate,
    CycleRefusal,
    run_feature_end_cycle,
)
from des.application.feature_end_sign_service import (
    SignRefusal,
    sign_feature_end_review,
)


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object (the command's observable)."""
    print(json.dumps(payload))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des feature-end",
        description=(
            "The consolidated feature-end command namespace. Verbs: sign "
            "(produce a keyless content-seal FeatureEndReviewVerdict hash from "
            "a real deep-review verdict); run (run the feature-end cycle -- run "
            "the gates, then sign + emit the feature-end records)."
        ),
    )
    verbs = parser.add_subparsers(dest="verb", required=True)

    sign = verbs.add_parser(
        "sign",
        help="Seal a real deep-review verdict into a verifiable verdict hash.",
        description=(
            "Produce a keyless content-seal verdict_hash from a real reviewer "
            "deep-review verdict (agent + APPROVED/REJECTED + findings) that "
            "feeds `des emit-feature-end --verdict-hash`. A non-real verdict "
            "(no/empty agent, unknown/missing verdict) is refused "
            "(anti-theater); no hash is minted."
        ),
    )
    sign.add_argument(
        "--repo",
        required=True,
        help=(
            "Path to the project root (retained for API-stability; "
            "sign reads no key post-demotion)."
        ),
    )
    sign.add_argument(
        "--feature-id",
        required=True,
        help="The kebab-case feature identifier the verdict is scoped to.",
    )
    sign.add_argument(
        "--reviewer-agent-id",
        default=None,
        help="The reviewer agent that produced the deep-review verdict.",
    )
    sign.add_argument(
        "--verdict",
        default=None,
        help="The deep-review decision: APPROVED or REJECTED.",
    )
    sign.add_argument(
        "--finding",
        action="append",
        default=[],
        dest="findings",
        help="A reviewer finding (repeatable). Documentary; not part of the "
        "signed region.",
    )

    run = verbs.add_parser(
        "run",
        help="Run the feature-end cycle: run the gates, then sign + emit.",
        description=(
            "Run the feature-end cycle -- run the walking-skeleton and "
            "environmental-e2e gates (leaving their genuine heartbeat records), "
            "then sign the deep-review verdict and emit the EBatchRefactorCompleted "
            "+ FeatureEndReviewVerdict records. A failed gate fail-closes the "
            "cycle (anti-theater); no record is emitted."
        ),
    )
    run.add_argument(
        "--repo",
        required=True,
        help="Path to the project root holding the .nwave/ ledger substrate.",
    )
    run.add_argument(
        "--feature-id",
        required=True,
        help="The kebab-case feature identifier the cycle is scoped to.",
    )
    run.add_argument(
        "--feature-dir",
        required=True,
        help="The feature directory the cycle's gates run against.",
    )
    run.add_argument(
        "--reviewer-agent-id",
        default=None,
        help="The reviewer agent that produced the deep-review verdict.",
    )
    run.add_argument(
        "--verdict",
        default=None,
        help="The deep-review decision: APPROVED or REJECTED.",
    )
    return parser


def _run_sign(args: argparse.Namespace) -> int:
    """Marshal args into the use-case, print the result, return the exit code."""
    outcome = sign_feature_end_review(
        feature_id=args.feature_id,
        reviewer_agent_id=args.reviewer_agent_id,
        verdict=args.verdict,
        repo_root=Path(args.repo),
    )
    if isinstance(outcome, SignRefusal):
        _emit({"event": "SignRefused", "verb": "sign", "error": outcome.error})
        return 2

    _emit(
        {
            "event": "FeatureEndReviewSigned",
            "verb": "sign",
            "feature_id": args.feature_id,
            "verdict_hash": outcome.verdict_hash,
        }
    )
    return 0


def _run_cycle(args: argparse.Namespace) -> int:
    """Marshal args into the cycle use-case, print the result, return the exit code."""
    outcome = run_feature_end_cycle(
        repo_root=Path(args.repo),
        feature_id=args.feature_id,
        feature_dir=Path(args.feature_dir),
        reviewer_agent_id=args.reviewer_agent_id,
        verdict=args.verdict,
    )
    if isinstance(outcome, CycleRefusal):
        _emit(
            {
                "event": "FeatureEndCycleRefused",
                "verb": "run",
                "feature_id": args.feature_id,
                "error": outcome.error,
            }
        )
        return 2

    if isinstance(outcome, CycleIndeterminate):
        # ADR-GV-002 D4: exit 3, mirroring run_contract_gate.py's existing
        # local `_GATE_INDETERMINATE_EXIT_CODE` pattern -- a LOUD refusal to
        # decide, never a fabricated FeatureEndCycleComplete over a leg the
        # cycle never actually observed (DDD-CERT-2).
        _emit(
            {
                "event": "FeatureEndCycleIndeterminate",
                "verb": "run",
                "feature_id": args.feature_id,
                "error": outcome.reason,
                "leg_census": {
                    "ran": outcome.leg_census.ran,
                    "not_applicable": outcome.leg_census.not_applicable,
                    "indeterminate": outcome.leg_census.indeterminate,
                },
            }
        )
        return 3

    _emit(
        {
            "event": "FeatureEndCycleComplete",
            "verb": "run",
            "feature_id": args.feature_id,
            "verdict_hash": outcome.verdict_hash,
            "leg_census": {
                "ran": outcome.leg_census.ran,
                "not_applicable": outcome.leg_census.not_applicable,
                "indeterminate": outcome.leg_census.indeterminate,
            },
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch a `des feature-end <verb>` invocation to its handler."""
    args = _build_parser().parse_args(argv)
    if args.verb == "run":
        return _run_cycle(args)
    return _run_sign(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
