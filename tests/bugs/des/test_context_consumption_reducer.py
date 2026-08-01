"""Acceptance tests -- D71 `context_consumption` REDUCER (component 2 of 2).

Feature: f-context-consumption-probe, slice-01. Full design:
`docs/feature/f-context-consumption-probe/feature-delta.md` +
`docs/product/architecture/ADR-D71-context-consumption-probe.md`.

SCOPE: `scripts/telemetry/context_consumption_reduce.py` (CREATE_NEW), a new
stdlib-only, `des`-independent, offline reducer with two legs:

  1. SUBAGENT leg (`reduce_transcript_stream` / `reduce_transcripts_directory`)
     -- streams `subagents/agent-*.jsonl` transcripts, dedups `type:
     assistant` records by `requestId` (MAX), emits `context_consumption`.
  2. PAIRING leg (`pair_admission_records`) -- streams the MAIN-SESSION
     transcript's `hook_success`/`hook_additional_context` attachments and
     emits `context_admission_paired`.

MEASURED-FACT override for the pairing leg (dispatch, 2026-07-29,
overriding the feature-delta's earlier `toolUseID`-keyed description where
they conflict): `toolUseID` is NOT a per-hook key -- one SessionStart
`toolUseID` is shared by 4 distinct hook commands, and the literal value
`"SessionStart"` recurs 11 times across the live corpus. The pairing leg
therefore joins a `context_admission_paired` record to a `context_admission`
input record on `stdout_sha256` (sha256 of `hook_success.stdout`,
recomputed by the reducer and compared against the value the EMITTER
already recorded honestly at write time) -- never on `toolUseID`. Pairing
is PARTIAL BY CONSTRUCTION (measured 54-55/277 on the live corpus): an
unpaired admission is the EXPECTED case (`could_not_verify` /
`pairing_unavailable`), never an error and never silently dropped. A join
key that resolves to more than one candidate is COUNTED
(`join_key_collision_count`) and surfaced, never silently resolved to one
of N colliding rows.

Driving port (Mandate 16, no-direct-domain-testing): `reduce_transcript_
stream`, `reduce_transcripts_directory`, and `pair_admission_records` are
the exact composition-root driving-port targets the DESIGN wave's
Contract-Tests table names for this leaf, single-responsibility script
(`## Wave: DESIGN / [REF] Architecture & Contract Tests`) -- there is no
deeper internal layering to violate; these ARE this artifact's application-
service methods (Architecture of Reference, "Driving... in-process call").
Called IN-PROCESS via direct import, per the L2 default. The single
`@walking_skeleton` scenario for this FEATURE drives the standalone CLI
entry `main(argv)` via subprocess -- the one genuine process-boundary proof
that the offline tool is actually invokable as shipped, complementing the
emitter's already-wired subprocess coverage in
`test_context_admission_emitter.py` / the pre-existing
`test_orchestrator_affordance_refresh_independent.py`.

RED-for-right-reason: every driving-port function in
`scripts/telemetry/context_consumption_reduce.py` is a Mandate-7 RED
scaffold (`__SCAFFOLD__ = True`) whose body unconditionally raises
`AssertionError("... not yet implemented -- RED scaffold ...")`. Module-
level imports below name ONLY the stable scaffold module (already on disk)
-- never a not-yet-existing module -- so collection never raises; every
scenario's own body raises/propagates a semantic `AssertionError` at
execution time, per the in-process active-RED pattern (P1-P4,
`nw-distill-red-scaffolding`).
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.telemetry.context_consumption_reduce import (
    discover_transcript_roots,
    pair_admission_records,
    reduce_transcript_stream,
    reduce_transcripts_directory,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_REDUCER_SCRIPT = _REPO_ROOT / "scripts" / "telemetry" / "context_consumption_reduce.py"


# ===========================================================================
# Shared fixture-construction helpers
# ===========================================================================


def _assistant_line(
    request_id: str,
    *,
    input_tokens: int,
    cache_creation: int,
    cache_read: int,
    output_tokens: int,
) -> dict[str, object]:
    return {
        "type": "assistant",
        "requestId": request_id,
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output_tokens,
            }
        },
    }


def _write_jsonl(path: Path, lines: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line) + "\n")


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_3_turn_transcript() -> list[dict[str, object]]:
    """Hand-computed, chain-law-clean 3-turn transcript.

    turn0: cache_creation=1000, cache_read=0
    turn1: cache_creation=200,  cache_read=1000  (== 0 + 1000, no drift)
    turn2: cache_creation=50,   cache_read=1200  (== 1000 + 200, no drift)

    prefix_turn0_tokens = cache_read[0] + cache_creation[0] = 1000
    cache_read_total = 0 + 1000 + 1200 = 2200
    fixed_reread_tokens = min(1000 * (3-1), 2200) = min(2000, 2200) = 2000
    accrued_reread_tokens = 2200 - 2000 = 200
    """
    return [
        _assistant_line(
            "req-a", input_tokens=5, cache_creation=1000, cache_read=0, output_tokens=20
        ),
        _assistant_line(
            "req-b",
            input_tokens=5,
            cache_creation=200,
            cache_read=1000,
            output_tokens=25,
        ),
        _assistant_line(
            "req-c",
            input_tokens=5,
            cache_creation=50,
            cache_read=1200,
            output_tokens=30,
        ),
    ]


# ===========================================================================
# 1. SUBAGENT LEG -- valid transcript -> measured + correct decomposition
#    -- R6
# ===========================================================================


def test_valid_transcript_yields_measured_with_correct_reread_decomposition(
    tmp_path: Path,
) -> None:
    # covers: R6
    # @contract-shape:bounded-change
    transcript = tmp_path / "subagents" / "agent-1.jsonl"
    _write_jsonl(transcript, _clean_3_turn_transcript())

    record = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-1"
    )

    assert record["determination"] == "measured", f"got record={record!r}"
    assert record["prefix_turn0_tokens"] == 1000, f"got record={record!r}"
    assert record["fixed_reread_tokens"] == 2000, f"got record={record!r}"
    assert record["accrued_reread_tokens"] == 200, f"got record={record!r}"
    assert record["turns"] == 3, f"got record={record!r}"


# ===========================================================================
# 2. requestId dedup takes MAX, and re-reducing is idempotent -- R7
# ===========================================================================


def test_request_id_dedup_takes_max_and_reducing_twice_is_idempotent(
    tmp_path: Path,
) -> None:
    # covers: R7
    # @contract-shape:bounded-change
    lines = _clean_3_turn_transcript()
    # A protocol-level duplicate emission of req-a: same prefix values
    # (cache_creation/cache_read identical, per the ADR's verified
    # invariant), but a SMALLER output_tokens -- dedup must take MAX, not
    # the latest-seen value.
    duplicate_req_a = _assistant_line(
        "req-a", input_tokens=5, cache_creation=1000, cache_read=0, output_tokens=8
    )
    transcript = tmp_path / "subagents" / "agent-1.jsonl"
    _write_jsonl(transcript, [lines[0], duplicate_req_a, lines[1], lines[2]])

    first = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-1"
    )
    second = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-1"
    )

    assert first["determination"] == "measured", f"got first={first!r}"
    assert first["prefix_turn0_tokens"] == 1000, (
        f"MAX-dedup on req-a's duplicate must not change the prefix -- "
        f"got first={first!r}"
    )
    assert first["turns"] == 3, (
        "the duplicate req-a line must dedup into ONE turn, not four -- "
        f"got first={first!r}"
    )

    for key in (
        "prefix_turn0_tokens",
        "fixed_reread_tokens",
        "accrued_reread_tokens",
        "turns",
    ):
        assert first[key] == second[key], (
            f"reducing the same transcript twice must be idempotent -- "
            f"key={key!r}, first={first[key]!r}, second={second[key]!r}"
        )


# ===========================================================================
# 3. NEGATIVE -- zero valid requestId-keyed assistant records -> could_not_
#    verify, NEVER an all-zero "measured" record -- R8
# ===========================================================================


@pytest.mark.negative_at
def test_zero_valid_assistant_records_yields_could_not_verify_never_all_zero_measured(
    tmp_path: Path,
) -> None:
    # covers: R8
    # @contract-shape:bounded-change
    transcript = tmp_path / "subagents" / "agent-empty.jsonl"
    _write_jsonl(
        transcript,
        [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "system", "content": "init"},
        ],
    )

    record = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-empty"
    )

    assert record["determination"] == "could_not_verify", (
        "a transcript with zero valid requestId-keyed assistant records "
        f"must NEVER read as 'measured' -- got record={record!r}"
    )
    assert record.get("could_not_verify_reason"), (
        f"the reason must be named -- got record={record!r}"
    )


# ===========================================================================
# 4. Unopenable file yields could_not_verify naming the OSError + path;
#    the run continues to the next file -- R9
# ===========================================================================


def test_unopenable_transcript_yields_could_not_verify_and_the_run_continues(
    tmp_path: Path,
) -> None:
    # covers: R9
    # @contract-shape:bounded-change
    subagents_dir = tmp_path / "subagents"
    subagents_dir.mkdir()

    # A path that LOOKS like a transcript file but is actually a directory
    # -- opening it for read raises IsADirectoryError (an OSError
    # subclass), portably, without chmod/root tricks.
    (subagents_dir / "agent-broken.jsonl").mkdir()

    good_transcript = subagents_dir / "agent-good.jsonl"
    _write_jsonl(good_transcript, _clean_3_turn_transcript())

    records = reduce_transcripts_directory(subagents_dir, session_id="sess-1")

    assert len(records) == 2, (
        f"one bad transcript must not abort the whole directory run -- "
        f"got {len(records)} records: {records!r}"
    )
    by_could_not_verify = [
        r for r in records if r.get("determination") == "could_not_verify"
    ]
    by_measured = [r for r in records if r.get("determination") == "measured"]

    assert len(by_could_not_verify) == 1, f"got records={records!r}"
    assert len(by_measured) == 1, f"got records={records!r}"

    broken_record = by_could_not_verify[0]
    reason = str(broken_record.get("could_not_verify_reason", ""))
    assert "oserror" in reason.lower() or "directory" in reason.lower(), (
        f"the reason must NAME the OSError -- got broken_record={broken_record!r}"
    )
    assert "agent-broken.jsonl" in reason, (
        f"the reason must NAME the path -- got broken_record={broken_record!r}"
    )


# ===========================================================================
# 5. A malformed line is skipped and counted; 99% valid still reduces --
#    R10
# ===========================================================================


def test_a_malformed_line_is_skipped_and_counted_mostly_valid_still_reduces(
    tmp_path: Path,
) -> None:
    # covers: R10
    # @contract-shape:bounded-change
    lines: list[object] = list(_clean_3_turn_transcript())
    lines.insert(1, "{not-well-formed-json,,,")
    lines.insert(2, "")
    transcript = tmp_path / "subagents" / "agent-1.jsonl"
    _write_jsonl(transcript, lines)

    record = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-1"
    )

    assert record["determination"] == "measured", (
        "a mostly-valid transcript (2 malformed lines among otherwise "
        f"valid ones) must still reduce -- got record={record!r}"
    )
    assert record.get("malformed_line_count", 0) >= 1, (
        f"malformed lines must be COUNTED, not silently dropped -- got "
        f"record={record!r}"
    )


# ===========================================================================
# 6. Chain-identity-law violation increments drift, still emits measured
#    -- R11
# ===========================================================================


def test_chain_identity_violation_increments_drift_but_still_emits_measured(
    tmp_path: Path,
) -> None:
    # covers: R11
    # @contract-shape:bounded-change
    lines = [
        _assistant_line(
            "req-a", input_tokens=5, cache_creation=1000, cache_read=0, output_tokens=20
        ),
        # Chain law expects cache_read == 0 + 1000 == 1000; this turn
        # carries cache_read=1 -- a genuine drift (compaction/eviction).
        _assistant_line(
            "req-b", input_tokens=5, cache_creation=50, cache_read=1, output_tokens=25
        ),
    ]
    transcript = tmp_path / "subagents" / "agent-1.jsonl"
    _write_jsonl(transcript, lines)

    record = reduce_transcript_stream(
        transcript, session_id="sess-1", agent_name="crafter", agent_id="agent-1"
    )

    assert record["determination"] == "measured", (
        "the drift is the signal, never a fatal error -- the record must "
        f"still be measured -- got record={record!r}"
    )
    assert record.get("chain_identity_drift", 0) >= 1, (
        f"the chain-law violation must increment chain_identity_drift -- "
        f"got record={record!r}"
    )


# ===========================================================================
# 7. STREAMING INVARIANT -- never .read()/.readlines() a transcript
#    handle whole; a genuine `for line in fh` streaming loop exists --
#    R15
# ===========================================================================


def test_reducer_streams_transcripts_never_loads_a_transcript_whole(
    tmp_path: Path,
) -> None:
    # covers: R15
    # @contract-shape:unbounded-preservation
    source = _REDUCER_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_REDUCER_SCRIPT))

    target_functions = {
        "reduce_transcript_stream",
        "reduce_transcripts_directory",
        "pair_admission_records",
    }
    function_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in target_functions
    ]
    assert len(function_nodes) == len(target_functions), (
        f"expected all of {sorted(target_functions)!r} defined in "
        f"{_REDUCER_SCRIPT} -- found {[n.name for n in function_nodes]!r}"
    )

    for node in function_nodes:
        segment = ast.get_source_segment(source, node) or ""
        assert ".read(" not in segment and ".readlines(" not in segment, (
            f"{node.name} must NEVER call .read()/.readlines() on a "
            f"transcript handle (largest real transcript measured 914 MB) "
            f"-- forbidden call found in its source"
        )

    # The streaming loop itself is asserted only on the functions that
    # actually OPEN a transcript. Requiring the literal `for line in` in
    # every function above would forbid one of them delegating to another --
    # which is what a single implementation of the streaming guarantee looks
    # like. What must hold is the PROPERTY (nothing reads a transcript
    # whole, asserted for all three above) plus a real streaming loop
    # wherever a handle is opened.
    for name in ("reduce_transcript_stream", "pair_admission_records"):
        node = next(n for n in function_nodes if n.name == name)
        segment = ast.get_source_segment(source, node) or ""
        assert ".open(" in segment, (
            f"{name} is expected to be a transcript-opening function -- no "
            f"`.open(` found, so this assertion is checking the wrong "
            f"function and must be re-targeted, not deleted"
        )
        assert "for line in" in segment, (
            f"{name} opens a transcript handle, so it must stream it with a "
            f"genuine `for line in <handle>:` loop -- none found"
        )


# ===========================================================================
# 8. PAIRING LEG, NEGATIVE -- an unpairable hook_success yields could_not_
#    verify/pairing_unavailable, never a fabricated bytes_admitted -- R12
# ===========================================================================


@pytest.mark.negative_at
def test_unpairable_admission_yields_could_not_verify_pairing_unavailable(
    tmp_path: Path,
) -> None:
    # covers: R12
    # @contract-shape:bounded-change
    admission_records = [
        {
            "kind": "context_admission",
            "session_id": "sess-1",
            "stdout_sha256": _sha256_hex('{"orphan": true}'),
            "total_bytes_offered": 500,
        }
    ]
    main_transcript = tmp_path / "main-session.jsonl"
    # The transcript carries NO hook_success whose stdout hashes to the
    # admission record's stdout_sha256 -- the EXPECTED, non-anomalous
    # unpaired case (measured 54-55/277 pair on the live corpus).
    _write_jsonl(
        main_transcript,
        [
            {"type": "hook_success", "toolUseID": "tu-1", "stdout": '{"unrelated": 1}'},
        ],
    )

    paired = pair_admission_records(
        main_transcript, admission_records, session_id="sess-1"
    )

    assert len(paired) == 1, f"got paired={paired!r}"
    record = paired[0]
    assert record["determination"] == "could_not_verify", f"got record={record!r}"
    assert record.get("could_not_verify_reason") == "pairing_unavailable", (
        f"got record={record!r}"
    )
    assert record.get("bytes_admitted") is None, (
        "an unpairable admission must NEVER carry a fabricated "
        f"bytes_admitted -- got record={record!r}"
    )


# ===========================================================================
# 9. PAIRING LEG, NEGATIVE -- a colliding join key is COUNTED and
#    surfaced, never silently resolved to one of N colliding rows -- R13
# ===========================================================================


@pytest.mark.negative_at
def test_colliding_join_key_is_counted_and_surfaced_never_silently_resolved(
    tmp_path: Path,
) -> None:
    # covers: R13
    # @contract-shape:bounded-change
    stdout_text = '{"hookSpecificOutput": {"hookEventName": "SessionStart"}}'
    admission_records = [
        {
            "kind": "context_admission",
            "session_id": "sess-1",
            "stdout_sha256": _sha256_hex(stdout_text),
            "total_bytes_offered": 400,
        }
    ]
    main_transcript = tmp_path / "main-session.jsonl"
    # The MEASURED collision: the literal toolUseID "SessionStart" recurs
    # -- TWO hook_additional_context attachments claim to be the admitted
    # content for the SAME matching hook_success.
    _write_jsonl(
        main_transcript,
        [
            {
                "type": "hook_success",
                "toolUseID": "SessionStart",
                "stdout": stdout_text,
            },
            {
                "type": "hook_additional_context",
                "toolUseID": "SessionStart",
                "content": "first candidate admitted content",
            },
            {
                "type": "hook_additional_context",
                "toolUseID": "SessionStart",
                "content": "second, DIFFERENT candidate admitted content",
            },
        ],
    )

    paired = pair_admission_records(
        main_transcript, admission_records, session_id="sess-1"
    )

    assert len(paired) == 1, f"got paired={paired!r}"
    record = paired[0]
    assert record.get("join_key_collision_count", 0) >= 2, (
        f"the collision must be COUNTED -- got record={record!r}"
    )
    assert record["determination"] == "could_not_verify", (
        "a colliding join key must NEVER be silently resolved by keeping "
        f"one of N colliding rows -- got record={record!r}"
    )
    reason = str(record.get("could_not_verify_reason", "")).lower()
    assert "collision" in reason, f"got record={record!r}"


# ===========================================================================
# 10. PAIRING LEG -- a genuine unique pair yields
#     truncated = bytes_admitted < bytes_offered -- R14
# ===========================================================================


def test_genuine_unique_pair_yields_truncated_flag(tmp_path: Path) -> None:
    # covers: R14
    # @contract-shape:bounded-change
    stdout_text = '{"hookSpecificOutput": {"additionalContext": "x" * 1000}}'
    admitted_content = "x" * 42  # far shorter -- the harness truncated it
    admission_records = [
        {
            "kind": "context_admission",
            "session_id": "sess-1",
            "stdout_sha256": _sha256_hex(stdout_text),
            "total_bytes_offered": len(stdout_text.encode("utf-8")),
        }
    ]
    main_transcript = tmp_path / "main-session.jsonl"
    _write_jsonl(
        main_transcript,
        [
            {"type": "hook_success", "toolUseID": "tu-unique", "stdout": stdout_text},
            {
                "type": "hook_additional_context",
                "toolUseID": "tu-unique",
                "content": admitted_content,
            },
        ],
    )

    paired = pair_admission_records(
        main_transcript, admission_records, session_id="sess-1"
    )

    assert len(paired) == 1, f"got paired={paired!r}"
    record = paired[0]
    expected_bytes_admitted = len(admitted_content.encode("utf-8"))
    assert record.get("bytes_admitted") == expected_bytes_admitted, (
        f"got record={record!r}"
    )
    assert record.get("truncated") is True, (
        f"bytes_admitted ({expected_bytes_admitted}) < bytes_offered "
        f"({admission_records[0]['total_bytes_offered']}) must yield "
        f"truncated=True -- got record={record!r}"
    )


# ===========================================================================
# 11. WALKING SKELETON (the ONE subprocess-e2e for this FEATURE) --
#     the standalone reducer CLI is genuinely invokable end-to-end
# ===========================================================================


@pytest.mark.negative_at
def test_discovery_counts_a_symlink_aliased_transcript_store_exactly_once(
    tmp_path: Path,
) -> None:
    # covers: R7
    # @contract-shape:bounded-change
    # Three Claude profiles share this machine and the alt profiles'
    # `projects/` are SYMLINKS to the main profile's, so a naive glob over
    # `~/.claude*/projects/*/*/subagents` returns each REAL directory once
    # per profile (measured 93 globbed vs 28 distinct). Reducing the aliases
    # would multiply every token total in the aggregate -- the same
    # transcript counted N times is exactly the inflated number this
    # instrument exists to prevent.
    fake_home = tmp_path / "home"
    real_projects = fake_home / ".claude" / "projects"
    subagents = real_projects / "proj" / "session" / "subagents"
    subagents.mkdir(parents=True)
    _write_jsonl(subagents / "agent-1.jsonl", _clean_3_turn_transcript())

    for alias in (".claude-alt", ".claude-alt3"):
        alias_profile = fake_home / alias
        alias_profile.mkdir(parents=True)
        (alias_profile / "projects").symlink_to(real_projects)

    globbed = sorted(fake_home.glob(".claude*/projects/*/*/subagents"))
    assert len(globbed) == 3, (
        "the fixture must reproduce the aliasing -- a naive glob is expected "
        f"to see the same directory 3 times, got {globbed!r}"
    )

    roots = discover_transcript_roots(home=fake_home)

    assert len(roots) == 1, (
        "the same subagents/ directory reached through 3 profile symlinks "
        f"must be discovered ONCE -- got {len(roots)}: {roots!r}"
    )


@pytest.mark.negative_at
def test_an_agent_id_absent_record_is_ineligible_for_dedup_and_says_so(
    tmp_path: Path,
) -> None:
    # covers: R7
    # @contract-shape:bounded-change
    # Keying a record on a stringified `None` would collapse EVERY
    # identity-less record in a run onto one key, and a downstream reader
    # taking MAX(reduction_seq) would silently discard all but one of them.
    # `reduction_key: null` says "do not dedup me" instead.
    transcript = tmp_path / "no-identity.jsonl"
    _write_jsonl(transcript, _clean_3_turn_transcript())

    record = reduce_transcript_stream(transcript, session_id="sess-1")

    assert record.get("agent_id") is None, (
        "this transcript states no agentId and the filename carries none -- "
        f"got record={record!r}"
    )
    assert record.get("reduction_key") is None, (
        "a record with no agent_id must carry reduction_key: null -- NEVER a "
        f"key built from a stringified None -- got record={record!r}"
    )


def test_a_transcript_that_states_its_own_identity_beats_the_asserted_one(
    tmp_path: Path,
) -> None:
    # covers: R7
    # @contract-shape:bounded-change
    # A sessionId/agentId IN the transcript is a measured fact; the value on
    # the command line is the operator's assertion about the file. The
    # measured one wins, and the key becomes a real dedup key.
    transcript = tmp_path / "agent-alane-abc123.jsonl"
    lines = [
        dict(line, sessionId="MEASURED-SESSION", agentId="MEASURED-AGENT")
        for line in _clean_3_turn_transcript()
    ]
    _write_jsonl(transcript, lines)

    record = reduce_transcript_stream(transcript, session_id="ASSERTED-SESSION")

    assert record.get("session_id") == "MEASURED-SESSION", f"got record={record!r}"
    assert record.get("agent_id") == "MEASURED-AGENT", f"got record={record!r}"
    assert record.get("agent_name") == "lane", (
        f"the lane name is embedded in the filename -- got record={record!r}"
    )
    assert (
        record.get("reduction_key")
        == hashlib.sha256(b"MEASURED-SESSION|MEASURED-AGENT").hexdigest()
    ), f"got record={record!r}"


def test_the_summary_excludes_unverifiable_records_and_says_how_many(
    tmp_path: Path,
) -> None:
    # covers: R8
    # @contract-shape:bounded-change
    # The aggregate is the answer to "how many times did the same bytes
    # re-enter". A total that quietly folded in unverifiable records would
    # be the same class of lie this instrument exists to catch, so the
    # excluded count reaches the aggregate as its own field.
    subagents_dir = tmp_path / "subagents"
    _write_jsonl(subagents_dir / "agent-1.jsonl", _clean_3_turn_transcript())
    (subagents_dir / "agent-2.jsonl").write_text("{not json\n", encoding="utf-8")
    out_ledger = tmp_path / "context-consumption.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(_REDUCER_SCRIPT),
            "--subagents-dir",
            str(subagents_dir),
            "--session-id",
            "sess-1",
            "--out",
            str(out_ledger),
            "--summary",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"stderr={result.stderr!r}"
    aggregate = json.loads(result.stdout)
    assert aggregate["records"] == 2, f"got aggregate={aggregate!r}"
    assert aggregate["measured"] == 1, f"got aggregate={aggregate!r}"
    assert aggregate["could_not_verify"] == 1, (
        "the number of records EXCLUDED from the totals must reach the "
        f"aggregate -- got aggregate={aggregate!r}"
    )
    # 3 clean turns: unique admitted = input + cache_creation; cache_read is
    # the same bytes arriving again, so the multiplier is a real ratio.
    assert isinstance(aggregate["reentry_multiplier"], float), (
        f"got aggregate={aggregate!r}"
    )
    assert "1 of 2" in result.stderr, (
        f"the exclusion must also be stated in words -- got {result.stderr!r}"
    )


@pytest.mark.negative_at
def test_the_cli_pairs_one_record_per_parent_admission_not_per_ledger_row(
    tmp_path: Path,
) -> None:
    # covers: R12
    # @contract-shape:bounded-change
    # The emitter writes a FLAT block: one `context_admission` PARENT row
    # plus N `context_admission_payload` CHILD rows, every one of them
    # carrying the same `stdout_sha256` (that is how a child joins its
    # parent). A reader that treats every ledger ROW as an admission
    # therefore emits N+1 paired records for ONE firing -- a silent
    # (N+1)x inflation of exactly the count this instrument exists to make
    # honest. The rows that are NOT admissions must be reported, not
    # silently discarded: a ledger of children only must not look like a
    # ledger of no admissions.
    stdout_text = '{"hookSpecificOutput": {"additionalContext": "x"}}'
    sha = _sha256_hex(stdout_text)
    admission_ledger = tmp_path / "context-admission.jsonl"
    _write_jsonl(
        admission_ledger,
        [
            {
                "kind": "context_admission",
                "session_id": "sess-1",
                "stdout_sha256": sha,
                "total_bytes_offered": 300,
            },
            {"kind": "context_admission_payload", "stdout_sha256": sha, "path": "a.md"},
            {"kind": "context_admission_payload", "stdout_sha256": sha, "path": "b.md"},
            {"kind": "context_admission_payload", "stdout_sha256": sha, "path": "c.md"},
        ],
    )
    main_transcript = tmp_path / "main-session.jsonl"
    _write_jsonl(
        main_transcript,
        [
            {"type": "hook_success", "toolUseID": "tu-1", "stdout": stdout_text},
            {
                "type": "hook_additional_context",
                "toolUseID": "tu-1",
                "content": "x" * 42,
            },
        ],
    )
    out_ledger = tmp_path / "context-consumption.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(_REDUCER_SCRIPT),
            "--session-id",
            "sess-1",
            "--main-transcript",
            str(main_transcript),
            "--admission-records",
            str(admission_ledger),
            "--out",
            str(out_ledger),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = [
        json.loads(ln)
        for ln in out_ledger.read_text(encoding="utf-8").splitlines()
        if ln
    ]
    paired = [r for r in records if r.get("kind") == "context_admission_paired"]
    assert len(paired) == 1, (
        "a 4-row ledger block describing ONE firing must yield exactly ONE "
        "paired record -- one per PARENT admission, never one per ledger "
        f"row -- got {len(paired)}: {paired!r}"
    )
    assert paired[0].get("bytes_admitted") == 42, f"got paired={paired[0]!r}"

    assert "3" in result.stderr, (
        "the 3 non-admission rows the reader skipped must be SURFACED (a "
        "ledger of children only must not look like a ledger of no "
        f"admissions) -- got stderr={result.stderr!r}"
    )


@pytest.mark.walking_skeleton
def test_walking_skeleton_reducer_cli_produces_a_context_consumption_ledger(
    tmp_path: Path,
) -> None:
    # covers: R6
    # @contract-shape:bounded-change
    subagents_dir = tmp_path / "subagents"
    _write_jsonl(subagents_dir / "agent-1.jsonl", _clean_3_turn_transcript())
    out_ledger = tmp_path / "context-consumption.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(_REDUCER_SCRIPT),
            "--subagents-dir",
            str(subagents_dir),
            "--session-id",
            "sess-1",
            "--out",
            str(out_ledger),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        "the standalone reducer CLI must run end-to-end and exit 0 -- got "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    assert out_ledger.exists(), (
        f"expected the CLI to write {out_ledger} -- stderr={result.stderr!r}"
    )
    lines = [ln for ln in out_ledger.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 1, f"got lines={lines!r}"
    record = json.loads(lines[0])
    assert record.get("determination") == "measured", f"got record={record!r}"
