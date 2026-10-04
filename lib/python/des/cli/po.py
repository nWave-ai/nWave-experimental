"""Construct host-authored product authority or a source-bound expectation charter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.application.expectation_charter_producer import construct_or_reuse
from des.application.handover import Blocked, acquire_delivery_lock, stored_handover
from des.cli._document_scope_args import (
    add_document_scope_arguments,
    scope_arguments,
    selected_scope,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)
from des.domain.delivery_disposition import Disposition
from des.domain.document_scope import legacy_scope


#: Two lines, because the terminal must name the move AVAILABLE NOW and a
#: success leaves a different one than a refusal.  One shared sentence about
#: "a rejecting turn" printed over a Success describes a refusal that did not
#: happen, which is the same class of untruth as a HOW naming a repair the
#: reader cannot perform.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des po",
        description="Construct supplied PO facts; specialist execution belongs to the host.",
    )
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    add_document_scope_arguments(parser)
    parser.add_argument("--charter", action="store_true")
    parser.add_argument("--value", type=int, help="selected value; --charter only")
    parser.add_argument("--replace-current", action="store_true")
    parser.add_argument(
        "--input",
        help="DISCUSS manifest on stdin (-); for --charter, JSON file or - containing value facts and structured_output",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    scope_flags = scope_arguments(args)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            f"des po --repo-root <root> {scope_flags} --input - -- after the HOW above",
        )
    if args.charter:
        return _run_charter(root, args, scope_flags)
    if args.value is not None or args.input != "-":
        parser.error(
            "product construction requires --input -; --value belongs to --charter"
        )
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(raw, f"des po --repo-root {root} {scope_flags} --input -")
    outcome = DeliverySteps().discuss_document(
        root,
        raw,
        feature=selected_scope(args),
        project=args.project,
        replace_current=args.replace_current,
    )
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(
                root,
                "des po --repo-root {root} " + scope_flags + " --input -",
                outcome.failure.what,
            ),
            facts=list(outcome.facts),
        )
    return succeed(list(outcome.facts), after_step(root))


def _run_charter(root: Path, args: argparse.Namespace, scope_flags: str) -> int:
    """Construct or reuse one selected value's expectation charter.

    The host obtains a fresh source-blind PO contribution from only the stored
    observation and caller intent/recipe. DES validates and persists supplied
    facts; it neither invokes the PO nor claims to prove host isolation.
    """
    invoke = (
        f"des po --repo-root {root} {scope_flags} --charter --value <n> --input <file>"
    )
    if args.value is None:
        return refuse(
            StepRefusal(
                "ExpectationCharterValueRequired",
                "--charter requires --value <n>",
                "supply the one-based selected value position",
            ),
            invoke,
        )

    def raw_input() -> str | None:
        if args.input == "-":
            return sys.stdin.read()
        if args.input is None:
            return None
        candidate = Path(args.input)
        path = candidate if candidate.is_absolute() else root / candidate
        if path.is_symlink() or not path.is_file():
            raise OSError("--input must name a regular readable file")
        return path.read_text(encoding="utf-8")

    lock = acquire_delivery_lock(root)
    if isinstance(lock, Blocked):
        return refuse(
            StepRefusal(lock.what, lock.why, lock.how),
            invoke,
        )
    try:
        stored = stored_handover(root)
        if isinstance(stored, Blocked):
            return refuse(StepRefusal(stored.what, stored.why, stored.how), invoke)
        if stored is None:
            return refuse(
                StepRefusal(
                    "HandoverAbsent",
                    "no decomposition is recorded in this repository, so there "
                    "is no value at any position to charter",
                    "construct one Request first with `des po --input -` and an explicit scope",
                ),
                invoke,
            )
        try:
            scope = legacy_scope(selected_scope(args))
        except Exception as error:  # narrow: argparse already validated shape
            return refuse(
                StepRefusal(
                    "DocumentScopeMissing", str(error), "supply an explicit scope"
                ),
                invoke,
            )
        if scope != stored.scope:
            return refuse(
                StepRefusal(
                    "CharterScopeMismatch",
                    "selected scope does not match the persisted handover scope",
                    "select the scope recorded by the persisted Request",
                ),
                invoke,
            )
        outcome = construct_or_reuse(root, stored, args.value, raw_input)
    finally:
        lock.release()
    if outcome.kind == "reused":
        return succeed(
            [
                f"CHARTER: {outcome.path}",
                "VALID-REUSE: supplied --input, if any, was ignored",
            ],
            after_step(root),
        )
    if outcome.kind == "constructed":
        return succeed(
            [f"CHARTER: {outcome.path}"],
            after_step(root),
            diagnostic=outcome.diagnostic,
        )
    disposition = (
        Disposition.Retry
        if outcome.kind == "retry"
        else Disposition.Indeterminate
        if outcome.kind == "indeterminate"
        else Disposition.Refusal
    )
    return refuse(
        StepRefusal(outcome.what, outcome.why, outcome.how, disposition),
        invoke,
        diagnostic=outcome.diagnostic,
    )
