"""Compare-and-swap one candidate in, reconcile the owned index, close the graph.

ADR-SSOT-002 Section 4b: «Integrating by compare-and-swap -- takes the candidate
and the expected-old ref, returns the integrated SHA, or the refusal that the
destination moved» and «Reconciling the owned index and releasing the workspace».

ONE SWAP AND NEVER TWO.  The expected-old ref is the candidate's own single
parent, read back from the object rather than passed in, so a caller cannot name
a base the candidate does not have.  A destination that moved refuses; nothing
is forced and nothing is retried, which is why a confused orchestrator calling
this twice cannot integrate twice.

IT BUYS NO TURN.  Integration is enactment, and Section 4b keeps enactment in
the software whole.  The handover is closed here, with the turn records
released: a graph outliving its own integrated candidate would make the next
`des state` name work that is already in the destination.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


#: The form that reads the orchestrator's own reason from stdin, spelled like
#: every other reason this surface takes.
STDIN = "-"


#: One direction, because this step buys no turn: there is never a role's
#: answer for its refusal to point at, and the shared terminal says so itself.
INTEGRATED = (
    "the candidate is the destination, the owned index is reconciled and the "
    "graph is closed -- this Request is done"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des integrate")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--on-my-evidence", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            "des integrate --repo-root <root> --candidate <sha> -- after the HOW above",
        )
    own = "des integrate --repo-root {root} --candidate " + args.candidate
    evidence = args.on_my_evidence
    if evidence == STDIN:
        read = read_request()
        if isinstance(read, StepRefusal):
            return refuse(
                StepRefusal(
                    "InvalidEvidence",
                    "`--on-my-evidence -` reads your reason from stdin, and "
                    "stdin carried no non-empty strict-UTF-8 text",
                    "pipe the evidence that answers the judge into this step on "
                    "stdin -- it is written into the durable record beside the "
                    "verdict it goes over",
                ),
                (own.format(root=root) + " --on-my-evidence - -- after the HOW above",),
            )
        evidence = read
    outcome = DeliverySteps().integrate(root, args.candidate, evidence)
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
    return succeed(
        list(outcome.facts),
        after_step(root) if _still_owed(root) else NOTHING_OWED,
    )


def _still_owed(root: Path) -> bool:
    """Does any graph remain in this repository after the swap?

    Measured, never assumed.  A successful integration closes THIS Request's
    graph, and whether another one is open is a fact on disk -- reporting
    "nothing owed" without looking would hide a second Request mid-flight.
    """
    from des.application.handover import handover_path

    try:
        return handover_path(root).exists()
    except OSError:
        return True
