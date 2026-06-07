"""Tests for HOOK_COMPLETED event in claude_code_hook_adapter.

Each handler emits a HOOK_COMPLETED audit event with hook_id, handler,
exit_code, decision, and duration_ms. Tests exercise through the handler
driving ports and assert at the AuditLogWriter driven port boundary.

Test Budget: 5 distinct behaviors x 2 = 10 max. Using 6 tests.

Acceptance criteria covered:
- HOOK_COMPLETED emitted on allow/block/error paths with correct exit_code and decision
- HOOK_COMPLETED emitted for post_tool_use (always exit_code=0)
- duration_ms is a positive float
- hook_id in HOOK_COMPLETED matches hook_id in HOOK_INVOKED
- HOOK_COMPLETED emitted even when handler raises exception (finally block)
- _log_hook_completed wrapped in try/except (never raises)
- slow_hook=true when duration_ms exceeds threshold
"""

import io
import json
import re
from unittest.mock import patch

import pytest

from des.adapters.drivers.hooks import hook_protocol, service_factory


UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _build_pre_tool_use_stdin() -> str:
    """Valid Agent input (allow path — non-DES task passes through)."""
    return json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "Do something",
                "subagent_type": "code",
            },
        }
    )


def _build_subagent_stop_stdin() -> str:
    """SubagentStop input with no DES markers (passthrough = allow)."""
    return json.dumps(
        {
            "session_id": "s1",
            "hook_event_name": "SubagentStop",
            "agent_id": "a1",
            "agent_type": "code",
            "cwd": "/tmp",
        }
    )


def _build_post_tool_use_stdin() -> str:
    """PostToolUse input (always allow)."""
    return json.dumps({"tool_name": "Agent", "tool_input": {"prompt": "done"}})


def _build_pre_write_stdin() -> str:
    """PreWrite input (no deliver session = allow)."""
    return json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.py"}}
    )


def _build_pre_tool_use_block_stdin() -> str:
    """Agent input with DES marker but missing mandatory sections (triggers block)."""
    return json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "<!-- DES-VALIDATION : required -->\nDo something",
                "subagent_type": "code",
            },
        }
    )


# --- Test 1: HOOK_COMPLETED emitted with correct exit_code and decision for each handler ---


@pytest.mark.parametrize(
    "handler_name,stdin_factory,expected_decision",
    [
        ("handle_pre_tool_use", _build_pre_tool_use_stdin, "allow"),
        ("handle_subagent_stop", _build_subagent_stop_stdin, "allow"),
        ("handle_post_tool_use", _build_post_tool_use_stdin, "allow"),
        ("handle_pre_write", _build_pre_write_stdin, "allow"),
    ],
    ids=[
        "pre_tool_use_allow",
        "subagent_stop_allow",
        "post_tool_use_allow",
        "pre_write_allow",
    ],
)
def test_hook_completed_emitted_with_correct_exit_code_and_decision(
    handler_name, stdin_factory, expected_decision, monkeypatch, audit_events
):
    """HOOK_COMPLETED event is emitted with correct exit_code and decision for each handler."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_factory()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    exit_code = getattr(adapter, handler_name)()

    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]
    assert len(completed_events) == 1, (
        f"Expected exactly one HOOK_COMPLETED event from {handler_name}, "
        f"got {len(completed_events)}. All events: {[e.event_type for e in audit_events]}"
    )

    event = completed_events[0]
    assert event.data["handler"] == handler_name.replace("handle_", "")
    assert event.data["exit_code"] == exit_code
    assert event.data["decision"] == expected_decision


# --- Test 2: HOOK_COMPLETED emitted on block path with exit_code=2, decision='block' ---


def test_hook_completed_emitted_on_block_path(monkeypatch, audit_events):
    """HOOK_COMPLETED event is emitted with exit_code=2, decision='block' when validation fails."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(_build_pre_tool_use_block_stdin()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    exit_code = adapter.handle_pre_tool_use()

    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]
    assert len(completed_events) == 1, (
        f"Expected HOOK_COMPLETED on block path, got {len(completed_events)} events"
    )

    event = completed_events[0]
    assert event.data["exit_code"] == exit_code
    assert exit_code == 2
    assert event.data["decision"] == "block"


# --- Test 3: hook_id in HOOK_COMPLETED matches hook_id in HOOK_INVOKED ---


