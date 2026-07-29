#!/usr/bin/env python3
"""BYTE-TURNS: rank what to cut by bytes x residency, not bytes.

A payload admitted at turn k of a T-turn agent is billed (T-k) more times.
Cutting a big document that agents read LATE saves little; cutting a small
one admitted at turn 0 saves a lot. This computes the real ranking.

For each tool_result carrying bytes, charge bytes * (turns_remaining).
Turn index = ordinal of the requestId in which the result was consumed.
"""

import json
import os
import sys
from collections import Counter, OrderedDict


root = sys.argv[1]
topn = int(sys.argv[2]) if len(sys.argv) > 2 else 30

bt_by_file = Counter()
bytes_by_file = Counter()
adm_by_file = Counter()
bt_by_tool = Counter()
bt_total = 0
skipped = 0

for f in sorted(os.listdir(root)):
    if not f.endswith(".jsonl"):
        continue
    p = os.path.join(root, f)
    tool_by_id, target_by_id = {}, {}
    # pass 1: ordinal of each requestId, and total turns
    order = OrderedDict()
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
                if isinstance(rec, dict) and rec.get("type") == "assistant":
                    rid = rec.get("requestId")
                    if rid and rid not in order:
                        order[rid] = len(order)
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        skipped += 1
        continue
    T = len(order)
    if T < 2:
        continue
    # pass 2: attribute each tool_result to a turn index
    cur_turn = 0
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
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            if rec.get("type") == "assistant":
                rid = rec.get("requestId")
                if rid in order:
                    cur_turn = order[rid]
                for blk in msg.get("content") or []:
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        tool_by_id[blk.get("id")] = blk.get("name")
                        inp = blk.get("input") or {}
                        tgt = (
                            inp.get("file_path") or inp.get("path") or inp.get("skill")
                        )
                        if tgt:
                            target_by_id[blk.get("id")] = str(tgt)
            elif rec.get("type") == "user":
                for blk in msg.get("content") or []:
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
                    residency = max(T - cur_turn - 1, 0)
                    bt = sz * residency
                    bt_by_tool[tool_by_id.get(tid, "?")] += bt
                    globals()["bt_total"] = globals()["bt_total"] + bt
                    tgt = target_by_id.get(tid)
                    if tgt:
                        bt_by_file[tgt] += bt
                        bytes_by_file[tgt] += sz
                        adm_by_file[tgt] += 1

print(f"skipped/indeterminate transcripts: {skipped}")
print(f"\ntotal byte-turns charged (tool-admitted only): {bt_total:,}")
print(f"  ~= {bt_total // 4:,} token-turns\n")
print("=== byte-turns by TOOL ===")
for k, v in bt_by_tool.most_common(10):
    print(f"  {k[:26]:26s} {v:>18,}")
print(f"\n=== top {topn} FILES by BYTE-TURNS (the real cut list) ===")
print(f"{'byte-turns':>18} {'bytes':>11} {'reads':>6}  path")
for k, v in bt_by_file.most_common(topn):
    print(f"{v:>18,} {bytes_by_file[k]:>11,} {adm_by_file[k]:>6}  {k}")
print("\n=== same files ranked by RAW BYTES (the naive list, for contrast) ===")
for k, v in bytes_by_file.most_common(12):
    rank_bt = [i for i, (kk, _) in enumerate(bt_by_file.most_common(), 1) if kk == k]
    print(f"{v:>11,} B  byte-turn-rank #{rank_bt[0] if rank_bt else '?':<4}  {k}")
