"""des blast-radius -- the blast-radius measurement primitive (slice-01).

Charter/feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Slice Plan slice-01, [REF] Architecture & Contract Tests).

    des blast-radius --repo <path> --paths <f1> [<f2> ...]

Slice-01 supports ONLY the `--paths` input mode (`--staged`/`--diff <ref>`
are slice-02 scope). Emits ONE single-line JSON verdict on stdout plus a
human-readable summary line on stderr (REUSE: `human_surface
.print_human_summary`).

stdout token, success:
    {"event": "BlastRadiusMeasured", "tier": "S"|"M",
     "measures": {"files": <int>, "lines_changed": <int|null>,
                  "boundary_files": [], "consumer_counts": {}},
     "reasons": [<str>, ...]}

stdout token, a named `--paths` entry does not exist on disk (exit 2, never
a silently-fabricated S):
    {"event": "BlastRadiusInputRejected", "reasons": [<str>, ...]}

Exit codes: 0 = a measurement was produced (tier S or M). 2 = malformed
input -- a missing `--repo`/`--paths` flag, or a named `--paths` entry that
does not exist on disk.
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des blast-radius",
        description=(
            "Measure a change's blast radius (files/lines) and report its tier."
        ),
    )
    parser.add_argument("--repo", required=True, help="The repository root.")
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Explicit list of repo-relative paths to measure (slice-01 input mode).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # A required flag (--repo / --paths) is missing -- argparse already
        # printed a self-explaining usage error naming the flag to stderr;
        # convert its SystemExit into a plain return so an in-process caller
        # gets an int, never an uncaught exception (P3 in-process contract).
        return exc.code if isinstance(exc.code, int) else 2

    repo = Path(args.repo)

    try:
        verdict = measure_blast_radius(repo, args.paths)
    except BlastRadiusInputRejected as exc:
        rejection_payload: dict[str, object] = {
            "event": "BlastRadiusInputRejected",
            "reasons": [str(exc)],
        }
        print(json.dumps(rejection_payload))
        print_human_summary(Verdict.FAIL, f"blast-radius input rejected: {exc}")
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
