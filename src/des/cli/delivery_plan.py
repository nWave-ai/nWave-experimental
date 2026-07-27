"""`des plan` -- advisory ready-set and unused-parallelism report.

Reads a validated feature's Slice Plan and an explicit set of already-complete
slices.  It never launches work, changes a ledger, or authorizes a gate.  Its
single job is to make safe, declared parallelism visible before an operator
falls back to a serial delivery path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary
from des.cli.validate_feature_delta import (
    VERDICT_ACCEPTED,
    read_slice_plan_dependencies,
    validate_slice_plan_content,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des plan",
        description="Report ready delivery slices and declared unused parallelism.",
    )
    parser.add_argument("--feature-delta", required=True)
    parser.add_argument(
        "--completed",
        action="append",
        default=[],
        metavar="SLICE-ID",
        help="A slice already completed in the current immutable candidate.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Emit a deterministic, read-only plan projection.

    Invalid plan input is not treated as an empty ready-set: doing so would
    falsely hide available work or fabricate an order.  Unknown completed ids
    are rejected for the same reason.
    """
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    content = Path(args.feature_delta).read_text(encoding="utf-8")
    validation = validate_slice_plan_content(content)
    if validation.verdict != VERDICT_ACCEPTED:
        return _reject(validation.detail)

    graph = read_slice_plan_dependencies(content)
    if graph is None:
        # Should be unreachable: validate_slice_plan_content above already
        # rejects an absent Slice Plan heading before this line runs. Kept
        # as an explicit, self-explaining guard rather than trusting that
        # invariant silently (GDP-6, no silent-wrong) -- if the two ever
        # disagree, this fails loud instead of crashing on `for _ in None`.
        return _reject(
            "no '## Wave: DISCUSS / [REF] Slice Plan' section at all -- "
            "expected validate_slice_plan_content to have already rejected this"
        )
    known_ids = {slice_id for slice_id, _ in graph}
    completed = frozenset(args.completed)
    unknown = sorted(completed - known_ids)
    if unknown:
        return _reject(f"completed ids are absent from the Slice Plan: {unknown}")

    dangling = sorted(
        {
            prerequisite
            for _, prerequisites in graph
            for prerequisite in prerequisites
            if prerequisite not in known_ids
        }
    )
    if dangling:
        return _reject(
            "a declared 'depends-on' prerequisite names no slice in this "
            f"Slice Plan (typo or corrupted token?): {dangling}"
        )

    ready = tuple(
        slice_id
        for slice_id, prerequisites in graph
        if slice_id not in completed and set(prerequisites) <= completed
    )
    payload = {
        "event": "DeliveryPlan",
        "completed": sorted(completed),
        "ready": list(ready),
        "unused_parallelism": len(ready) > 1,
    }
    print(json.dumps(payload, separators=(",", ":")))
    verdict = Verdict.DEGRADED if payload["unused_parallelism"] else Verdict.PASS
    why = (
        "multiple declared slices are ready and can be safely dispatched in parallel"
        if payload["unused_parallelism"]
        else "no additional declared-parallel ready work exists"
    )
    print_human_summary(verdict, "delivery ready-set computed", why=why)
    return 0


def _reject(reason: str) -> int:
    print(json.dumps({"event": "DeliveryPlanRejected", "reason": reason}))
    print_human_summary(
        Verdict.FAIL,
        "delivery plan input rejected",
        why=reason,
        how="supply a well-formed feature delta and completed ids declared by its Slice Plan",
    )
    return 2
