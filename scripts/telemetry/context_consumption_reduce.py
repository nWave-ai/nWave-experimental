#!/usr/bin/env python3
"""Context-consumption REDUCER -- D71 (component 2 of 2).

Full design: `docs/feature/f-context-consumption-probe/feature-delta.md`
("Wave: DESIGN / [REF] Record Schemas", "... Failure Behaviour") +
`docs/product/architecture/ADR-D71-context-consumption-probe.md`.

Two legs, both stdlib-only, zero `des` import, zero external tool:

  1. `reduce_transcript_stream` / `reduce_transcripts_directory` -- stream
     subagent transcript file(s) (`~/.claude/projects/<proj>/<uuid>/
     subagents/agent-*.jsonl`) line by line (never `.read()`/`.readlines()`
     -- observed max transcript size 914 MB), dedup `type: assistant`
     records by `requestId` (MAX, idempotent), and emit one
     `context_consumption` record per transcript.
  2. `pair_admission_records` -- streams the MAIN-SESSION transcript, pairs
     `hook_success`/`hook_additional_context` attachments against
     already-loaded `context_admission` records, and emits one
     `context_admission_paired` record per admission record. MEASURED-FACT
     override (dispatch, 2026-07-29): the join key is `stdout_sha256`
     (recomputed from `hook_success.stdout`), NEVER `tool_use_id` --
     `toolUseID` is measured non-unique (the literal "SessionStart"
     recurs) and is not a per-hook key.

`main(argv)` is the standalone CLI entry (direct script invocation) that
ties both legs together for offline, repo-local use. It is NOT a Claude
Code hook and never ships to an end-user install (see the feature-delta's
Reuse Analysis, Alternative 3).

GDP-6 (degrade LOUD): an unopenable file, a zero-valid-line transcript, or
an unpairable admission always yields `determination: "could_not_verify"`
with a `could_not_verify_reason` naming the cause -- never an all-zero
record that reads as "consumed nothing", never a silent drop. A
chain-identity-law violation (`cache_read[n] != cache_read[n-1] +
cache_creation[n-1]`) increments `chain_identity_drift` and the record is
STILL emitted as `measured` -- the drift is the signal, never smoothed
away. A join-key collision is COUNTED (`join_key_collision_count`) and
surfaced, never silently resolved to one of N colliding rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


REDUCER_VERSION = "1"


def _reduction_key(session_id: str | None, agent_id: str | None) -> str | None:
    """The dedup key, or `None` when either identity is unknown.

    A record whose `session_id` or `agent_id` is absent is INELIGIBLE for
    reduction-keyed dedup: keying it on a stringified `None` would collapse
    every such record in a run onto ONE key, and a downstream reader taking
    MAX(`reduction_seq`) would silently discard all but one of them. `None`
    says "do not dedup me" instead of inventing an identity.
    """
    if not session_id or not agent_id:
        return None
    return hashlib.sha256(f"{session_id}|{agent_id}".encode()).hexdigest()


def _could_not_verify_consumption_record(
    *,
    session_id: str | None,
    agent_name: str | None = None,
    agent_id: str | None = None,
    reason: str,
    malformed_line_count: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": REDUCER_VERSION,
        "kind": "context_consumption",
        "ts": time.time(),
        "session_id": session_id,
        "agent_name": agent_name,
        "agent_id": agent_id,
        "turns": 0,
        "input_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "prefix_turn0_tokens": 0,
        "fixed_reread_tokens": 0,
        "accrued_reread_tokens": 0,
        "chain_identity_drift": 0,
        "determination": "could_not_verify",
        "could_not_verify_reason": reason,
        "reduction_key": _reduction_key(session_id, agent_id),
        "reduced_through_request": None,
        "reduction_seq": 0,
        "reducer_version": REDUCER_VERSION,
        "malformed_line_count": malformed_line_count,
    }


def _finalize_turns_record(
    ordered_usages: list[dict[str, int]],
    malformed_line_count: int,
    last_request_id: str | None,
    *,
    session_id: str | None,
    agent_name: str | None = None,
    agent_id: str | None = None,
) -> dict[str, object]:
    """Pure formula step (no I/O): dedup'd per-turn usages -> one record.

    Chain law: `cache_read[n] == cache_read[n-1] + cache_creation[n-1]`. A
    violation increments `chain_identity_drift` -- named, never swallowed,
    never fatal.
    """
    if not ordered_usages:
        return _could_not_verify_consumption_record(
            session_id=session_id,
            agent_name=agent_name,
            agent_id=agent_id,
            reason="zero_valid_assistant_records",
            malformed_line_count=malformed_line_count,
        )

    turns_count = len(ordered_usages)
    input_tokens = sum(u["input_tokens"] for u in ordered_usages)
    cache_creation_tokens = sum(
        u["cache_creation_input_tokens"] for u in ordered_usages
    )
    cache_read_tokens = sum(u["cache_read_input_tokens"] for u in ordered_usages)
    output_tokens = sum(u["output_tokens"] for u in ordered_usages)

    prefix_turn0_tokens = (
        ordered_usages[0]["cache_read_input_tokens"]
        + ordered_usages[0]["cache_creation_input_tokens"]
    )
    fixed_reread_tokens = min(
        prefix_turn0_tokens * (turns_count - 1), cache_read_tokens
    )
    accrued_reread_tokens = cache_read_tokens - fixed_reread_tokens

    chain_identity_drift = 0
    for i in range(1, turns_count):
        expected = (
            ordered_usages[i - 1]["cache_read_input_tokens"]
            + ordered_usages[i - 1]["cache_creation_input_tokens"]
        )
        if ordered_usages[i]["cache_read_input_tokens"] != expected:
            chain_identity_drift += 1

    return {
        "schema_version": REDUCER_VERSION,
        "kind": "context_consumption",
        "ts": time.time(),
        "session_id": session_id,
        "agent_name": agent_name,
        "agent_id": agent_id,
        "turns": turns_count,
        "input_tokens": input_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "prefix_turn0_tokens": prefix_turn0_tokens,
        "fixed_reread_tokens": fixed_reread_tokens,
        "accrued_reread_tokens": accrued_reread_tokens,
        "chain_identity_drift": chain_identity_drift,
        "determination": "measured",
        "could_not_verify_reason": None,
        "reduction_key": _reduction_key(session_id, agent_id),
        "reduced_through_request": last_request_id,
        "reduction_seq": turns_count,
        "reducer_version": REDUCER_VERSION,
        "malformed_line_count": malformed_line_count,
    }


def _consume_transcript_line(
    stripped_line: str,
    request_order: list[str],
    request_max: dict[str, dict[str, int]],
    observed_identity: dict[str, str | None] | None = None,
) -> bool:
    """Parse one stripped transcript line into the requestId-MAX accumulator.

    Also captures the FIRST `sessionId`/`agentId` seen anywhere in the file
    into `observed_identity` (any record type, not only `assistant` -- the
    ids appear on lines that carry no usage). A measured identity is a fact
    about the transcript; an identity supplied on the command line is the
    operator's assertion about it, so the measured one wins where both
    exist.

    Returns `True` when the line was malformed JSON (caller counts it) --
    `False` for any other line, whether or not it was a usable
    `type: assistant` / `requestId` / `usage` record.
    """
    try:
        payload = json.loads(stripped_line)
    except json.JSONDecodeError:
        return True
    if not isinstance(payload, dict):
        return False
    if observed_identity is not None:
        for source_key, field in (("sessionId", "session_id"), ("agentId", "agent_id")):
            if observed_identity.get(field) is None:
                value = payload.get(source_key)
                if isinstance(value, str) and value:
                    observed_identity[field] = value
    if payload.get("type") != "assistant":
        return False
    request_id = payload.get("requestId")
    usage = payload.get("message", {}).get("usage")
    if not isinstance(request_id, str) or not isinstance(usage, dict):
        return False
    fields = {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cache_creation_input_tokens": int(
            usage.get("cache_creation_input_tokens") or 0
        ),
        "cache_read_input_tokens": int(usage.get("cache_read_input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
    }
    if request_id not in request_max:
        request_order.append(request_id)
        request_max[request_id] = fields
    else:
        existing = request_max[request_id]
        request_max[request_id] = {
            key: max(existing[key], fields[key]) for key in fields
        }
    return False


def _agent_name_from_filename(transcript_path: Path) -> str | None:
    """The human lane name embedded in `agent-a<name>-<hash>.jsonl`, or None.

    A hash-only filename carries no lane name, and `None` says so rather
    than reporting the hash as if it were a name.
    """
    stem = transcript_path.stem
    if not stem.startswith("agent-a"):
        return None
    body = stem[len("agent-a") :]
    if "-" not in body:
        return None
    return body.rsplit("-", 1)[0]


def reduce_transcript_stream(
    transcript_path: Path,
    *,
    session_id: str | None = None,
    agent_name: str | None = None,
    agent_id: str | None = None,
) -> dict[str, object]:
    """Stream ONE subagent transcript -> one `context_consumption` record.

    Never loads the transcript handle whole -- iterates `for line in fh:`
    only (largest real transcript measured 914 MB). An unopenable file
    yields `determination: "could_not_verify"` naming the `OSError` and the
    path; zero valid `requestId`-keyed assistant records does the same,
    naming `"zero_valid_assistant_records"`.

    `session_id`/`agent_id`/`agent_name` are MEASURED from the transcript
    where the transcript states them (`sessionId`/`agentId` fields; the lane
    name from the filename), and fall back to the caller's value only where
    it does not. A record left with no `agent_id` or no `session_id` is
    ineligible for reduction-keyed dedup and says so -- see
    `_reduction_key`.
    """
    try:
        fh = transcript_path.open("r", encoding="utf-8")
    except OSError as exc:
        return _could_not_verify_consumption_record(
            session_id=session_id,
            agent_name=agent_name or _agent_name_from_filename(transcript_path),
            agent_id=agent_id,
            reason=f"{exc.__class__.__name__}: {transcript_path} -- {exc}",
        )

    request_order: list[str] = []
    request_max: dict[str, dict[str, int]] = {}
    observed: dict[str, str | None] = {"session_id": None, "agent_id": None}
    malformed_line_count = 0

    with fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            if _consume_transcript_line(stripped, request_order, request_max, observed):
                malformed_line_count += 1

    ordered_usages = [request_max[rid] for rid in request_order]
    last_request_id = request_order[-1] if request_order else None
    return _finalize_turns_record(
        ordered_usages,
        malformed_line_count,
        last_request_id,
        session_id=observed["session_id"] or session_id,
        agent_name=agent_name or _agent_name_from_filename(transcript_path),
        agent_id=observed["agent_id"] or agent_id,
    )


def reduce_transcripts_directory(
    subagents_dir: Path, *, session_id: str | None = None
) -> list[dict[str, object]]:
    """Reduce every `agent-*.jsonl` under `subagents_dir`, one record per file.

    A single file that cannot be opened, or reduces to zero valid records,
    contributes its own `could_not_verify` record and the run CONTINUES to
    the next file -- never aborts the whole directory on one bad transcript.
    Delegates each file to `reduce_transcript_stream`, so the never-load-a
    -transcript-whole guarantee has exactly ONE implementation to hold.
    """
    return [
        reduce_transcript_stream(
            transcript_path,
            session_id=session_id,
            agent_id=transcript_path.stem,
        )
        for transcript_path in sorted(subagents_dir.glob("agent-*.jsonl"))
    ]


def _pair_one_admission_record(
    admission: dict[str, object],
    hook_successes: list[dict[str, object]],
    hook_contexts: list[dict[str, object]],
    session_id: str,
) -> dict[str, object]:
    target_sha = admission.get("stdout_sha256")
    total_bytes_offered = admission.get("total_bytes_offered")

    matching_successes = [
        hs
        for hs in hook_successes
        if isinstance(hs.get("stdout"), str)
        and hashlib.sha256(hs["stdout"].encode("utf-8")).hexdigest() == target_sha
    ]

    if not matching_successes:
        return _could_not_verify_paired_record(
            session_id=session_id, reason="pairing_unavailable"
        )
    if len(matching_successes) > 1:
        return _could_not_verify_paired_record(
            session_id=session_id,
            reason=(
                "join_key_collision -- multiple hook_success records share "
                "stdout_sha256"
            ),
            collision_count=len(matching_successes),
        )

    tool_use_id = matching_successes[0].get("toolUseID")
    matching_contexts = [
        hc for hc in hook_contexts if hc.get("toolUseID") == tool_use_id
    ]

    if not matching_contexts:
        return _could_not_verify_paired_record(
            session_id=session_id,
            reason="pairing_unavailable",
            tool_use_id=tool_use_id,
        )
    if len(matching_contexts) > 1:
        return _could_not_verify_paired_record(
            session_id=session_id,
            reason=(
                "join_key_collision -- multiple hook_additional_context "
                "records share toolUseID"
            ),
            tool_use_id=tool_use_id,
            collision_count=len(matching_contexts),
        )

    content = matching_contexts[0].get("content", "")
    bytes_admitted = len(str(content).encode("utf-8"))
    truncated = (
        isinstance(total_bytes_offered, int) and bytes_admitted < total_bytes_offered
    )

    return {
        "schema_version": REDUCER_VERSION,
        "kind": "context_admission_paired",
        "ts": time.time(),
        "session_id": session_id,
        "tool_use_id": tool_use_id,
        "bytes_admitted": bytes_admitted,
        "truncated": truncated,
        "determination": "measured",
        "could_not_verify_reason": None,
        "join_key_collision_count": 0,
        "reduction_key": f"{session_id}:{tool_use_id}",
        "reduction_seq": 1,
        "reducer_version": REDUCER_VERSION,
    }


def _could_not_verify_paired_record(
    *,
    session_id: str,
    reason: str,
    tool_use_id: str | None = None,
    collision_count: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": REDUCER_VERSION,
        "kind": "context_admission_paired",
        "ts": time.time(),
        "session_id": session_id,
        "tool_use_id": tool_use_id,
        "bytes_admitted": None,
        "truncated": None,
        "determination": "could_not_verify",
        "could_not_verify_reason": reason,
        "join_key_collision_count": collision_count,
        "reduction_key": f"{session_id}:{tool_use_id}",
        "reduction_seq": 1,
        "reducer_version": REDUCER_VERSION,
    }


def pair_admission_records(
    main_transcript_path: Path,
    admission_records: list[dict[str, object]],
    *,
    session_id: str,
) -> list[dict[str, object]]:
    """Stream the main-session transcript -> one `context_admission_paired`
    record per input `admission_records` entry.

    Pairing is PARTIAL BY CONSTRUCTION (measured 54-55/277 on the live
    corpus): an unpaired admission is the EXPECTED case
    (`could_not_verify`/`pairing_unavailable`), never an error, never
    silently dropped. The join key is `stdout_sha256` (recomputed from
    `hook_success.stdout`), NEVER `tool_use_id` (measured non-unique). A
    join-key collision (either level: multiple `hook_success` records
    sharing the same `stdout_sha256`, or multiple `hook_additional_context`
    records sharing the matched `toolUseID`) is COUNTED via
    `join_key_collision_count` and surfaced -- never silently resolved to
    one of N colliding rows. A genuine unique pair yields
    `truncated = bytes_admitted < bytes_offered`.
    """
    try:
        fh = main_transcript_path.open("r", encoding="utf-8")
    except OSError as exc:
        reason = f"{exc.__class__.__name__}: {main_transcript_path} -- {exc}"
        return [
            _could_not_verify_paired_record(session_id=session_id, reason=reason)
            for _ in admission_records
        ]

    hook_successes: list[dict[str, object]] = []
    hook_contexts: list[dict[str, object]] = []
    with fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            kind = payload.get("type")
            if kind == "hook_success":
                hook_successes.append(payload)
            elif kind == "hook_additional_context":
                hook_contexts.append(payload)

    return [
        _pair_one_admission_record(admission, hook_successes, hook_contexts, session_id)
        for admission in admission_records
    ]


def dedup_by_resolved_path(paths: list[Path]) -> list[Path]:
    """The input paths with every symlink-alias of an already-seen path dropped.

    Order-stable: the FIRST spelling of a path wins, so a caller's explicit
    argument is never displaced by a later alias of the same directory.
    """
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def discover_transcript_roots(home: Path | None = None) -> list[Path]:
    """Every DISTINCT `subagents/` directory under every local Claude profile.

    Three profiles share this machine (`~/.claude`, `~/.claude-alt`,
    `~/.claude-alt3`), so an operator asked to name one root would silently
    measure a fraction of the corpus. But the alt profiles' `projects/` are
    SYMLINKS to the main profile's, so the naive glob returns each real
    directory once per profile -- measured 93 globbed vs 28 distinct on this
    machine, which would multiply every token total in the aggregate by ~3.3.
    Deduping by resolved path is therefore load-bearing, not tidiness: the
    same transcript counted twice is exactly the inflated number this
    instrument exists to prevent.

    Filesystem + stdlib only -- no external tool, no network.
    """
    base = home if home is not None else Path.home()
    roots: list[Path] = []
    for profile in sorted(base.glob(".claude*")):
        projects = profile / "projects"
        if not projects.is_dir():
            continue
        roots.extend(sorted(p for p in projects.glob("*/*/subagents") if p.is_dir()))
    return dedup_by_resolved_path(roots)


def summarise(records: list[dict[str, object]]) -> dict[str, object]:
    """The aggregate that answers "how many times did the same bytes re-enter".

    Totals are computed over `measured` records ONLY, and the number of
    records EXCLUDED for `could_not_verify` reaches the aggregate as its own
    field (GDP-8 third state) -- a total that quietly folded in unverifiable
    records would be the same class of lie this instrument exists to catch.

    `reentry_multiplier` = cache_read / (input + cache_creation): the unique
    admitted tokens are paid once, the cache reads are the SAME bytes
    arriving again, so the ratio is how many extra times the context was
    re-served.
    """
    measured = [r for r in records if r.get("determination") == "measured"]
    could_not_verify = [r for r in records if r.get("determination") != "measured"]

    def total(field: str) -> int:
        return sum(int(r.get(field) or 0) for r in measured)

    aggregate: dict[str, object] = {
        "records": len(records),
        "measured": len(measured),
        "could_not_verify": len(could_not_verify),
        "turns": total("turns"),
        "input_tokens": total("input_tokens"),
        "cache_creation_tokens": total("cache_creation_tokens"),
        "cache_read_tokens": total("cache_read_tokens"),
        "output_tokens": total("output_tokens"),
        "fixed_reread_tokens": total("fixed_reread_tokens"),
        "accrued_reread_tokens": total("accrued_reread_tokens"),
        "chain_identity_drift": total("chain_identity_drift"),
    }
    unique_admitted = total("input_tokens") + total("cache_creation_tokens")
    cache_read = total("cache_read_tokens")
    output_tokens = total("output_tokens")
    aggregate["unique_admitted_tokens"] = unique_admitted
    aggregate["reentry_multiplier"] = (
        round(cache_read / unique_admitted, 2) if unique_admitted else None
    )
    aggregate["cache_read_over_output"] = (
        round(cache_read / output_tokens, 2) if output_tokens else None
    )
    aggregate["fixed_share_pct"] = (
        round(100 * total("fixed_reread_tokens") / cache_read, 1)
        if cache_read
        else None
    )
    return aggregate


def select_admission_parents(
    ledger_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Split a `context-admission.jsonl` block into admissions + the rest.

    The emitter writes ONE `context_admission` PARENT row per firing plus N
    flat CHILD rows (`context_admission_payload`,
    `context_admission_dropped_asset`), every one of them carrying the same
    `stdout_sha256` -- that is how a child joins its parent. A reader that
    treats every ROW as an admission therefore pairs N+1 times per firing
    and inflates the very count this instrument exists to make honest.

    Returns `(parents, ignored_kind_counts)`. The ignored rows are RETURNED,
    not discarded: a caller must be able to say "I read 4 rows and 3 of them
    were not admissions", because a ledger of children only must never look
    like a ledger of no admissions (GDP-6).
    """
    parents: list[dict[str, object]] = []
    ignored: dict[str, int] = {}
    for row in ledger_rows:
        kind = row.get("kind")
        if kind == "context_admission":
            parents.append(row)
            continue
        label = kind if isinstance(kind, str) and kind else "<no-kind>"
        ignored[label] = ignored.get(label, 0) + 1
    return parents, ignored


