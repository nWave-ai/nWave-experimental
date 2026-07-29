#!/usr/bin/env python3
"""Tighten the bound on the ADMISSION PREFIX: how much is really unattributed?

For each subagent dispatch, the turn-0 prefix (cr[0]+cw[0]) is MEASURED in
tokens. The transcript-visible admission payload (dispatch prompt, deferred
tool schemas, skill listing, agent roster, system-reminders) is MEASURED in
bytes. Known-but-invisible candidates (CLAUDE.md x2, memory index) are
MEASURED in bytes on disk.

    residual = prefix_tokens - visible_tokens - known_invisible_tokens

The bytes->tokens conversion is the one estimate. It is reported as a RANGE
(3.2 - 4.2 B/token) so the residual is a band, not a false point.
"""

import json
import os
import statistics
import sys


root = sys.argv[1]

KNOWN_INVISIBLE = {
    "CLAUDE.md (global)": os.path.expanduser("~/.claude-alt3/CLAUDE.md"),
    "CLAUDE.md (project)": "/home/alexd/Projects/nWave-dev/CLAUDE.md",
    "MEMORY.md (index)": os.path.expanduser(
        "~/.claude-alt3/projects/-home-alexd-Projects-nWave-dev/memory/MEMORY.md"
    ),
}
known_bytes = {}
for k, p in KNOWN_INVISIBLE.items():
    try:
        known_bytes[k] = os.path.getsize(p)
    except OSError as e:
        print(f"!! INDETERMINATE {k}: {e}", file=sys.stderr)
        known_bytes[k] = None

rows = []
for f in sorted(os.listdir(root)):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    prefix_tokens = None
    visible = 0
    seen_first_assistant = False
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict):
                    continue
                t = r.get("type")
                # everything BEFORE the first assistant turn is admission payload
                if t == "assistant" and not seen_first_assistant:
                    u = (r.get("message") or {}).get("usage") or {}
                    if u:
                        prefix_tokens = (u.get("cache_read_input_tokens") or 0) + (
                            u.get("cache_creation_input_tokens") or 0
                        )
                        seen_first_assistant = True
                    continue
                if seen_first_assistant:
                    continue
                if t == "attachment":
                    a = r.get("attachment") or {}
                    visible += len(json.dumps(a, ensure_ascii=False))
                elif t == "user":
                    c = (r.get("message") or {}).get("content")
                    if isinstance(c, str):
                        visible += len(c)
                    elif isinstance(c, list):
                        visible += len(json.dumps(c, ensure_ascii=False))
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    if prefix_tokens:
        rows.append((f, prefix_tokens, visible))

print(f"dispatches with a measured turn-0 prefix: {len(rows)}\n")
pt = sorted(r[1] for r in rows)
vb = sorted(r[2] for r in rows)
n = len(pt)
q = lambda a, x: a[min(int(len(a) * x), len(a) - 1)]
print("=== MEASURED ===")
print(
    f"  turn-0 prefix (tokens) : p50 {q(pt, 0.5):,}  p90 {q(pt, 0.9):,}  max {q(pt, 1):,}"
)
print(
    f"  visible payload (bytes): p50 {q(vb, 0.5):,}  p90 {q(vb, 0.9):,}  max {q(vb, 1):,}"
)
print("\n=== KNOWN-BUT-INVISIBLE (bytes on disk) ===")
tot_known = 0
for k, v in known_bytes.items():
    if v is None:
        print(f"  {k:24s} INDETERMINATE")
    else:
        print(f"  {k:24s} {v:>8,} B")
        tot_known += v
print(f"  {'TOTAL':24s} {tot_known:>8,} B")

print("\n=== RESIDUAL, as a band over the bytes/token assumption ===")
med_prefix = statistics.median(r[1] for r in rows)
med_visible = statistics.median(r[2] for r in rows)
print(
    f"  median prefix {med_prefix:,.0f} tok;  median visible {med_visible:,.0f} B;"
    f"  known-invisible {tot_known:,} B"
)
print(
    f"{'B/token':>9} {'visible tok':>12} {'known tok':>11} {'residual tok':>13} {'residual %':>11}"
)
for bpt in (3.2, 3.5, 3.8, 4.0, 4.2):
    vt = med_visible / bpt
    kt = tot_known / bpt
    res = med_prefix - vt - kt
    print(
        f"{bpt:9.1f} {vt:12,.0f} {kt:11,.0f} {res:13,.0f} {100 * res / med_prefix:10.1f}%"
    )
print("\n  The residual is the SYSTEM PROMPT + TOOL SCHEMAS: harness-owned,")
print("  not ours to cut. Everything attributable to us is the 'known tok' column.")
