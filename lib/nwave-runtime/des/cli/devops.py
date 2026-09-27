"""Write locatable operational constraints, as one OPTIONAL step before `des po`.

`F-DEVOPS-CONSTRAINTS-INTO-DISTILL` (`docs/product/backlog.md`) states the
decision: DEVOPS is optional, and when it is asked for, its product is not an
essay -- it is CONSTRAINTS the Product Owner decomposes into observable values
and the acceptance designer turns into execution-observing oracles, examined
like any other code.

WHAT MAKES A CONSTRAINT A CONSTRAINT HERE, and not prose.  The step resolves its
own product through the SAME authority resolver the architect will later cite
that section by, and refuses when what the turn left is unreachable or empty.
That is item (3) of the same backlog row -- «verifica che il resolver
dell'autorita' legga le sezioni che DEVOPS scrive» -- turned into a gate that
fires before the Request consuming it is ever decomposed (GDP-1).

NO DEVOPS ROLE ENTERS THE RUNNER, per the same row: «Nessun ruolo devops nel
runner: la verifica dell'infra e' un valore come gli altri.»  This step runs
BEFORE any decomposition, writes durable authority, and hands back a locator.
Everything downstream is an ordinary value with an ordinary oracle.

IT IS OPTIONAL, and nothing invokes it.  No `NEXT` line of any other step names
it: a project that deploys nothing must not be handed an operational-constraints
turn to refuse, which is `F-WAVE-DENSITY-BY-PROJECT-SHAPE`'s whole point -- cut
the paper, not the verification.  The orchestrator invokes it when platform risk
is real, and never otherwise.
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
from des.cli.step_next import moves_after_refusal
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
    parser.add_argument("--authority")
    parser.add_argument("--section")
    parser.add_argument("--input")
    parser.add_argument("--replace-current", action="store_true")
    add_document_scope_arguments(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    scope_flags = scope_arguments(args)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            f"des devops --repo-root <root> {scope_flags} --authority <doc.md> --section <heading>"
            " -- after the HOW above",
        )
    if args.replace_current and args.input != "-":
        return refuse(
            StepRefusal(
                "InvalidDEVOPSForm",
                "--replace-current is valid only with --input -",
                "use --replace-current only with closed v1 input",
            ),
            f"des devops --repo-root <root> {scope_flags} --input -",
        )
    if args.input is not None:
        if args.input != "-" or args.authority is not None or args.section is not None:
            return refuse(
                StepRefusal(
                    "InvalidDEVOPSForm",
                    "--input - cannot be combined with --authority or --section",
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
    if args.authority is None or args.section is None:
        return refuse(
            StepRefusal(
                "InvalidDEVOPSForm",
                "locator-only DEVOPS requires both --authority and --section",
                "use --authority DOC.md --section HEADING, or --input -",
            ),
            f"des devops --repo-root <root> {scope_flags} --input -",
        )
    own = (
        "des devops --repo-root {root} "
        + scope_flags
        + " --authority "
        + args.authority
        + " --section "
        + repr(args.section)
    )
    request = read_request()
    if isinstance(request, StepRefusal):
        return refuse(request, (own.format(root=root) + " -- after the HOW above",))
    outcome = DeliverySteps().devops(
        root,
        request,
        args.authority,
        args.section,
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
            moves_after_refusal(root, own, outcome.failure.what),
            facts=list(outcome.facts),
            diagnostic=outcome.diagnostic,
            turns_bought=outcome.turns_bought,
            role=outcome.role,
        )
    locator = next(
        item[len("CONSTRAINTS: ") :]
        for item in outcome.facts
        if item.startswith("CONSTRAINTS: ")
    )
    return succeed(
        list(outcome.facts),
        f"des po --repo-root {root} {scope_flags} -- one Request on stdin that CITES "
        f"{locator}, so the Product Owner decomposes those constraints into "
        "observable values",
        diagnostic=outcome.diagnostic,
        turns_bought=outcome.turns_bought,
        role=outcome.role,
    )
