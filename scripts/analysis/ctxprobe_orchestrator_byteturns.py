#!/usr/bin/env python3
"""BYTE-TURNS on the ORCHESTRATOR's own session -- the ledger no other probe sees.

Every other probe in this family streams `subagents/agent-*.jsonl`. That corpus
structurally CANNOT contain the hook-injected payloads: the affordance, persona
and project-context hooks fire on the orchestrator's own `SessionStart` /
`UserPromptSubmit`, and a dispatched subagent's transcript never carries them.
ADR-D71 puts the main-session reconciliation explicitly out of scope, so the
population went unmeasured -- while being the one where residency-weighted cost
is LARGEST, because the orchestrator session is the longest-lived conversation
in the system.

Charging rule is IDENTICAL to `ctxprobe_byteturns.py` (`bytes * turns_remaining`,
turn index = ordinal of the assistant `requestId` in effect), so the numbers are
directly comparable to the subagent-corpus figures. Comparing them is the point:
the same payload measures 0.18% of tool-admitted byte-turns on the subagent
corpus and 72.6% of hook-injected byte-turns here.

Usage:  ctxprobe_orchestrator_byteturns.py <main-session-transcript.jsonl>

CAVEATS, which travel with the numbers:

1. This is a MODELLED charge, not a billed `cache_read`. It answers "how many
   times was this byte re-served", not "what did the invoice say". For billed
   totals use `ctxprobe_account.py`, whose conservation law keys on real usage
   records.
2. The re-entry multiplier tends to T/2 for a payload injected uniformly across
   a T-turn session, so it is DOMINATED by session length. A large multiplier is
   evidence the session was long, not that the payload was badly designed. Read
   the byte-turn TOTAL, and the share between payloads -- never the multiplier
   alone.
3. Hook identity is inferred from marker strings in the payload text, because
   the `attachment` record does not name which hook script produced it (only the
   EVENT, `SessionStart`/`UserPromptSubmit`, which several hooks share). A
   payload matching no marker lands in `other hook (<event>)` rather than being
   dropped -- an under-attribution is visible, a silent discard is not.
"""

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path


# Ordered: first match wins, so the most specific marker must come first.
_HOOK_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("orchestrator-affordance", ("TRUNCATED PREVIEW", "standing-loops")),
    ("project context", ("vision.md", "roadmap.md", "backlog")),
    ("persona reload", ("Lyra", "persona")),
)


def _classify(text: str, event: str) -> tuple[str, bool]:
    """Name the hook payload from its content. Returns (label, was_ambiguous).

    First match wins, so MARKER ORDER IS LOAD-BEARING -- reordering two entries
    once moved ~13 percentage points between `persona reload` and `project
    context`, because several injections carry markers for both. The caller
    reports the ambiguous count rather than letting the winner absorb it
    silently: a mis-attribution you can see is a caveat, one you cannot is a
    wrong number.
    """
    hits = [
        label for label, markers in _HOOK_MARKERS if any(m in text for m in markers)
    ]
    if not hits:
        return f"other hook ({event})", False
    return hits[0], len(hits) > 1


def _turn_ordinals(path: Path) -> OrderedDict[str, int]:
    """Map each assistant `requestId` to its ordinal -- the session's turn axis."""
    order: OrderedDict[str, int] = OrderedDict()
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "assistant":
                continue
            rid = rec.get("requestId")
            if rid and rid not in order:
                order[rid] = len(order)
    return order


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])

    order = _turn_ordinals(path)
    total_turns = len(order)
    print(
        f"orchestrator session turns (distinct assistant requestIds): {total_turns:,}"
    )
    if total_turns < 2:
        print("!! INDETERMINATE: fewer than 2 turns, residency is undefined")
        return 1

    byte_turns: Counter[str] = Counter()
    raw_bytes: Counter[str] = Counter()
    injections: Counter[str] = Counter()
    first_turn: dict[str, int] = {}
    ambiguous_records = 0
    cur_turn = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            if rec.get("type") == "assistant":
                rid = rec.get("requestId")
                if rid in order:
                    cur_turn = order[rid]
                continue
            att = rec.get("attachment")
            if not isinstance(att, dict):
                continue
            if att.get("type") != "hook_additional_context":
                continue
            content = att.get("content")
            text = (
                content
                if isinstance(content, str)
                else json.dumps(content, ensure_ascii=False)
            )
            key, ambiguous = _classify(text, str(att.get("hookEvent", "?")))
            if ambiguous:
                ambiguous_records += 1
            size = len(text)
            byte_turns[key] += size * max(total_turns - cur_turn - 1, 0)
            raw_bytes[key] += size
            injections[key] += 1
            first_turn.setdefault(key, cur_turn)

    total_bt = sum(byte_turns.values())
    if not total_bt:
        print("no hook_additional_context records found")
        return 0

    print(f"hook-injected records: {sum(injections.values()):,}")
    if ambiguous_records:
        print(
            f"  !! {ambiguous_records:,} matched MORE THAN ONE marker set and were "
            "charged to the first -- their split is not reliable"
        )
    print(f"hook-injected RAW bytes: {sum(raw_bytes.values()):,}")
    print(f"hook-injected BYTE-TURNS: {total_bt:,}  (~{total_bt // 4:,} token-turns)\n")

    header = (
        f"{'hook payload':32s} {'byte-turns':>16} {'%':>7} "
        f"{'raw bytes':>11} {'n':>6} {'1st turn':>9} {'re-entry':>9}"
    )
    print(header)
    for key, value in byte_turns.most_common():
        multiplier = value / max(raw_bytes[key], 1)
        print(
            f"{key:32s} {value:>16,} {100.0 * value / total_bt:>6.1f}% "
            f"{raw_bytes[key]:>11,} {injections[key]:>6,} "
            f"{first_turn[key]:>9,} {multiplier:>8.0f}x"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
