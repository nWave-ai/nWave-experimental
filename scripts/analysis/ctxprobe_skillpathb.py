#!/usr/bin/env python3
"""Bound PATH (b): the Skill TOOL, whose payload is invisible in transcripts.

Path (a) (explicit Read of SKILL.md) is measurable and small. Path (b) is the
one the wave commands use, and its tool_result is 26 bytes -- the core is
injected by the harness, like CLAUDE.md. If path (b) is large it overturns the
verdict, so bound it rather than assume it away.

Measures, in a session transcript:
  - every Skill tool invocation, by name
  - every `invoked_skills` / `skill_listing` attachment and its byte size
  - the IMPLIED cost: sum(core size on disk) x turns remaining after invocation
"""

import json
import os
import sys
from collections import Counter, OrderedDict
from pathlib import Path


path = sys.argv[1]

DISK = {}
for base in (
    str(Path("~/.claude/skills").expanduser()),
    "/home/alexd/Projects/nWave-dev/nWave/skills",
):
    if not os.path.isdir(base):
        continue
    for d in [p.name for p in Path(base).iterdir()]:
        f = os.path.join(base, d, "SKILL.md")
        if os.path.isfile(f):
            DISK.setdefault(d, Path(f).stat().st_size)

order = OrderedDict()
with open(path, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and r.get("type") == "assistant":
            rid = r.get("requestId")
            if rid and rid not in order:
                order[rid] = len(order)
T = len(order)

invocations = []  # (turn_index, skill_name)
att_bytes = Counter()
att_count = Counter()
cur = 0
tool_by_id = {}

with open(path, encoding="utf-8", errors="replace") as fh:
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
        if r.get("type") == "attachment":
            a = r.get("attachment") or {}
            t = a.get("type", "?")
            if t in ("invoked_skills", "skill_listing"):
                att_bytes[t] += len(json.dumps(a, ensure_ascii=False))
                att_count[t] += 1
            continue
        m = r.get("message")
        if not isinstance(m, dict):
            continue
        if r.get("type") == "assistant":
            rid = r.get("requestId")
            if rid in order:
                cur = order[rid]
            for blk in m.get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    tool_by_id[blk.get("id")] = blk.get("name")
                    if blk.get("name") == "Skill":
                        nm = str((blk.get("input") or {}).get("skill", "?"))
                        invocations.append((cur, nm))

print(f"session turns (dedup requestId): {T:,}")
print(f"\n=== Skill TOOL invocations: {len(invocations)} ===")
by_name = Counter(n for _, n in invocations)
for n, c in by_name.most_common(20):
    print(f"   {c:>3}x  {n:38s} core on disk = {DISK.get(n, 0):,} B")

print("\n=== attachments that could carry skill payload ===")
for t in ("invoked_skills", "skill_listing"):
    print(f"   {t:18s} {att_count[t]:>4} records, {att_bytes[t]:>12,} B")

print("\n=== IMPLIED path-(b) cost, if each invoked core stays resident ===")
tot_bt = 0
unknown = 0
for turn, nm in invocations:
    sz = DISK.get(nm)
    if sz is None:
        unknown += 1
        continue
    tot_bt += sz * max(T - turn - 1, 0)
print(f"   invocations with a known core size : {len(invocations) - unknown}")
print(f"   invocations with UNKNOWN core size : {unknown}  (excluded, not zeroed)")
print(f"   implied byte-turns                 : {tot_bt:,}")
print(f"   ~= token-turns (4 B/token)         : {tot_bt // 4:,}")
print("\n   NOTE: this is an UPPER BOUND on path (b) -- it assumes every invoked")
print("   core is admitted WHOLE and stays resident for the rest of the session.")
print("   The transcript cannot confirm either assumption; the tool_result is 26 B.")
