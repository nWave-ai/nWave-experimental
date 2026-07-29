"""des parallel-safety-report -- advisory measured cross-check of a plan's
declared-parallel claims (measured-parallel-safety-report, slice-01 WS;
generalized to a Feature-Plan input by parallel-by-default-feature-plan
slice-02, D-6).

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Driving Ports, [REF] Decisions Table DA/DE/DF/DH, [REF] Contract Tests).
Generalized by: docs/feature/parallel-by-default-feature-plan/feature-delta.md
  ([REF] Driving Ports, D-6/D-7, [REF] Contract Tests CT-6..CT-10).

    des parallel-safety-report (--feature-delta <path> | --epic-delta <path>)
        --repo <path>
        --scope <id>=<p1>[,<p2>...]         # EXACTLY TWO; id = slice-id or feature-id
        [--timeout <seconds>]               # wall-clock per blast-radius (default 200)

`--feature-delta` reads a Slice Plan's declared-parallel SLICE rows;
`--epic-delta` reads an epic-delta's Feature Plan declared-parallel FEATURE
rows (mutually exclusive, exactly one required). Reads the declared plan
(reusing `validate_feature_delta`), classifies the two declared-parallel
rows, measures each via the REAL `des blast-radius` (through
`SubprocessBlastRadiusAdapter`), and emits ONE single-line JSON event on
stdout + a human summary on stderr -- BYTE-IDENTICAL event shape regardless
of input source (D-6).

stdout token, success (advisory -- exit 0 on BOTH verdicts, DF/D-2):
    {"event": "ParallelSafetyReport",
     "verdict": "MEASURED-SAFE" | "DRIFT",
     "pair": ["slice-02", "slice-03"],
     "overlap": {"files": [...], "boundary_files": [...], "consumer_symbols": [...]},
     "reasons": [<str>, ...]}

stdout token, malformed invocation (exit 2, mirrors blast-radius's
`BlastRadiusInputRejected`):
    {"event": "ParallelSafetyInputRejected", "reasons": [<str>, ...]}

Exit codes: 0 = a verdict was produced (advisory, never a refusal, DF/D-2).
2 = a malformed invocation (a --scope naming a declared-serial or absent row,
or not exactly two scopes), or a --feature-delta carrying NO Slice Plan section
at all -- rejected at validation, BEFORE any measurement. A Slice Plan that IS
present but declares zero parallel slices is NOT that case: it is a valid
monolithic plan, and only the --scope bindings are rejected.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.adapters.driven.parallel_safety.subprocess_blast_radius_adapter import (
    SubprocessBlastRadiusAdapter,
    SubprocessBlastRadiusRejected,
)
from des.application.parallel_safety_report import (
    ParallelSafetyReport,
    run_parallel_safety_report,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.validate_feature_delta import (
    read_declared_parallel_feature_ids,
    read_declared_parallel_slice_ids,
)
from des.ports.slice_blast_radius_port import SliceScope


_DEFAULT_TIMEOUT_S = 200.0

#: verdict token -> the human-surface face (DH): MEASURED-SAFE -> PASS ✅,
#: DRIFT -> DEGRADED ⚠️, UNMEASURED -> INDETERMINATE ❓ (absence-vs-incapacity
#: visibly distinct, D-4).
_FACE_BY_VERDICT: dict[str, Verdict] = {
    "MEASURED-SAFE": Verdict.PASS,
    "DRIFT": Verdict.DEGRADED,
    "UNMEASURED": Verdict.INDETERMINATE,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des parallel-safety-report",
        description=(
            "Advisory POST-HOC measured cross-check of a plan's declared-"
            "parallel claims: MEASURED-SAFE / DRIFT per declared-parallel pair."
        ),
    )
    parser.add_argument(
        "--feature-delta",
        default=None,
        help=(
            "The feature-delta whose Slice Plan declares the parallel claims. "
            "Mutually exclusive with --epic-delta; exactly one is required."
        ),
    )
    parser.add_argument(
        "--epic-delta",
        default=None,
        help=(
            "The epic-delta whose Feature Plan declares the parallel claims "
            "(parallel-by-default-feature-plan slice-02, D-6). Mutually "
            "exclusive with --feature-delta; exactly one is required."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo",
        required=True,
        help="The repository root, forwarded to des blast-radius --repo.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=None,
        metavar="SLICE-ID=PATHS",
        help=(
            "Bind a declared-parallel slice to its comma-separated path-set "
            "(EXACTLY TWO for slice-01)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT_S,
        help="Wall-clock bound per blast-radius subprocess (default 200s).",
    )
    return parser


def _reject(reasons: list[str], how: str | None = None) -> int:
    """Emit the input-rejection event + human face; exit 2 (mirrors
    blast-radius). `how` overrides the default invocation-shape remedy for a
    rejection whose repair is a different action."""
    print(json.dumps({"event": "ParallelSafetyInputRejected", "reasons": reasons}))
    print_human_summary(
        Verdict.FAIL,
        "parallel-safety-report input rejected",
        why=reasons[0] if reasons else "",
        how=how
        or (
            "supply EXACTLY ONE of --feature-delta/--epic-delta and EXACTLY "
            "TWO --scope <id>=<paths> bindings, each naming a DECLARED-"
            "PARALLEL Slice/Feature Plan row (no `depends-on`)"
        ),
    )
    return 2


def _parse_scope(raw: str) -> tuple[str, tuple[str, ...]] | None:
    """Parse one `<slice-id>=<p1>[,<p2>...]` binding. Returns None if malformed
    (no `=`, empty slice-id, or empty path-set)."""
    if "=" not in raw:
        return None
    slice_id, _, paths_csv = raw.partition("=")
    slice_id = slice_id.strip()
    paths = tuple(p.strip() for p in paths_csv.split(",") if p.strip())
    if not slice_id or not paths:
        return None
    return slice_id, paths


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # A required flag missing -- argparse printed a self-explaining usage
        # error; convert its SystemExit into an int so an in-process caller
        # gets a return value, never an uncaught exception (P3 contract).
        return exc.code if isinstance(exc.code, int) else 2

    input_sources_supplied = [
        s for s in (args.feature_delta, args.epic_delta) if s is not None
    ]
    if len(input_sources_supplied) != 1:
        return _reject(
            [
                "exactly one of --feature-delta or --epic-delta is required; "
                f"got {len(input_sources_supplied)}"
            ]
        )

    if args.epic_delta is not None:
        content = Path(args.epic_delta).read_text(encoding="utf-8")
        declared_feature_ids = read_declared_parallel_feature_ids(content)
        if declared_feature_ids is None:
            return _reject(
                [
                    f"{args.epic_delta} carries NO '## Wave: DISCUSS / [REF] "
                    f"Feature Plan' section at all -- a structural omission, NOT "
                    f"a plan that declares zero parallel features; there is no "
                    f"declared claim to cross-check"
                ],
                how=(
                    f"run `des feature-delta-doctor {args.epic_delta}` -- it "
                    f"reports the missing locked section and the command that "
                    f"emits its canonical heading -- then re-run this report"
                ),
            )
        declared_parallel = declared_feature_ids
        plan_row_noun = "Feature Plan row"
    else:
        content = Path(args.feature_delta).read_text(encoding="utf-8")
        declared_slice_ids = read_declared_parallel_slice_ids(content)
        if declared_slice_ids is None:
            return _reject(
                [
                    f"{args.feature_delta} carries NO '## Wave: DISCUSS / [REF] "
                    f"Slice Plan' section at all -- a structural omission, NOT a "
                    f"plan that declares zero parallel slices; there is no "
                    f"declared claim to cross-check"
                ],
                how=(
                    f"run `des feature-delta-doctor {args.feature_delta}` -- it "
                    f"reports the missing locked section and the command that "
                    f"emits its canonical heading -- then re-run this report"
                ),
            )
        declared_parallel = declared_slice_ids
        plan_row_noun = "Slice Plan row"

    raw_scopes = args.scope or []
    reasons: list[str] = []
    if len(raw_scopes) != 2:
        reasons.append(
            f"exactly two --scope bindings are required (slice-01 compares one "
            f"pair); got {len(raw_scopes)}"
        )

    parsed: list[tuple[str, tuple[str, ...]]] = []
    for raw in raw_scopes:
        binding = _parse_scope(raw)
        if binding is None:
            reasons.append(
                f"malformed --scope {raw!r}: expected <slice-id>=<p1>[,<p2>...]"
            )
            continue
        slice_id, paths = binding
        if slice_id not in declared_parallel:
            reasons.append(
                f"--scope names {slice_id!r}, which is NOT a declared-parallel "
                f"{plan_row_noun} (declared-parallel: {list(declared_parallel)}); "
                f"a scope may only bind a row with no `depends-on`"
            )
            continue
        parsed.append((slice_id, paths))

    if reasons:
        return _reject(reasons)

    (id_a, paths_a), (id_b, paths_b) = parsed
    adapter = SubprocessBlastRadiusAdapter(Path(args.repo))
    try:
        report = run_parallel_safety_report(
            adapter,
            ((id_a, SliceScope(paths_a)), (id_b, SliceScope(paths_b))),
            timeout_s=args.timeout,
        )
    except SubprocessBlastRadiusRejected as exc:
        return _reject([f"measurement rejected by des blast-radius: {exc}"])

    _emit_report(report)
    return 0


def _emit_report(report: ParallelSafetyReport) -> None:
    """Emit the single-line JSON event on stdout + the distinct human face on
    stderr (advisory -- no exit code work here, DF/D-2)."""
    payload: dict[str, object] = {
        "event": "ParallelSafetyReport",
        "verdict": report.verdict,
        "pair": list(report.pair),
        "overlap": {
            "files": list(report.overlap.files),
            "boundary_files": list(report.overlap.boundary_files),
            "consumer_symbols": list(report.overlap.consumer_symbols),
        },
        "reasons": list(report.reasons),
    }
    if report.unmeasured is not None:
        payload["unmeasured"] = {
            "slice": report.unmeasured.slice_id,
            "paths": list(report.unmeasured.paths),
            "reason": report.unmeasured.reason,
        }
    print(json.dumps(payload))

    face = _FACE_BY_VERDICT[report.verdict]
    print_human_summary(
        face,
        f"parallel-safety {report.verdict} for pair {report.pair[0]}, {report.pair[1]}",
        why=report.reasons[0] if report.reasons else "",
    )


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
