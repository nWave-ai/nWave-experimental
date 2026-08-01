#!/usr/bin/env python3
"""Token accounting per agent transcript, with the cache-chain identity check.

Method (binding): dedup by requestId, MAX on output_tokens. For the prefix
fields (input/cache_creation/cache_read) a requestId's records all carry the
SAME values, so MAX is also correct there.

Identity under test:
    cache_read[n] == cache_read[n-1] + cache_creation[n-1] + input[n-1]
If it holds, the prefix is a monotonically growing cached chain and
"how many times the same byte re-entered" is exactly sum(cache_read).
"""

import json
import os
import sys
from collections import OrderedDict


def account(path):
    per_req = OrderedDict()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "assistant":
                continue
            rid = rec.get("requestId")
            msg = rec.get("message") or {}
            u = msg.get("usage") or {}
            if not rid or not u:
                continue
            cur = per_req.setdefault(
                rid,
                {
                    "in": 0,
                    "cw": 0,
                    "cr": 0,
                    "out": 0,
                    "model": msg.get("model"),
                    "ts": rec.get("timestamp"),
                },
            )
            cur["in"] = max(cur["in"], u.get("input_tokens") or 0)
            cur["cw"] = max(cur["cw"], u.get("cache_creation_input_tokens") or 0)
            cur["cr"] = max(cur["cr"], u.get("cache_read_input_tokens") or 0)
            cur["out"] = max(cur["out"], u.get("output_tokens") or 0)
    return per_req


def main():
    path = sys.argv[1]
    verbose = "-v" in sys.argv
    reqs = account(path)
    tot = {"in": 0, "cw": 0, "cr": 0, "out": 0}
    ok = bad = 0
    prev = None
    rows = []
    for rid, r in reqs.items():
        for k in tot:
            tot[k] += r[k]
        drift = None
        if prev is not None:
            expect = prev["cr"] + prev["cw"]
            drift = r["cr"] - expect
            if drift == 0:
                ok += 1
            else:
                bad += 1
        rows.append((rid, r, drift))
        prev = r
    print(f"file: {os.path.basename(path)}")
    print(f"  requests(dedup by requestId): {len(reqs)}")
    print(f"  input_tokens        : {tot['in']:>12,}")
    print(f"  cache_creation      : {tot['cw']:>12,}")
    print(f"  cache_read          : {tot['cr']:>12,}")
    print(f"  output_tokens       : {tot['out']:>12,}")
    uniq = tot["in"] + tot["cw"]
    print(f"  UNIQUE bytes in     : {uniq:>12,}  (input + cache_creation)")
    print(f"  RE-ENTRY (cache_read): {tot['cr']:>12,}")
    if uniq:
        print(f"  re-entry multiplier : {tot['cr'] / uniq:>12.2f}x")
    print(f"  chain identity      : {ok} hold / {bad} drift")
    if verbose:
        print("\n  turn-by-turn:")
        for i, (_rid, r, drift) in enumerate(rows[:60]):
            d = "" if drift is None else f" drift={drift:+d}"
            print(
                f"   {i:3d} in={r['in']:>7} cw={r['cw']:>8} cr={r['cr']:>9} "
                f"out={r['out']:>6}{d}"
            )


if __name__ == "__main__":
    main()
