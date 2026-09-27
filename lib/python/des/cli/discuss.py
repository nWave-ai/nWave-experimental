"""Construct DISCUSS authority and its ordered DESIGN handover graph."""

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
from des.domain.discuss_contract import (
    DESCRIBE_FLAG,
    HELP_EPILOG,
    HOW_TO_FIX,
    describe_input,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des discuss",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_repo_root_argument(parser, "--repo-root", type=Path, default=None)
    parser.add_argument(
        "--input", default=None, help="use - to read the JSON from stdin"
    )
    parser.add_argument(
        "--describe-input",
        action="store_true",
        help="print the full input schema and a minimal copyable example, then exit",
    )
    parser.add_argument("--replace-current", action="store_true")
    add_document_scope_arguments(
        parser,
        required="--describe-input" not in (sys.argv[1:] if argv is None else argv),
    )
    args = parser.parse_args(argv)
    if args.describe_input:
        sys.stdout.write(describe_input())
        return 0
    if (
        not args.project
        and args.feature is None
        and args.epic is None
        and args.slice is None
    ):
        parser.error(
            "one of --project, --epic ID, --feature ID, or --slice FEATURE_ID SLICE_ID is required"
        )
    if args.repo_root is None or args.input is None:
        parser.error(
            f"--repo-root and --input are required; see `{DESCRIBE_FLAG}` for the input"
        )
    scope_flags = scope_arguments(args)
    root = resolved_root(args.repo_root)
    invocation = f"des discuss --repo-root <root> {scope_flags} --input -"
    if isinstance(root, StepRefusal):
        return refuse(root, invocation)
    if args.replace_current and args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidDiscussInput",
                "--replace-current is valid only with --input -",
                f"use --replace-current only with --input -; see `{DESCRIBE_FLAG}`",
            ),
            invocation,
        )
    if args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidDiscussInput",
                "--input accepts only -",
                HOW_TO_FIX,
            ),
            invocation,
        )
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidDiscussDocument",
                "stdin must carry one non-empty strict-UTF-8 DISCUSS JSON",
                HOW_TO_FIX,
            ),
            invocation,
        )
    outcome = DeliverySteps().discuss_document(
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
            invocation,
            facts=list(outcome.facts),
        )
    return succeed(list(outcome.facts), "des design --repo-root <root> --value 1")
