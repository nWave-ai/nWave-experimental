"""Decompose one Request into its ordered observable values, as one step.

ADR-SSOT-002 Section 4b: «Recording an accepted decomposition as owned state --
takes the validated ordered observations, returns the persisted graph, or the
drift that prevented the write.»

WHAT THIS STEP STOPPED DOING, and it is the whole point of it existing.  In run
`20260905T062139Z-38400` the Product Owner answered `rejected` while its
diagnostic carried a complete and correct three-value decomposition, and the
runner -- which owned the sequence as well as the turn -- converted that LOCAL
outcome into a verdict about the whole Request and discarded all three values.
Invoked alone the step reports what the role said, forwards its words verbatim,
and returns.  Splitting one Request into three is the orchestrator's decision.

IDEMPOTENT AGAINST THE HANDOVER.  A graph that already exists for this exact
Request is reported, never re-elicited: a re-invocation after a crash is a
resume and not a second paid turn.  A graph that exists for a DIFFERENT Request
is refused LOUD, and this step deletes nothing -- those bytes are somebody's
unfinished delivery.
"""

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
from des.domain.operational_document import (
    OperationalDocumentInvalid,
    operational_facts_from_json,
)


#: Two lines, because the terminal must name the move AVAILABLE NOW and a
#: success leaves a different one than a refusal.  One shared sentence about
#: "a rejecting turn" printed over a Success describes a refusal that did not
#: happen, which is the same class of untruth as a HOW naming a repair the
#: reader cannot perform.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des po")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument(
        "--finding",
        default=None,
        help="additional PO context; '-' reads a finding on stdin for the stored Request",
    )
    add_document_scope_arguments(parser)
    parser.add_argument(
        "--operational-facts",
        default=None,
        help="repository-relative path to OperationalFacts v1 JSON from des devops",
    )
    parser.add_argument(
        "--charter",
        action="store_true",
        help="construct or reuse the selected value's independent expectation charter",
    )
    parser.add_argument(
        "--value",
        type=int,
        default=None,
        help="one-based selected value position (required with --charter)",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="repository-relative or absolute path to charter construction JSON, "
        "or '-' to read it on stdin",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    scope_flags = scope_arguments(args)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root, f"des po --repo-root <root> {scope_flags} -- after the HOW above"
        )
    if args.charter:
        return _run_charter(root, args, scope_flags)
    request = read_request()
    if isinstance(request, StepRefusal):
        return refuse(
            request, f"des po --repo-root {root} {scope_flags} -- after the HOW above"
        )
    operational_facts = None
    if args.operational_facts is not None:
        candidate = Path(args.operational_facts)
        path = root / candidate
        try:
            if (
                candidate.is_absolute()
                or ".." in candidate.parts
                or not candidate.parts
                or path.is_symlink()
                or not path.is_file()
                or not path.resolve().is_relative_to(root.resolve())
            ):
                raise OSError(
                    "--operational-facts must name a regular repository-local file"
                )
            operational_facts = operational_facts_from_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, OperationalDocumentInvalid) as error:
            return refuse(
                StepRefusal(
                    "InvalidOperationalFacts",
                    str(error),
                    "provide a canonical OperationalFacts v1 repository-relative JSON file",
                ),
                f"des po --repo-root {root} {scope_flags} --operational-facts <repository-relative-json>",
            )
    finding = args.finding
    if finding == "-":
        # Resolve the stored Request inside the step's lock. The finding is
        # context for that Request, never a replacement for its original text.
        finding, request = request, None
    outcome = DeliverySteps().decompose(
        root,
        request,
        finding,
        operational_facts,
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
            moves_after_refusal(
                root, "des po --repo-root {root} " + scope_flags, outcome.failure.what
            ),
            diagnostic=outcome.diagnostic,
            turns_bought=outcome.turns_bought,
            role=outcome.role,
        )
    facts = list(outcome.facts)
    # ADR-DES-003 §7: where something was ARCHIVED a second `NEXT` offers the
    # objection, so the orchestrator can send the split back with one more turn.
    # That second line is a real fork under G7 -- the one decision 7 names --
    # and it is the difference between a correctable partition and a silent
    # deletion.
    moves = (after_step(root),)
    if any(item.startswith("ARCHIVED: ") for item in facts):
        moves = (
            *moves,
            f"des po --repo-root {root} {scope_flags} --finding - -- your objection to the "
            "KEPT/ARCHIVED split on stdin, answered by one more Product Owner "
            "turn; the archived bytes are at the ARCHIVE ref above",
        )
    return succeed(
        facts,
        moves,
        diagnostic=outcome.diagnostic,
        turns_bought=outcome.turns_bought,
        role=outcome.role,
    )


def _run_charter(root: Path, args: argparse.Namespace, scope_flags: str) -> int:
    """Construct or reuse one selected value's expectation charter.

    A closed value oracle independent of the whole-diff reviewer: the charter
    Product Owner's only product inputs are the persisted value's own
    observation and the caller-supplied intent/recipe, so no design,
    implementation, test or diff material ever reaches it.
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
                    "decompose one Request first -- pipe it into `des po` on stdin",
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
        from des.adapters.driven.task_invocation.configured_task_adapter import (
            ConfiguredTaskAdapter,
        )

        def resolve_port():
            return ConfiguredTaskAdapter(root)

        outcome = construct_or_reuse(root, resolve_port, stored, args.value, raw_input)
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
            turns_bought=outcome.turns_bought,
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
        turns_bought=outcome.turns_bought,
        diagnostic=outcome.diagnostic,
    )
