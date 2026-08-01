"""Regression: `UnifiedEventStoreAdapter.append`/`.append_derived` erase the
GDP-8 third state on read (D71 lane-d71deliver finding, `/nw-bugfix` lane).

RCA (already done -- reproduced here, not redone): neither `append` nor
`append_derived` stamps `envelope_generation` into the fields dict handed to
`AtCompletionLedger.append_event`. `_classify_line`
(`src/des/adapters/driven/logging/unified_event_store_adapter.py:415`) routes
a row to `LegacyEnvelopeNormalizer.normalize` whenever `"envelope_generation"
not in row` -- true for EVERY record either method writes today, so a
genuinely `scope="session"`, `determination="could_not_verify"` record is
silently overlaid to `scope="feature"`, `determination="measured"` on read
(`legacy_envelope_normalizer.py:50-55` unconditionally overlays those three
keys). The write itself is honest; the loss is entirely at the read boundary.

Design-grounded pin (authoritative over any looser prose elsewhere): per
`docs/feature/f-context-consumption-probe/feature-delta.md` line 556 ("Reuse
Analysis" / `UnifiedEventStoreAdapter` envelope-generation repair row), the
regression test asserts a record written via `append()`/`append_derived()`
and read back via `read()` in the SAME process is classified into
`primary_new_rows`/`derived_rows` (the NEW-envelope branch), NEVER
`legacy_rows` -- i.e. `_classify_line` routes it past `"envelope_generation"
not in row"` -- and that the record's own `scope`/`determination` fields
survive the round trip verbatim, byte-for-byte. Line 567 additionally names a
SECOND axis (GDP-8 witness corollary): a fresh process re-opening the raw
ledger file must see the on-disk row itself carry the `envelope_generation`
key -- covered here by re-reading the raw JSONL directly rather than only
through the port.

Deliberately NOT asserted here (documented, not silently dropped): the
dispatching envelope's prose additionally asked for
`ReadResult.could_not_verify_count == 1` on the could-not-verify PRIMARY
scenario. Empirically verified NOT achievable by the design-authorized fix
(feature-delta.md's own "Mechanism the bugfix must apply" text: "confined to
UnifiedEventStoreAdapter... zero change to `_classify_line`'s branch
condition" -- i.e. add exactly one key to the fields dict, nothing else).
`_classify_primary_new_row` counts EVERY row that passes the `agent_id` gate
into `primary_new_rows`, and `read()`'s `measured_count` is `len(primary_new_
rows)` unconditionally -- it never inspects a primary row's own
`determination` field (confirmed by direct probe: a hand-crafted on-disk row
carrying `envelope_generation="unified"` + `determination="could_not_verify"`
reads back as `measured_count=1, could_not_verify_count=0`, IDENTICAL to the
pre-fix legacy-routed number for this same record -- the `determination`
field was never the source of `could_not_verify_count` for a primary row, in
either the buggy or the fixed world). Making that literal assertion true
would require NEW classify-time semantics (primary rows self-report
determination) that feature-delta.md does not authorize and that would widen
this bugfix into new adapter behavior -- out of a `/nw-bugfix` lane's scope.
The two properties feature-delta.md DOES pin (classification branch +
verbatim scope/determination survival) are exactly what this file asserts.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.domain.telemetry_paths import LedgerFamily, ledger_path
from des.ports.driven_ports.event_store_port import EventRecord, ReductionKey


def test_append_read_roundtrip_preserves_determination_and_scope(
    tmp_path: Path,
) -> None:
    """PRIMARY write via `append()`, read back via `read()`, SAME process.

    A could-not-verify, session-scoped record must round-trip through the
    real port with `determination`/`scope` byte-for-byte intact, classified
    as a NEW-envelope row -- never silently normalized into a `feature`-
    scoped, `measured` legacy row.
    """
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    record = EventRecord(
        family=LedgerFamily.CONTEXT,
        event="context_admission_paired",
        scope="session",
        partition_key="sess-x",
        agent_id="ag-1",
        fields={
            "determination": "could_not_verify",
            "could_not_verify_reason": "tool_use_id_not_id_shaped",
            "tool_use_id": "hook-9cb337da-239e-45e3-adcf-453cf9ecadea",
        },
    )

    adapter.append(record)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-x")

    assert len(result.records) == 1, (
        f"expected exactly one record read back -- got {result.records!r}"
    )
    row = result.records[0]

    assert row.get("envelope_generation") != "legacy", (
        "the row must NOT be routed through LegacyEnvelopeNormalizer -- "
        f"got envelope_generation={row.get('envelope_generation')!r}, "
        f"row={row!r}"
    )
    assert row.get("determination") == "could_not_verify", (
        "determination must survive the append()->read() round trip "
        f"verbatim -- got {row.get('determination')!r}, row={row!r}"
    )
    assert row.get("scope") == "session", (
        "scope must survive the append()->read() round trip verbatim -- "
        f"got {row.get('scope')!r}, row={row!r}"
    )


def test_append_derived_read_roundtrip_preserves_determination_and_scope(
    tmp_path: Path,
) -> None:
    """DERIVED write via `append_derived()`, read back via `read()`, SAME
    process -- same round-trip pin, the DERIVED sibling of the PRIMARY test
    above. `agent_id` is non-null (DD-8 eligibility) and `reduction_seq` is
    supplied so the row is well-formed on the derived-branch gate
    (ADR-EVT-002) -- this test isolates the envelope_generation defect, not
    the separate DD-7 required-keys gate.
    """
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    record = EventRecord(
        family=LedgerFamily.CONTEXT,
        event="context_consumption",
        scope="session",
        partition_key="sess-y",
        agent_id="ag-2",
        fields={
            "determination": "could_not_verify",
            "could_not_verify_reason": "pairing_unavailable",
            "reduction_seq": 1,
        },
    )
    reduction = ReductionKey(reduction_key="sess-y:ag-2", reducer_version="v1")

    adapter.append_derived(record, reduction)
    result = adapter.read(LedgerFamily.CONTEXT, "sess-y")

    assert len(result.records) == 1, (
        f"expected exactly one record read back -- got {result.records!r}"
    )
    row = result.records[0]

    assert row.get("envelope_generation") != "legacy", (
        "the derived row must NOT be routed through LegacyEnvelopeNormalizer "
        f"-- got envelope_generation={row.get('envelope_generation')!r}, "
        f"row={row!r}"
    )
    assert row.get("determination") == "could_not_verify", (
        "determination must survive the append_derived()->read() round trip "
        f"verbatim -- got {row.get('determination')!r}, row={row!r}"
    )
    assert row.get("scope") == "session", (
        "scope must survive the append_derived()->read() round trip "
        f"verbatim -- got {row.get('scope')!r}, row={row!r}"
    )


def test_on_disk_row_carries_envelope_generation_key_second_axis(
    tmp_path: Path,
) -> None:
    """GDP-8 witness corollary (feature-delta.md line 567): a FRESH read of
    the raw ledger file -- independent of `UnifiedEventStoreAdapter.read()`
    -- must show the on-disk row itself carrying `envelope_generation`, not
    only the in-process `ReadResult`. Corroborates the fix on a second axis
    distinct from the round-trip pin above.
    """
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    record = EventRecord(
        family=LedgerFamily.CONTEXT,
        event="context_admission_paired",
        scope="session",
        partition_key="sess-z",
        agent_id="ag-3",
        fields={"determination": "could_not_verify"},
    )

    adapter.append(record)

    path = ledger_path(tmp_path, LedgerFamily.CONTEXT, "sess-z")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1, f"expected exactly one on-disk line -- got {lines!r}"
    on_disk_row = json.loads(lines[0])

    assert "envelope_generation" in on_disk_row, (
        "the RAW on-disk row must carry the envelope_generation key -- "
        f"got on_disk_row={on_disk_row!r}"
    )
