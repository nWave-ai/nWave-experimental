"""Construct DISCUSS authority and its ordered DESIGN handover graph."""

from __future__ import annotations

import argparse
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des discuss")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    invocation = "des discuss --repo-root <root> --input -"
    if isinstance(root, StepRefusal):
        return refuse(root, invocation)
    if args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidDiscussInput",
                "--input accepts only -",
                "pipe closed v1 DISCUSS JSON into des discuss --input -",
            ),
            invocation,
        )
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidDiscussDocument",
                "stdin must carry one non-empty strict-UTF-8 DISCUSS JSON",
                "pipe closed v1 DISCUSS JSON into des discuss --input -",
            ),
            invocation,
        )
    outcome = DeliverySteps().discuss_document(root, raw)
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            invocation,
            facts=list(outcome.facts),
        )
    return succeed(list(outcome.facts), "des design --repo-root <root> --value 1")
