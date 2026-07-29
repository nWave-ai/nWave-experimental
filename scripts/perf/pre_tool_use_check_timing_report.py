"""Attribute the ``pre_tool_use`` hook's p99 tail to one of its 3 checks.

D48 (mikado ``docs/mikado/2026-07-28-des-mikado-tree.md``): 8 days of telemetry
showed the ``pre_tool_use`` hook at p50 90ms / p99 1.082ms / worst single
invocation 329569ms (5.5min), summing to 87% of all hook wall-clock across
11132 invocations -- but the number could not say WHICH internal check paid
for the tail. That gap is what this reads.

``PreToolUseService.validate()`` (commit ``233e2a7ea``) now emits a
``check_durations_ms`` field on the ``HOOK_PRE_TOOL_USE_ALLOWED`` /
``HOOK_PRE_TOOL_USE_BLOCKED`` audit events -- 3 wall-clock buckets
(``wave_enforcement``, the one bucket that does real filesystem I/O;
``completeness``; ``atdd_pure_validation``) for whichever checks ran on that
invocation. This script is the NAMED CONSUMER of that field: it joins those
events to the paired ``HOOK_COMPLETED`` event on the SAME ``hook_id`` (the
join key the hook adapter already stamps on every event of one invocation),
and reports each bucket's share of TOTAL hook duration, split between the
bulk of invocations and the slow tail -- the read that turns "which of the
three checks produces the queue" from a question into a table.

## Why this has nothing to report yet, and that is not a defect here

The hook that actually fires today runs the INSTALLED nWave copy, not this
worktree's ``src/des`` -- the per-check field only appears in NEW audit
records once this commit (a) merges to trunk and (b) the installed runtime is
reinstalled from it (see ``feedback_hook_spine_runs_installed_runtime_...``).
Until then this script's own output says exactly that: zero qualifying
records is reported as ``no_records: true``, never as an empty table dressed
up as "the tail is thin" -- see the D48 -> D02 caveat already logged in the
decisions table: the tail could be fixture-contaminated without the
``run_context`` field this same writer already stamps (D02, merged) to
discriminate real dispatches from test/fixture ones. Re-run this AFTER both
land and enough real dispatch volume accumulates.

Usage::

    uv run python scripts/perf/pre_tool_use_check_timing_report.py \\
        [--log-dir .nwave/des/logs] [--tail-fraction 0.01]
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_LOG_DIR = Path(".nwave/des/logs")
BUCKET_NAMES = ("wave_enforcement", "completeness", "atdd_pure_validation")


@dataclass
class _Invocation:
    hook_id: str
    total_duration_ms: float | None = None
    check_durations_ms: dict[str, float] = field(default_factory=dict)


def _iter_audit_events(log_dir: Path) -> list[dict[str, object]]:
    """Read every JSON line across ``audit-*.log`` in ``log_dir``.

    A malformed line is skipped, not fatal -- the log is append-only and
    written by multiple concurrent hook processes (GDP-6: this reads past a
    torn line rather than refusing the whole file over one bad row).
    """
    events: list[dict[str, object]] = []
    for path in sorted(log_dir.glob("audit-*.log")):
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _join_by_hook_id(events: list[dict[str, object]]) -> dict[str, _Invocation]:
    """Correlate HOOK_COMPLETED.duration_ms with check_durations_ms by hook_id.

    Only invocations carrying BOTH sides are useful for attribution -- an
    invocation with a total but no check_durations_ms predates this
    instrumentation (or ran the installed pre-D48 runtime); it is counted in
    the summary as "unattributed", never silently folded into the buckets.
    """
    by_id: dict[str, _Invocation] = {}
    for event in events:
        hook_id = event.get("hook_id")
        if not isinstance(hook_id, str) or not hook_id:
            continue
        inv = by_id.setdefault(hook_id, _Invocation(hook_id=hook_id))
        if (
            event.get("event") == "HOOK_COMPLETED"
            and event.get("handler") == "pre_tool_use"
        ):
            duration = event.get("duration_ms")
            if isinstance(duration, (int, float)):
                inv.total_duration_ms = float(duration)
        elif event.get("event") in (
            "HOOK_PRE_TOOL_USE_ALLOWED",
            "HOOK_PRE_TOOL_USE_BLOCKED",
        ):
            durations = event.get("check_durations_ms")
            if isinstance(durations, dict):
                inv.check_durations_ms = {
                    k: float(v) for k, v in durations.items() if k in BUCKET_NAMES
                }
    return by_id


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(int(len(ordered) * p), len(ordered) - 1)
    return ordered[idx]


def build_report(log_dir: Path, tail_fraction: float) -> dict[str, object]:
    """Build the attribution report: which check dominates the tail vs the bulk."""
    events = _iter_audit_events(log_dir)
    invocations = list(_join_by_hook_id(events).values())

    total_pre_tool_use = sum(
        1 for inv in invocations if inv.total_duration_ms is not None
    )
    attributed = [
        inv
        for inv in invocations
        if inv.total_duration_ms is not None and inv.check_durations_ms
    ]

    if not attributed:
        return {
            "no_records": True,
            "total_pre_tool_use_invocations_seen": total_pre_tool_use,
            "attributed_invocations": 0,
            "why": (
                "no invocation carries both HOOK_COMPLETED.duration_ms and a "
                "check_durations_ms field -- the installed hook runtime has not "
                "been reinstalled from a commit at/after 233e2a7ea, or no "
                "atdd_pure-allow dispatch has fired since it was"
            ),
        }

    attributed.sort(key=lambda inv: inv.total_duration_ms or 0.0)
    tail_count = max(1, int(len(attributed) * tail_fraction))
    tail = attributed[-tail_count:]
    bulk = attributed[:-tail_count] or attributed

    def _bucket_stats(pool: list[_Invocation]) -> dict[str, object]:
        totals = [inv.total_duration_ms or 0.0 for inv in pool]
        buckets: dict[str, object] = {}
        for name in BUCKET_NAMES:
            values = [
                inv.check_durations_ms[name]
                for inv in pool
                if name in inv.check_durations_ms
            ]
            if not values:
                buckets[name] = {"n": 0}
                continue
            share_of_total = [
                v / t for v, t in zip(values, totals, strict=False) if t > 0
            ]
            buckets[name] = {
                "n": len(values),
                "p50_ms": statistics.median(values),
                "p99_ms": _percentile(values, 0.99),
                "max_ms": max(values),
                "mean_share_of_total": (
                    statistics.mean(share_of_total) if share_of_total else float("nan")
                ),
            }
        return {
            "n": len(pool),
            "total_duration_ms_p50": _percentile(totals, 0.50),
            "total_duration_ms_p99": _percentile(totals, 0.99),
            "buckets": buckets,
        }

    return {
        "no_records": False,
        "total_pre_tool_use_invocations_seen": total_pre_tool_use,
        "attributed_invocations": len(attributed),
        "tail_fraction": tail_fraction,
        "bulk": _bucket_stats(bulk),
        "tail": _bucket_stats(tail),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--tail-fraction", type=float, default=0.01)
    args = parser.parse_args()

    report = build_report(args.log_dir, args.tail_fraction)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
