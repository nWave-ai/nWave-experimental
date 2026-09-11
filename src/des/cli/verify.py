"""Build one candidate, run its declared native commands, and persist evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import moves_after_refusal, projection
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
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, "des verify --repo-root <root> -- after the HOW above")
    outcome = DeliverySteps().verify(root)
    facts = list(outcome.facts)

    def _fact(label: str) -> str | None:
        return next(
            (item[len(label) + 2 :] for item in facts if item.startswith(f"{label}: ")),
            None,
        )

    owner = _fact("DEFECT-OWNER")
    positions = [item for item in (_fact("DEFECT-POSITIONS") or "").split(",") if item]
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            _owner_moves(root, owner, positions)
            if owner is not None
            else _moves(root, outcome.failure.what),
            facts=facts,
            diagnostic=outcome.diagnostic,
            turns_bought=outcome.turns_bought,
            role=outcome.role,
        )
    return succeed(
        facts,
        NOTHING_OWED,
        diagnostic=outcome.diagnostic,
        turns_bought=outcome.turns_bought,
        role=outcome.role,
    )


#: Which step answers a finding, by the closed word the judge used. `product`
#: names neither: what is owed then is a decision about the Request, and the
#: projection below is the honest move.
_ANSWERING_STEP = {"oracle": "oracle", "design": "design"}


def _owner_moves(root: Path, owner: str, positions: list[str]) -> tuple[str, ...]:
    """The forms that could answer a finding a judge charged to a named role.

    ADR-DES-003 §6: a finding «the oracle does not cover surface X» returns as
    `DEFECT-OWNER: oracle` and `NEXT` names the author's step. Every line is an
    EXACT invocation form over a real position -- the judge's own value when it
    named one, otherwise every position of this Request, all lawful and none
    invented. More than one line means more than one lawful move, which is the
    fork G7 signals by cardinality; this software ranks none of them.
    """
    step = _ANSWERING_STEP.get(owner)
    if step is None:
        return (projection(root),)
    return (
        *(
            f"des {step} --repo-root {root} --value {position} --finding - -- "
            "the finding on stdin, answered by the role that owns it"
            for position in positions
        ),
        projection(root),
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
