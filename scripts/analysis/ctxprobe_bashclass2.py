#!/usr/bin/env python3
"""Bash byte-turns by command class -- v2, with a segment-aware classifier.

v1 was WRONG: 93% of commands are compound and `cd <path> && grep ...` was
classified on the basename of the path. This version splits the command into
command-position segments and classifies on the SET of tools present.

Priority when a call spans classes (stated, not hidden):
    execution > git > search/nav
because a `cd X && uv run pytest` call's output is the pytest run, not the cd.
Multi-class calls are counted so the residual ambiguity is visible.
"""

import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path


root = sys.argv[1]

SEARCH = {
    "grep",
    "rg",
    "egrep",
    "fgrep",
    "find",
    "ls",
    "cat",
    "sed",
    "awk",
    "head",
    "tail",
    "wc",
    "tree",
    "du",
    "stat",
    "realpath",
    "basename",
    "dirname",
    "sort",
    "uniq",
    "cut",
    "comm",
    "jq",
    "readlink",
    "xargs",
    "printf",
    "echo",
}
EXEC = {
    "pytest",
    "uv",
    "poe",
    "pre-commit",
    "des",
    "make",
    "npm",
    "node",
    "ruff",
    "mypy",
    "pip",
    "tox",
    "cargo",
    "go",
    "nwave",
    "coverage",
    "mutmut",
    "hatch",
    "twine",
    "python",
    "python3",
}
GIT = {"git", "gh"}
SEPS = re.compile(r"&&|\|\||;|\||\$\(|`|\bdo\b|\bthen\b|\n")
ENV_ASSIGN = re.compile(r"^[A-Z_][A-Z0-9_]*=")


def segment_cmds(cmd: str) -> set:
    """Leading tool of every command-position segment."""
    out = set()
    for seg in SEPS.split(cmd):
        s = seg.strip().lstrip("(){ \t")
        if not s:
            continue
        toks = s.split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if ENV_ASSIGN.match(t) or t in (
                "sudo",
                "command",
                "exec",
                "time",
                "nohup",
                "for",
                "while",
                "until",
                "if",
                "!",
                "{",
                "(",
            ):
                i += 1
                continue
            if t == "cd":  # cd consumes its argument, produces no output
                i += 2
                continue
            if t == "timeout":  # timeout <dur> <realcmd>
                i += 2
                continue
            if t.startswith("/") or t.startswith("./") or t.startswith("$"):
                t = os.path.basename(t)
            out.add(t.strip("\"'"))
            break
    return out


def classify(tools: set) -> tuple:
    e, g, s = tools & EXEC, tools & GIT, tools & SEARCH
    multi = sum(1 for x in (e, g, s) if x) > 1
    if e:
        return "execution", multi
    if g:
        return "git", multi
    if s:
        return "search/nav", multi
    return "other", multi


bt_by_class, n_by_class, bytes_by_class = Counter(), Counter(), Counter()
bt_by_cmd, n_by_cmd = Counter(), Counter()
multi_ct = Counter()
other_tokens = Counter()
sizes, sizes_by_class = [], {}
cmd_repeat = Counter()
total_calls = 0

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
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict) and rec.get("type") == "assistant":
                    rid = rec.get("requestId")
                    if rid and rid not in order:
                        order[rid] = len(order)
    except Exception as e:
        print(f"!! INDETERMINATE {f}: {e}", file=sys.stderr)
        continue
    T = len(order)
    if T < 2:
        continue
    tool_by_id, cmd_by_id = {}, {}
    cur = 0
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
                    cur = order[rid]
                for blk in msg.get("content") or []:
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        tool_by_id[blk.get("id")] = blk.get("name")
                        if blk.get("name") == "Bash":
                            cmd_by_id[blk.get("id")] = (blk.get("input") or {}).get(
                                "command"
                            ) or ""
            elif rec.get("type") == "user":
                for blk in msg.get("content") or []:
                    if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                        continue
                    tid = blk.get("tool_use_id")
                    if tool_by_id.get(tid) != "Bash":
                        continue
                    cc = blk.get("content")
                    sz = (
                        len(cc)
                        if isinstance(cc, str)
                        else len(json.dumps(cc, ensure_ascii=False))
                        if cc is not None
                        else 0
                    )
                    cmd = cmd_by_id.get(tid, "")
                    tools = segment_cmds(cmd)
                    cls, multi = classify(tools)
                    if cls == "other":
                        for t in tools:
                            other_tokens[t] += 1
                    bt = sz * max(T - cur - 1, 0)
                    bt_by_class[cls] += bt
                    n_by_class[cls] += 1
                    bytes_by_class[cls] += sz
                    if multi:
                        multi_ct[cls] += 1
                    for t in tools & (EXEC | GIT | SEARCH):
                        bt_by_cmd[(cls, t)] += bt
                        n_by_cmd[(cls, t)] += 1
                    sizes.append(sz)
                    sizes_by_class.setdefault(cls, []).append(sz)
                    cmd_repeat[cmd.strip()[:400]] += 1
                    total_calls += 1

