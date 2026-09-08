"""Implement one value's batch behind its admitted oracle, as one step.

ADR-SSOT-002 Section 4b, Amendment 2026-09-06: «A refusing craft turn names its
blocker in a closed `blocked_by` word of its typed payload, and the runner
spends ONE window per value on the role that word names.»  That is the COMPOSED
run.  A step invoked alone does the other half of the same rule: it forwards the
word on `BLOCKED-BY` and stops, because Section 4b makes choosing which role
answers a finding the orchestrator's decision and not the software's.

The defect both halves close is measured.  In runs 31, 32b and 33 (2026-09-06)
the crafter ran the declared oracle, found a case red for a defect of the ORACLE
itself and refused, and a single `CraftRejected` answer sent the finding to a
resume that returned to the same crafter over the same oracle -- three runs and
roughly $8 to buy what one $0.3 designer turn answers.  So a refusal here names
both roles that could answer it, in their exact invocation form, and ranks
neither.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal, projection
from des.cli.step_terminal import StepRefusal, refuse, resolved_root, succeed


def _unblocking_moves(root: Path, value: int) -> tuple[str, ...]:
    """Both roles that can unblock a refusing craft turn, ranked by nothing.

    `BLOCKED-BY` is printed above these lines and this software does not read it
    to pick one: the crafter's word is for the orchestrator.  The third member
    of that closed vocabulary is `product`, which names neither role -- and for
    it the projection below is the honest move, because what is owed then is a
    decision about the Request rather than another turn.
    """
    return (
        f"des oracle --repo-root {root} --value {value} --finding - -- the "
        "finding on stdin, answered by the oracle's own author",
        f"des design --repo-root {root} --value {value} --finding - -- the "
        "finding on stdin, answered by the architect that bound this value",
        projection(root),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des craft")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--value", type=int, required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root, "des craft --repo-root <root> --value N -- after the HOW above"
        )
    own = "des craft --repo-root {root} --value " + str(args.value)
    outcome = DeliverySteps().craft(root, args.value)
    facts = list(outcome.facts)
    if not outcome.succeeded:
        blocked = any(item.startswith("BLOCKED-BY: ") for item in facts)
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            _unblocking_moves(root, args.value)
            if blocked
            else moves_after_refusal(root, own, outcome.failure.what),
            facts=facts,
            diagnostic=outcome.diagnostic,
            turns_bought=outcome.turns_bought,
            role=outcome.role,
        )
    return succeed(
        facts,
        after_step(root),
        diagnostic=outcome.diagnostic,
        turns_bought=outcome.turns_bought,
        role=outcome.role,
    )
