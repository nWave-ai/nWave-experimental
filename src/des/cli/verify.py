"""Build one candidate, run its declared native commands, and persist evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.lane import LaneSteps, LinkedLane, Unobservable, lane_integrate_invocation
from des.cli.role_guidance import prepare_next
from des.cli.step_next import moves_after_refusal
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    resolved_root,
    succeed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des verify")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--fresh",
        action="store_true",
        help="execute every declared native check again; invalidate current approval first",
    )
    modes.add_argument(
        "--integrated-candidate",
        metavar="SHA",
        help="measure HEAD from this retained integrated candidate without reviving its Request",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, "des verify --repo-root <root> -- after the HOW above")
    steps = DeliverySteps()
    outcome = (
        steps.reverify_integrated(root, args.integrated_candidate)
        if args.integrated_candidate is not None
        else steps.verify(root, fresh=args.fresh)
    )
    facts = list(outcome.facts)

    def _fact(label: str) -> str | None:
        return next(
            (item[len(label) + 2 :] for item in facts if item.startswith(f"{label}: ")),
            None,
        )

    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            _moves(root, outcome.failure.what),
            facts=facts,
            diagnostic=outcome.diagnostic,
            role=outcome.role,
        )
    if args.integrated_candidate is not None:
        identity = LaneSteps().lane_identity(root)
        next_step = NOTHING_OWED
        if isinstance(identity, LinkedLane):
            next_step = lane_integrate_invocation(identity.principal_worktree, root)
        elif isinstance(identity, Unobservable):
            facts.append(f"LANE-IDENTITY: unknown: {identity.why}")
            next_step = (
                f"inspect Git worktree registration for {root}; "
                "the remaining lane integration step is unknown"
            )
        return succeed(facts, next_step)
    candidate = _fact("CANDIDATE")
    assert candidate is not None
    return succeed(
        facts,
        prepare_next(root, "reviewer", candidate),
        diagnostic=outcome.diagnostic,
        role=outcome.role,
    )


def _moves(root: Path, what: str) -> tuple[str, ...]:
    """The moves a refusal leaves, with the candidate named when one exists.

    A source-blind refusal carries its candidate SHA inside the WHAT, because
    the ephemeral worktree is gone by then and the SHA is the only handle left.
    The host may inspect that candidate and choose mechanical integration; this
    terminal neither admits it nor requires an evidence override.
    """
    moves = list(moves_after_refusal(root, "des verify --repo-root {root}", what))
    sha = what.rpartition(" on candidate ")[2].strip()
    if len(sha) == 40:
        moves.insert(
            0,
            f"des integrate --repo-root {root} --candidate {sha}",
        )
    return tuple(moves)
