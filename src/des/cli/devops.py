"""Construct optional operational authority from closed semantic facts.

The platform architect supplies facts; this command renders the document and
its canonical sidecar without handing document ownership to a role.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._document_scope_args import (
    add_document_scope_arguments,
    scope_arguments,
    selected_scope,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des devops")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--input")
    parser.add_argument("--replace-current", action="store_true")
    add_document_scope_arguments(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    scope_flags = scope_arguments(args)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            f"des devops --repo-root <root> {scope_flags} --input -"
            " -- after the HOW above",
        )
    if args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidDEVOPSForm",
                "DEVOPS requires one strict UTF-8 OperationalDocumentInput on stdin",
                f"use des devops --repo-root ROOT {scope_flags} --input -",
            ),
            f"des devops --repo-root <root> {scope_flags} --input -",
        )
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidOperationalDocument",
                "stdin must carry one non-empty strict-UTF-8 JSON "
                "OperationalDocumentInput",
                "provide strict UTF-8 OperationalDocumentInput JSON",
            ),
            f"des devops --repo-root <root> {scope_flags} --input -",
        )
    outcome = DeliverySteps().operational_document(
        root,
        raw,
        replace_current=args.replace_current,
        feature=selected_scope(args),
        project=args.project,
    )
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            f"des devops --repo-root <root> {scope_flags} --input -",
        )
    return succeed(
        list(outcome.facts),
        f"des po --repo-root {root} {scope_flags} --operational-facts <repository-relative-json>",
    )
