"""des report-delivery-metrics -- the read-side closing "0 readers" (F1) and
the git-free time-to-green query (F2), declared-facts-reachable-recorded
slice-07 (DD-12).

Usage:
    des report-delivery-metrics --feature-id <id> --metric agent-usage-by-stage
    des report-delivery-metrics --feature-id <id> --metric time-to-green

Two independent queries behind one CLI (DD-12: "one query, two datums" --
splitting them would duplicate the `--feature-id`/`--repo-root` plumbing for
no benefit; each metric owns its own read path and neither touches the
other's data source):

- ``agent-usage-by-stage`` -- deduped token totals (dedup key `request_id`,
  MAX per category) for `feature_id`, grouped by `stage`. Reads the JSONL
  audit log via `JsonlAuditLogReader.aggregate_agent_usage_by_stage`.
- ``time-to-green`` -- wall-clock from the first `RedObserved` to the first
  `SliceCommitVerified` per slice, joined on `slice_id`. Reads the
  AT-completion ledger via `AtCompletionLedger.read_records`. Replaces the
  git-history join the source design named as a git-free-constraint
  violation (AD-21) -- this reads ONLY the ledger, never `git log`.

Both queries degrade LOUD, never a silent zero (GDP-6): a feature with no
matching records reports an explicit `"could-not-verify"` status, not an
empty-looking `0`. A corrupt AT-completion ledger raises
`LedgerIntegrityViolation`; this CLI catches it and renders the violation's
own `detail`/message as a structured JSON error with a non-zero exit --
mirrors the existing `attest_bundled_slice.py` catch shape -- never
swallowed into a falsely-clean report (Reuse Analysis: "the exception it
must propagate loudly", satisfied by surfacing it, not suppressing it).

Stdlib-only (argparse + json), matching every other `des.cli.*` module.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.adapters.driven.logging.jsonl_audit_log_reader import JsonlAuditLogReader
from des.domain.repo_path_resolver import resolve_repo_root


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["main", "time_to_green_report"]

_METRIC_AGENT_USAGE = "agent-usage-by-stage"
_METRIC_TIME_TO_GREEN = "time-to-green"
_METRICS = (_METRIC_AGENT_USAGE, _METRIC_TIME_TO_GREEN)

_GREEN = "GREEN"
_IN_PROGRESS = "IN_PROGRESS"
_UNATTRIBUTED = "UNATTRIBUTED"


@dataclass(frozen=True)
class SliceTimeToGreen:
    """One slice's RedObserved -> SliceCommitVerified join outcome.

    Three states, not a bare duration (GDP-8 arity): `GREEN` (both events
    present, duration computed from the FIRST RedObserved to the FIRST
    SliceCommitVerified that followed it -- "how long did it take to first
    go green"), `IN_PROGRESS` (RedObserved seen, no SliceCommitVerified yet
    -- still red), `UNATTRIBUTED` (a SliceCommitVerified with no matching
    RedObserved -- e.g. pre-slice-06 data, or `--feature-id`/`--slice-id`
    were omitted at RED time). `UNATTRIBUTED` is never silently dropped or
    folded into `GREEN`.
    """

    slice_id: str
    status: str
    red_observed_at: str | None
    green_verified_at: str | None
    duration_seconds: float | None


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def time_to_green_report(
    records: list[dict[str, Any]],
) -> tuple[SliceTimeToGreen, ...]:
    """Join `RedObserved` x `SliceCommitVerified` ledger records by `slice_id`.

    Pure function over already-read ledger records (no I/O) -- the CLI's
    `main` is the only caller that reads the ledger, so this stays testable
    without a filesystem fixture. `records` is the UNFILTERED record list
    `AtCompletionLedger.read_records()` returns; this function does its own
    event-type filtering so a caller never has to pre-filter correctly.
    """
    red_by_slice: dict[str, list[str]] = {}
    green_by_slice: dict[str, list[str]] = {}
    for record in records:
        slice_id = record.get("slice_id")
        timestamp = record.get("timestamp")
        if (
            not isinstance(slice_id, str)
            or not slice_id
            or not isinstance(timestamp, str)
        ):
            continue
        if record.get("event") == "RedObserved":
            red_by_slice.setdefault(slice_id, []).append(timestamp)
        elif record.get("event") == "SliceCommitVerified":
            green_by_slice.setdefault(slice_id, []).append(timestamp)

    results: list[SliceTimeToGreen] = []
    for slice_id in sorted(set(red_by_slice) | set(green_by_slice)):
        reds = sorted(red_by_slice.get(slice_id, []))
        greens = sorted(green_by_slice.get(slice_id, []))
        if reds and greens:
            first_red = reds[0]
            # First green AT OR AFTER the first red -- a green timestamped
            # before any red observation on this slice cannot be the green
            # that red led to.
            candidates = [g for g in greens if g >= first_red] or greens
            first_green = candidates[0]
            duration = (_parse_ts(first_green) - _parse_ts(first_red)).total_seconds()
            results.append(
                SliceTimeToGreen(
                    slice_id=slice_id,
                    status=_GREEN,
                    red_observed_at=first_red,
                    green_verified_at=first_green,
                    duration_seconds=duration,
                )
            )
        elif reds:
            results.append(
                SliceTimeToGreen(
                    slice_id=slice_id,
                    status=_IN_PROGRESS,
                    red_observed_at=sorted(reds)[0],
                    green_verified_at=None,
                    duration_seconds=None,
                )
            )
        else:
            results.append(
                SliceTimeToGreen(
                    slice_id=slice_id,
                    status=_UNATTRIBUTED,
                    red_observed_at=None,
                    green_verified_at=sorted(greens)[0],
                    duration_seconds=None,
                )
            )
    return tuple(results)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des report-delivery-metrics",
        description="Read-only delivery-cost/time-to-green report over the "
        "audit log and AT-completion ledger.",
    )
    parser.add_argument("--feature-id", required=True, help="Feature id to query.")
    parser.add_argument(
        "--metric", required=True, choices=_METRICS, help="Which metric to report."
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root (default: NWAVE_REPO_ROOT env, then cwd).",
    )
    return parser


def _render_agent_usage(repo_root: Path, feature_id: str) -> dict[str, Any]:
    reader = JsonlAuditLogReader(cwd=repo_root)
    report = reader.aggregate_agent_usage_by_stage(feature_id)
    if report.total_records_scanned == 0:
        return {
            "metric": _METRIC_AGENT_USAGE,
            "feature_id": feature_id,
            "status": "could-not-verify",
            "reason": f"no AGENT_USAGE_OBSERVED record names feature_id "
            f"{feature_id!r} in the scanned audit log",
        }
    return {
        "metric": _METRIC_AGENT_USAGE,
        "feature_id": feature_id,
        "status": "measured",
        "total_records_scanned": report.total_records_scanned,
        "stages": [
            {
                "stage": s.stage,
                "request_count": s.request_count,
                "input_tokens": s.input_tokens,
                "cache_creation_input_tokens": s.cache_creation_input_tokens,
                "cache_read_input_tokens": s.cache_read_input_tokens,
                "output_tokens": s.output_tokens,
                "unattributed_record_count": s.unattributed_record_count,
            }
            for s in report.stages
        ],
    }


def _render_time_to_green(repo_root: Path, feature_id: str) -> dict[str, Any]:
    ledger = AtCompletionLedger(feature_id, repo_root)
    try:
        records = ledger.read_records()
    except LedgerIntegrityViolation as exc:
        return {
            "metric": _METRIC_TIME_TO_GREEN,
            "feature_id": feature_id,
            "status": "error",
            "event": "LedgerIntegrityViolation",
            "detail": exc.detail,
            "error": f"AT-completion ledger is corrupt ({exc.detail}): {exc}",
        }
    if not records:
        return {
            "metric": _METRIC_TIME_TO_GREEN,
            "feature_id": feature_id,
            "status": "could-not-verify",
            "reason": f"no AT-completion ledger records found for feature_id "
            f"{feature_id!r}",
        }
    slices = time_to_green_report(records)
    return {
        "metric": _METRIC_TIME_TO_GREEN,
        "feature_id": feature_id,
        "status": "measured",
        "slices": [
            {
                "slice_id": s.slice_id,
                "status": s.status,
                "red_observed_at": s.red_observed_at,
                "green_verified_at": s.green_verified_at,
                "duration_seconds": s.duration_seconds,
            }
            for s in slices
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = resolve_repo_root(args.repo_root)

    if args.metric == _METRIC_AGENT_USAGE:
        result = _render_agent_usage(repo_root, args.feature_id)
    else:
        result = _render_time_to_green(repo_root, args.feature_id)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("status") == "error" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
