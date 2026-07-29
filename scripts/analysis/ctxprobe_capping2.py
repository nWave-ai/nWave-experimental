#!/usr/bin/env python3
"""Capping, v2: REPLAY the measured prefix instead of modelling it.

v1 assumed prefix(t) = P0 + g*t with g = mean cache_creation. It predicted
savings of 556% / 125% / 114% of measured cache_read -- saving more than the
total cost, which is impossible. The model failed because the real prefix is
NOT monotone (context compaction resets it: 291 drop events, 52.6M tokens)
and because mean-g is skewed by a few huge turns.

This version uses NO growth model. It replays the agent's OWN measured
cache_creation sequence under a k-way split and sums the resulting prefixes:

    piece starting at turn s, its j-th turn re-reads:  P0 + sum(cw[s .. s+j-1])

so the counterfactual is arithmetic on measured values only. The one
assumption left is stated, not hidden: a restart re-pays the admission
prefix P0 and re-does no work. The second half of that is FALSE in reality
and is exactly the cost the transcripts cannot see.
"""

import json
import os
import statistics
import sys
from collections import OrderedDict


root = sys.argv[1]
KS = (2, 3, 4)
rows_out = []

for f in sorted(os.listdir(root)):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    usage = OrderedDict()
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
                if not isinstance(r, dict) or r.get("type") != "assistant":
                    continue
                rid = r.get("requestId")
                u = (r.get("message") or {}).get("usage") or {}
                if not rid or not u:
                    continue
                cur = usage.setdefault(rid, {"cw": 0, "cr": 0})
                cur["cw"] = max(cur["cw"], u.get("cache_creation_input_tokens") or 0)
                cur["cr"] = max(cur["cr"], u.get("cache_read_input_tokens") or 0)
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue

    rows = list(usage.values())
    T = len(rows)
    if T < 10:
        continue
    cw = [r["cw"] for r in rows]
    cr = [r["cr"] for r in rows]
    P0 = cr[0] + cw[0]
    measured = sum(cr)

    def counterfactual(k):
        """Replay measured cw under a k-way equal split."""
        total = 0
        bounds = [round(i * T / k) for i in range(k + 1)]
        for i in range(k):
            s, e = bounds[i], bounds[i + 1]
            if s >= e:
                continue
            prefix = P0 if i > 0 else cr[0]  # piece 0 keeps its real turn-0 read
            acc = 0
            for j in range(s, e):
                total += prefix + acc if i > 0 else cr[j]
                acc += cw[j]
            # note: piece 0 is left EXACTLY as measured; only restarts are modelled
        return total

    res = {
        "name": f.replace("agent-a", "").rsplit("-", 1)[0][:34],
        "T": T,
        "P0": P0,
        "measured": measured,
    }
    for k in KS:
        cfx = counterfactual(k)
        res[f"k{k}"] = cfx
        res[f"save{k}"] = 100 * (measured - cfx) / measured if measured else 0
    rows_out.append(res)

longs = sorted([a for a in rows_out if a["T"] >= 200], key=lambda a: -a["T"])
print(f"agents with T>=10: {len(rows_out)}   T>=200: {len(longs)}\n")

print("=== COUNTERFACTUAL SAVING FROM SPLITTING (replayed, not modelled) ===")
print(f"{'agent':34s} {'T':>5} {'measured cr':>14} {'k=2':>7} {'k=3':>7} {'k=4':>7}")
for a in longs:
    print(
        f"{a['name']:34s} {a['T']:5d} {a['measured']:14,} "
        f"{a['save2']:6.1f}% {a['save3']:6.1f}% {a['save4']:6.1f}%"
    )

print("\n=== SANITY: no saving may exceed 100% ===")
bad = [a for a in rows_out for k in KS if a[f"save{k}"] > 100 or a[f"save{k}"] < -200]
print(f"  impossible values: {len(bad)}   (v1 had many; 0 expected here)")

print("\n=== SAVING BY LIFETIME COHORT (median) ===")
print(f"{'cohort':14s} {'n':>5} {'k=2':>8} {'k=3':>8} {'k=4':>8}")
for label, lo, hi in (
    ("T<25", 0, 25),
    ("25-50", 25, 50),
    ("50-100", 50, 100),
    ("100-200", 100, 200),
    ("T>=200", 200, 10**9),
):
    grp = [a for a in rows_out if lo <= a["T"] < hi]
    if not grp:
        continue
    print(
        f"{label:14s} {len(grp):5d} "
        + " ".join(f"{statistics.median(a[f'save{k}'] for a in grp):7.1f}%" for k in KS)
    )

print("\n=== WHERE DOES SPLITTING START TO PAY? (median k=2 saving by T) ===")
for lo, hi in (
    (10, 20),
    (20, 30),
    (30, 40),
    (40, 60),
    (60, 90),
    (90, 140),
    (140, 200),
    (200, 10**9),
):
    grp = [a for a in rows_out if lo <= a["T"] < hi]
    if not grp:
        continue
    med = statistics.median(a["save2"] for a in grp)
    print(
        f"  T in [{lo:>3},{hi if hi < 10**9 else 'inf'!s:>4}) n={len(grp):>3}  median k=2 saving {med:6.1f}%"
    )

tot_m = sum(a["measured"] for a in rows_out)
tot_2 = sum(a["k2"] for a in rows_out)
print("\n=== FLEET TOTAL ===")
print(f"  measured cache_read      : {tot_m:,}")
print(f"  counterfactual (k=2 all) : {tot_2:,}")
print(f"  fleet saving             : {100 * (tot_m - tot_2) / max(tot_m, 1):.1f}%")
tot_long_m = sum(a["measured"] for a in longs)
tot_long_2 = sum(a["k2"] for a in longs)
print(f"  if applied ONLY to T>=200 ({len(longs)} agents):")
print(f"    their measured {tot_long_m:,} -> {tot_long_2:,}")
print(f"    fleet-wide saving {100 * (tot_long_m - tot_long_2) / max(tot_m, 1):.1f}%")
