"""des forward-context-admission -- slice-02 CLI (f-context-consumption-probe).

Charter: docs/product/architecture/ADR-D71-context-consumption-probe.md,
section "Slice-02 -- CONTEXT-family production writer".
Feature-delta: docs/feature/f-context-consumption-probe/feature-delta.md

Reads `.nwave/staging/d71/{context-admission,context-admission-paired}.jsonl`
past a forward-cursor and calls `EventStorePort.append` (never
`append_derived` -- `agent_id` is null for 100% of this hook's population,
so DD-8 would refuse every call) for every row whose `session_id` is
non-null. `context-consumption.jsonl` (the reducer's subagent-leg token-
accounting output) is deliberately NOT read here -- out of this slice's
Contract-Tests scope (feature-delta.md row 555).

A `session_id`-null row is skipped, never appended, and counted
`partition_key_absent` in the run summary; the cursor still advances past
it (a permanently-null `session_id` would loop forever if retried). A
re-run past an already-advanced cursor forwards zero rows (idempotent
no-op). An absent spool file is a clean zero-work exit, not an error. A
corrupt/unreadable cursor file makes the forwarder refuse to run rather
than guess a start offset. A row `EventStorePort.append` refuses (e.g.
`InvalidScope` for a malformed `scope` value) is not forwarded and the
cursor does not advance past it, so it is retried on the next run.

Cursor-advance ordering (idempotency, feature-delta.md Failure Behaviour
table): the cursor for one row is persisted only AFTER that row's
`EventStorePort.append` call returns successfully (or, for a
`session_id`-null row, only after the skip is decided -- no write is ever
attempted for it). If the process dies between a successful `append()` and
the cursor write that follows it, the NEXT run re-appends that same row --
a duplicate ledger record, never a lost one. This is the deliberate,
documented choice per the dispatch instruction ("meglio riscrivere un
record che perderlo"): duplication is observable and cheap to dedupe later,
silent loss is not.

`reduction_key`/`reduction_seq`/`reducer_version` are stripped from the
forwarded payload even though the D71 paired-row schema always carries
them (the reducer's OWN bookkeeping fields, D71-owned, per the ADR's
Consequences section: "the store's DD-7/DD-8 reduction/dedup machinery is
NOT exercised for D71's CONTEXT-family data"). Forwarding `reduction_key`
verbatim would make `UnifiedEventStoreAdapter.read()`'s own row-shape gate
misclassify the row as DERIVED (its own reserved-key convention, unrelated
to D71) and, missing `agent_id`, drop it out of `result.records` entirely
instead of preserving it as a PRIMARY row -- defeating the round-trip
contract this component exists to satisfy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.adapters.driven.logging.at_completion_ledger import LedgerIntegrityViolation
from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.telemetry_paths import LedgerFamily
from des.ports.driven_ports.event_store_port import (
    EventRecord,
    InvalidScope,
    PartitionKeyRequired,
)


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort

#: Spool filenames the forwarder reads, relative to `.nwave/staging/d71/`
#: (ADR-D71 Slice-02 Decision). `context-consumption.jsonl` (the reducer's
#: subagent-leg token-accounting output) is deliberately excluded -- out of
#: this slice's Contract-Tests scope (feature-delta.md row 555).
ADMISSION_SPOOL_FILENAME = "context-admission.jsonl"
PAIRED_SPOOL_FILENAME = "context-admission-paired.jsonl"
CURSOR_FILENAME = "forward-cursor.json"

#: Keys the forwarder computes/supplies itself (`scope`, `event`) or which
#: collide by name with the store's OWN DD-7/DD-8 reserved dedup-gate keys
#: (`reduction_key` -- see module docstring). Stripped from the row before
#: it rides through as `EventRecord.fields` payload.
_EXCLUDED_FIELD_NAMES = frozenset({"scope", "event", "reduction_key"})

#: `EventStorePort.append` refusals for a row the forwarder believed was
#: well-formed (Failure Behaviour table, feature-delta.md): a genuine
#: store-side refusal, distinct from the permanent `partition_key_absent`
#: skip decided before `append()` is ever called.
_APPEND_REFUSAL_EXCEPTIONS = (
    InvalidScope,
    PartitionKeyRequired,
    LedgerIntegrityViolation,
)


class _CorruptCursorError(Exception):
    """The cursor file exists but could not be parsed as a JSON object."""

    def __init__(self, cursor_path: Path, cause: Exception) -> None:
        self.cursor_path = cursor_path
        self.cause = cause
        super().__init__(
            f"WHAT: cursor file at {cursor_path} is corrupt/unreadable. "
            f"WHY: {cause}. "
            f"HOW: delete {cursor_path} to re-forward from the start -- "
            "idempotent, since append() on an already-forwarded row "
            "produces a duplicate record, not a corruption."
        )


class _RowRejectedError(Exception):
    """`EventStorePort.append` refused a row the forwarder believed well-formed."""

    def __init__(self, filename: str, row: dict[str, object], cause: Exception) -> None:
        self.filename = filename
        self.row = row
        self.cause = cause
        super().__init__(
            f"WHAT: EventStorePort.append refused a row from {filename} "
            f"({cause.__class__.__name__}: {cause}). "
            "WHY: a genuine store-side refusal for a row this forwarder's "
            "own pre-check did not anticipate. "
            "HOW: fix the row and re-run -- the cursor was NOT advanced "
            f"past it, so it will be retried. row={row!r}"
        )


def _emit(payload: dict[str, object], output: OutputPort) -> None:
    """Emit exactly one single-line JSON object through the injected sink."""
    output.emit_line(json.dumps(payload))


def _spool_dir(repo_root: Path) -> Path:
    return repo_root / ".nwave" / "staging" / "d71"


def _load_cursor(cursor_path: Path) -> dict[str, int]:
    if not cursor_path.is_file():
        return {}
    try:
        raw: Any = json.loads(cursor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _CorruptCursorError(cursor_path, exc) from exc
    if not isinstance(raw, dict):
        raise _CorruptCursorError(
            cursor_path,
            ValueError(f"expected a JSON object, got {type(raw).__name__}"),
        )
    return raw


def _save_cursor(cursor_path: Path, cursor: dict[str, int]) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(cursor), encoding="utf-8")


def _row_event_record(row: dict[str, object]) -> EventRecord | None:
    """Build the `EventRecord` for one spool row, or `None` when the row's
    `session_id` is null -- the caller counts that as `partition_key_absent`
    and never calls `append()` for it (see module docstring)."""
    session_id = row.get("session_id")
    if session_id is None:
        return None
    scope = row.get("scope") or "session"
    event = str(row.get("kind"))
    fields = {k: v for k, v in row.items() if k not in _EXCLUDED_FIELD_NAMES}
    return EventRecord(
        family=LedgerFamily.CONTEXT,
        event=event,
        scope=str(scope),
        partition_key=str(session_id),
        agent_id=row.get("agent_id"),
        fields=fields,
    )


def _forward_all(repo_root: Path) -> dict[str, object]:
    """Forward every eligible spool row into `LedgerFamily.CONTEXT`."""
    spool_dir = _spool_dir(repo_root)
    cursor_path = spool_dir / CURSOR_FILENAME
    cursor = _load_cursor(cursor_path)
    adapter = UnifiedEventStoreAdapter(project_root=repo_root)

    forwarded = 0
    partition_key_absent = 0

    for filename in (ADMISSION_SPOOL_FILENAME, PAIRED_SPOOL_FILENAME):
        file_path = spool_dir / filename
        if not file_path.is_file():
            continue
        lines = file_path.read_text(encoding="utf-8").splitlines()
        offset = cursor.get(filename, 0)
        for index in range(offset, len(lines)):
            row = json.loads(lines[index])
            record = _row_event_record(row)
            if record is None:
                partition_key_absent += 1
                cursor[filename] = index + 1
                _save_cursor(cursor_path, cursor)
                continue
            try:
                adapter.append(record)
            except _APPEND_REFUSAL_EXCEPTIONS as exc:
                raise _RowRejectedError(filename, row, exc) from exc
            forwarded += 1
            cursor[filename] = index + 1
            _save_cursor(cursor_path, cursor)

    return {"forwarded": forwarded, "partition_key_absent": partition_key_absent}


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """CLI entry point -- forward the D71 spool into the unified event store.

    ``output`` mirrors the sibling ``event_store_probe.main``/
    ``event_store_query.main`` convention: an in-process acceptance test
    injects ``CapturingOutput`` instead of the real terminal sink (Mandate
    13 L2 default -- no interpreter fork needed to observe emitted output).
    """
    parser = argparse.ArgumentParser(
        prog="des forward-context-admission",
        description=(
            "Forward .nwave/staging/d71/{context-admission,"
            "context-admission-paired}.jsonl rows past their cursor into "
            "LedgerFamily.CONTEXT via EventStorePort.append."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        required=True,
        type=Path,
        help=(
            "The target repository root whose .nwave/staging/d71/ spool is forwarded."
        ),
    )
    args = parser.parse_args(argv)
    sink = output if output is not None else StdoutOutput()

    try:
        summary = _forward_all(args.repo_root)
    except _CorruptCursorError as exc:
        _emit(
            {
                "event": "ContextAdmissionForwardCursorCorrupt",
                "cursor_path": str(exc.cursor_path),
                "message": str(exc),
            },
            sink,
        )
        return 1
    except _RowRejectedError as exc:
        _emit(
            {
                "event": "ContextAdmissionForwardRowRejected",
                "filename": exc.filename,
                "row": exc.row,
                "message": str(exc),
            },
            sink,
        )
        return 1

    _emit({"event": "ContextAdmissionForwardResult", **summary}, sink)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
