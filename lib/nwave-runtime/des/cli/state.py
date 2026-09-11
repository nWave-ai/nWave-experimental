"""Read the owned delivery state as a projection, and name the next step.

ADR-SSOT-002 Section 4b: the DES is a tool the orchestrating model invokes.
This is the step that step reads itself against -- the exact Request, the
ordered values, what each already carries, and the canonical next step as DATA
it does not execute.

It is READ-ONLY, and that is its whole contract: it writes no byte, invokes no
role and spawns no provider.  An orchestrator calls it after every terminal,
including a terminal it did not understand, so a projection that could change
the state would make "look at where I am" a move with consequences.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.application.delivery_state import canonical_next, read_state
from des.application.delivery_steps import blocked_disposition
from des.application.handover import Blocked
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_terminal import StepRefusal, refuse, resolved_root, succeed


#: What the projection prints for a root nothing has been decomposed in.  An
#: absence STATED, never a blank line that reads like an empty Request.
NO_REQUEST = "(none)"


def _value_lines(state: object) -> list[str]:
    lines = []
    for value in state.values:  # type: ignore[attr-defined]
        carried = " ".join(
            (
                f"design={'bound' if value.design_bound else 'absent'}",
                f"oracle={value.oracle}",
                f"craft={value.craft}",
            )
        )
        lines.append(
            f"VALUE-{value.position}: {json.dumps(value.observation, ensure_ascii=False)}"
            f" {carried}"
        )
    return lines


def _candidate_lines(state: object) -> list[str]:
    """What the Request already carries as a verification, when it carries one.

    Printed with its record state rather than as a bare SHA, because the two
    states a candidate can be in differ by what the orchestrator may do next:
    one is integrable, the other was measured against a graph a wave producer
    has since corrected and buys nothing until it is verified again.
    """
    if state.candidate is None:  # type: ignore[attr-defined]
        return []
    return [f"CANDIDATE: {state.candidate} {state.candidate_record}"]  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des state")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, "des state --repo-root <root> -- after the HOW above")
    state = read_state(root)
    if isinstance(state, Blocked):
        return refuse(
            StepRefusal(
                state.what,
                state.why,
                state.how,
                blocked_disposition(state),
            ),
            f"des state --repo-root {root} -- after the HOW above",
        )
    request = (
        NO_REQUEST
        if state.request is None
        else json.dumps(state.request, ensure_ascii=False)
    )
    return succeed(
        [f"REQUEST: {request}", *_value_lines(state), *_candidate_lines(state)],
        canonical_next(state, root),
    )
