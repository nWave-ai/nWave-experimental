"""``des next`` -- read-only advisory projection of the atdd_pure DELIVER loop.

NON-GOAL (pinned, load-bearing -- feature-delta.md [REF] Non-Goals): ``des
next`` MUST NOT be wrapped in an automated poll-and-auto-execute loop within
nwave-dev, even for ``step_kind=producing-tool`` steps -- doing so recreates
the rejected sequencer (ADR-FLOW-001, the OSS hook-only mandate). This tool
returns a copy-paste-able command precisely because pasting is a human/agent
decision point; NEVER auto-invoke the returned ``how`` command.

Thin argparse shell over ``des.application.deliver_loop_projection.
project_next_step`` (the pure composition core). Prints exactly ONE JSON
``NextStepProjected`` object to stdout in ``--format json`` mode, mirroring
the ``des verify-red-green`` / ``des record-examine-verdict`` single-JSON-
line precedent.

CONTRACT_SHAPE: bounded-change -- declared mutation set = {stdout}; no
filesystem writes.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from des.application.deliver_loop_projection import project_next_step
from des.cli._repo_root_arg import add_repo_root_argument


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="next",
        description=(
            "Read-only advisory projection of the next legal atdd_pure "
            "DELIVER-loop step for a feature. NEVER auto-execute the "
            "returned `how` command -- pasting it is a human/agent decision "
            "point (feature-delta.md [REF] Non-Goals)."
        ),
    )
    parser.add_argument("--feature-id", required=True, help="The feature id.")
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the project root (default: cwd)."
    )
    parser.add_argument(
        "--slice",
        dest="slice_id",
        default=None,
        help=(
            "The slice THIS lane owns, e.g. slice-06. Declare it whenever the "
            "Slice Plan carries more than one pending row -- a pending row is "
            "not evidence the slice is yours, since in a parallel worktree "
            "every slice the lane does not own stays pending forever. Omitted "
            "on an ambiguous plan, the projection reports INDETERMINATE rather "
            "than naming a slice by table position."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "human"),
        default="json",
        help="Output format.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse argv, project the next step, print it. Returns the exit code."""
    args = _build_parser().parse_args(argv)
    step = project_next_step(Path(args.repo), args.feature_id, args.slice_id)
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(step)))
    else:
        print(f"{step.what}\n{step.why}\n{step.how}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
