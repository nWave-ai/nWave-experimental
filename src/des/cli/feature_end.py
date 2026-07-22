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

from des.application.feature_end_batch_service import (
    BatchIndeterminate,
    BatchIneligible,
    BatchManifestRefused,
    BatchRefused,
    parse_batch_manifest,
    run_feature_end_batch,
)
from des.application.feature_end_cycle_service import (
    CycleIndeterminate,
    CycleRefusal,
    CycleSuccess,
    run_feature_end_cycle,
)
from des.application.feature_end_sign_service import (
    SignRefusal,
    sign_feature_end_review,
)
from des.cli.carpaccio_format import GateError as _CarpaccioGateError
from des.cli.carpaccio_format import mark_feature_end_sealed as _mark_feature_end_sealed
from des.cli.carpaccio_format import (
    mark_slice_status_shipped as _mark_slice_status_shipped,
)
from des.cli.carpaccio_format import parse_slice_plan as _parse_slice_plan
from des.domain.repo_path_resolver import feature_delta_path as _feature_delta_path


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object (the command's observable)."""
    print(json.dumps(payload))


# ---------------------------------------------------------------------------
# Feature-delta markdown sync (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED,
# GDP-1/4/6): `des feature-end run` mints the `FeatureEndReviewVerdict`
# ledger record but never wrote back to the feature-delta.md `[REF] Slice
# Plan` table -- so a genuinely feature-end-sealed feature could sit on
# disk with stale `pending` rows indefinitely. PURELY ADDITIVE: runs
# strictly AFTER a genuine `CycleSuccess`; never affects the cycle's own
# exit code. Best-effort-loud (GDP-6), mirrors `commit_slice._sync_slice_
# plan_status` / `_notify_feature_end_unmissable`'s shape.
# ---------------------------------------------------------------------------


def _sync_feature_delta_on_feature_end(repo_root: Path, feature_id: str) -> None:
    """Best-effort-loud (GDP-6): backstop-flip every declared slice's
    Status to ``shipped`` and append the feature-end-sealed marker.

    PURELY ADDITIVE: runs strictly AFTER the cycle's ``FeatureEndReviewVerdict``
    record has already been minted -- never affects the cycle's own exit
    code. A missing ``feature-delta.md`` (a bugfix, or a feature with no
    Slice Plan) is a silent no-op -- the feature-end cycle succeeding is
    the primary outcome, this markdown sync is a best-effort side effect.
    Idempotent: an already-shipped row or an already-sealed marker is a
    no-op (the pure helpers' own contract).
    """
    try:
        delta_path = _feature_delta_path(repo_root, feature_id)
        if not delta_path.is_file():
            return
        original = delta_path.read_text(encoding="utf-8")
        text = original
        try:
            plan = _parse_slice_plan(text)
        except _CarpaccioGateError:
            plan = None
        if plan is not None:
            for row in plan.rows:
                rewritten = _mark_slice_status_shipped(text, row.slice_id)
                if rewritten is not None:
                    text = rewritten
        sealed = _mark_feature_end_sealed(text)
        if sealed is not None:
            text = sealed
        if text != original:
            delta_path.write_text(text, encoding="utf-8")
    except Exception as exc:
        print(
            "WARNING: des feature-end could not sync the feature-delta.md "
            f"for feature {feature_id!r}: {exc}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des feature-end",
        description=(
            "The consolidated feature-end command namespace. Verbs: sign "
            "(produce a keyless content-seal FeatureEndReviewVerdict hash from "
            "a real deep-review verdict); run (run the feature-end cycle -- run "
            "the gates, then sign + emit the feature-end records)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "FEATURE-END EXAMINE, resolved 2026-07-20 (feature "
            "feature-end-examine-phase) -- the gap this epilog described "
            "until today (the DES phase vocabulary had no word for a "
            "feature-SCOPE examine) is closed:\n"
            "  Dispatch `DES-PHASE: FEATURE_END_EXAMINE` + `DES-SLICE: "
            "feature-end` -- `classify_atdd_pure_dispatch` accepts it "
            "(regression-sealed: tests/des/unit/domain/test_des_marker_parser.py"
            "::test_feature_end_examine_phase_with_feature_end_scope_is_valid). "
            "The canonical per-slice `EXAMINE` at a `slice-NN` scope is "
            "UNCHANGED and stays legal (the anti-regression twin in the same "
            "file) -- the trap of widening FEATURE_END_PHASES with that word "
            "was avoided by using a distinct one.\n"
            "\n"
            "  This `run` verb already enforces it: for every charter under "
            "docs/product/expectations/<feature-id>/ it requires a fresh "
            "PASS `ExamineVerdict` recorded at `--slice feature-end` "
            "(see `_check_feature_end_examine`); a missing/failed/stale "
            "verdict refuses LOUD with the exact `des record-examine-verdict "
            "--slice feature-end ...` remediation.\n"
            "\n"
            "  Known ceremony lag (not a functional gap): the "
            "`feature-end-examine-phase` feature-delta's own Slice Plan row "
            "still reads `pending` and has no SliceCommitVerified record, "
            "even though its code is merged and its regression tests are "
            "green on this branch -- close that bookkeeping via the normal "
            "commit-slice flow when convenient, it does not block using the "
            "phase word today."
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
            "cycle (anti-theater); no record is emitted. Sealing MULTIPLE "
            "features that share one clean whole-tree pass? See "
            "'des feature-end run-batch' -- it pays the full-suite cost ONCE "
            "for the whole set instead of once per invocation."
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

    run_batch = verbs.add_parser(
        "run-batch",
        help=(
            "Run the feature-end cycle over a SET of features, paying the "
            "whole-tree full-suite cost ONCE for the whole batch."
        ),
        description=(
            "Run the feature-end cycle over a manifest-declared SET of "
            "features. The whole-tree full-suite leg runs EXACTLY ONCE for "
            "the whole batch (D-3); every other leg, sign, and emit still "
            "run PER FEATURE, and each feature still emits its OWN "
            "FeatureEnd records. A malformed manifest refuses before any "
            "gate is dispatched (GDP-1). A RED shared suite refuses the "
            "WHOLE batch with zero member cycles run and zero FeatureEnd "
            "records for any feature (D-4) -- never bisected."
        ),
    )
    run_batch.add_argument(
        "manifest",
        help=(
            "Path to a JSON array of {feature_id, feature_dir, "
            "reviewer_agent_id, verdict} entries (>=1)."
        ),
    )
    run_batch.add_argument(
        "--repo",
        required=True,
        help="Path to the project root holding the .nwave/ ledger substrate.",
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


def _member_cycle_payload(
    feature_id: str,
    outcome: CycleRefusal | CycleIndeterminate,
    *,
    verb: str,
) -> dict[str, object]:
    """The `FeatureEndCycleRefused` / `FeatureEndCycleIndeterminate` payload
    shape for one member's cycle outcome, parameterized by `verb`.

    SSOT for the payload SHAPE both `_run_cycle` (verb "run") and `_run_batch`
    (verb "run-batch", per member line) emit -- extracting the shared shape
    guarantees the two verbs stay byte-identical on every field beyond `verb`
    itself (D-1: `run-batch` over a single-entry manifest is indistinguishable
    from the classic `run` close)."""
    if isinstance(outcome, CycleRefusal):
        payload: dict[str, object] = {
            "event": "FeatureEndCycleRefused",
            "verb": verb,
            "feature_id": feature_id,
            "error": outcome.error,
        }
        # fix-feature-end-refusal-names-failing-tests (GDP-3): the full-suite
        # leg's refusal carries the WHAT-detail an operator needs to act
        # without a 25-30 min diagnostic re-run. `None` (every OTHER leg's
        # refusal) omits the key entirely -- never a false zero standing in
        # for "not applicable to this refusal".
        if outcome.failing_tests is not None:
            payload["failing_tests"] = list(outcome.failing_tests)
        if outcome.failing_count is not None:
            payload["failing_count"] = outcome.failing_count
        if outcome.junit_artifact is not None:
            payload["junit_artifact"] = outcome.junit_artifact
        return payload

    # ADR-GV-002 D4: exit 3, mirroring run_contract_gate.py's existing
    # local `_GATE_INDETERMINATE_EXIT_CODE` pattern -- a LOUD refusal to
    # decide, never a fabricated FeatureEndCycleComplete over a leg the
    # cycle never actually observed (DDD-CERT-2).
    return {
        "event": "FeatureEndCycleIndeterminate",
        "verb": verb,
        "feature_id": feature_id,
        "error": outcome.reason,
        "leg_census": {
            "ran": outcome.leg_census.ran,
            "not_applicable": outcome.leg_census.not_applicable,
            "indeterminate": outcome.leg_census.indeterminate,
        },
    }


def _member_cycle_success_payload(
    feature_id: str, outcome: CycleSuccess, *, verb: str
) -> dict[str, object]:
    """The `FeatureEndCycleComplete` payload shape for one member's
    successful cycle outcome (SSOT, mirrors :func:`_member_cycle_payload`)."""
    return {
        "event": "FeatureEndCycleComplete",
        "verb": verb,
        "feature_id": feature_id,
        "verdict_hash": outcome.verdict_hash,
        "leg_census": {
            "ran": outcome.leg_census.ran,
            "not_applicable": outcome.leg_census.not_applicable,
            "indeterminate": outcome.leg_census.indeterminate,
        },
    }


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
        _emit(_member_cycle_payload(args.feature_id, outcome, verb="run"))
        return 2

    if isinstance(outcome, CycleIndeterminate):
        _emit(_member_cycle_payload(args.feature_id, outcome, verb="run"))
        return 3

    _sync_feature_delta_on_feature_end(Path(args.repo), args.feature_id)
    _emit(_member_cycle_success_payload(args.feature_id, outcome, verb="run"))
    return 0


_MEMBER_EXIT_CODES = {
    "FeatureEndCycleComplete": 0,
    "FeatureEndCycleRefused": 2,
    "FeatureEndCycleIndeterminate": 3,
}


def _run_batch(args: argparse.Namespace) -> int:
    """Marshal args into the batch use-case, print JSON-lines, return the
    worst-outcome-wins exit code (D-D9)."""
    repo_root = Path(args.repo)
    specs = parse_batch_manifest(Path(args.manifest))
    if isinstance(specs, BatchManifestRefused):
        _emit(
            {
                "event": "FeatureEndBatchManifestRefused",
                "verb": "run-batch",
                "error": specs.error,
            }
        )
        return 2

    outcome = run_feature_end_batch(repo_root, specs)
    if isinstance(outcome, BatchIneligible):
        _emit(
            {
                "event": "FeatureEndBatchIneligible",
                "verb": "run-batch",
                "feature_id": outcome.feature_id,
                "error": outcome.error,
            }
        )
        return 2

    if isinstance(outcome, BatchRefused):
        payload: dict[str, object] = {
            "event": "FeatureEndBatchRefused",
            "verb": "run-batch",
            "error": outcome.error,
        }
        if outcome.failing_tests is not None:
            payload["failing_tests"] = list(outcome.failing_tests)
        if outcome.failing_count is not None:
            payload["failing_count"] = outcome.failing_count
        if outcome.junit_artifact is not None:
            payload["junit_artifact"] = outcome.junit_artifact
        _emit(payload)
        return 2

    if isinstance(outcome, BatchIndeterminate):
        _emit(
            {
                "event": "FeatureEndBatchIndeterminate",
                "verb": "run-batch",
                "error": outcome.reason,
            }
        )
        return 3

    worst_exit = 0
    succeeded = refused = indeterminate = 0
    for feature_id, member_outcome in outcome.members:
        if isinstance(member_outcome, (CycleRefusal, CycleIndeterminate)):
            payload = _member_cycle_payload(
                feature_id, member_outcome, verb="run-batch"
            )
        else:
            _sync_feature_delta_on_feature_end(repo_root, feature_id)
            payload = _member_cycle_success_payload(
                feature_id, member_outcome, verb="run-batch"
            )
        _emit(payload)
        member_exit = _MEMBER_EXIT_CODES[str(payload["event"])]
        worst_exit = max(worst_exit, member_exit)
        if payload["event"] == "FeatureEndCycleComplete":
            succeeded += 1
        elif payload["event"] == "FeatureEndCycleRefused":
            refused += 1
        else:
            indeterminate += 1

    _emit(
        {
            "event": "FeatureEndBatchComplete",
            "verb": "run-batch",
            "members": len(outcome.members),
            "succeeded": succeeded,
            "refused": refused,
            "indeterminate": indeterminate,
        }
    )
    return worst_exit


def main(argv: list[str] | None = None) -> int:
    """Dispatch a `des feature-end <verb>` invocation to its handler."""
    args = _build_parser().parse_args(argv)
    if args.verb == "run":
        return _run_cycle(args)
    if args.verb == "run-batch":
        return _run_batch(args)
    return _run_sign(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