def test_hook_completed_hook_id_matches_hook_invoked(monkeypatch, audit_events):
    """The hook_id in HOOK_COMPLETED matches the hook_id in the corresponding HOOK_INVOKED event."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(_build_pre_tool_use_stdin()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    adapter.handle_pre_tool_use()

    invoked_events = [e for e in audit_events if e.event_type == "HOOK_INVOKED"]
    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]

    assert len(invoked_events) >= 1, "Expected at least one HOOK_INVOKED event"
    assert len(completed_events) == 1, "Expected exactly one HOOK_COMPLETED event"

    invoked_hook_id = invoked_events[0].data["hook_id"]
    completed_hook_id = completed_events[0].data["hook_id"]

    assert invoked_hook_id == completed_hook_id, (
        f"hook_id mismatch: HOOK_INVOKED has '{invoked_hook_id}', "
        f"HOOK_COMPLETED has '{completed_hook_id}'"
    )
    assert UUID4_PATTERN.match(completed_hook_id), (
        f"hook_id '{completed_hook_id}' is not a valid UUID4"
    )


# --- Test 4: duration_ms is a positive float ---


def test_hook_completed_duration_ms_is_positive(monkeypatch, audit_events):
    """HOOK_COMPLETED event has duration_ms as a positive float."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(_build_pre_tool_use_stdin()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    adapter.handle_pre_tool_use()

    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]
    assert len(completed_events) == 1

    duration_ms = completed_events[0].data["duration_ms"]
    assert isinstance(duration_ms, float), (
        f"duration_ms should be float, got {type(duration_ms).__name__}"
    )
    assert duration_ms > 0, f"duration_ms should be positive, got {duration_ms}"


# --- Test 5: HOOK_COMPLETED emitted even when handler raises exception ---


def test_hook_completed_emitted_on_exception(monkeypatch, audit_events):
    """HOOK_COMPLETED event is emitted even when the handler raises an exception (finally block)."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    # Provide valid JSON stdin but make the service creation blow up
    monkeypatch.setattr("sys.stdin", io.StringIO(_build_pre_tool_use_stdin()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    def exploding_service():
        raise RuntimeError("Simulated service failure")

    with patch.object(
        service_factory,
        "create_pre_tool_use_service",
        side_effect=exploding_service,
    ):
        exit_code = adapter.handle_pre_tool_use()

    # Should return 1 (error/fail-closed)
    assert exit_code == 1

    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]
    assert len(completed_events) == 1, (
        f"Expected HOOK_COMPLETED even on exception, got {len(completed_events)} events. "
        f"All events: {[e.event_type for e in audit_events]}"
    )

    event = completed_events[0]
    assert event.data["exit_code"] == 1
    assert event.data["decision"] == "error"
    assert event.data["duration_ms"] > 0


# --- Test 6: _log_hook_completed never raises even if audit writer throws ---


def test_log_hook_completed_never_raises():
    """log_hook_completed is wrapped in try/except and never propagates exceptions."""

    class ExplodingWriter:
        def log_event(self, event):
            raise RuntimeError("Writer explosion")

    with patch.object(
        hook_protocol, "_audit_writer_factory", return_value=ExplodingWriter()
    ):
        # Should not raise
        hook_protocol.log_hook_completed(
            hook_id="test-id",
            handler="test_handler",
            exit_code=0,
            decision="allow",
            duration_ms=1.5,
        )


# --- Test 7: slow_hook=true when duration_ms exceeds threshold ---


def test_hook_completed_slow_hook_detection(monkeypatch, audit_events):
    """HOOK_COMPLETED event includes slow_hook=true when duration_ms exceeds threshold."""
    # We need to simulate a slow handler. We can do this by patching
    # time.perf_counter_ns to return values with a large gap.
    import time

    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    call_count = 0

    # Simulate 6000ms elapsed (6 seconds > any reasonable threshold)
    def fake_perf_counter_ns():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 0  # start_ns
        return 6_000_000_000  # 6000ms later

    monkeypatch.setattr("sys.stdin", io.StringIO(_build_pre_tool_use_stdin()))
    monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

    with patch.object(time, "perf_counter_ns", side_effect=fake_perf_counter_ns):
        adapter.handle_pre_tool_use()

    completed_events = [e for e in audit_events if e.event_type == "HOOK_COMPLETED"]
    assert len(completed_events) == 1

    event = completed_events[0]
    assert event.data.get("slow_hook") is True, (
        f"Expected slow_hook=true for duration_ms={event.data.get('duration_ms')}, "
        f"but got slow_hook={event.data.get('slow_hook')}"
    )
    assert event.data["duration_ms"] == 6000.0
