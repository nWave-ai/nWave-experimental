#!/usr/bin/env python3
"""Two questions v2 left open.

(1) Is there a HARNESS CEILING on Bash output? max was ~29.5 KB in every
    class, which would mean the transcript shows ADMITTED bytes, not PRODUCED
    bytes -- the same offered/admitted boundary found on the hooks.
(2) Within the search/nav class, WHAT is being searched? A structured tool
    (Tsunami) can only replace CODE-STRUCTURAL questions. Reading back one's
    own redirected output is compressible only by the redirect discipline.
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
    "sort",
    "uniq",
    "cut",
    "jq",
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
    "cargo",
    "go",
    "nwave",
    "coverage",
    "python",
    "python3",
}
GIT = {"git", "gh"}
SEPS = re.compile(r"&&|\|\||;|\||\$\(|`|\bdo\b|\bthen\b|\n")
ENV = re.compile(r"^[A-Z_][A-Z0-9_]*=")

SCRATCH = re.compile(r"/tmp/|scratchpad|\.out\b|\.err\b|\.log\b|/tasks/")
TRANSCRIPT = re.compile(r"\.claude(-alt3)?/projects|\.jsonl")
CODE = re.compile(r"\.py\b|\.pyi\b|src/|tests/|scripts/")
DOCS = re.compile(r"\.md\b|docs/|\.yaml\b|\.yml\b|\.json\b")
NWAVE_STATE = re.compile(r"\.nwave/|telemetry|ledger")


def segs(cmd):
    out = set()
    for seg in SEPS.split(cmd):
        s = seg.strip().lstrip("(){ \t")
        if not s:
            continue
        toks = s.split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if ENV.match(t) or t in (
                "sudo",
                "command",
                "exec",
                "time",
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
            if t in ("cd", "timeout"):
                i += 2
                continue
            if t.startswith(("/", "./", "$")):
                t = os.path.basename(t)
            out.add(t.strip("\"'"))
            break
    return out


def cls_of(tools):
    if tools & EXEC:
        return "execution"
    if tools & GIT:
        return "git"
    if tools & SEARCH:
        return "search/nav"
    return "other"


def target_of(cmd):
    if TRANSCRIPT.search(cmd):
        return "transcripts/.jsonl"
    if SCRATCH.search(cmd):
        return "own redirected output (scratchpad/tmp/.out)"
    if NWAVE_STATE.search(cmd):
        return "nwave state (.nwave/ledgers)"
    if CODE.search(cmd):
        return "source code (.py, src/, tests/)"
    if DOCS.search(cmd):
        return "docs/config (.md .yaml .json)"
    return "unclassified"


bt_by_target, n_by_target, b_by_target = Counter(), Counter(), Counter()
sizes = []
big = []
total = 0

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
    tool_by_id, cmd_by_id = {}, {}
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
                        if blk.get("name") == "Bash":
                            cmd_by_id[blk.get("id")] = (blk.get("input") or {}).get(
                                "command"
                            ) or ""
            elif r.get("type") == "user":
                for blk in m.get("content") or []:
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
                    sizes.append(sz)
                    total += 1
                    if sz > 25000:
                        big.append((sz, cmd[:90]))
                    if cls_of(segs(cmd)) != "search/nav":
                        continue
                    tg = target_of(cmd)
                    bt = sz * max(T - cur - 1, 0)
                    bt_by_target[tg] += bt
                    n_by_target[tg] += 1
                    b_by_target[tg] += sz

print("=== (1) IS THERE A HARNESS CEILING ON BASH OUTPUT? ===")
sizes.sort()
n = len(sizes)
print(f"  calls {n:,}   max {sizes[-1]:,} B")
print("  largest 20 results (bytes):")
print("   ", list(sizes[-20:]))
print(
    f"  calls in 25,000-30,000 B band: {sum(1 for s in sizes if 25000 < s <= 30000):,}"
)
print(f"  calls above 30,000 B         : {sum(1 for s in sizes if s > 30000):,}")
print("\n  the largest results and their commands:")
for s, c in sorted(big, reverse=True)[:8]:
    print(f"    {s:>7,} B  {c}")

tb = sum(bt_by_target.values())
print("\n=== (2) SEARCH/NAV CLASS BY TARGET -- what is being searched ===")
print(f"{'target':42s} {'byte-turns':>16} {'share':>7} {'calls':>7} {'bytes':>12}")
for k, v in bt_by_target.most_common():
    print(
        f"{k[:42]:42s} {v:>16,} {100 * v / max(tb, 1):6.1f}% {n_by_target[k]:>7,} {b_by_target[k]:>12,}"
    )
print(f"{'TOTAL search/nav':42s} {tb:>16,}")
