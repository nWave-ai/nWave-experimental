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
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


#: Two lines, because the terminal must name the move AVAILABLE NOW and a
#: success leaves a different one than a refusal.  One shared sentence about
#: "a rejecting turn" printed over a Success describes a refusal that did not
#: happen, which is the same class of untruth as a HOW naming a repair the
#: reader cannot perform.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des po")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--finding", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, "des po --repo-root <root> -- after the HOW above")
    request = read_request()
    if isinstance(request, StepRefusal):
        return refuse(request, f"des po --repo-root {root} -- after the HOW above")
    finding = args.finding
    if finding == "-":
        # The objection on stdin, when the Request itself came another way: a
        # rewrite the orchestrator wants to correct is one more turn, not a
        # deletion.
        finding, request = request, ""
    outcome = DeliverySteps().decompose(root, request or finding or "", finding)
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(
                root, "des po --repo-root {root}", outcome.failure.what
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
            f"des po --repo-root {root} --finding - -- your objection to the "
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
