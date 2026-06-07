"""L1 Token Instrumentation — Walking Skeleton acceptance tests.

Drives the additive token-usage instrumentation of subagent_stop_handler:
the same code path that walks the agent transcript for DES markers must
also emit one AGENT_USAGE_OBSERVED audit event per assistant message
that carries a valid `message.usage` block.

Tests invoke handle_subagent_stop() directly (the same function the
production hook adapter dispatches to). The audit log is redirected to
a tmp_path via the DES_AUDIT_LOG_DIR env var, so we observe outcomes at
the JsonlAuditLogWriter port boundary by reading the produced file.

WS strategy: C — real local. Real JsonlAuditLogWriter, real fixture
transcript JSONL, real filesystem.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenario, then, when


FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "fixtures"
    / "l1-token-instrumentation"
)


# ---------------------------------------------------------------------------
# Scenario bindings — un-skip one at a time during DELIVER
# ---------------------------------------------------------------------------


@scenario(
    "walking-skeleton.feature",
    "Token usage events are emitted for valid assistant messages",
)
def test_token_usage_walking_skeleton() -> None:
    """WS: real hook + real audit writer + real fixture transcript."""


@scenario(
    "walking-skeleton.feature",
    "Empty transcript produces no token usage events and no exception",
)
def test_empty_transcript() -> None:
    """Edge case: empty transcript produces no events, no exception."""


# ---------------------------------------------------------------------------
# Shared context fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mutable scenario context with redirected audit log directory."""
    audit_dir = tmp_path / "audit-logs"
    audit_dir.mkdir()
    monkeypatch.setenv("DES_AUDIT_LOG_DIR", str(audit_dir))
    return {"tmp_path": tmp_path, "audit_dir": audit_dir, "exception": None}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a Claude transcript with four assistant messages")
def given_transcript_four_messages(ctx: dict[str, Any]) -> None:
    """Use the canonical fixture transcript with 4 assistant messages."""
    fixture = FIXTURE_DIR / "transcript-with-usage.jsonl"
    assert fixture.exists(), f"Fixture missing: {fixture}"
    ctx["transcript_path"] = str(fixture)


@given("three of the four assistant messages carry a valid usage block")
def given_three_messages_have_usage(ctx: dict[str, Any]) -> None:
    """Verify fixture invariant: 3 of 4 assistant lines have usage."""
    with open(ctx["transcript_path"]) as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assistant_lines = [entry for entry in lines if entry.get("type") == "assistant"]
    with_usage = [
        entry
        for entry in assistant_lines
        if isinstance(entry.get("message"), dict)
        and isinstance(entry["message"].get("usage"), dict)
    ]
    assert len(assistant_lines) == 4
    assert len(with_usage) == 3


@given("an empty Claude transcript")
def given_empty_transcript(ctx: dict[str, Any]) -> None:
    fixture = FIXTURE_DIR / "transcript-empty.jsonl"
    assert fixture.exists(), f"Fixture missing: {fixture}"
    ctx["transcript_path"] = str(fixture)


@given("the audit writer points at a temporary log directory")
def given_audit_writer_redirected(ctx: dict[str, Any]) -> None:
    """No-op: handled by the autouse `ctx` fixture which sets DES_AUDIT_LOG_DIR."""
    assert ctx["audit_dir"].exists()


# ---------------------------------------------------------------------------
# When step
# ---------------------------------------------------------------------------


def _build_hook_input(transcript_path: str, cwd: str) -> str:
    return json.dumps(
        {
            "session_id": "test-session-l1",
            "hook_event_name": "SubagentStop",
            "agent_id": "agent-l1-test",
            "agent_type": "researcher",
            "agent_transcript_path": transcript_path,
            "stop_hook_active": False,
            "cwd": cwd,
            "transcript_path": "/tmp/parent-session.jsonl",
            "permission_mode": "default",
        }
    )


@when("the SubagentStop hook processes the transcript via the real adapter")
def when_hook_processes_transcript(
    ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the real handle_subagent_stop() function with a Claude Code stdin payload."""
    from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop

    hook_input = _build_hook_input(ctx["transcript_path"], str(ctx["tmp_path"]))
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input))
    try:
        ctx["exit_code"] = handle_subagent_stop()
    except Exception as exc:  # pragma: no cover - asserted in Then steps
        ctx["exception"] = exc


# ---------------------------------------------------------------------------
# Then steps — read the audit log produced by JsonlAuditLogWriter
# ---------------------------------------------------------------------------


def _read_audit_events(audit_dir: Path) -> list[dict[str, Any]]:
    """Read all JSONL audit events from the daily log files in audit_dir."""
    events: list[dict[str, Any]] = []
    for log_file in sorted(audit_dir.glob("audit-*.log")):
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))
    return events


@then(
    parsers.parse(
        "the audit log contains exactly {count:d} AGENT_USAGE_OBSERVED events"
    )
)
def then_audit_log_contains_n_usage_events(ctx: dict[str, Any], count: int) -> None:
    events = _read_audit_events(ctx["audit_dir"])
    usage_events = [e for e in events if e.get("event") == "AGENT_USAGE_OBSERVED"]
    assert len(usage_events) == count, (
        f"Expected {count} AGENT_USAGE_OBSERVED events, got {len(usage_events)}; "
        f"all events: {[e.get('event') for e in events]}"
    )
    ctx["usage_events"] = usage_events


@then("each event records input, cache_creation, cache_read, and output tokens")
def then_each_event_has_token_fields(ctx: dict[str, Any]) -> None:
    required_fields = {
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
    }
    for event in ctx["usage_events"]:
        missing = required_fields - set(event.keys())
        assert not missing, f"Event missing token fields {missing}: {event}"
        for field in required_fields:
            assert isinstance(event[field], int), (
                f"Field {field} not int in event {event}"
            )


@then("the assistant message without a usage block produces no event")
def then_message_without_usage_skipped(ctx: dict[str, Any]) -> None:
    """Verified by total count == 3 (4 assistant messages, 1 missing usage)."""
    assert len(ctx["usage_events"]) == 3


@then("the hook exits without raising an exception")
def then_hook_no_exception(ctx: dict[str, Any]) -> None:
    assert ctx["exception"] is None, f"Hook raised: {ctx['exception']!r}"
