#!/usr/bin/env python3
"""K3.5 lane B — how much context each dispatch processes, per unit of output.

DIAGNOSIS, NOT A TARGET. This tool may not be used to claim quality or
acceleration, and the reason is recorded rather than assumed: its denominator is
`output_tokens` from the transcript channel, which a documented Claude Code
defect (anthropics/claude-code#27361) UNDERCOUNTS, and raw token totals are not
comparable across harnesses because cache reads bill at 0.1x base input while
writes bill at 1.25-2x. A ratio built on it points at where to look. It cannot
say anything went faster, and a low ratio can equally reward a dispatch that
produced little of value.

## The four terms the lane asks for, and which two are honest here

| Term | Measurable from a transcript? |
|---|---|
| **admitted** | YES — what the model actually processed: `input + cache_creation + cache_read` per request. |
| **re-read** | YES — `cache_read_input_tokens`: context re-processed rather than newly written. |
| **offered** | **NO.** A transcript records what was processed, never what the parent made available and the model did not take. Reporting a number here would be an invention. |
| **inherited** | **NO.** Nothing in the record separates context that came from the parent's accumulated state from context specific to the task. Distinguishing them needs the dispatch site, not the transcript. |

Two of four are therefore reported and two are declared absent. The lane's own
contract asks for the transcript's limits, and these are the two that matter:
a reduction proposal aimed at "offered" or "inherited" cannot be evidenced from
this channel and needs an instrumented dispatch boundary.

## What the numbers are for

`reread_per_output` ranks dispatches by how much context they re-process for each
token they produce. `growth` is the sharper signal: re-read per request in the
last third of a dispatch against the first third. A dispatch whose growth is far
above 1 is accumulating — each turn re-reads what the previous turns added — and
that is the shape a bounded-context intervention would change.

Stdlib only. Reads transcripts for counts and identifiers, never content.

    dispatch_context_profile.py --root ~/.claude/projects/<project> --limit 60
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from dataclasses import dataclass
from pathlib import Path


_CATS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


@dataclass(frozen=True)
class Dispatch:
    """One subagent transcript, deduplicated by request id."""

    name: str
    requests: int
    admitted: int
    reread: int
    output: int
    first_turn_admitted: int
    growth: float | None
    """Re-read per request, last third over first third. `None` when the dispatch
    is too short for the halves to mean anything — stated, never defaulted to 1."""

    @property
    def reread_per_output(self) -> float | None:
        return self.reread / self.output if self.output else None


def profile(path: Path) -> Dispatch | None:
    """One transcript to one dispatch, or None when it holds no usage at all."""
    per_request: dict[str, dict[str, int]] = {}
    order: list[str] = []
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return None
    with handle:
        for line in handle:
            if '"usage"' not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = entry.get("message") or {}
            usage = message.get("usage") if isinstance(message, dict) else None
            if not isinstance(usage, dict):
                continue
            request_id = entry.get("requestId") or message.get("id")
            if not isinstance(request_id, str) or not request_id:
                continue
            # MAX per category within a request id: the reduction K3 confirmed on
            # 13,388 groups, where only output varies across streaming snapshots.
            group = per_request.setdefault(request_id, dict.fromkeys(_CATS, 0))
            if len(order) < len(per_request):
                order.append(request_id)
            for category in _CATS:
                group[category] = max(group[category], usage.get(category, 0) or 0)

    if not per_request:
        return None

    rereads = [per_request[r]["cache_read_input_tokens"] for r in order]
    third = len(order) // 3
    growth: float | None = None
    if third >= 2:
        head, tail = st.mean(rereads[:third]), st.mean(rereads[-third:])
        growth = tail / head if head else None

    first = per_request[order[0]]
    stem = path.stem.removeprefix("agent-")
    return Dispatch(
        name=stem[1:].rsplit("-", 1)[0] if len(stem) > 1 else stem,
        requests=len(per_request),
        admitted=sum(g[c] for g in per_request.values() for c in _CATS[:3]),
        reread=sum(rereads),
        output=sum(g["output_tokens"] for g in per_request.values()),
        first_turn_admitted=first["input_tokens"]
        + first["cache_creation_input_tokens"],
        growth=growth,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="a project dir under ~/.claude*/projects/",
    )
    parser.add_argument(
        "--limit", type=int, default=60, help="most recent subagent transcripts"
    )
    args = parser.parse_args(argv)

    files = sorted(
        args.root.rglob("subagents/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    files = files[: args.limit]
    dispatches = [d for d in (profile(p) for p in files) if d is not None]

    print(f"subagent transcripts read : {len(files)}")
    print(f"  carrying usage          : {len(dispatches)}")
    print(f"  empty / unreadable      : {len(files) - len(dispatches)}\n")
    if not dispatches:
        print("nothing to profile.")
        return 1

    print("NOT MEASURABLE from this channel, and therefore not reported:")
    print("  offered   — what the parent made available but the model did not take")
    print("  inherited — which part came from the parent's state rather than the task")
    print("  Both need an instrumented dispatch boundary, not a transcript.\n")

    header = f"{'dispatch':38s}{'reqs':>5s}{'admitted':>12s}{'re-read':>12s}{'output':>8s}{'rr/out':>8s}{'growth':>8s}"
    print(header + "\n" + "-" * len(header))
    ranked = sorted(dispatches, key=lambda d: -(d.reread_per_output or 0))
    for d in ranked[:18]:
        rr = f"{d.reread_per_output:.0f}" if d.reread_per_output else "n/a"
        gr = f"{d.growth:.1f}x" if d.growth else "n/a"
        print(
            f"{d.name[:38]:38s}{d.requests:5d}{d.admitted:12,}{d.reread:12,}{d.output:8,}{rr:>8s}{gr:>8s}"
        )

    total_reread = sum(d.reread for d in dispatches)
    total_output = sum(d.output for d in dispatches)
    total_admitted = sum(d.admitted for d in dispatches)
    growths = [d.growth for d in dispatches if d.growth]
    print(
        f"\n  totals: admitted {total_admitted:,} · re-read {total_reread:,} · output {total_output:,}"
    )
    print(
        f"  re-read share of admitted context : {100 * total_reread / max(total_admitted, 1):.1f}%"
    )
    print(
        f"  re-read per output token          : {total_reread / max(total_output, 1):.0f}x"
    )
    if growths:
        print(
            f"  median growth (last third / first): {st.median(growths):.1f}x over {len(growths)} dispatches"
        )
    print(
        "\nDIAGNOSIS ONLY. This says where context is re-processed. It does not"
        "\nsay anything is faster, cheaper or better: the output denominator is"
        "\nundercounted by a documented defect, and raw tokens are not comparable"
        "\nacross harnesses with different cache mixes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
