"""Build the one candidate, verify it natively, review it, and judge it blind.

ADR-SSOT-002 Section 4b names four properties, and this command holds three of
them: «Constructing the whole-Request candidate from an identified base»,
«Verifying natively on the candidate», and «Judging the promised observation
source-blind».

WHY THE JUDGEMENT IS NOT A COMMAND OF ITS OWN.  Two of Section 4b's preserved
invariants decide it together.  Native evidence is «captured exactly once and
never re-executed», and for the source-blind pass «the software still CONSTRUCTS
those three inputs».  A separate `des examine` could satisfy both only by
carrying captured stdout and stderr between two processes -- either in new owned
state, which Section 4b's own falsifiers forbid («a persisted field records a
phase, a status ...», «no second resident owner of ... owned state»), or through
the orchestrator's hands, which would stop the software constructing the input
it must construct.  Re-executing to recapture is the third option and it is
excluded by name.  So the capture and the judgement share one process.

Nothing here moves a ref.  The candidate is a real commit parented on the base
and OUT of the destination's history until `des integrate` swaps it in, so a
refusing review or a refusing examiner leaves the checkout exactly where it was.

NO CORRECTION PASS.  The composed run answers a failed verification or a vetoed
diff with one crafter correction turn; invoked alone this step returns the
finding and stops, because that edge is a move the orchestrator may make and not
one the runner takes on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import moves_after_refusal, projection
from des.cli.step_terminal import StepRefusal, refuse, resolved_root, succeed


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
    candidate = next(
        item[len("CANDIDATE: ") :] for item in facts if item.startswith("CANDIDATE: ")
    )
    # ONE next step, and it is not what the state projection would say. The
    # projection derives its answer from the handover and the turn records, and
    # neither records a verified candidate -- Section 4b keeps the candidate in
    # Git and nothing else -- so after a successful verify it still answers
    # `des verify`. Printing that beside the integration form would offer the
    # orchestrator a re-run as a canonical move, which would spend two paid
    # judgements to reach the state it is already in.
    return succeed(
        facts,
        f"des integrate --repo-root {root} --candidate {candidate}",
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
    It is named as an integration form here for exactly the reason Section 4b
    gives: the orchestrator may integrate with evidence of its own, and the step
    says so as an OPTION rather than doing it.  The form carries the FLAG that
    move actually requires: a NEXT line naming an invocation the next step
    refuses is the class of defect this project records as a lying terminal.
    """
    moves = list(moves_after_refusal(root, "des verify --repo-root {root}", what))
    sha = what.rpartition(" on candidate ")[2].strip()
    if len(sha) == 40:
        moves.insert(
            0,
            f"des integrate --repo-root {root} --candidate {sha} "
            "--on-my-evidence - -- only if you hold evidence of your own that "
            "answers the refusal above, with that evidence on stdin",
        )
    return tuple(moves)
