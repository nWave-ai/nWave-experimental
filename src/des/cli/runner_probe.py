"""des runner-probe CLI -- QW5, mikado.md:47: the runner-capability probe report.

Usage:
    des runner-probe
    des runner-probe --target-root /path/to/repo
    des runner-probe --json

Reports, for every declared runner (pytest plus every language-adapter runner
`runner_registry.seed_runner_registry` registers as a built-in run-facet),
whether it is `supported`, `unsupported`, or `indeterminate` on THIS live
environment -- probed via
`des.adapters.driven.runner.runner_capability_probe.probe_all_runner_capabilities`,
never inferred from documentation or a static reference table.

Exit-code contract (mirrors `des doctor`'s informational shape, NOT
`des health-check`'s pass/fail shape): a report is not a verdict on the
environment's fitness -- a repo with zero Rust code legitimately reports
`cargo-test: unsupported`, and that is not a failure of the probe. Emitting
the report successfully is the only thing this exit code attests.

    0 = report emitted successfully
    2 = usage error (argparse default)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from des.adapters.driven.runner.runner_capability_probe import (
    RunnerCapability,
    probe_all_runner_capabilities,
)


def _format_human(results: tuple[RunnerCapability, ...]) -> str:
    lines = ["nWave Runner Capability Probe"]
    for result in results:
        lines.append(f"  [{result.status.upper()}] {result.runner}: {result.evidence}")
        if result.remediation:
            lines.append(f"           remediation: {result.remediation}")

    counts = {"supported": 0, "unsupported": 0, "indeterminate": 0}
    for result in results:
        counts[result.status] += 1
    lines.append("")
    lines.append(
        f"Summary: {counts['supported']} supported, "
        f"{counts['unsupported']} unsupported, "
        f"{counts['indeterminate']} indeterminate"
    )
    return "\n".join(lines)


def _format_json(results: tuple[RunnerCapability, ...]) -> str:
    data = {"runners": [asdict(r) for r in results]}
    return json.dumps(data, indent=2)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des runner-probe",
        description=(
            "Probe which runners are actually invocable on this environment "
            "(QW5) -- never inferred from static references."
        ),
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=None,
        help="Repo root to probe against (default: current working directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON for machine consumption.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the runner-probe CLI tool."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    results = probe_all_runner_capabilities(args.target_root)

    if args.json_output:
        print(_format_json(results))
    else:
        print(_format_human(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
