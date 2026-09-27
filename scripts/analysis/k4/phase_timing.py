"""Where a delivery's wall-clock went, read from its own transcript.

The August 2026 decomposition opened one campaign's wall-clock by hand and found
that 657.8 s -- 22.8% of the treatment arm's 2887.4 s -- was time when NO
delegated turn was open: the root session reading what had just come back and
composing the next dispatch. Fourteen separate intervals, 10.5 s to 181.0 s, not
one block.

That number describes ONE run of an arm that has since been rewritten. Inheriting
it would be exactly the mistake this project keeps catching: a property measured
on another unit is not a property of this one. So the decomposition is mechanised
here, to be re-measured per run rather than quoted.

## What it measures, and what it cannot

The span is the transcript's own first and last timestamps -- never the payload's
`duration_ms`, which under-reported by 4.1% on the treatment arm and by 19.2% on
the control in that same campaign, because a background subagent's tail is not
closed in the root payload.

Delegated time is the UNION of the intervals in which at least one delegated turn
was open, so two turns running at once count once. Root-only time is the
complement. A run with no delegation is all root-only, which is a fact about it,
not a failure of this module.

This attributes TIME, never blame: root-only time includes work that must happen
there. What it gives is the split, per run, so a change can be measured against
it instead of argued about.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Interval:
    """One delegated turn's open span, in seconds from the run's own start."""

    start: float
    end: float


@dataclass(frozen=True)
class Decomposition:
    """One arm's wall-clock, split by whether a delegated turn was open."""

    arm: str
    span_seconds: float
    delegated_seconds: float
    gaps: tuple[float, ...]

    @property
    def root_only_seconds(self) -> float:
        return max(0.0, self.span_seconds - self.delegated_seconds)

    @property
    def root_only_share(self) -> float:
        if self.span_seconds <= 0:
            return 0.0
        return self.root_only_seconds / self.span_seconds

    def report(self) -> str:
        if not self.span_seconds:
            return f"{self.arm}: no timestamped transcript"
        gap_range = (
            f", {len(self.gaps)} gaps {min(self.gaps):.1f}-{max(self.gaps):.1f}s"
            if self.gaps
            else ""
        )
        return (
            f"{self.arm}: span {self.span_seconds:.1f}s, "
            f"delegated {self.delegated_seconds:.1f}s, "
            f"root-only {self.root_only_seconds:.1f}s "
            f"({self.root_only_share:.1%}){gap_range}"
        )


def _seconds(stamp: str) -> float | None:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def _stamps(transcript: Path) -> list[float]:
    found: list[float] = []
    with transcript.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            moment = _seconds(record.get("timestamp", ""))
            if moment is not None:
                found.append(moment)
    return sorted(found)


def merge(intervals: list[Interval]) -> list[Interval]:
    """The union of overlapping spans, so concurrent turns count once."""
    merged: list[Interval] = []
    for span in sorted(intervals, key=lambda i: i.start):
        if merged and span.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, span.end))
        else:
            merged.append(span)
    return merged


def decompose(arm_workspace: Path, arm: str) -> Decomposition:
    """Split one arm's wall-clock into delegated and root-only time."""
    roots = [
        path
        for path in sorted(arm_workspace.rglob("*.jsonl"))
        if "subagents" not in path.parts
    ]
    root_stamps = [stamp for path in roots for stamp in _stamps(path)]
    if not root_stamps:
        return Decomposition(arm, 0.0, 0.0, ())
    start, end = min(root_stamps), max(root_stamps)

    delegated: list[Interval] = []
    for path in sorted(arm_workspace.rglob("*.jsonl")):
        if "subagents" not in path.parts:
            continue
        stamps = _stamps(path)
        if stamps:
            delegated.append(Interval(min(stamps) - start, max(stamps) - start))

    merged = merge(delegated)
    delegated_seconds = sum(span.end - span.start for span in merged)

    gaps: list[float] = []
    cursor = 0.0
    for span in merged:
        if span.start > cursor:
            gaps.append(span.start - cursor)
        cursor = max(cursor, span.end)
    if (end - start) > cursor:
        gaps.append((end - start) - cursor)

    return Decomposition(arm, end - start, delegated_seconds, tuple(gaps))


def decompose_campaign(campaign: Path, arm: str = "nwave") -> list[Decomposition]:
    results: list[Decomposition] = []
    for pair in sorted(campaign.glob("pair-*")):
        workspace = pair / arm
        if workspace.is_dir():
            results.append(decompose(workspace, f"{pair.name}/{arm}"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--arm", default="nwave")
    args = parser.parse_args(argv)

    results = decompose_campaign(args.campaign, args.arm)
    if not results:
        print(
            f"WHAT: no `{args.arm}` workspace under any pair of {args.campaign}\n"
            "WHY:  the decomposition reads the arm's own transcripts\n"
            "HOW:  point --campaign at an archived campaign holding pair-*/<arm>/"
        )
        return 2
    for result in results:
        print(result.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
