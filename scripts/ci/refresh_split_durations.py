#!/usr/bin/env python3
"""Refresh pytest-split input from CI artifacts, never by running the suite.

Pass --baseline for an older green run and --records for newer run shards.
xdist writes controller and worker copies: retain the maximum per node/phase,
then sum setup, call and teardown. --allure accepts result directories for an
incomplete newer run, matched against --nodeids (a JSON array from collection).
Allure start/stop measures the call only; phase records take precedence over it.
Unknown tests are omitted, allowing pytest-split's mean-duration fallback.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def phase_totals(path: Path) -> dict[str, float]:
    phases: dict[tuple[str, str], float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        key = (record["nodeid"], record["when"])
        phases[key] = max(phases.get(key, 0.0), record["duration"])
    totals: dict[str, float] = defaultdict(float)
    for (nodeid, _phase), duration in phases.items():
        totals[nodeid] += duration
    return dict(totals)


def allure_totals(directories: list[Path], nodeids: list[str]) -> dict[str, float]:
    candidates: dict[tuple[str, str], list[str]] = defaultdict(list)
    for nodeid in nodeids:
        parts = nodeid.split("::")
        package = parts[0].removesuffix(".py").replace("/", ".")
        candidates[(package, parts[-1])].append(nodeid)
    totals: dict[str, float] = {}
    for directory in directories:
        for path in sorted(directory.glob("*-result.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            labels = {label["name"]: label["value"] for label in result["labels"]}
            matches = candidates.get((labels.get("package", ""), result["name"]), [])
            if len(matches) != 1:
                continue  # never guess an ambiguous or renamed test identity
            nodeid = matches[0]
            seconds = (result["stop"] - result["start"]) / 1000
            totals[nodeid] = max(totals.get(nodeid, 0.0), seconds)
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, action="append", required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--allure", type=Path, action="append", default=[])
    parser.add_argument("--nodeids", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".test_durations"))
    args = parser.parse_args(argv)
    if args.allure and args.nodeids is None:
        parser.error("--allure requires --nodeids to match exact collected identities")
    totals: dict[str, float] = phase_totals(args.baseline) if args.baseline else {}
    if args.allure:
        totals.update(allure_totals(args.allure, json.loads(args.nodeids.read_text())))
    for path in args.records:
        totals.update(phase_totals(path))
    if args.nodeids:
        population = set(json.loads(args.nodeids.read_text()))
        totals = {
            nodeid: seconds
            for nodeid, seconds in totals.items()
            if nodeid in population
        }
    if not totals:
        parser.error("artifacts contain no matching measured tests")
    args.output.write_text(
        json.dumps(totals, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(totals)} measured test durations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
