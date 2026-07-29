# @feature-declared-facts-reachable-recorded
# @slice-05
"""slice-05 (F1 write-side): token-usage observations carry join keys.

Today `AGENT_USAGE_OBSERVED` audit rows carry none of `feature_id`/`slice_id`/
`stage`/`request_id` at write time, so they cannot be joined to any feature,
slice, or stage -- the data exists and answers no question
(docs/feature/declared-facts-reachable-recorded/feature-delta.md DD-3/DD-4/DD-5).

Three defects, one theme, three test groups below:

* DD-3 -- `AgentUsageObservedEvent` must declare `request_id`/`slice_id`/`stage`
  (all optional, all excluded from `to_audit_data()` when `None`).
* DD-5 -- `extract_token_usage_events` must thread `entry["requestId"]` (a
  TOP-LEVEL transcript field) plus new `slice_id`/`stage` keyword arguments.
* DD-4 -- `handle_subagent_stop` must call `_emit_token_usage_events` AFTER
  `_resolve_des_context`, not before, so the resolved project_id/slice_id/
  atdd_pure_phase are available to thread. Driven end-to-end through the real
  hook entry point (not a fixture-only unit test) -- exactly the wiring this
  slice fixes.

ACTIVE-RED: every test below fails today against the un-fixed tree. Guard
helpers (`_construct_event` / `_extract`) turn a rejected DD-3/DD-5 keyword
argument into a named `AssertionError` instead of a bare `TypeError`, so the
RED reason is always the missing BEHAVIOUR, never a broken import/construction.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.logging.audit_events import AgentUsageObservedEvent
from des.adapters.drivers.hooks.token_usage_extractor import (
    extract_token_usage_events,
)


# ---------------------------------------------------------------------------
# Construction guards -- RED-not-BROKEN: a rejected DD-3/DD-5 keyword argument
# becomes a named AssertionError, never an uncaught TypeError.
# ---------------------------------------------------------------------------

_BASE_EVENT_KWARGS: dict[str, Any] = {
    "agent_name": "nw-software-crafter",
    "model": "claude-opus-4-7-20251101",
    "timestamp": "2026-07-28T00:00:00.000Z",
    "input_tokens": 10,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 20,
}


def _construct_event(**overrides: Any) -> AgentUsageObservedEvent:
    """Build an `AgentUsageObservedEvent`, naming a DD-3 gap instead of raising."""
    kwargs = {**_BASE_EVENT_KWARGS, **overrides}
    try:
        return AgentUsageObservedEvent(**kwargs)
    except TypeError as exc:
        raise AssertionError(
            "AgentUsageObservedEvent does not yet accept the DD-3 join-key "
            f"field(s) {sorted(overrides)}: {exc}"
        ) from None


def _extract(
    entries: list[dict[str, Any]], **kwargs: Any
) -> list[AgentUsageObservedEvent]:
    """Call `extract_token_usage_events`, naming a DD-5 gap instead of raising."""
    call_kwargs: dict[str, Any] = {"agent_name": "nw-software-crafter", **kwargs}
    try:
        return extract_token_usage_events(entries, **call_kwargs)
    except TypeError as exc:
        raise AssertionError(
            "extract_token_usage_events does not yet accept the DD-5 "
            f"keyword argument(s) {sorted(kwargs)}: {exc}"
        ) from None


def _request_id_of(event: AgentUsageObservedEvent) -> str | None:
    """Read `.request_id`, naming a DD-3/DD-5 gap instead of an AttributeError."""
    try:
        return event.request_id
    except AttributeError as exc:
        raise AssertionError(
            "AgentUsageObservedEvent instances do not yet carry a request_id "
            f"attribute (DD-3 field / DD-5 threading not implemented): {exc}"
        ) from None


def _assistant_entry(
    uuid_: str,
    *,
    request_id: Any = "__absent__",
    timestamp: str = "2026-07-28T00:00:00.000Z",
) -> dict[str, Any]:
    """One valid assistant transcript entry, optionally carrying `requestId`.

    `requestId` is a TOP-LEVEL field (sibling of `type`/`message`), per DD-5 --
    never nested inside `message.usage`.
    """
    entry: dict[str, Any] = {
        "type": "assistant",
        "uuid": uuid_,
        "timestamp": timestamp,
        "message": {
            "id": f"msg-{uuid_}",
            "model": "claude-opus-4-7-20251101",
            "usage": {
                "input_tokens": 5,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 9,
            },
        },
    }
    if request_id != "__absent__":
        entry["requestId"] = request_id
    return entry


# ---------------------------------------------------------------------------
# DD-3 -- AgentUsageObservedEvent gains request_id/slice_id/stage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("request_id", "req-8f21c4"),
        ("slice_id", "slice-05"),
        ("stage", "A_GREEN"),
    ],
)
def test_to_audit_data_threads_join_key_when_present(
    field_name: str, value: str
) -> None:
    """DD-3: a present join-key field is threaded into to_audit_data()."""
    event = _construct_event(**{field_name: value})
    payload = event.to_audit_data()
    assert payload.get(field_name) == value, (
        f"{field_name} was not threaded into to_audit_data(): {payload}"
    )


def test_to_audit_data_never_emits_null_join_keys_for_absent_fields() -> None:
    """Negative: a naive `"stage": null` implementation must fail this.

    Reuses the module's existing None-exclusion idiom (feature_id/wave already
    do this) -- an absent join key must be OMITTED from the payload, never
    present with a null value.
    """
    event = _construct_event(request_id=None, slice_id=None, stage=None)
    payload = event.to_audit_data()
    leaked = {"request_id", "slice_id", "stage"} & set(payload)
    assert not leaked, f"join-key field(s) leaked a null value into payload: {payload}"


# ---------------------------------------------------------------------------
# DD-5 -- extract_token_usage_events threads request_id/slice_id/stage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_id_value,expected",
    [
        ("req-alpha-001", "req-alpha-001"),
        ("__absent__", None),
    ],
)
def test_extractor_threads_request_id_from_top_level_field(
    request_id_value: Any, expected: str | None
) -> None:
    """DD-5: requestId is read from the TOP-LEVEL entry field, or degrades to None."""
    entry = _assistant_entry("a-1", request_id=request_id_value)
    events = _extract([entry])
    assert len(events) == 1, f"expected exactly 1 event, got {len(events)}"
    actual = _request_id_of(events[0])
    assert actual == expected, (
        f"request_id not threaded correctly: got {actual!r}, expected {expected!r}"
    )


def test_extractor_preserves_shared_request_id_across_streaming_snapshots() -> None:
    """Domain note: two assistant rows for the SAME request share ONE request_id.

    Without this, a downstream reader (slice-07) cannot distinguish two partial
    streaming snapshots of ONE request from two DIFFERENT requests -- the
    distinction the MAX(output_tokens)-not-sum dedup strategy depends on.
    """
    entries = [
        _assistant_entry("a-1", request_id="req-shared-9f2c"),
        _assistant_entry("a-2", request_id="req-shared-9f2c"),
    ]
    events = _extract(entries)
    assert len(events) == 2, f"expected 2 events, got {len(events)}"
    first_request_id = _request_id_of(events[0])
    second_request_id = _request_id_of(events[1])
    assert first_request_id == second_request_id == "req-shared-9f2c", (
        "two rows of the SAME request must carry the SAME request_id: "
        f"{first_request_id!r} vs {second_request_id!r}"
    )


def test_extractor_never_raises_and_never_drops_observation_on_non_string_request_id() -> (
    None
):
    """Negative: a malformed (non-string) requestId must not raise or drop the row.

    The event still emits (fail-open, D4); the field degrades to None -- it
    is typed `str | None`, so a non-string value is not silently propagated.
    """
    entry = _assistant_entry("a-1", request_id=12345)
    events = _extract([entry])
    assert len(events) == 1, (
        f"a non-string requestId must not drop the observation, got {len(events)} events"
    )
    actual = _request_id_of(events[0])
    assert actual is None, (
        f"a non-string requestId must degrade to None, got {actual!r}"
    )


def test_extractor_threads_slice_id_and_stage_kwargs_into_events() -> None:
    """DD-5: extract_token_usage_events gains slice_id/stage keyword arguments."""
    entry = _assistant_entry("a-1")
    events = _extract([entry], slice_id="slice-05", stage="A_GREEN")
    assert len(events) == 1, f"expected exactly 1 event, got {len(events)}"
    assert events[0].slice_id == "slice-05", (
        f"slice_id not threaded into the event: {events[0]!r}"
    )
    assert events[0].stage == "A_GREEN", (
        f"stage not threaded into the event: {events[0]!r}"
    )


# ---------------------------------------------------------------------------
# DD-4 -- the handler wiring: emit fires AFTER context resolution
# ---------------------------------------------------------------------------


def _write_transcript(tmp_path: Path, lines: list[dict[str, Any]]) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    with open(transcript, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return transcript


def _des_marker_message(
    *, project_id: str, slice_id: str, phase: str
) -> dict[str, Any]:
    """A transcript entry carrying a well-formed atdd_pure DES marker block."""
    content = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        f"<!-- DES-PROJECT-ID : {project_id} -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        f"<!-- DES-PHASE : {phase} -->\n"
    )
    return {
        "type": "user",
        "uuid": "u-des-context",
        "timestamp": "2026-07-28T00:00:00.000Z",
        "message": {"role": "user", "content": content},
    }


def _hook_input(transcript_path: str, cwd: str) -> str:
    return json.dumps(
        {
            "session_id": "test-session-slice-05",
            "hook_event_name": "SubagentStop",
            "agent_id": "agent-slice-05-test",
            "agent_type": "nw-software-crafter",
            "agent_transcript_path": transcript_path,
            "stop_hook_active": False,
            "cwd": cwd,
            "transcript_path": "/tmp/parent-session.jsonl",
            "permission_mode": "default",
        }
    )


def _read_audit_events(audit_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for log_file in sorted(audit_dir.glob("audit-*.log")):
        with open(log_file) as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                events.append(json.loads(stripped))
    return events


def test_handler_threads_resolved_context_join_keys_into_audit_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DD-4: `_emit_token_usage_events` must fire AFTER `_resolve_des_context`.

    Today the call fires at line ~2752, BEFORE context resolution at line
    ~2758 -- feature_id/slice_id/stage are never populated because the
    resolved values do not exist yet at the call site. Drives the REAL
    `handle_subagent_stop()` entry point (not a fixture-only unit test) with
    a crafted hook_input + fake transcript, and inspects what the audit
    writer actually received -- the same JSONL shape slice-07's reader will
    consume.

    Sibling-branch pin (never a dropped observation): a SECOND, marker-less
    transcript must still produce exactly one AGENT_USAGE_OBSERVED event with
    the join keys simply ABSENT (never present-but-null) -- the DD-4 reorder
    must not turn the existing passthrough-allow into a dropped observation.
    """
    from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop

    # --- Scenario 1: a resolvable atdd_pure DES context -----------------
    audit_dir_resolved = tmp_path / "audit-logs-resolved"
    audit_dir_resolved.mkdir()
    monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir_resolved))

    transcript_resolved = _write_transcript(
        tmp_path,
        [
            _des_marker_message(
                project_id="declared-facts-reachable-recorded",
                slice_id="slice-05",
                phase="A_GREEN",
            ),
            {
                "type": "assistant",
                "uuid": "a-1",
                "timestamp": "2026-07-28T00:00:01.000Z",
                "requestId": "req-handler-wiring-1",
                "message": {
                    "id": "msg-a-1",
                    "model": "claude-opus-4-7-20251101",
                    "usage": {
                        "input_tokens": 4,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "output_tokens": 7,
                    },
                },
            },
        ],
    )

    hook_payload = _hook_input(str(transcript_resolved), str(tmp_path / "cwd-1"))
    (tmp_path / "cwd-1").mkdir()
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_payload))
    try:
        handle_subagent_stop()
    except Exception:
        # The downstream atdd_pure gate machinery is not this AT's target --
        # _emit_token_usage_events is fail-open and unconditional ahead of any
        # gate decision, so only the ALREADY-WRITTEN audit event is asserted.
        pass

    events_resolved = _read_audit_events(audit_dir_resolved)
    usage_events_resolved = [
        e for e in events_resolved if e.get("event") == "AGENT_USAGE_OBSERVED"
    ]
    assert len(usage_events_resolved) == 1, (
        "expected exactly 1 AGENT_USAGE_OBSERVED event, got "
        f"{len(usage_events_resolved)}: {events_resolved}"
    )
    event = usage_events_resolved[0]
    assert event.get("feature_id") == "declared-facts-reachable-recorded", (
        "feature_id was not threaded from the resolved DES context -- the "
        f"DD-4 emit-before-resolve ordering bug: {event}"
    )
    assert event.get("slice_id") == "slice-05", (
        f"slice_id was not threaded from the resolved DES context: {event}"
    )
    assert event.get("stage") == "A_GREEN", (
        f"stage was not threaded from the resolved atdd_pure_phase: {event}"
    )

    # --- Scenario 2: sibling-branch pin, no DES markers at all ----------
    audit_dir_unresolved = tmp_path / "audit-logs-unresolved"
    audit_dir_unresolved.mkdir()
    monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir_unresolved))

    transcript_unresolved = _write_transcript(
        tmp_path,
        [
            {
                "type": "assistant",
                "uuid": "b-1",
                "timestamp": "2026-07-28T00:00:02.000Z",
                "message": {
                    "id": "msg-b-1",
                    "model": "claude-opus-4-7-20251101",
                    "usage": {
                        "input_tokens": 3,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "output_tokens": 6,
                    },
                },
            }
        ],
    )
    hook_payload_unresolved = _hook_input(
        str(transcript_unresolved), str(tmp_path / "cwd-2")
    )
    (tmp_path / "cwd-2").mkdir()
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_payload_unresolved))
    try:
        handle_subagent_stop()
    except Exception:
        pass

    events_unresolved = _read_audit_events(audit_dir_unresolved)
    usage_events_unresolved = [
        e for e in events_unresolved if e.get("event") == "AGENT_USAGE_OBSERVED"
    ]
    assert len(usage_events_unresolved) == 1, (
        "a genuinely non-DES return must still emit the observation (never "
        f"dropped), got {len(usage_events_unresolved)}: {events_unresolved}"
    )
    unresolved_event = usage_events_unresolved[0]
    leaked = {"feature_id", "slice_id", "stage"} & set(unresolved_event)
    assert not leaked, (
        "a non-DES return must never emit null/placeholder join keys -- "
        f"they must be simply ABSENT: {unresolved_event}"
    )
