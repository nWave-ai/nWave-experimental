#!/usr/bin/env python3
"""Attribute ACCRUED context bytes to a named SOURCE.

For every tool_result that entered an agent's context, charge its bytes to
the tool that produced it and, where the tool names a file, to that FILE.
This measures how much of the growing prefix is attributable-by-name today.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path


root = sys.argv[1]
by_tool = Counter()
by_tool_n = Counter()
by_file = Counter()
attributable = opaque = 0
prompt_bytes = 0
attach_bytes = Counter()

files = [
    f for f in sorted([p.name for p in Path(root).iterdir()]) if f.endswith(".jsonl")
]
for f in files:
    tool_by_id = {}
    target_by_id = {}
    try:
        fh = open(os.path.join(root, f), encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            t = rec.get("type")
            if t == "attachment":
                a = rec.get("attachment") or {}
                attach_bytes[a.get("type", "?")] += len(
                    json.dumps(a, ensure_ascii=False)
                )
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            c = msg.get("content")
            if t == "assistant" and isinstance(c, list):
                for blk in c:
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        tool_by_id[blk.get("id")] = blk.get("name")
                        inp = blk.get("input") or {}
                        tgt = (
                            inp.get("file_path")
                            or inp.get("path")
                            or inp.get("skill")
                            or inp.get("notebook_path")
                        )
                        if tgt:
                            target_by_id[blk.get("id")] = str(tgt)
            elif t == "user":
                if isinstance(c, str):
                    prompt_bytes += len(c)
                elif isinstance(c, list):
                    for blk in c:
                        if not isinstance(blk, dict):
                            continue
                        if blk.get("type") != "tool_result":
                            if blk.get("type") == "text":
                                prompt_bytes += len(blk.get("text", ""))
                            continue
                        tid = blk.get("tool_use_id")
                        name = tool_by_id.get(tid, "<unknown>")
                        cc = blk.get("content")
                        sz = (
                            len(cc)
                            if isinstance(cc, str)
                            else len(json.dumps(cc, ensure_ascii=False))
                            if cc is not None
                            else 0
                        )
                        by_tool[name] += sz
                        by_tool_n[name] += 1
                        tgt = target_by_id.get(tid)
                        if tgt:
                            by_file[tgt] += sz
                            attributable += sz
                        else:
                            opaque += sz

tot = attributable + opaque
print(f"agents scanned: {len(files)}")
print("\n=== tool_result bytes that entered context, by TOOL ===")
print(f"{'tool':26s} {'results':>8} {'bytes':>16} {'% of results':>13} {'avg':>9}")
for k, v in by_tool.most_common(18):
    print(
        f"{k[:26]:26s} {by_tool_n[k]:8,} {v:16,} {100 * v / max(tot, 1):12.1f}% {v // max(by_tool_n[k], 1):9,}"
    )

print("\n=== attributable-by-NAME vs OPAQUE ===")
print(
    f"  named target (file/skill) : {attributable:>16,} B  {100 * attributable / max(tot, 1):5.1f}%"
)
print(
    f"  opaque (Bash/agent/search): {opaque:>16,} B  {100 * opaque / max(tot, 1):5.1f}%"
)
print(f"  total tool_result bytes   : {tot:>16,} B  (~{tot // 4:,} tokens)")
print(f"  dispatch prompt/text bytes: {prompt_bytes:>16,} B")

print("\n=== top 25 FILES by bytes admitted into agent contexts ===")
for k, v in by_file.most_common(25):
    print(f"  {v:>12,} B  {k}")

print("\n=== attachment bytes by type (fleet-wide) ===")
for k, v in attach_bytes.most_common(12):
    print(f"  {v:>14,} B  {k}")
