#!/usr/bin/env python3
"""Decompose the UNPAIRABLE hook-injection population.

The 96.3% offered->admitted ratio rests on 53 pairable injections out of 242
hook_success records carrying stdout. Question that decides whether the ratio
generalises: is the unpairable remainder a HOMOGENEOUS class (guard hooks that
emit no additionalContext, therefore nothing to pair and no admission to miss)
or a MIXTURE that includes large injections whose fate is unknown?

Decisive test: do any UNPAIRED hook_success records carry LARGE stdout?
If unpaired stdout is uniformly tiny, the pairable subset covers all the
injections that could possibly matter and the ratio travels.
"""

import json
import sys
from collections import Counter


path = sys.argv[1]

success = {}  # toolUseID -> list of (bytes, command)
addctx = {}  # toolUseID -> bytes
order = []

with open(path, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict) or rec.get("type") != "attachment":
            continue
        a = rec.get("attachment") or {}
        at = a.get("type")
        tid = a.get("toolUseID")
        if at == "hook_success":
            so = a.get("stdout")
            n = len(so) if isinstance(so, str) else 0
            cmd = a.get("command") or a.get("hookName") or "?"
            success.setdefault(tid, []).append((n, cmd))
        elif at == "hook_additional_context":
            c = a.get("content")
            if isinstance(c, list):
                n = sum(len(x) for x in c if isinstance(x, str))
            elif isinstance(c, str):
                n = len(c)
            else:
                n = 0
            addctx[tid] = addctx.get(tid, 0) + n

# flatten: one row per hook_success record carrying stdout
rows = []
for _tid, lst in success.items():
    for n, cmd in lst:
        if n > 0:
            rows.append((tid, n, cmd, tid in addctx))

paired = [r for r in rows if r[3]]
unpaired = [r for r in rows if not r[3]]

print("=== POPULATION ===")
print(f"  hook_success records carrying stdout : {len(rows)}")
print(f"  ... PAIRED with a hook_additional_context : {len(paired)}")
print(f"  ... UNPAIRED                              : {len(unpaired)}")
print(f"  hook_additional_context records total     : {len(addctx)}")


def stats(rs, label):
    if not rs:
        print(f"  {label}: none")
        return
    ns = sorted(r[1] for r in rs)
    m = len(ns)
    print(
        f"  {label}: n={m}  total={sum(ns):,} B  "
        f"p50={ns[m // 2]:,}  p90={ns[min(int(m * 0.9), m - 1)]:,}  max={ns[-1]:,}"
    )


print("\n=== STDOUT SIZE: paired vs unpaired ===")
stats(paired, "PAIRED  ")
stats(unpaired, "UNPAIRED")

print("\n=== THE DECISIVE TEST: large UNPAIRED injections ===")
big_unpaired = sorted([r for r in unpaired if r[1] >= 10000], key=lambda x: -x[1])
print(f"  unpaired records with stdout >= 10,000 B : {len(big_unpaired)}")
for _tid, n, cmd, _ in big_unpaired[:12]:
    print(f"    {n:>8,} B  {cmd[:78]}")
big_paired = [r for r in paired if r[1] >= 10000]
print(f"  paired   records with stdout >= 10,000 B : {len(big_paired)}")

print("\n=== UNPAIRED by command (are they one homogeneous class?) ===")
by_cmd = Counter()
bytes_cmd = Counter()
for _tid, n, cmd, _ in unpaired:
    key = cmd[:70]
    by_cmd[key] += 1
    bytes_cmd[key] += n
for k, v in by_cmd.most_common(12):
    print(f"    {v:>4}x  {bytes_cmd[k]:>10,} B  avg {bytes_cmd[k] // v:>8,}  {k}")

print("\n=== PAIRED by command ===")
by_cmd_p = Counter()
bytes_cmd_p = Counter()
adm_p = Counter()
for _tid, n, cmd, _ in paired:
    key = cmd[:70]
    by_cmd_p[key] += 1
    bytes_cmd_p[key] += n
    adm_p[key] += addctx.get(tid, 0)
for k, v in by_cmd_p.most_common(12):
    o, a = bytes_cmd_p[k], adm_p[k]
    print(
        f"    {v:>4}x  offered {o:>10,}  admitted {a:>9,}  ratio {a / max(o, 1):.3f}  {k}"
    )
