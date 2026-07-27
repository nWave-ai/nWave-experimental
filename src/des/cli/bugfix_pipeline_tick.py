"""des-bugfix-pipeline-tick -- the two-lane bugfix pipeline (D-4).

DELIVER-wired (slice-03 of autonomous-consolidation-and-bugfix-loops --
charter `the-bugfix-loop-drains-the-queue-as-a-pipeline.md`, feature-delta
Slice Plan row slice-03, Locked Decision D-4). This module is the driving
port a bugfix loop's tick calls once per defect stage transition:
"cloud-lane stages (RCA, charter authoring, AT authoring) fan out
concurrently at near-zero box cost; box-lane stages (RED seal, crafter
GREEN, Vera examine, commit-slice) stay strictly serialized to exactly ONE
in-flight item -- a LOCAL invariant the pipeline itself enforces, no
cross-instance coordination required."

THE CONTROLLABLE CLOCK (deterministic, NO real sleep): `--now` is an
explicit ISO-8601 instant the CALLER supplies (production: the real
wall-clock at tick time; acceptance tests: a synthetic instant advanced by
the fixture) -- mirrors the slice-02 `des work-exhausted-tick` pattern.

THE FOUR ACTIONS a single tick performs (`--action`):
  * `stage-started`   -- a defect enters a stage. Cloud-lane stages are
                          ALWAYS admitted (no concurrency ceiling). Box-lane
                          stages are admitted ONLY if no OTHER defect
                          currently holds an open box-lane stage; otherwise
                          the entry is DEFERRED (`BoxLaneEntryDeferred`,
                          naming the current occupant) -- never silently
                          admitted, never silently dropped.
  * `stage-completed` -- a defect leaves a stage successfully. For a
                          box-lane stage this releases the box-lane slot for
                          the next entrant.
  * `stage-failed`    -- a defect's stage fails (charter: "its RCA turns up
                          nothing actionable, or its crafter GREEN pass
                          fails"). Recorded loudly (`PipelineStageFailed`,
                          non-empty `reason`), never silently marked done.
                          For a box-lane stage this ALSO releases the slot
                          (a failure must not leave the box lane stuck).
  * `claim-drained`   -- a direct claim that a defect is "done"/"drained".
                          Refused (`DrainClaimRejectedNoAttestation`, D-8)
                          unless the ledger already carries a
                          `PipelineStageCompleted` record for the terminal
                          `commit-slice` stage -- the `SliceCommitVerified`-
                          class record this charter's Negative-1 names.

The domain pipeline-evaluation logic this tick delegates to is
`des.domain.bugfix_pipeline.evaluate_and_record(*, ledger, feature_id,
defect_id, action, stage, now, reason) -> None`.

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/feature-delta.md
           slice-03 (## Wave: DISTILL / [REF] Scaffolds).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.domain.bugfix_pipeline import evaluate_and_record
from des.domain.iso_utc import parse_iso_utc


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort

# The 7-stage vocabulary the DISTILL-authored D-4 resolution fixes.
_STAGES = (
    "rca",
    "charter-authoring",
    "at-authoring",
    "red-seal",
    "crafter-green",
    "vera-examine",
    "commit-slice",
)
_ACTIONS = ("stage-started", "stage-completed", "stage-failed", "claim-drained")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des bugfix-pipeline-tick",
        description=(
            "Evaluate one bugfix-pipeline stage transition against the "
            "cloud-lane-fans-out / box-lane-serialized-to-one invariant (D-4)."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--defect-id", required=True)
    parser.add_argument("--action", required=True, choices=_ACTIONS)
    parser.add_argument(
        "--stage",
        default=None,
        choices=_STAGES,
        help="Required for every --action except claim-drained.",
    )
    parser.add_argument(
        "--now",
        required=True,
        help="ISO-8601 instant this tick observes (the controllable clock).",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="Non-empty for stage-failed (charter: fail loud, never silent).",
    )
    return parser


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """Evaluate one bugfix-pipeline tick against the D-4 two-lane invariant.

    ``output`` injects the terminal-output sink (in-process default per the
    Architecture of Reference) -- defaults to ``StdoutOutput()`` so a real
    invocation (``des bugfix-pipeline-tick ...``) is byte-for-byte unchanged
    from an in-process acceptance-test call.
    """
    if output is None:
        output = StdoutOutput()
    args = _build_parser().parse_args(argv)

    if args.action != "claim-drained" and args.stage is None:
        output.emit_line(
            "--stage is required unless --action=claim-drained (exit 2, "
            "no ledger write attempted)."
        )
        return 2

    now = parse_iso_utc(args.now)
    ledger = AtCompletionLedger(args.feature_id, Path(args.project_root))
    evaluate_and_record(
        ledger=ledger,
        feature_id=args.feature_id,
        defect_id=args.defect_id,
        action=args.action,
        stage=args.stage,
        now=now,
        reason=args.reason,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry, not exercised by import
    import sys

    sys.exit(main())


__all__ = ["main"]
