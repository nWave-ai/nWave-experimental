"""des-consolidation-signal-tick -- trunk-health signal intake into the
shared bugfix pipeline (D-4/D-19).

DISTILL-authored RED scaffold (slice-04 of
autonomous-consolidation-and-bugfix-loops -- charter
`trunk-health-signals-become-queue-items-that-never-vanish.md`, feature-delta
Slice Plan row slice-04). This module is the driving port a consolidation
loop's tick calls once per DETECTED trunk-health signal: "drift, un-merged
work, stale branches, and failing gates each become exactly one queue item,
drained through the shared cloud/box pipeline -- no bespoke per-signal-type
runner."

REUSE, DON'T REBUILD (D-4/D-19): this slice adds exactly ONE net-new thing --
the signal-to-queue-item INTAKE contract (derive a stable ``defect_id`` from
``(signal_type, signal_key)``, refuse an unsupported signal type loudly,
recognize an already-queued signal instead of duplicating it). Once a signal
is accepted, its item enters the pipeline via a DIRECT call into the SAME
``des.domain.bugfix_pipeline.evaluate_and_record`` seam slice-03 already
ships (GREEN today) -- never a second pipeline, never a second ledger-event
vocabulary.

THE CONTROLLABLE CLOCK (deterministic, NO real sleep): ``--now`` is an
explicit ISO-8601 instant the CALLER supplies (production: the real
wall-clock at tick time; acceptance tests: a synthetic instant advanced by
the fixture) -- mirrors the slice-02/slice-03 pattern.

DISTILL-INTERIM SCOPE DECISION (row 7b advisory -- DESIGN was skipped for
this feature): the caller supplies an ALREADY-DETECTED ``(signal_type,
signal_key)`` pair. Scanning the real git/CI state to DECIDE whether a
branch is stale, a gate is failing, drift exists, or work sits unmerged is
OUT OF SCOPE for this driving port -- the same carve-out the feature-delta's
Out-of-Scope table already grants defect-classification/triage for slice-03.
``--signal-type`` is intentionally NOT constrained by ``argparse choices``
(unlike ``des bugfix-pipeline-tick --stage``): an unsupported value must
reach the domain seam so it can be refused LOUDLY with a named reason
(D-8), never rejected silently at the argument-parsing layer where no
ledger record could be written.

DELIVER-pinned assumption (update in this scaffold's own docstring if
DELIVER picks a different seam shape): the not-yet-built domain seam this
scaffold LAZILY imports is

    des.domain.consolidation_queue_intake.intake_signal(*, ledger,
        feature_id, signal_type, signal_key, now) -> None

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/
           feature-delta.md, slice-04 (## Wave: DISTILL / [REF] Scaffolds).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.iso_utc import parse_iso_utc


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des consolidation-signal-tick",
        description=(
            "Turn one already-detected trunk-health signal into exactly "
            "one queue item flowing through the shared bugfix pipeline "
            "(D-4/D-19)."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    add_repo_root_argument(parser, "--project-root", required=True)
    parser.add_argument(
        "--signal-type",
        required=True,
        help=(
            "One of drift / unmerged-work / stale-branch / failing-gate -- "
            "NOT constrained by argparse choices so an unsupported value "
            "reaches the domain seam and is refused loudly (D-8), rather "
            "than a silent argparse error."
        ),
    )
    parser.add_argument("--signal-key", required=True)
    parser.add_argument(
        "--now",
        required=True,
        help="ISO-8601 instant this tick observes (the controllable clock).",
    )
    return parser


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """Evaluate one consolidation-signal-intake tick.

    ``output`` injects the terminal-output sink (in-process default per the
    Architecture of Reference) -- defaults to ``StdoutOutput()`` so a real
    invocation (``des consolidation-signal-tick ...``) is byte-for-byte
    unchanged from an in-process acceptance-test call.
    """
    if output is None:
        output = StdoutOutput()
    args = _build_parser().parse_args(argv)

    now = parse_iso_utc(args.now)
    ledger = AtCompletionLedger(args.feature_id, Path(args.project_root))

    try:
        from des.domain.consolidation_queue_intake import (
            IntakeDecision,
            intake_signal,
        )
    except ModuleNotFoundError:
        output.emit_line(
            "CONSOLIDATION_INTAKE_NOT_WIRED: "
            "des.domain.consolidation_queue_intake does not exist yet "
            "(DELIVER's job) -- no ledger write attempted."
        )
        return 2

    result = intake_signal(
        ledger=ledger,
        feature_id=args.feature_id,
        signal_type=args.signal_type,
        signal_key=args.signal_key,
        now=now,
    )

    if result.decision is IntakeDecision.REJECTED:
        # EXAMINE fix (Vera FAIL): the ledger's own `ConsolidationSignal
        # IntakeRejected` record already carried this reason -- the CLI
        # surface must say it too (WHAT/WHY/HOW), never exit 0 silent.
        output.emit_line(f"CONSOLIDATION_SIGNAL_INTAKE_REJECTED: {result.reason}")
        return 1

    # Bugfix (defects.md: "consolidation-signal-tick succeeds in total
    # silence while its refusal branch speaks"): a caller watching only this
    # CLI's own output -- never opening the ledger -- had no way to tell
    # ACCEPTED from ALREADY_QUEUED, or to learn the derived defect_id,
    # unless the intake was REJECTED. Symmetric with the REJECTED line above.
    output.emit_line(
        f"CONSOLIDATION_SIGNAL_INTAKE_{result.decision.name}: "
        f"signal_type={args.signal_type} signal_key={args.signal_key} "
        f"-> defect_id={result.defect_id}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry, not exercised by import
    import sys

    sys.exit(main())


__all__ = ["main"]
