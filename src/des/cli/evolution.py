"""Construct a feature evolution document from explicit completed-feature evidence."""

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
    parser = argparse.ArgumentParser(prog="des evolution")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, "des evolution --repo-root <root> --input -")
    if args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidEvolutionInput",
                "--input accepts only -",
                "pipe closed v1 feature-evolution JSON into des evolution --input -",
            ),
            "des evolution --repo-root <root> --input -",
        )
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidEvolutionDocument",
                "stdin must carry one non-empty strict-UTF-8 feature-evolution JSON",
                "pipe closed v1 feature-evolution JSON into des evolution --input -",
            ),
            "des evolution --repo-root <root> --input -",
        )
    outcome = DeliverySteps().evolution_document(root, raw)
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            "des evolution --repo-root <root> --input -",
        )
    return succeed(
        list(outcome.facts),
        "the caller decides whether and when completed-feature evidence is ready for cleanup",
    )
