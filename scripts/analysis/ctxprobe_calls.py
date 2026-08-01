#!/usr/bin/env python3
"""Where is the fat: call COUNT and agent LIFETIME, per dispatch.

If eliminating a call removes 100% of its byte-turns, the distribution of
calls per AGENT says where a remedy would land. An agent making 400 calls and
one making 20 do not have the same cure.
"""

import json
import os
import sys
from collections import Counter, OrderedDict
from pathlib import Path


root = sys.argv[1]
per_agent = []

for f in sorted([p.name for p in Path(root).iterdir()]):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    order = OrderedDict()
    tool_by_id = {}
    tool_calls = Counter()
    cr_tot = 0
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
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
                m = rec.get("message")
                if not isinstance(m, dict):
                    continue
                if rec.get("type") == "assistant":
                    rid = rec.get("requestId")
                    if rid and rid not in order:
                        order[rid] = len(order)
                        u = m.get("usage") or {}
                        cr_tot += u.get("cache_read_input_tokens") or 0
                    for blk in m.get("content") or []:
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            tool_by_id[blk.get("id")] = blk.get("name")
                            tool_calls[blk.get("name")] += 1
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    T = len(order)
    if T < 1:
        continue
    name = f.replace("agent-a", "").rsplit("-", 1)[0]
    per_agent.append(
        {
            "name": name,
            "turns": T,
            "cr": cr_tot,
            "bash": tool_calls.get("Bash", 0),
            "read": tool_calls.get("Read", 0),
            "all_tools": sum(tool_calls.values()),
        }
    )

n = len(per_agent)
print(f"agents: {n}\n")


def dist(key, label):
    v = sorted(a[key] for a in per_agent)
    m = len(v)

    def q(x):
        return v[min(int(m * x), m - 1)]

    print(
        f"  {label:22s} total {sum(v):>10,}  p50 {q(0.5):>6,}  p75 {q(0.75):>6,}  "
        f"p90 {q(0.9):>6,}  p99 {q(0.99):>6,}  max {v[-1]:>6,}"
    )


print("=== PER-DISPATCH DISTRIBUTIONS ===")
dist("turns", "turns (requests)")
dist("bash", "Bash calls")
dist("read", "Read calls")
dist("all_tools", "all tool calls")

print(
    "\n=== CONCENTRATION: how much of the fleet's cache_read do the LONGEST agents hold? ==="
)
by_cr = sorted(per_agent, key=lambda a: -a["cr"])
tot_cr = sum(a["cr"] for a in per_agent)
for k in (5, 10, 25, 50, 100):
    if k <= n:
        s = sum(a["cr"] for a in by_cr[:k])
        print(
            f"  top {k:>3} agents of {n}: {100 * s / max(tot_cr, 1):5.1f}% of all cache_read"
        )

print("\n=== CONCENTRATION BY TURNS (agent lifetime) ===")
by_t = sorted(per_agent, key=lambda a: -a["turns"])
tot_t = sum(a["turns"] for a in per_agent)
for k in (5, 10, 25, 50):
    if k <= n:
        s = sum(a["turns"] for a in by_t[:k])
        cr = sum(a["cr"] for a in by_t[:k])
        print(
            f"  top {k:>3} longest agents: {100 * s / max(tot_t, 1):5.1f}% of turns, "
            f"{100 * cr / max(tot_cr, 1):5.1f}% of cache_read"
        )

print("\n=== THE 20 LONGEST-LIVED DISPATCHES ===")
print(
    f"{'agent':34s} {'turns':>6} {'bash':>6} {'read':>6} {'tools':>7} {'cache_read':>14}"
)
for a in by_t[:20]:
    print(
        f"{a['name'][:34]:34s} {a['turns']:6,} {a['bash']:6,} {a['read']:6,} "
        f"{a['all_tools']:7,} {a['cr']:14,}"
    )

print("\n=== QUADRATIC CHECK: cache_read vs turns ===")
print("  If prefix is roughly constant, cache_read grows ~ turns^2 / 2 * growth.")
print(
    f"{'turn bucket':16s} {'agents':>7} {'mean turns':>11} {'mean cache_read':>16} {'cr/turn':>10}"
)
buckets = [(0, 25), (25, 50), (50, 100), (100, 200), (200, 10000)]
for lo, hi in buckets:
    grp = [a for a in per_agent if lo <= a["turns"] < hi]
    if not grp:
        continue
    mt = sum(a["turns"] for a in grp) / len(grp)
    mc = sum(a["cr"] for a in grp) / len(grp)
    print(
        f"{f'{lo}-{hi}':16s} {len(grp):7,} {mt:11.1f} {mc:16,.0f} {mc / max(mt, 1):10,.0f}"
    )
