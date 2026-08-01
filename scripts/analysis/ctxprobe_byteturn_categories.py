#!/usr/bin/env python3
"""BYTE-TURNS bucketed by CATEGORY, so competing cut proposals share a denominator.

`ctxprobe_byteturns.py` ranks individual files. That answers "which single file
costs most" but not "does this whole class of content deserve a cutting node",
which is the question a mikado tree actually argues about. Two nodes quoting
percentages of two different denominators cannot be compared, and the tree has
done exactly that: skill cores measured against tool-result byte-turns, the
affordance measured against cache_read, the dispatch envelope against total
re-read tokens.

This bucket categories against ONE denominator, computed in the same pass with
the same charging rule as `ctxprobe_byteturns.py` (`bytes * turns_remaining`).

Usage:  ctxprobe_byteturn_categories.py <subagents-dir>

CAVEATS:

1. Only tool-ADMITTED bytes are attributable. Results with no `file_path`/`path`/
   `skill` input (Bash above all) are reported as an explicit `untargeted` share
   rather than silently omitted -- roughly a quarter of the total, and a reader
   who does not see it will over-read every percentage below.
2. The buckets are PATH heuristics tuned to this repo's layout. `SKILL.md` is
   matched on basename so that reference files living beside a core do not
   inflate the core's share -- the two are reported separately precisely because
   conflating them once inflated the skill-core figure.
3. A byte can belong to two arguments at once (a skill core is also part of the
   turn-0 prefix). These buckets partition by PATH, not by mechanism; they do not
   decompose `fixed_reread_tokens`, and nothing here should be subtracted from it.
"""

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path


def _bucket(target: str) -> str:
    """Name the argument a path belongs to. Path heuristics, see caveat 2."""
    t = target.replace("\\", "/")
    if "/orchestrator-affordance/" in t:
        return "orchestrator-affordance"
    if t.endswith("/SKILL.md"):
        return "skill CORE files"
    if "/skills/" in t:
        return "other files under /skills/"
    if t.endswith("feature-delta.md"):
        return "feature-delta"
    if "/src/" in t or "/scripts/" in t:
        return "production source"
    if t.endswith((".md", ".txt", ".csv")):
        return "other docs/text"
    return "other"


def _turn_ordinals(path: Path) -> OrderedDict[str, int]:
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
    root = Path(sys.argv[1])

    byte_turns: Counter[str] = Counter()
    raw_bytes: Counter[str] = Counter()
    reads: Counter[str] = Counter()
    total_bt = 0
    untargeted_bt = 0
    measured = 0
    skipped = 0

    for path in sorted(root.glob("*.jsonl")):
        try:
            order = _turn_ordinals(path)
        except OSError as exc:
            print(f"!! INDETERMINATE {path.name}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        total_turns = len(order)
        if total_turns < 2:
            continue
        measured += 1

        tool_targets: dict[str, str] = {}
        cur_turn = 0
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                if rec.get("type") == "assistant":
                    rid = rec.get("requestId")
                    if rid in order:
                        cur_turn = order[rid]
                    for blk in msg.get("content") or []:
                        if not isinstance(blk, dict) or blk.get("type") != "tool_use":
                            continue
                        inp = blk.get("input") or {}
                        target = (
                            inp.get("file_path") or inp.get("path") or inp.get("skill")
                        )
                        if target:
                            tool_targets[blk.get("id")] = str(target)
                elif rec.get("type") == "user":
                    for blk in msg.get("content") or []:
                        if (
                            not isinstance(blk, dict)
                            or blk.get("type") != "tool_result"
                        ):
                            continue
                        content = blk.get("content")
                        size = (
                            len(content)
                            if isinstance(content, str)
                            else len(json.dumps(content, ensure_ascii=False))
                            if content is not None
                            else 0
                        )
                        charge = size * max(total_turns - cur_turn - 1, 0)
                        total_bt += charge
                        target = tool_targets.get(blk.get("tool_use_id"))
                        if not target:
                            untargeted_bt += charge
                            continue
                        bucket = _bucket(target)
                        byte_turns[bucket] += charge
                        raw_bytes[bucket] += size
                        reads[bucket] += 1

    if not total_bt:
        print("no tool-admitted byte-turns found")
        return 1

    print(f"transcripts measured: {measured:,}   skipped/indeterminate: {skipped}")
    print(f"TOTAL byte-turns (tool-admitted): {total_bt:,}")
    print(
        f"  of which UNTARGETED (Bash etc, no file path): {untargeted_bt:,} "
        f"({100.0 * untargeted_bt / total_bt:.1f}%)\n"
    )
    print(
        f"{'bucket':32s} {'byte-turns':>18} {'% total':>9} {'raw bytes':>14} {'reads':>8}"
    )
    for bucket, value in byte_turns.most_common():
        print(
            f"{bucket:32s} {value:>18,} {100.0 * value / total_bt:>8.2f}% "
            f"{raw_bytes[bucket]:>14,} {reads[bucket]:>8,}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
