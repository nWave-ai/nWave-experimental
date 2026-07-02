"""AT-review verdict producer (ADR-029 D5 -- PRODUCER half).

After the acceptance-designer reviewer APPROVES a slice's AT set, the atdd_pure
DISTILL step records the approval as an ``ATReviewVerdict`` record appended to
the AT-completion ledger ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.

``carpaccio_slice_gate.py`` is the CONSUMER (assertion 5) that reads this record
at the DELIVER entry gate; this module is the PRODUCER that writes it. The
record carries the veto-relevant fields (reviewer_agent_id, slice_id, verdict,
at_ids, at_content_hash, timestamp) and the content seal (at_content_hash is a
SHA-256 over sorted scenario bodies). No ``hmac_sha256`` field is written; key
absence is a non-event (OSS threat model: key holder and would-be forger are the
same person -- keyed signing adds friction without adding a guarantee).

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Literal

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.carpaccio_format import GateError
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.repo_path_resolver import (
    resolve_repo_root as _resolve_repo_root,
)


__all__ = [
    "main",
    "record_at_review_verdict",
    "record_review_outcome",
]

_SCHEMA_VERSION = "1.0.0"
_EVENT = "ATReviewVerdict"
_APPROVED = "APPROVED"

# Slice-05 wiring (feature-fix-robustness-pbt-density-gate, slice-05 AT1):
# the verdict producer consults the robustness density gate CLI at DISTILL
# exit. When both --robustness-declaration AND --robustness-at-scope are
# supplied AND the verdict is APPROVED, the producer invokes
# scripts.cli.check_robustness_density as a subprocess; a non-zero gate exit
# blocks the APPROVED ledger write and surfaces the gate's stdout diagnostic
# (e.g. RobustnessCoverageMiss / RobustnessPBTShallow) on this producer's
# stderr. The producer remains backward-compatible: omitting both flags keeps
# the slice-01..04 invocation shape unchanged (existing callers untouched).
_ROBUSTNESS_GATE_MODULE = "scripts.cli.check_robustness_density"


def record_at_review_verdict(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    verdict: str,
    reviewer_agent_id: str,
    at_ids: list[str],
    at_content_hash: str,
    timestamp: str,
    findings_summary: list[object],
) -> None:
    """Append a keyless ATReviewVerdict record to the AT-completion ledger.

    Writes a single JSONL line to ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``
    carrying the record fields (event, schema_version, slice_id, verdict,
    reviewer_agent_id, at_ids, at_content_hash, timestamp, findings_summary).
    No ``hmac_sha256`` field is written; key absence is a non-event.
    Earlier ledger records are never altered (append-only).
    """
    record: dict[str, object] = {
        "event": _EVENT,
        "schema_version": _SCHEMA_VERSION,
        "slice_id": slice_id,
        "verdict": verdict,
        "reviewer_agent_id": reviewer_agent_id,
        "at_ids": list(at_ids),
        "at_content_hash": at_content_hash,
        "timestamp": timestamp,
        "findings_summary": list(findings_summary),
    }

    # F-13 closure: append through the M7 `AtCompletionLedger` API rather than
    # a hand-written JSONL line. The M7 critical section assigns the monotonic
    # `seq` + `record_hash` every gate-event record carries, so the verdict
    # record shares ONE uniform schema with the rest of the ledger -- the M8
    # carpaccio-order read (`AtCompletionLedger.read_records`) no longer
    # rejects a verdict record interleaved among gate events. The producer's
    # own `timestamp` is preserved (the critical section honours a timestamp
    # already present); the ledger adds only `seq` + `feature_id` + `record_hash`.
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo_root)
    verdict_fields = {
        key: value for key, value in record.items() if key not in ("slice_id", "event")
    }
    ledger.append_review_verdict(slice_id=slice_id, verdict_fields=verdict_fields)


def _consult_robustness_gate(
    repo_root: Path,
    declaration_path: Path,
    at_scope_dir: Path,
) -> tuple[int, str]:
    """Invoke ``check_robustness_density`` as a subprocess; return (exit_code, stdout).

    Slice-05 AT1 wiring (feature-fix-robustness-pbt-density-gate). Runs the
    gate CLI from ``repo_root`` so the namespace package resolution mirrors
    ``run_gate_against_staged_scope`` in the slice's composition root. The
    gate's exit code is the wiring observable; its stdout carries the
    discriminating diagnostic token (e.g. ``RobustnessCoverageMiss``) that
    the verdict producer forwards on its own stderr.
    """
    from des.runtime.interpreter import des_spawn

    completed = des_spawn(
        None,
        _ROBUSTNESS_GATE_MODULE,
        "--declaration",
        str(declaration_path),
        "--at-scope",
        str(at_scope_dir),
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout or ""


def record_review_outcome(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    verdict: str,
    reviewer_agent_id: str,
    at_ids: list[str],
    at_content_hash: str,
    timestamp: str,
    findings_summary: list[object],
    robustness_declaration: Path | None = None,
    robustness_at_scope: Path | None = None,
) -> bool:
    """Record a reviewer outcome; return whether a verdict was written.

    ADR-029 D5 producer half: on an ``APPROVED`` verdict the producer appends a
    keyless ``ATReviewVerdict`` record (via :func:`record_at_review_verdict`) and
    returns ``True``. On ``NEEDS_REVISION`` it writes NOTHING -- the slice loops
    back to the acceptance-designer -- and returns ``False``. The
    APPROVED-writes / NEEDS_REVISION-skips decision is the producer's, not the
    caller's.

    Slice-05 wiring (AT1): when both ``robustness_declaration`` AND
    ``robustness_at_scope`` are supplied AND the verdict is APPROVED, the
    producer FIRST consults the robustness density gate CLI. A non-zero
    gate exit BLOCKS the ledger write (returns ``False``) and writes the
    gate's stdout diagnostic to this process's stderr. Existing call sites
    that omit both args keep the slice-01..04 behavior verbatim.
    """
    if verdict != _APPROVED:
        return False

    if robustness_declaration is not None and robustness_at_scope is not None:
        gate_exit, gate_stdout = _consult_robustness_gate(
            repo_root, robustness_declaration, robustness_at_scope
        )
        if gate_exit != 0:
            sys.stderr.write(gate_stdout)
            return False

    record_at_review_verdict(
        repo_root=repo_root,
        feature_id=feature_id,
        slice_id=slice_id,
        verdict=verdict,
        reviewer_agent_id=reviewer_agent_id,
        at_ids=at_ids,
        at_content_hash=at_content_hash,
        timestamp=timestamp,
        findings_summary=findings_summary,
    )
    return True


# ---------------------------------------------------------------------------
# CLI -- friction-fix F-02
# ---------------------------------------------------------------------------
#
# docs/analysis/atdd-pure-dogfooding-friction-2026-05-20.md F-02: the producer
# exposed only library functions, so an operator recording an ATReviewVerdict
# had to hand-script the ``at_ids`` + ``at_content_hash`` derivation against
# ``carpaccio_slice_gate`` internals. This CLI computes those itself by reusing
# the gate's scenario parser, keeping the producer and consumer derivations DRY.


def _slice_at_derivation(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    at_kind: Literal["gherkin", "pytest-regression"] = "gherkin",
    regression_test_file: Path | None = None,
) -> tuple[list[str], str]:
    """Derive ``(at_ids, at_content_hash)`` for ``slice_id`` (ADR-001 producer mirror).

    ``at_kind="gherkin"`` (default) reuses ``carpaccio_slice_gate``'s ``.feature``
    resolution + parsing + the consumer's ``_at_content_hash`` so the producer
    signs exactly what the gate will later verify. ``carpaccio_slice_gate`` is
    stdlib-only at import time (``yaml`` is imported lazily), so this import
    keeps the bundle safe.

    ``at_kind="pytest-regression"`` (ADR-001, fix-pre-push-hook-dual-installer-
    collision) mirrors the consumer-side derivation in ``carpaccio_format``:
    AST-counted ``test_*`` functions for ``at_ids`` + a sha256 over the
    regression file's raw source text for the content hash. Raises
    ``ValueError`` (a programming-contract violation, never a ``GateError``)
    when ``at_kind="pytest-regression"`` is passed with
    ``regression_test_file=None`` -- only the CLI's own arg-parsing can
    mis-wire this combination.
    """
    if at_kind == "pytest-regression" and regression_test_file is None:
        raise ValueError(
            "_slice_at_derivation: at_kind='pytest-regression' requires "
            "regression_test_file"
        )
    if at_kind == "pytest-regression":
        assert regression_test_file is not None  # guarded above
        from des.cli import carpaccio_format

        at_count = carpaccio_format.count_pytest_regression_ats(regression_test_file)
        at_ids = [f"AT-{n}" for n in range(1, at_count + 1)]
        at_content_hash = carpaccio_format.pytest_regression_content_hash(
            regression_test_file
        )
        return at_ids, at_content_hash

    from des.cli import carpaccio_slice_gate

    scenarios = carpaccio_slice_gate.parse_scenarios(
        carpaccio_slice_gate._read_feature_files(repo_root, feature_id)
    )
    slice_scenarios = [s for s in scenarios if slice_id in s.slice_tags]
    at_ids = [f"AT-{n}" for n in range(1, len(slice_scenarios) + 1)]
    at_content_hash = carpaccio_slice_gate._at_content_hash(slice_scenarios)
    return at_ids, at_content_hash


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="at_review_verdict",
        description=(
            "Record an AT-review verdict (ADR-029 D5 producer). On APPROVED a "
            "keyless ATReviewVerdict record is appended to the AT-completion "
            "ledger; on NEEDS_REVISION nothing is written."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument(
        "--verdict", required=True, choices=["APPROVED", "NEEDS_REVISION"]
    )
    parser.add_argument("--reviewer-agent-id", required=True)
    parser.add_argument("--findings", nargs="*", default=[])
    parser.add_argument("--repo-root", default=None)
    parser.add_argument(
        "--robustness-declaration",
        default=None,
        help=(
            "Optional path to a robustness unbounded-domains.yaml projection. "
            "When supplied alongside --robustness-at-scope, the producer "
            "consults check_robustness_density at DISTILL exit; a non-zero "
            "gate exit blocks the APPROVED ledger write and surfaces the "
            "gate's stdout diagnostic on this producer's stderr."
        ),
    )
    parser.add_argument(
        "--robustness-at-scope",
        default=None,
        help=(
            "Optional path to the staged AT-scope directory the robustness "
            "gate walks. Required alongside --robustness-declaration to "
            "activate the slice-05 gate-consultation wiring."
        ),
    )
    parser.add_argument(
        "--at-kind",
        choices=["gherkin", "pytest-regression"],
        default="gherkin",
        help=(
            "AT-discovery mode (ADR-001, fix-pre-push-hook-dual-installer-"
            "collision). 'gherkin' (default) derives (at_ids, at_content_hash) "
            "from .feature Scenario blocks -- existing callers see byte-"
            "identical behavior. 'pytest-regression' AST-counts module-level "
            "test_* functions in --regression-test-file."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        default=None,
        help=(
            "Repo-relative path to a plain-pytest regression-test file. "
            "Required iff --at-kind=pytest-regression."
        ),
    )
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Record an AT-review verdict from the command line.

    Computes ``at_ids`` + ``at_content_hash`` itself from the entering slice's
    scenarios -- the operator supplies only the feature id, slice id, verdict
    and reviewer id. On APPROVED a keyless record is appended to the ledger; on
    NEEDS_REVISION nothing is written. Returns 0 on success.
    """
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    at_kind = args.at_kind
    regression_test_file = (
        (repo_root / args.regression_test_file) if args.regression_test_file else None
    )
    try:
        if at_kind == "pytest-regression" and regression_test_file is None:
            # Only the CLI's own arg-parsing can mis-wire this combination
            # (ADR-001 DD-7): `_slice_at_derivation` raises `ValueError` on it
            # (a programming-contract violation), so the CLI shell enforces
            # it itself as a `GateError` diagnostic before that function is
            # ever called with `regression_test_file=None`.
            raise GateError(
                2,
                {
                    "event": "MalformedInput",
                    "cause": "the pytest regression-test file",
                    "error": (
                        "--at-kind=pytest-regression requires --regression-test-file"
                    ),
                },
            )
        at_ids, at_content_hash = _slice_at_derivation(
            repo_root,
            args.feature_id,
            args.slice_id,
            at_kind=at_kind,
            regression_test_file=regression_test_file,
        )
    except GateError as gate_error:
        error_line = json.dumps(gate_error.payload, sort_keys=True) + "\n"
        sys.stdout.write(error_line)
        sys.stderr.write(error_line)
        print_human_summary(
            Verdict.FAIL,
            f"AT-review verdict CLI refused: {gate_error.payload.get('error')}",
        )
        return gate_error.exit_code
    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    robustness_declaration = (
        Path(args.robustness_declaration) if args.robustness_declaration else None
    )
    robustness_at_scope = (
        Path(args.robustness_at_scope) if args.robustness_at_scope else None
    )
    written = record_review_outcome(
        repo_root=repo_root,
        feature_id=args.feature_id,
        slice_id=args.slice_id,
        verdict=args.verdict,
        reviewer_agent_id=args.reviewer_agent_id,
        at_ids=at_ids,
        at_content_hash=at_content_hash,
        timestamp=timestamp,
        findings_summary=list(args.findings),
        robustness_declaration=robustness_declaration,
        robustness_at_scope=robustness_at_scope,
    )
    outcome = "recorded" if written else "skipped (NEEDS_REVISION)"
    event_line = (
        json.dumps(
            {
                "event": "ATReviewVerdictCLI",
                "feature_id": args.feature_id,
                "slice_id": args.slice_id,
                "verdict": args.verdict,
                "verdict_written": written,
                "outcome": outcome,
            },
            sort_keys=True,
        )
        + "\n"
    )
    # Pre-existing machine-readable contract keeps the JSON event on stdout
    # (no breaking change for existing CI / hook consumers); the slice-02
    # surface co-emits it on stderr alongside a colored human-readable line.
    # Verdict mapping per slice-02: APPROVED → ✅ PASS (ledger record written),
    # NEEDS_REVISION → ⚠️ DEGRADED (soft refusal, no ledger write).
    sys.stdout.write(event_line)
    sys.stderr.write(event_line)
    human_verdict = Verdict.PASS if written else Verdict.DEGRADED
    summary = (
        f"AT-review {args.verdict} recorded for {args.feature_id}/{args.slice_id}"
        if written
        else f"AT-review {args.verdict} -- {args.feature_id}/{args.slice_id} needs revision (no ledger write)"
    )
    print_human_summary(human_verdict, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
