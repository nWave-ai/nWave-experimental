"""Bind one value's typed design facts, as one architect turn invoked alone.

ADR-SSOT-002 Section 4b: «One role turn under a provider-enforced typed
contract -- takes the role, the minimum facts that role consumes, the private
workspace; returns the closed outcome, the role's typed output, its diagnostic
verbatim.»

REPEATABLE BY DESIGN, and that is the correction.  Invoked a second time over a
value that is already bound, with `--finding -` reading the finding from stdin,
the turn receives the CURRENT typed facts beside it and what it returns REPLACES
them.  Section 4b: «The fixed correction edges as the software's own routing
table ... are moves an orchestrator may make, not moves the runner takes on its
own.»  So this step holds no edge: it names the moves and returns.

The Request is not an argument.  It is IN the handover the software owns, and
asking the orchestrator to retype it would make one mistyped character refuse
the graph as another Request's.
"""

from __future__ import annotations

import argparse
import sys
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


#: The one form that reads the finding from stdin.  A finding is a role's own
#: prose -- newlines, quotes, whatever it wrote -- so it travels on a stream and
#: never through a shell argument that would have to be escaped to survive.
STDIN = "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des design")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--value", type=int, required=True)
    parser.add_argument("--finding", default=None)
    parser.add_argument("--input", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root, "des design --repo-root <root> --value N -- after the HOW above"
        )
    own = "des design --repo-root {root} --value " + str(args.value)
    if args.input is not None:
        if args.input != STDIN:
            return refuse(
                StepRefusal(
                    "InvalidDesignInput",
                    "--input accepts only -",
                    "pipe closed v1 semantic JSON into `des design --input -`",
                ),
                (own.format(root=root),),
            )
        manifest = read_request()
        if isinstance(manifest, StepRefusal):
            return refuse(
                StepRefusal(
                    "InvalidDesignDocument",
                    "stdin must carry one non-empty strict-UTF-8 JSON manifest",
                    "pipe closed v1 semantic JSON into `des design --input -`",
                ),
                (own.format(root=root),),
            )
        outcome = DeliverySteps().design_document(root, args.value, manifest)
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
            )
        return succeed(list(outcome.facts), after_step(root))
    finding = args.finding
    if finding == STDIN:
        read = read_request()
        if isinstance(read, StepRefusal):
            return refuse(
                StepRefusal(
                    "InvalidFinding",
                    "`--finding -` reads the finding from stdin, and stdin carried "
                    "no non-empty strict-UTF-8 text",
                    "pipe the role's own finding into this step on stdin, or drop "
                    "`--finding` to author this value's facts from nothing",
                ),
                (own.format(root=root) + " -- after the HOW above",),
            )
        finding = read
    outcome = DeliverySteps().design(root, args.value, finding)
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(root, own, outcome.failure.what),
            diagnostic=outcome.diagnostic,
            turns_bought=outcome.turns_bought,
            role=outcome.role,
        )
    return succeed(
        list(outcome.facts),
        after_step(root),
        diagnostic=outcome.diagnostic,
        turns_bought=outcome.turns_bought,
        role=outcome.role,
    )
