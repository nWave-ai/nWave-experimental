#!/usr/bin/env python3
"""D64: what do SKILL CORES actually cost, in BYTE-TURNS, per role and lifetime?

Two admission paths, measured separately because they are not equivalent:
  (a) Read of a SKILL.md          -> visible as tool_result bytes
  (b) Skill tool invocation       -> content arrives via an `invoked_skills`
                                     attachment; the tool_result itself is tiny
                                     ({commandName, success}) so counting only
                                     tool_results would UNDERCOUNT path (b).

Decides on the PROPERTY (byte-turns), never the designation (file size).
"""

import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path


root = sys.argv[1]
SKILL_RE = re.compile(r"/skills/([^/]+)/SKILL\.md$")

bt_by_skill = Counter()  # byte-turns via Read
b_by_skill = Counter()  # raw bytes via Read
n_read = Counter()
invoked = Counter()  # Skill-tool invocations by name
invoked_bytes = Counter()  # bytes seen in invoked_skills attachments
bt_invoked = Counter()
per_agent_skill_bt = Counter()
agent_turns = {}
agent_cr = Counter()
skill_by_agent = {}
tot_bt_all = 0  # byte-turns of ALL tool_results, for share math

for f in sorted([p.name for p in Path(root).iterdir()]):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    order = OrderedDict()
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
                if isinstance(r, dict) and r.get("type") == "assistant":
                    rid = r.get("requestId")
                    if rid and rid not in order:
                        order[rid] = len(order)
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    T = len(order)
    if T < 2:
        continue
    agent = f.replace("agent-a", "").rsplit("-", 1)[0]
    agent_turns[agent] = T

    tool_by_id, target_by_id = {}, {}
    cur = 0
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

            # path (b): invoked_skills / skill attachments
            if r.get("type") == "attachment":
                a = r.get("attachment") or {}
                if a.get("type") == "invoked_skills":
                    blob = json.dumps(a, ensure_ascii=False)
                    sz = len(blob)
                    residency = max(T - cur - 1, 0)
                    bt_invoked["<invoked_skills attachment>"] += sz * residency
                    invoked_bytes["<invoked_skills attachment>"] += sz
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
                        nm = blk.get("name")
                        tool_by_id[blk.get("id")] = nm
                        inp = blk.get("input") or {}
                        if nm == "Skill":
                            invoked[str(inp.get("skill", "?"))] += 1
                        tgt = inp.get("file_path") or inp.get("path")
                        if tgt:
                            target_by_id[blk.get("id")] = str(tgt)
            elif r.get("type") == "user":
                for blk in m.get("content") or []:
                    if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                        continue
                    tid = blk.get("tool_use_id")
                    cc = blk.get("content")
                    sz = (
                        len(cc)
                        if isinstance(cc, str)
                        else len(json.dumps(cc, ensure_ascii=False))
                        if cc is not None
                        else 0
                    )
                    residency = max(T - cur - 1, 0)
                    tot_bt_all += sz * residency
                    tgt = target_by_id.get(tid)
                    if not tgt:
                        continue
                    mm = SKILL_RE.search(tgt)
                    if not mm:
                        continue
                    name = mm.group(1)
                    bt = sz * residency
                    bt_by_skill[name] += bt
                    b_by_skill[name] += sz
                    n_read[name] += 1
                    per_agent_skill_bt[agent] += bt
                    skill_by_agent.setdefault(agent, set()).add(name)

print("=== PATH (a): SKILL.md READ into context ===")
print(f"{'skill':44s} {'byte-turns':>15} {'bytes':>10} {'reads':>6}")
for k, v in bt_by_skill.most_common(20):
    print(f"{k[:44]:44s} {v:>15,} {b_by_skill[k]:>10,} {n_read[k]:>6}")
print(
    f"{'TOTAL (path a)':44s} {sum(bt_by_skill.values()):>15,} "
    f"{sum(b_by_skill.values()):>10,} {sum(n_read.values()):>6}"
)

print("\n=== PATH (b): Skill TOOL invocations ===")
print(f"  distinct skills invoked : {len(invoked)}")
print(f"  total invocations       : {sum(invoked.values())}")
for k, v in invoked.most_common(15):
    print(f"    {v:>4}x  {k}")
print(f"  invoked_skills attachment bytes seen: {sum(invoked_bytes.values()):,}")
print(f"  invoked_skills attachment byte-turns: {sum(bt_invoked.values()):,}")

print("\n=== SHARE OF ALL TOOL-ADMITTED BYTE-TURNS ===")
sa = sum(bt_by_skill.values())
print(f"  all tool_result byte-turns : {tot_bt_all:,}")
print(f"  SKILL.md reads             : {sa:,}  ({100 * sa / max(tot_bt_all, 1):.2f}%)")

print("\n=== WHICH AGENTS PAY, AND HOW LONG DO THEY LIVE ===")
print(f"{'agent':34s} {'turns':>6} {'skill byte-turns':>18} {'skills read':>12}")
for agent, bt in per_agent_skill_bt.most_common(20):
    print(
        f"{agent[:34]:34s} {agent_turns.get(agent, 0):6,} {bt:>18,} "
        f"{len(skill_by_agent.get(agent, ())):>12}"
    )
print(
    f"\n  agents that read ANY SKILL.md: {len(per_agent_skill_bt)} of {len(agent_turns)}"
)
