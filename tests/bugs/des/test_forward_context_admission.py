# @feature-f-context-consumption-probe @slice-02
"""Acceptance tests -- D71 `forward_context_admission` (slice-02, forwarder).

Feature: f-context-consumption-probe, slice-02. Full design:
`docs/feature/f-context-consumption-probe/feature-delta.md` +
`docs/product/architecture/ADR-D71-context-consumption-probe.md`, section
"Slice-02 -- CONTEXT-family production writer".

SCOPE: `src/des/cli/forward_context_admission.py` (NEW `des`-importing CLI).
Reads `.nwave/staging/d71/{context-admission,context-admission-paired}.jsonl`
past a forward-cursor and calls `EventStorePort.append` (never
`append_derived` -- `agent_id` is null for 100% of this hook's population,
DD-8 would refuse it) for every row whose `session_id` is non-null.
`context-consumption.jsonl` (the reducer's subagent-leg token-accounting
output) is deliberately NOT read by this component -- out of Contract-Tests
row 555's scope.

DEPENDENCY, ALREADY LANDED: this AT set was BLOCKED (feature-delta.md row
555, Slice Plan annotation) on `UnifiedEventStoreAdapter.append`/
`.append_derived` stamping `envelope_generation` before delegating to
`AtCompletionLedger.append_event` -- without it, EVERY write is routed
through `LegacyEnvelopeNormalizer` on read, which unconditionally overlays
`scope="feature"`, `determination="measured"`. Landed via `/nw-bugfix`,
commit `086f02c00ce4ac844678b336cee3732262ab6fbc`
(`tests/bugs/des/test_unified_event_store_envelope_generation_roundtrip.py`),
merged into this worktree. Verified directly by this dispatch before
authoring below (`UnifiedEventStoreAdapter(...).append(...)` then
`.read(...)` in the SAME process preserves `determination='could_not_verify'
scope='session' envelope='unified'`) -- this file's own round-trip scenarios
below are the SAME pin, driven through the CLI + real spool instead of the
adapter directly.

**THE ONE RULE THIS FILE CANNOT BREAK** (catalogued, deliberately-NOT-repaired
defect: `read-result-aggregate-counts-a-declared-could-not-verify-row-as-
measured`, `defects.md`). `ReadResult.measured_count`/`.could_not_verify_count`
NEVER inspect a primary row's own `determination` field -- `measured_count` is
`len(primary_new_rows)` UNCONDITIONALLY (`unified_event_store_adapter.py:
341-346`). Measured: writing 1 `determination='measured'` row + 3
`determination='could_not_verify'` rows into one CONTEXT-family partition
yields `measured_count=4, could_not_verify_count=0` -- a 75% could-not-verify
rate by row, 0% by counter. Every scenario below therefore asserts by
FILTERING `result.records` on each row's own `determination` field -- NEVER
by reading `result.measured_count`/`result.could_not_verify_count`. An AT on
`could_not_verify_count > 0` cannot pass (post-defect); an AT on `== 0` would
pass even if the forwarder wrote garbage -- infalsifiable in both directions.
See `_rows_with_determination` below; every determination-bearing assertion
in this file routes through it.

Driving port (Mandate 16, no-direct-domain-testing; Mandate 2, IN-PROCESS
default): every scenario drives the REAL `forward_context_admission.main
(argv, output=CapturingOutput())` in-process (no interpreter fork -- the
feature's one `@walking_skeleton` is already claimed by the reducer CLI in
`test_context_consumption_reducer.py`, Mandate 2's "ONE per feature", so no
second is declared here) against a REAL `UnifiedEventStoreAdapter` on
`tmp_path` -- no double, per feature-delta.md's own Unobservability
Declaration slice-02 addendum ("what a test double for EventStorePort makes
unobservable").

SPOOL FIXTURES are hand-written JSONL matching the EXACT shape the real
emitter (`orchestrator_affordance_refresh.py`, slice-01, GREEN) and reducer
(`context_consumption_reduce.py`, slice-01, GREEN) already produce -- this is
the INPUT boundary the forwarder reads, not the CONTEXT-family LEDGER the
forwarder WRITES. The ledger itself is NEVER hand-constructed here: every
determination/scope assertion below reads back through the REAL
`UnifiedEventStoreAdapter.read()`, exactly the discipline this feature's own
prior defect (D80 read-side tests hand-constructing rows with
`envelope_generation` already baked in) was caught for missing one layer
down.

RED-for-right-reason: `forward_context_admission._forward_all` is a DISTILL
scaffold that raises a bare `AssertionError` uncaught (module docstring).
Every scenario below therefore fails on that SAME semantic AssertionError,
never a collection-time `ImportError` (the module, `add_repo_root_argument`,
`UnifiedEventStoreAdapter`, `CapturingOutput` all import cleanly today).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.cli import forward_context_admission
from des.domain.telemetry_paths import LedgerFamily
from des.testing.output_capture import CapturingOutput


_FORWARDER_SCRIPT = Path(forward_context_admission.__file__)
_SPOOL_DIRNAME = Path(".nwave") / "staging" / "d71"


# ===========================================================================
# Shared fixture-writing + driving + assertion helpers
# ===========================================================================


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _spool_dir(repo_root: Path) -> Path:
    return repo_root / _SPOOL_DIRNAME


def _run(repo_root: Path) -> tuple[int, CapturingOutput]:
    """Drive the REAL forwarder in-process (Mandate 2 L2 default)."""
    cap = CapturingOutput()
    exit_code = None
    try:
        exit_code = forward_context_admission.main(
            ["--repo-root", str(repo_root)], output=cap
        )
    except AssertionError:
        raise
    return exit_code, cap


def _admission_parent_row(
    *, session_id: str | None, scope: str = "session", stdout_sha256: str = "sha-a"
) -> dict[str, object]:
    """One `context_admission` PARENT row, matching the real emitter's shape
    (`orchestrator_affordance_refresh.py::_build_admission_records`)."""
    return {
        "schema_version": 1,
        "kind": "context_admission",
        "ts": 1_700_000_000.0,
        "session_id": session_id,
        "correlation_id": "corr-parent-1",
        "agent_name": None,
        "agent_id": None,
        "event": "SessionStart",
        "hook": "orchestrator_affordance_refresh",
        "tool_use_id": None,
        "payload_count": 1,
        "dropped_asset_count": 0,
        "total_bytes_offered": 300,
        "bytes_admitted": None,
        "stdout_sha256": stdout_sha256,
        "feature_id": None,
        "scope": scope,
    }


def _paired_row(
    *,
    session_id: str,
    determination: str,
    tool_use_id: str | None,
    could_not_verify_reason: str | None = None,
    bytes_admitted: int | None = None,
    truncated: bool | None = None,
) -> dict[str, object]:
    """One `context_admission_paired` row, matching the real reducer's shape
    (`context_consumption_reduce.py::_pair_one_admission_record` /
    `_could_not_verify_paired_record`) -- note: NO `scope` key (D71's own
    frozen schema does not carry one on this record kind; the forwarder
    itself assigns `scope="session"` when composing the `EventRecord`)."""
    return {
        "schema_version": 1,
        "kind": "context_admission_paired",
        "ts": 1_700_000_100.0,
        "session_id": session_id,
        "tool_use_id": tool_use_id,
        "bytes_admitted": bytes_admitted,
        "truncated": truncated,
        "determination": determination,
        "could_not_verify_reason": could_not_verify_reason,
        "join_key_collision_count": 0,
        "reduction_key": f"{session_id}:{tool_use_id}",
        "reduction_seq": 1,
        "reducer_version": 1,
    }


def _rows_with_determination(
    records: list[dict[str, object]], value: str
) -> list[dict]:
    """Filter `result.records` by each row's OWN `determination` field.

    NEVER read `ReadResult.measured_count`/`.could_not_verify_count` --
    those aggregate counters do not inspect `determination` at all
    (catalogued defect, module docstring). This helper is the ONLY sound way
    this file measures a determination split.
    """
    return [r for r in records if r.get("determination") == value]


# ===========================================================================
# 1. ROUND-TRIP -- a forwarded row preserves its OWN scope/determination,
#    never clobbered to feature/measured -- R16
# ===========================================================================


def test_a_forwarded_paired_could_not_verify_row_round_trips_with_determination_and_scope_preserved(
    tmp_path: Path,
) -> None:
    # covers: R16
    # @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission-paired.jsonl",
        [
            _paired_row(
                session_id="sess-round-trip",
                determination="could_not_verify",
                tool_use_id="hook-9cb337da-239e-45e3-adcf-453cf9ecadea",
                could_not_verify_reason="pairing_unavailable",
            )
        ],
    )

    exit_code, _cap = _run(tmp_path)

    assert exit_code == 0, "forwarding a well-formed row must exit 0"
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-round-trip")
    could_not_verify_rows = _rows_with_determination(result.records, "could_not_verify")
    assert len(could_not_verify_rows) == 1, (
        f"expected exactly one could_not_verify row on this partition -- got "
        f"records={result.records!r}"
    )
    row = could_not_verify_rows[0]
    assert row.get("scope") == "session", (
        f"scope must survive the spool->append()->read() round trip "
        f"verbatim -- got {row.get('scope')!r}, row={row!r}"
    )
    assert row.get("envelope_generation") != "legacy", (
        f"the row must not be routed through LegacyEnvelopeNormalizer -- "
        f"got envelope_generation={row.get('envelope_generation')!r}"
    )


def test_a_forwarded_admission_parent_row_round_trips_with_session_scope_preserved(
    tmp_path: Path,
) -> None:
    # covers: R16
    # @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission.jsonl",
        [_admission_parent_row(session_id="sess-parent", scope="session")],
    )

    exit_code, _cap = _run(tmp_path)

    assert exit_code == 0
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-parent")
    assert result.records, (
        f"expected >=1 record forwarded for sess-parent -- got zero, result={result!r}"
    )
    for row in result.records:
        assert row.get("scope") == "session", (
            f"every forwarded admission row must preserve scope='session' "
            f"-- got {row.get('scope')!r}, row={row!r}"
        )


# ===========================================================================
# 2. REGRESSION PIN -- a hook-<uuid>-shaped tool_use_id (Correction 8's
#    widened DD-6 shape) must NEVER be misclassified could_not_verify by the
#    round trip -- R23
# ===========================================================================


def test_a_hook_uuid_shaped_tool_use_id_paired_row_is_never_misclassified_could_not_verify_by_the_round_trip(
    tmp_path: Path,
) -> None:
    # covers: R23
    # @negative_at @contract-shape:bounded-change
    # Correction 8 (docs/feature/unified-event-store/feature-delta.md):
    # 635/636 of this hook's own hook_additional_context records carry the
    # hook-<uuid> id-space; DD-6's declared shape was widened specifically
    # to admit it after measuring a 100% could_not_verify rate would
    # otherwise be a FAILING state, not an acceptable degrade. This pins
    # that a genuinely MEASURED pair carrying a hook-<uuid> tool_use_id
    # survives the forward+read round trip as measured -- never silently
    # reclassified could_not_verify because of its id's shape.
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission-paired.jsonl",
        [
            _paired_row(
                session_id="sess-hook-uuid",
                determination="measured",
                tool_use_id="hook-3fa1c2b0-1111-4a22-9c3d-abcdef012345",
                bytes_admitted=42,
                truncated=False,
            )
        ],
    )

    exit_code, _cap = _run(tmp_path)

    assert exit_code == 0
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-hook-uuid")
    measured_rows = _rows_with_determination(result.records, "measured")
    assert len(measured_rows) == 1, (
        f"a genuinely measured hook-<uuid> pair must round-trip as "
        f"measured, never demoted to could_not_verify by its id's shape -- "
        f"got records={result.records!r}"
    )
    assert measured_rows[0].get("tool_use_id", "").startswith("hook-"), (
        f"the hook-<uuid> tool_use_id itself must survive the round trip "
        f"verbatim -- got {measured_rows[0].get('tool_use_id')!r}"
    )


# ===========================================================================
# 3. NEGATIVE -- a null session_id is skipped, counted partition_key_absent,
#    cursor still advances -- R17
# ===========================================================================


@pytest.mark.negative_at
def test_a_session_id_null_row_is_skipped_and_counted_partition_key_absent(
    tmp_path: Path,
) -> None:
    # covers: R17
    # @negative_at @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission.jsonl",
        [_admission_parent_row(session_id=None)],
    )

    exit_code, cap = _run(tmp_path)

    assert exit_code == 0, (
        "a session_id-null row is a structurally-unforwardable row, not an "
        "error -- the run must still exit 0"
    )
    assert "partition_key_absent" in cap.captured_text(), (
        f"the skip must be counted and named 'partition_key_absent' in the "
        f"run summary (Failure Behaviour table) -- got {cap.captured_text()!r}"
    )
    # The row must never have been appended anywhere queryable -- there is
    # no partition key to query it under, which is itself the observable.
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-parent")
    assert not result.records, (
        f"a null-session_id row must never leak into an unrelated "
        f"partition -- got records={result.records!r}"
    )


# ===========================================================================
# 4. IDEMPOTENCY -- a re-run past an already-advanced cursor forwards zero
#    new rows -- R18
# ===========================================================================


def test_a_rerun_past_an_already_advanced_cursor_forwards_zero_new_rows_idempotent(
    tmp_path: Path,
) -> None:
    # covers: R18
    # @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission.jsonl",
        [_admission_parent_row(session_id="sess-idempotent")],
    )

    first_exit, _first_cap = _run(tmp_path)
    assert first_exit == 0
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    after_first = adapter.read(LedgerFamily.CONTEXT, "sess-idempotent")
    assert after_first.records, "the first run must forward >=1 row"
    count_after_first = len(after_first.records)

    second_exit, _second_cap = _run(tmp_path)
    assert second_exit == 0, "a re-run past the cursor is a clean no-op, not an error"

    after_second = adapter.read(LedgerFamily.CONTEXT, "sess-idempotent")
    assert len(after_second.records) == count_after_first, (
        f"a re-run past an already-advanced cursor must forward ZERO new "
        f"rows -- record count grew from {count_after_first} to "
        f"{len(after_second.records)}: {after_second.records!r}"
    )


# ===========================================================================
# 5. ZERO CASE -- absent/empty spool is a clean zero-work exit, never an
#    error -- R19
# ===========================================================================


@pytest.mark.parametrize(
    ("prepare", "case_id"),
    [
        pytest.param(lambda repo: None, "directory-absent-entirely"),
        pytest.param(
            lambda repo: _spool_dir(repo).mkdir(parents=True), "directory-empty"
        ),
        pytest.param(
            lambda repo: _write_jsonl(
                _spool_dir(repo) / "context-admission-paired.jsonl",
                [
                    _paired_row(
                        session_id="sess-only-paired",
                        determination="measured",
                        tool_use_id="hook-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        bytes_admitted=10,
                        truncated=False,
                    )
                ],
            ),
            "admission-file-absent-paired-present",
        ),
    ],
)
def test_an_absent_or_empty_spool_is_a_clean_zero_work_exit(
    tmp_path: Path, prepare, case_id: str
) -> None:
    # covers: R19
    # @contract-shape:bounded-change
    prepare(tmp_path)

    exit_code, _cap = _run(tmp_path)

    assert exit_code == 0, (
        f"[{case_id}] nothing-to-forward must be a clean exit(0), never an error"
    )


# ===========================================================================
# 6. NEGATIVE -- a corrupt cursor file makes the forwarder refuse to run
#    rather than guess a start offset -- R20
# ===========================================================================


@pytest.mark.negative_at
def test_a_corrupt_cursor_file_causes_the_forwarder_to_refuse_not_guess_an_offset(
    tmp_path: Path,
) -> None:
    # covers: R20
    # @negative_at @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission.jsonl",
        [_admission_parent_row(session_id="sess-corrupt-cursor")],
    )
    cursor_path = _spool_dir(tmp_path) / forward_context_admission.CURSOR_FILENAME
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text("{not-valid-json", encoding="utf-8")

    exit_code, cap = _run(tmp_path)

    assert exit_code != 0, (
        "a corrupt cursor file must refuse the run (non-zero exit), never "
        "guess a start offset"
    )
    text = cap.captured_text()
    assert str(cursor_path) in text or cursor_path.name in text, (
        f"the refusal must name the cursor path -- got {text!r}"
    )


# ===========================================================================
# 7. NEGATIVE -- EventStorePort.append refuses a row the forwarder believed
#    well-formed (InvalidScope): not forwarded, cursor not advanced, exit
#    non-zero naming the row -- R21
# ===========================================================================


@pytest.mark.negative_at
def test_an_invalid_scope_row_is_not_forwarded_and_the_cursor_does_not_advance_past_it(
    tmp_path: Path,
) -> None:
    # covers: R21
    # @negative_at @contract-shape:bounded-change
    _write_jsonl(
        _spool_dir(tmp_path) / "context-admission.jsonl",
        [_admission_parent_row(session_id="sess-bad-scope", scope="bogus")],
    )

    exit_code, cap = _run(tmp_path)

    assert exit_code != 0, (
        "a row EventStorePort.append refuses (InvalidScope) must exit "
        "non-zero -- it is a genuine store-side refusal, not a clean skip"
    )
    text = cap.captured_text()
    assert "InvalidScope" in text or "bogus" in text, (
        f"the refusal must name the row and the exception -- got {text!r}"
    )
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-bad-scope")
    assert not result.records, (
        f"a row the store refused must never appear as a forwarded record "
        f"-- got records={result.records!r}"
    )


# ===========================================================================
# 8. ARCHITECTURE -- the forwarder never calls append_derived (DD-8:
#    agent_id is null for 100% of this hook's population) -- R22
# ===========================================================================


def test_forwarder_never_calls_append_derived(tmp_path: Path) -> None:
    # covers: R22
    # @contract-shape:unbounded-preservation
    source = _FORWARDER_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_FORWARDER_SCRIPT))

    violations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append_derived"
    ]
    assert not violations, (
        f"forward_context_admission.py must never call .append_derived(...) "
        f"-- agent_id is null for 100% of this hook's population, so DD-8 "
        f"(ReductionKeyIneligible) would refuse every such call -- found "
        f"{len(violations)} call site(s) at line(s) "
        f"{[getattr(v, 'lineno', '?') for v in violations]!r}"
    )