tot_bt = sum(bt_by_class.values())
tot_b = sum(bytes_by_class.values())
print(f"Bash calls with a result: {total_calls:,}\n")
print("=== BYTE-TURNS BY COMMAND CLASS (priority execution > git > search) ===")
print(
    f"{'class':14s} {'byte-turns':>17} {'share':>7} {'calls':>7} {'bytes':>13} {'avgB':>8} {'multi-class':>12}"
)
for c in ("search/nav", "execution", "git", "other"):
    bt, n, b = bt_by_class[c], n_by_class[c], bytes_by_class[c]
    print(
        f"{c:14s} {bt:>17,} {100 * bt / max(tot_bt, 1):6.1f}% {n:>7,} {b:>13,} "
        f"{b // max(n, 1):>8,} {multi_ct[c]:>12,}"
    )
print(f"{'TOTAL':14s} {tot_bt:>17,} {100.0:6.1f}% {total_calls:>7,} {tot_b:>13,}")

print("\n=== TOP TOOLS BY BYTE-TURNS (a call counts once per tool present) ===")
for c in ("search/nav", "execution", "git", "other"):
    rows = [(k[1], v) for k, v in bt_by_cmd.items() if k[0] == c]
    if not rows:
        continue
    print(f"  [{c}]")
    for tok, v in sorted(rows, key=lambda x: -x[1])[:8]:
        print(f"     {tok[:22]:22s} {v:>15,}  ({n_by_cmd[(c, tok)]:,} calls)")

print("\n=== residual 'other' -- what the classifier could NOT place ===")
for t, c in other_tokens.most_common(15):
    print(f"     {t[:40]:40s} {c}")

sizes.sort()
n = len(sizes)


def pct(q):
    return sizes[min(int(n * q), n - 1)] if n else 0


tot = sum(sizes)
print("\n=== PER-CALL Bash OUTPUT SIZE DISTRIBUTION ===")
print(f"  calls {n:,}  total {tot:,} B  mean {tot // max(n, 1):,} B")
print(
    f"  p50 {pct(0.50):,}  p75 {pct(0.75):,}  p90 {pct(0.90):,}  p95 {pct(0.95):,}  p99 {pct(0.99):,}  max {sizes[-1] if n else 0:,}"
)
print("\n  share of TOTAL bytes held by the largest calls:")
for frac in (0.001, 0.01, 0.05, 0.10, 0.25, 0.50):
    k = max(int(n * frac), 1)
    print(
        f"    top {frac * 100:5.1f}% ({k:>5,} calls): {100 * sum(sizes[-k:]) / max(tot, 1):5.1f}% of bytes"
    )
print("\n  threshold analysis -- if a wrapper only touched calls ABOVE a size:")
for thr in (1000, 2000, 5000, 10000, 20000):
    above = [s for s in sizes if s > thr]
    print(
        f"    > {thr:>6,} B : touches {len(above):>6,} calls "
        f"({100 * len(above) / max(n, 1):5.1f}%) capturing "
        f"{100 * sum(above) / max(tot, 1):5.1f}% of bytes"
    )
print("\n  per-class p50 / p90 / max:")
for c, arr in sorted(sizes_by_class.items()):
    a = sorted(arr)
    m = len(a)
    print(
        f"    {c:12s} n={m:>6,}  p50 {a[m // 2]:>7,}  p90 {a[min(int(m * 0.9), m - 1)]:>7,}  max {a[-1]:>8,}"
    )

rep = [(c, k) for k, c in cmd_repeat.items() if c > 1]
print("\n=== SAME COMMAND RE-RUN ===")
print(
    f"  distinct command strings {len(cmd_repeat):,}; run>1: {len(rep):,}; "
    f"repeat calls {sum(c for c, _ in rep) - len(rep):,} of {total_calls:,} "
    f"({100 * (sum(c for c, _ in rep) - len(rep)) / max(total_calls, 1):.1f}%)"
)
for c, k in sorted(rep, key=lambda x: -x[0])[:8]:
    print(f"    {c:>4}x  {k[:100]}")
