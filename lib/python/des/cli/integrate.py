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
`des state` name work that is already in this destination worktree. Integration
inside a linked lane still owes the explicit lane-to-principal integration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.lane import LaneSteps, LinkedLane, Unobservable, lane_integrate_invocation
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    resolved_root,
    succeed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des integrate")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            "des integrate --repo-root <root> --candidate <sha> -- after the HOW above",
        )
    own = "des integrate --repo-root {root} --candidate " + args.candidate
    outcome = DeliverySteps().integrate(root, args.candidate)
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
            role=outcome.role,
        )
    facts = list(outcome.facts)
    identity = LaneSteps().lane_identity(root)
    if isinstance(identity, LinkedLane):
        facts.extend(
            (
                f"DESTINATION-WORKTREE: {identity.worktree}",
                f"DESTINATION-BRANCH: {identity.branch}",
                f"PRINCIPAL-WORKTREE: {identity.principal_worktree}",
                f"PRINCIPAL-HEAD: {identity.principal_head}",
            )
        )
        return succeed(
            facts,
            lane_integrate_invocation(identity.principal_worktree, identity.worktree),
        )
    if isinstance(identity, Unobservable):
        facts.append(f"LANE-IDENTITY: unknown: {identity.why}")
        return succeed(
            facts,
            f"inspect Git worktree registration for {root}; "
            "the remaining lane integration step is unknown",
        )
    return succeed(facts, after_step(root) if _still_owed(root) else NOTHING_OWED)


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