def main(argv: list[str]) -> int:
    """Standalone offline CLI entry tying both legs together."""
    parser = argparse.ArgumentParser(
        prog="context_consumption_reduce",
        description="Offline D71 context-consumption reducer.",
    )
    parser.add_argument(
        "--subagents-dir",
        type=Path,
        default=None,
        action="append",
        help="a subagents/ directory to reduce (repeatable)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help=(
            "reduce every subagents/ dir under every ~/.claude* profile "
            "instead of naming them (three profiles share this machine)"
        ),
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help=(
            "fallback session id for transcripts that do not state their own; "
            "a sessionId measured IN the transcript always wins"
        ),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--main-transcript", type=Path, default=None)
    parser.add_argument("--admission-records", type=Path, default=None)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print the aggregate (re-entry multiplier, fixed share) to stdout",
    )
    args = parser.parse_args(argv)

    subagent_dirs: list[Path] = list(args.subagents_dir or [])
    if args.discover:
        subagent_dirs.extend(discover_transcript_roots())
    # A named root and a discovered one can be two spellings of the same
    # directory; reducing it twice would double its tokens in the aggregate.
    subagent_dirs = dedup_by_resolved_path(subagent_dirs)

    records: list[dict[str, object]] = []
    for subagents_dir in subagent_dirs:
        records.extend(
            reduce_transcripts_directory(subagents_dir, session_id=args.session_id)
        )

    if args.main_transcript is not None and args.admission_records is not None:
        with args.admission_records.open("r", encoding="utf-8") as fh:
            ledger_rows = [json.loads(line) for line in fh if line.strip()]
        admission_records, ignored_kinds = select_admission_parents(ledger_rows)
        if ignored_kinds:
            detail = ", ".join(
                f"{count} {kind}" for kind, count in sorted(ignored_kinds.items())
            )
            sys.stderr.write(
                f"[context_consumption_reduce] read {len(ledger_rows)} rows from "
                f"{args.admission_records}: {len(admission_records)} "
                f"context_admission parent(s); skipped {detail} (child rows "
                f"join their parent on stdout_sha256 and are not admissions)\n"
            )
        records.extend(
            pair_admission_records(
                args.main_transcript, admission_records, session_id=args.session_id
            )
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")

    if args.summary:
        aggregate = summarise(records)
        sys.stdout.write(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
        if aggregate["could_not_verify"]:
            sys.stderr.write(
                f"[context_consumption_reduce] {aggregate['could_not_verify']} of "
                f"{aggregate['records']} records could not be verified and are "
                f"EXCLUDED from the totals above\n"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
