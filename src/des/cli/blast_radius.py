"""des blast-radius -- the blast-radius measurement primitive (slice-02 complete).

Charter/feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Slice Plan slice-02, [REF] Architecture & Contract Tests).

    des blast-radius --repo <path> [--paths <f1> [<f2> ...] | --staged | --diff <ref>]

Exactly one of `--paths` / `--staged` / `--diff <ref>` is required; passing
zero or more than one is malformed input (exit 2). Emits ONE single-line JSON
verdict on stdout plus a human-readable summary line on stderr (REUSE:
`human_surface.print_human_summary`).

stdout token, success:
    {"event": "BlastRadiusMeasured", "tier": "S"|"M"|"L",
     "measures": {"files": <int>, "lines_changed": <int|null>,
                  "boundary_files": [<str>, ...],
                  "consumer_counts": {"<module.symbol>": <int|null>, ...}},
     "reasons": [<str>, ...]}

stdout token, a named `--paths` entry does not exist on disk, or the
exactly-one-input-mode grammar was violated (exit 2, never a silently
fabricated S):
    {"event": "BlastRadiusInputRejected", "reasons": [<str>, ...]}

stdout token, a present well-typed `.nwave/des-config.json` `blast_radius`
threshold is outside its documented floor/ceiling (D4, exit 2, never a
silent clamp/fallback):
    {"event": "BlastRadiusConfigRejected", "reasons": [<str>, ...]}

Exit codes: 0 = a measurement was produced (tier S, M, or L). 2 = malformed
input or a rejected configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.application.blast_radius_measurement import (
    BlastRadiusInputRejected,
    measure_blast_radius,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.blast_radius import BlastRadiusConfigRejected


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des blast-radius",
        description=(
            "Measure a change's blast radius (files/lines/boundary/consumers) "
            "and report its tier."
        ),
    )
    parser.add_argument("--repo", required=True, help="The repository root.")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=None,
        help="Explicit list of repo-relative paths to measure (one input mode).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        default=False,
        help="Measure the staged scope (git diff --cached) (one input mode).",
    )
    parser.add_argument(
        "--diff",
        metavar="REF",
        default=None,
        help="Measure the scope since REF (git diff REF) (one input mode).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # A required flag (--repo) is missing -- argparse already printed a
        # self-explaining usage error naming the flag to stderr; convert its
        # SystemExit into a plain return so an in-process caller gets an
        # int, never an uncaught exception (P3 in-process contract).
        return exc.code if isinstance(exc.code, int) else 2

    repo = Path(args.repo)

    modes_supplied = sum((args.paths is not None, args.staged, args.diff is not None))
    if modes_supplied != 1:
        reasons = [
            "exactly one of --paths / --staged / --diff <ref> is required "
            f"(got {modes_supplied}) -- pass exactly one input mode"
        ]
        rejection_payload: dict[str, object] = {
            "event": "BlastRadiusInputRejected",
            "reasons": reasons,
        }
        print(json.dumps(rejection_payload))
        print_human_summary(
            Verdict.FAIL,
            "blast-radius requires exactly one input mode (--paths/--staged/--diff)",
        )
        return 2

    try:
        verdict = measure_blast_radius(
            repo,
            paths=args.paths,
            staged=args.staged,
            diff_ref=args.diff,
        )
    except BlastRadiusInputRejected as exc:
        rejection_payload = {
            "event": "BlastRadiusInputRejected",
            "reasons": [str(exc)],
        }
        print(json.dumps(rejection_payload))
        print_human_summary(Verdict.FAIL, f"blast-radius input rejected: {exc}")
        return 2
    except BlastRadiusConfigRejected as exc:
        rejection_payload = {
            "event": "BlastRadiusConfigRejected",
            "reasons": [str(exc)],
        }
        print(json.dumps(rejection_payload))
        print_human_summary(Verdict.FAIL, f"blast-radius config rejected: {exc}")
        return 2

    measured_payload: dict[str, object] = {
        "event": "BlastRadiusMeasured",
        "tier": verdict.tier.value,
        "measures": {
            "files": verdict.measures.files,
            "lines_changed": verdict.measures.lines_changed,
            "boundary_files": list(verdict.measures.boundary_files),
            "consumer_counts": dict(verdict.measures.consumer_counts),
        },
        "reasons": verdict.reasons,
    }
    print(json.dumps(measured_payload))
    print_human_summary(
        Verdict.PASS,
        f"blast radius measured tier={verdict.tier.value} "
        f"(files={verdict.measures.files}, "
        f"lines_changed={verdict.measures.lines_changed})",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
