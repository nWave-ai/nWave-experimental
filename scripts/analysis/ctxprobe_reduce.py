#!/usr/bin/env python3
"""D71 context-consumption reducer -- deterministic, re-runnable, Python-only.

NOT THE CANONICAL REDUCER. The canonical one is
`scripts/telemetry/context_consumption_reduce.py` -- chartered by ADR-D71,
AT-covered, and the only one whose output shape the D80 store expects. This
file is a salvaged probe kept for its measurement history.

Both default into `.nwave/staging/d71/`, and their filenames differ by ONE
CHARACTER: this one writes `context_consumption.jsonl` (UNDERSCORE), the
canonical one writes `context-consumption.jsonl` (HYPHEN). Tell records apart
by `reducer_version` -- `"d71-reducer-1.0.0"` here, `"1"` canonical -- never
by the filename you believe you opened. Whether this file should be retired
now that its discovery, aggregate, and transcript-derived-identity
capabilities have been ported into the canonical reducer with tests is an
open decision, recorded in the f-context-consumption-probe feature-delta.

Reduces Claude Code subagent transcripts to `context_consumption` records in
the shape frozen with lane-store (node D80), written to `.nwave/staging/d71/`.

Same transcripts in => same records out, byte for byte. No external tool, no
network, no git. Streams every file line by line: the largest transcript seen
is 914 MB and reduces in ~80 s at ~38 MB peak RSS.

ACCOUNTING METHOD (binding, verified empirically):
  * Dedup by `requestId`, MAX on every usage field. A raw sum overcounts ~2.34x.
  * Never read `subagent_tokens` -- it omits cache-read and has been seen off
    by 11x and 2160x.
  * Chain law: cache_read[n] == cache_read[n-1] + cache_creation[n-1] on every
    non-compaction turn. `input_tokens` is the UNCACHED SUFFIX and is NOT part
    of the chain. Verified 34,165 hold / 1,129 drift over 35,295 turns (96.8%);
    the drifts are real context-compaction events and are COUNTED, never
    smoothed away.

GDP-6 / GDP-8: an unreadable or unparseable transcript yields a record with
`determination: "could_not_verify"` and a reason -- never a silent zero. The
could-not-verify count reaches the aggregate.

Usage:
    ctxprobe_reduce.py [TRANSCRIPT_ROOT ...] [--out DIR] [--summary]
    # with no root, discovers ~/.claude*/projects/*/*/subagents/
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
REDUCER_VERSION = "d71-reducer-1.0.0"
KIND = "context_consumption"
DEFAULT_OUT = Path(".nwave/staging/d71")


# ---------------------------------------------------------------- reduction


def _fold_usage(path: Path) -> tuple[OrderedDict, str | None, str | None, int]:
    """Fold a transcript into per-requestId usage. Returns (rows, session, agent, bad).

    `bad` counts unparseable lines. A file that yields zero valid rows is the
    could-not-verify case; a file with some bad lines still reduces on the rest.
    """
    rows: OrderedDict[str, dict] = OrderedDict()
    session_id: str | None = None
    agent_id: str | None = None
    bad = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                bad += 1
                continue
            if not isinstance(rec, dict):
                bad += 1
                continue
            session_id = session_id or rec.get("sessionId")
            agent_id = agent_id or rec.get("agentId")
            if rec.get("type") != "assistant":
                continue
            rid = rec.get("requestId")
            msg = rec.get("message")
            if not rid or not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            cur = rows.setdefault(rid, {"in": 0, "cw": 0, "cr": 0, "out": 0})
            cur["in"] = max(cur["in"], usage.get("input_tokens") or 0)
            cur["cw"] = max(cur["cw"], usage.get("cache_creation_input_tokens") or 0)
            cur["cr"] = max(cur["cr"], usage.get("cache_read_input_tokens") or 0)
            cur["out"] = max(cur["out"], usage.get("output_tokens") or 0)
    return rows, session_id, agent_id, bad


def _agent_name(path: Path) -> str | None:
    """Lane name from the filename, or None when the file is hash-named only."""
    stem = path.stem
    if not stem.startswith("agent-a"):
        return None
    body = stem[len("agent-a") :]
    if "-" not in body:
        return None  # pure hash, no human lane name
    return body.rsplit("-", 1)[0]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reduce_transcript(path: Path) -> dict:
    """One transcript -> one `context_consumption` record. Never raises."""
    base = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "ts": _ts(),
        "reducer_version": REDUCER_VERSION,
        "source_file": str(path),
        "agent_name": _agent_name(path),
    }
    try:
        rows, session_id, agent_id, bad = _fold_usage(path)
    except OSError as exc:
        return {
            **base,
            "session_id": None,
            "agent_id": None,
            "turns": 0,
            "determination": "could_not_verify",
            "could_not_verify_reason": f"unreadable: {type(exc).__name__}: {exc}",
        }

    base["session_id"] = session_id
    base["agent_id"] = agent_id

    if not rows:
        return {
            **base,
            "turns": 0,
            "determination": "could_not_verify",
            "could_not_verify_reason": (
                f"no valid assistant/usage records ({bad} unparseable lines)"
            ),
        }

    vals = list(rows.values())
    turns = len(vals)
    t0 = vals[0]
    prefix0 = t0["cr"] + t0["cw"]
    cr_total = sum(v["cr"] for v in vals)
    drift = sum(1 for a, b in itertools.pairwise(vals) if b["cr"] != a["cr"] + a["cw"])
    fixed = min(prefix0 * (turns - 1), cr_total)

    # Idempotent re-emission. A null agent_id makes the record INELIGIBLE for
    # reduction-keyed dedup: hashing a constant null would collapse every
    # null-agent record in a session onto one key and MAX(seq) would silently
    # discard the rest. Measured 0/296 today, but the main-session transcript
    # has no agentId at all, so this path is load-bearing for a population not
    # yet ingested.
    if agent_id and session_id:
        reduction_key = hashlib.sha256(f"{session_id}|{agent_id}".encode()).hexdigest()
        determination, reason = "measured", None
    else:
        reduction_key = None
        determination = "could_not_verify"
        reason = "agent_id_absent" if not agent_id else "session_id_absent"

    return {
        **base,
        "turns": turns,
        "input_tokens": sum(v["in"] for v in vals),
        "cache_creation_tokens": sum(v["cw"] for v in vals),
        "cache_read_tokens": cr_total,
        "output_tokens": sum(v["out"] for v in vals),
        "prefix_turn0_tokens": prefix0,
        "fixed_reread_tokens": fixed,
        "accrued_reread_tokens": cr_total - fixed,
        "chain_identity_drift": drift,
        "unparseable_lines": bad,
        "reduction_key": reduction_key,
        "reduced_through_request": next(reversed(rows)),
        "reduction_seq": turns,
        "determination": determination,
        "could_not_verify_reason": reason,
    }


# ---------------------------------------------------------------- discovery


def discover_roots() -> list[Path]:
    out = []
    for prof in sorted(Path.home().glob(".claude*")):
        projects = prof / "projects"
        if not projects.is_dir():
            continue
        out.extend(sorted(p for p in projects.glob("*/*/subagents") if p.is_dir()))
    return out


def transcripts(roots: list[Path]) -> list[Path]:
    seen, out = set(), []
    for r in roots:
        cand = [r] if r.is_file() else sorted(r.glob("*.jsonl"))
        for p in cand:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(p)
    return out


# ------------------------------------------------------------------- report


def summarise(records: list[dict]) -> dict:
    ok = [r for r in records if r["determination"] == "measured"]
    cnv = [r for r in records if r["determination"] != "measured"]
    agg = {
        "records": len(records),
        "measured": len(ok),
        "could_not_verify": len(cnv),  # GDP-8: reaches the aggregate
        "turns": sum(r.get("turns", 0) for r in ok),
        "input_tokens": sum(r.get("input_tokens", 0) for r in ok),
        "cache_creation_tokens": sum(r.get("cache_creation_tokens", 0) for r in ok),
        "cache_read_tokens": sum(r.get("cache_read_tokens", 0) for r in ok),
        "output_tokens": sum(r.get("output_tokens", 0) for r in ok),
        "fixed_reread_tokens": sum(r.get("fixed_reread_tokens", 0) for r in ok),
        "accrued_reread_tokens": sum(r.get("accrued_reread_tokens", 0) for r in ok),
        "chain_identity_drift": sum(r.get("chain_identity_drift", 0) for r in ok),
    }
    uniq = agg["input_tokens"] + agg["cache_creation_tokens"]
    agg["unique_admitted_tokens"] = uniq
    agg["reentry_multiplier"] = (
        round(agg["cache_read_tokens"] / uniq, 2) if uniq else None
    )
    agg["cache_read_over_output"] = (
        round(agg["cache_read_tokens"] / agg["output_tokens"], 2)
        if agg["output_tokens"]
        else None
    )
    cr = agg["cache_read_tokens"]
    agg["fixed_share_pct"] = (
        round(100 * agg["fixed_reread_tokens"] / cr, 1) if cr else None
    )
    return agg


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="subagents/ dirs or .jsonl files (default: auto-discover)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output dir (default {DEFAULT_OUT})",
    )
    ap.add_argument(
        "--summary", action="store_true", help="print the aggregate to stdout"
    )
    ap.add_argument(
        "--no-write",
        action="store_true",
        help="compute and summarise without writing records",
    )
    args = ap.parse_args(argv)

    roots = args.roots or discover_roots()
    if not roots:
        print("no transcript roots found", file=sys.stderr)
        return 2
    files = transcripts(roots)
    if not files:
        print(f"no .jsonl transcripts under {len(roots)} root(s)", file=sys.stderr)
        return 2

    records = [reduce_transcript(p) for p in files]
    # Deterministic order: same input set => same file, byte for byte.
    records.sort(key=lambda r: r["source_file"])

    if not args.no_write:
        args.out.mkdir(parents=True, exist_ok=True)
        dest = args.out / "context_consumption.jsonl"
        with dest.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"wrote {len(records)} records -> {dest}", file=sys.stderr)

    agg = summarise(records)
    if args.summary or args.no_write:
        print(json.dumps(agg, indent=2, sort_keys=True))
    if agg["could_not_verify"]:
        print(
            f"NOTE: {agg['could_not_verify']} of {agg['records']} transcripts "
            f"could not be verified and are EXCLUDED from the totals above.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
