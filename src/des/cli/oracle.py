"""Measure and record a host-authored public oracle; never invoke its author."""

from __future__ import annotations

import argparse
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des oracle")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--value", type=int, required=True)
    parser.add_argument(
        "--input",
        choices=("-",),
        required=True,
        help="host acceptance-designer structured_output JSON on stdin",
    )
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    own = "des oracle --repo-root {root} --value " + str(args.value) + " --input -"
    if isinstance(root, StepRefusal):
        return refuse(root, own)
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(raw, own.format(root=root))
    outcome = DeliverySteps().oracle(root, args.value, raw)
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(root, own, outcome.failure.what),
            facts=list(outcome.facts),
            diagnostic=outcome.diagnostic,
        )
    return succeed(list(outcome.facts), after_step(root), diagnostic=outcome.diagnostic)
