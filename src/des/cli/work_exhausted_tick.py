"""des-work-exhausted-tick -- the wall-clock work-exhausted escalation ladder.

DELIVER-wired (slice-02 of autonomous-consolidation-and-bugfix-loops --
charter `an-exhausted-loop-stops-instead-of-idle-holding.md`, feature-delta
Slice Plan row slice-02, Locked Decision D-2). This module is the driving
port a background loop's tick calls every time it evaluates whether its
safe-work tier is exhausted: "the queue is empty, or every remaining item is
gated/unblockable, or the queue read is ambiguous -- so I say so on a fixed
WALL-CLOCK ladder, not silently".

DISTILL-interim decision (feature-delta Open Question 2, no DESIGN wave ran
for this feature -- see feature-delta `## Wave: DISTILL / [REF]
Wave-Decision Reconciliation`, OQ-2 resolution): the "safe-work tier" this
tick observes is exactly the 4-way `--queue-state` this CLI accepts --
`empty` / `all-gated` / `has-unblocked-item` / `malformed` -- never a richer
model. `empty`, `all-gated` and `malformed` are ALL "exhausted" (malformed
is treated as exhausted -- SAFE per the charter's "What to explore" --
never as an indeterminate hang). `has-unblocked-item` is the ONLY
non-exhausted state and the ONLY fresh trigger that can resume a loop past
its own STOP/ESCALATE.

THE CONTROLLABLE CLOCK (deterministic ladder, NO real sleep): `--now` is an
explicit ISO-8601 instant the CALLER supplies (production: the real
wall-clock at tick time; acceptance tests: a synthetic instant advanced by
the fixture) -- this is the entire reason the wall-clock guarantee is
falsifiable without a real 45-minute wait and does NOT move with the loop's
tick cadence (D-2's ratified correction: the guarantee is anchored to
minutes-since-first-detected-exhausted, never to a tick count).

The domain ladder-evaluation logic this tick delegates to is
`des.domain.work_exhausted_ladder.evaluate_and_record(*, ledger, feature_id,
queue_state, now, gated_reasons) -> None`: it reads the AT-completion ledger
for this feature's open work-exhausted window (if any) and appends whichever
of `WorkExhaustedWindowOpened` / `WorkExhaustedFirstWarning` /
`WorkExhaustedSecondWarning` / `WorkExhaustedStopEscalate` /
`WorkExhaustedWindowResolved` the ratified 20/30/45-minute ladder newly
crosses at `now`, each record naming WHY (`queue_state` + `gated_reasons`).
A window already carrying `WorkExhaustedStopEscalate` is TERMINAL -- a
further exhausted tick against it appends NOTHING (the "no quiet un-stop"
guarantee); only a `has-unblocked-item` tick appends
`WorkExhaustedWindowResolved` and clears the terminal state so a LATER
exhausted tick can open a brand-new window.

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/feature-delta.md
           slice-02 (## Wave: DISTILL / [REF] Wave-Decision Reconciliation,
           OQ-2 resolution).
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.domain.work_exhausted_ladder import evaluate_and_record


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort


# The 4-way queue-state vocabulary the DISTILL-interim OQ-2 decision fixes.
_QUEUE_STATES = ("empty", "all-gated", "has-unblocked-item", "malformed")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des work-exhausted-tick",
        description=(
            "Evaluate one loop tick's safe-work-tier exhaustion state against "
            "the ratified 20/30/45-minute wall-clock escalation ladder."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--queue-state", required=True, choices=_QUEUE_STATES)
    parser.add_argument(
        "--now",
        required=True,
        help="ISO-8601 instant this tick observes (the controllable clock).",
    )
    parser.add_argument(
        "--gated-reasons",
        default=None,
        help="Comma-separated reasons naming WHY each gated item is blocked.",
    )
    return parser


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """Evaluate one work-exhausted tick against the ratified escalation ladder.

    ``output`` injects the terminal-output sink (in-process default per the
    Architecture of Reference) -- defaults to ``StdoutOutput()`` so a real
    invocation (``des work-exhausted-tick ...``) is byte-for-byte unchanged
    from an in-process acceptance-test call.
    """
    if output is None:
        output = StdoutOutput()
    args = _build_parser().parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
    ledger = AtCompletionLedger(args.feature_id, Path(args.project_root))
    evaluate_and_record(
        ledger=ledger,
        feature_id=args.feature_id,
        queue_state=args.queue_state,
        now=now,
        gated_reasons=args.gated_reasons,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry, not exercised by import
    import sys

    sys.exit(main())


__all__ = ["main"]
