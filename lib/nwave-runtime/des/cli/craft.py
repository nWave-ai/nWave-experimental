"""Measure and record a host-authored implementation against its recorded oracle."""

from __future__ import annotations

import argparse
from pathlib import Path

from des.application.delivery_state import (
    AFTER_MOVE,
    BEFORE_MOVE,
    prefactoring_form,
)
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
    parser = argparse.ArgumentParser(prog="des craft")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--value", type=int, required=True)
    parser.add_argument(
        "--input",
        choices=("-",),
        required=False,
        help="host crafter structured_output JSON on stdin",
    )
    parser.add_argument(
        "--prefactoring-phase",
        choices=(BEFORE_MOVE, AFTER_MOVE),
        help=(
            "measure the declared preservation oracle on the current host-owned "
            "bytes: `before-move` first, then, after only the declared move, "
            "`after-move-before-behavior`; the printed NEXT names whichever "
            "phase is owed before the feature oracle"
        ),
    )
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    # A preservation phase retries as that phase (it accepts no --input); only
    # ordinary craft re-invokes through the structured-output template.
    own = (
        prefactoring_form("{root}", args.value, args.prefactoring_phase)
        if args.prefactoring_phase is not None
        else "des craft --repo-root {root} --value " + str(args.value) + " --input -"
    )
    if isinstance(root, StepRefusal):
        return refuse(root, own)
    if args.prefactoring_phase is not None:
        if args.input is not None:
            parser.error(
                "--prefactoring-phase measures native bytes and accepts no --input"
            )
        outcome = DeliverySteps().prefactoring(
            root, args.value, args.prefactoring_phase
        )
    else:
        if args.input is None:
            parser.error("ordinary craft requires --input -")
        raw = read_request()
        if isinstance(raw, StepRefusal):
            return refuse(raw, own.format(root=root))
        outcome = DeliverySteps().craft(root, args.value, raw)
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
