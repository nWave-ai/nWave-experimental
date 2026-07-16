#!/usr/bin/env python3
"""Report where the test suite's wall-clock actually goes.

Reads the always-on per-test duration log the root conftest writes on EVERY run
(`.nwave/test-durations.jsonl`; see conftest section 3e) and answers the only
question that matters when a suite is too slow: *where do the minutes go?*

A `--durations=15` top-N window is a trap: it shows the tallest poles and hides
the long tail, and the tail routinely outweighs the poles (200 tests at 3 s beat
the slowest 15 and never appear). This report shows BOTH -- the poles, the
per-file/per-directory sums, and how much time lives below the top-N cut.

Usage
-----
    uv run poe test-durations                 # default: top 25 + tier sums
    uv run python scripts/test_durations_report.py --top 50
    uv run python scripts/test_durations_report.py --file <path.jsonl>

Pure stdlib. Read-only. Never fails a run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


_DEFAULT_LOG = (
    Path(__file__).resolve().parent.parent / ".nwave" / "test-durations.jsonl"
)


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(
            f"no duration log at {path}\n"
            "Run any pytest command first — the root conftest writes it on EVERY run.\n"
            "(Override the path with NWAVE_TEST_DURATIONS_FILE.)"
        )
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _per_test(records: list[dict]) -> dict[str, float]:
    """Total wall-clock per test node (setup + call + teardown)."""
    totals: dict[str, float] = defaultdict(float)
    for rec in records:
        nodeid = rec.get("nodeid")
        duration = rec.get("duration")
        if isinstance(nodeid, str) and isinstance(duration, (int, float)):
            totals[nodeid] += float(duration)
    return dict(totals)


def _group(totals: dict[str, float], depth: int) -> dict[str, float]:
    """Sum per file (depth=0) or per directory prefix (depth=N path segments)."""
    grouped: dict[str, float] = defaultdict(float)
    for nodeid, seconds in totals.items():
        path = nodeid.split("::", 1)[0]
        key = path if depth == 0 else "/".join(path.split("/")[:depth])
        grouped[key] += seconds
    return dict(grouped)


def _table(title: str, rows: list[tuple[str, float]], total: float) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for name, seconds in rows:
        share = (seconds / total * 100) if total else 0.0
        print(f"{seconds:8.1f}s  {share:5.1f}%  {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=_DEFAULT_LOG)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args(argv)

    records = _load(args.file)
    totals = _per_test(records)
    if not totals:
        print(f"duration log at {args.file} holds no usable records")
        return 1

    grand = sum(totals.values())
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

    print(
        f"tests: {len(totals)}   phases: {len(records)}   "
        f"summed wall-clock: {grand:.0f}s ({grand / 60:.1f} min serial-equivalent)"
    )

    _table(f"SLOWEST {args.top} TESTS", ranked[: args.top], grand)

    tail = sum(seconds for _, seconds in ranked[args.top :])
    tail_n = max(len(ranked) - args.top, 0)
    print(
        f"\nTHE TAIL: the other {tail_n} tests sum to {tail:.0f}s "
        f"({tail / grand * 100 if grand else 0:.1f}% of the total) — "
        f"{'the tail outweighs the poles' if tail > grand - tail else 'the poles dominate'}"
    )

    by_file = sorted(_group(totals, 0).items(), key=lambda kv: kv[1], reverse=True)
    _table("SLOWEST 15 FILES", by_file[:15], grand)

    by_tier = sorted(_group(totals, 2).items(), key=lambda kv: kv[1], reverse=True)
    _table("BY TIER (tests/<area>/<tier>)", by_tier[:15], grand)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
