"""Author one value's executable public oracle, measure it RED, and judge it.

ADR-SSOT-002 Section 4b: each step is invoked alone, returns one closed outcome,
and NAMES the canonical next step as data it does not execute.

ONE STEP AND NOT TWO.  Authoring, the RED measurement and the independent review
are three things the software does to the SAME artefact, and between them the
orchestrator has no decision to make: an authored-but-unmeasured oracle admits
no move, and a measured-but-unjudged one admits only the judgement.  A second
command whose only possible next step is the other half is ceremony (GDP-10).
The choice the orchestrator really has arrives AFTER a refusal, and there this
step gives it: it forwards `DEFECT-OWNER` as data and names both forms that
could answer the finding, ranking neither.

WHY RED IS MEASURED BEFORE THE JUDGEMENT.  On run 23 (2026-09-05) the reviewer
approved a broken oracle in 27.4s of paid turn, while the same oracle answers
`broken` to an execution in 1.1s of wall.  The two roles that hold the oracle
cannot run it, so "this fails on its assertion and not on its scaffolding" is a
property the SOFTWARE owns and measures.

`--finding -` reads a finding from stdin and makes this the CORRECTION turn:
the acceptance author receives the current executed RED beside it.  Which role
a finding goes back to is the orchestrator's decision, so the correction never
routes itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal, projection
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


STDIN = "-"


def _correction_moves(root: Path, value: int) -> tuple[str, ...]:
    """Both forms that could answer a finding about the oracle set, ranked by nothing.

    Section 4b: «A step never chooses the next step.»  The reviewer's owner word
    is forwarded on its own line for the orchestrator to read; this software
    does not read it to pick one of these two.
    """
    return (
        f"des oracle --repo-root {root} --value {value} --finding - -- the "
        "finding on stdin, answered by the oracle's own author",
        f"des design --repo-root {root} --value {value} --finding - -- the "
        "finding on stdin, answered by the architect that bound this value",
        projection(root),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des oracle")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--value", type=int, required=True)
    parser.add_argument("--finding", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root, "des oracle --repo-root <root> --value N -- after the HOW above"
        )
    own = "des oracle --repo-root {root} --value " + str(args.value)
    finding = args.finding
    if finding == STDIN:
        read = read_request()
        if isinstance(read, StepRefusal):
            return refuse(
                StepRefusal(
                    "InvalidFinding",
                    "`--finding -` reads the finding from stdin, and stdin carried "
                    "no non-empty strict-UTF-8 text",
                    "pipe the refusing judge's own finding into this step on "
                    "stdin, or drop `--finding` to author this value's oracle",
                ),
                (own.format(root=root) + " -- after the HOW above",),
            )
        finding = read
    outcome = DeliverySteps().oracle(root, args.value, finding)
    facts = list(outcome.facts)
    if not outcome.succeeded:
        owned = any(item.startswith("DEFECT-OWNER: ") for item in facts)
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            _correction_moves(root, args.value)
            if owned
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
