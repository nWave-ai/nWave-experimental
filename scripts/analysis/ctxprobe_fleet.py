#!/usr/bin/env python3
"""Fleet-wide context consumption census over all subagent transcripts.

Reports per agent: turns, turn-0 prefix (the FIXED admission cost),
unique tokens admitted, cache_read (re-entry), output, multipliers.
Plus the aggregate and the chain-identity health (GDP-6: drift is LOUD).
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctxprobe_account import account


def analyse(path):
    reqs = account(path)
    if not reqs:
        return None
    rows = list(reqs.values())
    tot_in = sum(r["in"] for r in rows)
    tot_cw = sum(r["cw"] for r in rows)
    tot_cr = sum(r["cr"] for r in rows)
    tot_out = sum(r["out"] for r in rows)
    drift = 0
    for a, b in zip(rows, rows[1:]):
        if b["cr"] != a["cr"] + a["cw"]:
            drift += 1
    t0 = rows[0]
    return {
        "turns": len(rows),
        "prefix0": t0["cr"] + t0["cw"],
        "in": tot_in,
        "cw": tot_cw,
        "cr": tot_cr,
        "out": tot_out,
        "unique": tot_in + tot_cw,
        "drift": drift,
        "model": t0["model"],
    }


def main():
    root = sys.argv[1]
    files = sorted(
        os.path.join(root, f) for f in os.listdir(root) if f.endswith(".jsonl")
    )
    results = []
    for p in files:
        try:
            r = analyse(p)
        except Exception as e:  # GDP-6: degrade LOUD
            print(f"!! INDETERMINATE {os.path.basename(p)}: {e}", file=sys.stderr)
            continue
        if r:
            r["name"] = os.path.basename(p).replace("agent-a", "").rsplit("-", 1)[0]
            results.append(r)

    agg = {
        k: sum(r[k] for r in results)
        for k in ("turns", "in", "cw", "cr", "out", "unique", "drift")
    }
    print(f"agents analysed: {len(results)} of {len(files)} files\n")
    print(
        f"{'agent':38s} {'turns':>5} {'prefix0':>9} {'unique':>10} {'cache_read':>12} {'out':>8} {'reentry':>8}"
    )
    for r in sorted(results, key=lambda x: -x["cr"])[:30]:
        mult = r["cr"] / r["unique"] if r["unique"] else 0
        print(
            f"{r['name'][:38]:38s} {r['turns']:5d} {r['prefix0']:9,} "
            f"{r['unique']:10,} {r['cr']:12,} {r['out']:8,} {mult:7.1f}x"
        )
    print("\n=== AGGREGATE ===")
    for k in ("turns", "in", "cw", "cr", "out", "unique"):
        print(f"  {k:12s} {agg[k]:>15,}")
    if agg["unique"]:
        print(f"  re-entry multiplier   {agg['cr'] / agg['unique']:>13.2f}x")
    if agg["out"]:
        print(f"  cache_read / output   {agg['cr'] / agg['out']:>13.2f}x")
        print(
            f"  total_in / output     {(agg['cr'] + agg['unique']) / agg['out']:>13.2f}x"
        )
    print(
        f"  chain-identity drift  {agg['drift']:>15,}  (0 = every turn's prefix explained)"
    )
    # distribution of the fixed admission cost
    pfx = sorted(r["prefix0"] for r in results)
    if pfx:
        n = len(pfx)
        print("\n=== turn-0 prefix (FIXED admission cost per dispatch) ===")
        print(
            f"  min {pfx[0]:,}  p50 {pfx[n // 2]:,}  p90 {pfx[int(n * 0.9)]:,}  max {pfx[-1]:,}"
        )
        print(f"  sum {sum(pfx):,} tokens paid just to START {n} dispatches")


if __name__ == "__main__":
    main()
