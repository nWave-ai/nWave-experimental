#!/usr/bin/env python3
"""Decompose cache_read into: FIXED-PREFIX re-reads vs TASK-ACCRUED re-reads.

For each agent, the turn-0 prefix P0 is admitted before the agent does any
work: system prompt + CLAUDE.md + memory index + tool schemas + skill listing
+ the dispatch prompt. Every later turn re-reads it.

    fixed_component  = P0 * (turns - 1)      # re-reads of never-task-specific bytes
    accrued_component= cache_read - fixed    # re-reads of work the agent produced

Also classifies the chain-identity drifts (GDP-6: named, not swallowed).
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctxprobe_account import account


root = sys.argv[1]
fixed_tot = accrued_tot = cr_tot = 0
turns_tot = 0
drops = []  # prefix SHRANK -> compaction / cache miss
misses = []  # prefix grew by more than declared -> cache eviction
per_agent = []

for f in sorted(os.listdir(root)):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    try:
        rows = list(account(p).values())
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    if not rows:
        continue
    p0 = rows[0]["cr"] + rows[0]["cw"]
    cr = sum(r["cr"] for r in rows)
    t = len(rows)
    fixed = min(p0 * (t - 1), cr)
    accrued = cr - fixed
    fixed_tot += fixed
    accrued_tot += accrued
    cr_tot += cr
    turns_tot += t
    name = f.replace("agent-a", "").rsplit("-", 1)[0]
    per_agent.append((name, t, p0, cr, fixed, accrued))
    for a, b in zip(rows, rows[1:]):
        expect = a["cr"] + a["cw"]
        if b["cr"] < expect:
            drops.append((name, expect - b["cr"]))
        elif b["cr"] > expect:
            misses.append((name, b["cr"] - expect))

print("=== WHERE THE CACHE-READ TOKENS GO ===")
print(f"  total cache_read            {cr_tot:>16,}")
print(
    f"  re-reads of FIXED prefix    {fixed_tot:>16,}  {100 * fixed_tot / cr_tot:5.1f}%"
)
print(
    f"  re-reads of TASK-accrued    {accrued_tot:>16,}  {100 * accrued_tot / cr_tot:5.1f}%"
)
print(f"  turns                       {turns_tot:>16,}")
print(f"  mean prefix re-read / turn  {cr_tot // max(turns_tot, 1):>16,}")

print("\n=== chain-identity anomalies (GDP-6: named, not swallowed) ===")
print(
    f"  prefix SHRANK (compaction/reset): {len(drops)} events, {sum(d for _, d in drops):,} tokens dropped"
)
print(
    f"  prefix GREW unexpectedly (cache miss/re-write): {len(misses)} events, {sum(d for _, d in misses):,} tokens"
)
for n, d in sorted(drops, key=lambda x: -x[1])[:5]:
    print(f"    drop {d:>10,}  {n}")
for n, d in sorted(misses, key=lambda x: -x[1])[:5]:
    print(f"    grow {d:>10,}  {n}")

print("\n=== top agents by FIXED-prefix waste ===")
print(
    f"{'agent':38s} {'turns':>5} {'prefix0':>9} {'fixed re-read':>15} {'%of its cr':>10}"
)
for name, t, p0, cr, fx, ac in sorted(per_agent, key=lambda x: -x[4])[:20]:
    print(f"{name[:38]:38s} {t:5d} {p0:9,} {fx:15,} {100 * fx / cr:9.1f}%")
