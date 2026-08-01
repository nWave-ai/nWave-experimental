#!/usr/bin/env python3
"""Which externally-supplied transcript fields are SAFE as join keys?

lane-store's new envelope rule: "a field supplied by an external producer is
not a join key until its uniqueness is MEASURED." That rule is only
enforceable if someone measures the candidates. `tool_use_id` already failed
(the literal "SessionStart" recurs). This checks every other field anyone
might reach for, so the next lane does not rediscover the class one instance
at a time.

For each candidate: total occurrences, distinct values, and the worst
offenders (values carried by more than one distinct record).
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


paths = sys.argv[1:]
CANDIDATES = [
    "uuid",
    "requestId",
    "agentId",
    "sessionId",
    "promptId",
    "parentUuid",
    "toolUseID",
    "leafUuid",
    "sourceToolUseID",
    "sourceToolAssistantUUID",
]

counts = {c: Counter() for c in CANDIDATES}
# distinct (type,line-identity) per value, to tell "same record repeated" from
# "different records colliding"
distinct_records = {c: defaultdict(set) for c in CANDIDATES}

files = []
for p in paths:
    if os.path.isdir(p):
        files.extend(
            sorted(
                os.path.join(p, f)
                for f in [p.name for p in Path(p).iterdir()]
                if f.endswith(".jsonl")
            )
        )
    else:
        files.append(p)

for path in files:
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"!! INDETERMINATE {path}: {e}", file=sys.stderr)
        continue
    with fh:
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
            scope = rec.get("type", "?")
            # attachments hide their identity one level down
            att = rec.get("attachment")
            atype = att.get("type") if isinstance(att, dict) else None
            for c in CANDIDATES:
                v = rec.get(c)
                if v is None and isinstance(att, dict):
                    v = att.get(c)
                if v is None or not isinstance(v, str):
                    continue
                counts[c][v] += 1
                distinct_records[c][v].add((scope, atype, rec.get("uuid")))

print(f"files scanned: {len(files)}\n")
print(f"{'field':26s} {'occurrences':>12} {'distinct':>10} {'collisions':>11}  verdict")
for c in CANDIDATES:
    total = sum(counts[c].values())
    if not total:
        continue
    distinct = len(counts[c])
    # a value is a COLLISION when >1 genuinely different record carries it
    coll = [v for v, recs in distinct_records[c].items() if len(recs) > 1]
    verdict = (
        "SAFE as join key" if not coll else f"UNSAFE -- {len(coll)} colliding value(s)"
    )
    print(f"{c:26s} {total:>12,} {distinct:>10,} {len(coll):>11,}  {verdict}")

print("\n=== colliding values, per field ===")
for c in CANDIDATES:
    coll = sorted(
        ((len(recs), v) for v, recs in distinct_records[c].items() if len(recs) > 1),
        reverse=True,
    )
    if not coll:
        continue
    print(f"\n  [{c}] {len(coll)} colliding value(s)")
    for n, v in coll[:8]:
        print(f"     {n:>5} distinct records share value {v[:70]!r}")
