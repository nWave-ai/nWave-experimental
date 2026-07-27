"""Transcript-read audit observability (techdebt drain, shard B).

Prior state: both `extract_des_context_from_transcript` and
`_read_transcript_entries` returned the SAME empty result (None / []) for a
missing-file, an unreadable-file, and (for the former) a readable-but-no-
markers-found transcript -- indistinguishable to any downstream reader,
including the stale-agent watchdog. `extract_des_context_from_transcript`
already logged a distinct audit event for its OSError/PermissionError and
no-markers branches; only its absent-file branch was silent.
`_read_transcript_entries` logged nothing on either of its two fail-open
branches.

Fix: every fail-open branch across both functions now emits a distinct
`_log_transcript_audit` event before returning. The return value/type is
UNCHANGED (None / [] respectively) -- this is an observability fix, not a
contract change: "an incapacity to read must never be indistinguishable
from having read nothing," achieved via the audit trail.

Test Budget: 5 distinct behaviors (3 in extract_des_context_from_transcript,
2 in _read_transcript_entries) x 2 = 10 max. Using 5 tests (one per branch).
"""

from __future__ import annotations

from unittest.mock import patch

from des.adapters.drivers.hooks import hook_protocol
from des.adapters.drivers.hooks import subagent_stop_handler as ssh

from .conftest import make_capturing_writer


# --- extract_des_context_from_transcript: 3 branches ---


def test_extract_context_absent_file_logs_hook_transcript_absent(tmp_path):
    """Missing transcript path emits HOOK_TRANSCRIPT_ABSENT (previously silent)."""
    events: list = []
    writer = make_capturing_writer(events)
    missing_path = str(tmp_path / "nonexistent-transcript.jsonl")

    with patch.object(hook_protocol, "_audit_writer_factory", return_value=writer):
        result = ssh.extract_des_context_from_transcript(missing_path)

    assert result is None
    matching = [e for e in events if e.event_type == "HOOK_TRANSCRIPT_ABSENT"]
    assert matching, f"Expected HOOK_TRANSCRIPT_ABSENT event; got {events}"
    assert matching[0].data["transcript_path"] == missing_path


def test_extract_context_unreadable_file_logs_hook_transcript_error(tmp_path):
    """Unreadable transcript (OSError/PermissionError) keeps logging HOOK_TRANSCRIPT_ERROR."""
    events: list = []
    writer = make_capturing_writer(events)
    transcript_path = tmp_path / "agent.jsonl"
    transcript_path.write_text('{"message": {}}\n')

    with (
        patch.object(hook_protocol, "_audit_writer_factory", return_value=writer),
        patch("builtins.open", side_effect=PermissionError("denied")),
    ):
        result = ssh.extract_des_context_from_transcript(str(transcript_path))

    assert result is None
    matching = [e for e in events if e.event_type == "HOOK_TRANSCRIPT_ERROR"]
    assert matching, f"Expected HOOK_TRANSCRIPT_ERROR event; got {events}"
    assert matching[0].data["transcript_path"] == str(transcript_path)
    assert "denied" in matching[0].data["error"]


def test_extract_context_no_markers_logs_hook_transcript_no_markers(tmp_path):
    """Readable transcript with no DES markers keeps logging HOOK_TRANSCRIPT_NO_MARKERS."""
    events: list = []
    writer = make_capturing_writer(events)
    transcript_path = tmp_path / "agent.jsonl"
    transcript_path.write_text(
        '{"message": {"role": "user", "content": "no markers here"}}\n'
    )

    with patch.object(hook_protocol, "_audit_writer_factory", return_value=writer):
        result = ssh.extract_des_context_from_transcript(str(transcript_path))

    assert result is None
    matching = [e for e in events if e.event_type == "HOOK_TRANSCRIPT_NO_MARKERS"]
    assert matching, f"Expected HOOK_TRANSCRIPT_NO_MARKERS event; got {events}"
    assert matching[0].data["transcript_path"] == str(transcript_path)


# --- _read_transcript_entries: 2 branches ---


def test_read_entries_absent_file_logs_hook_transcript_entries_absent(tmp_path):
    """Missing transcript path emits HOOK_TRANSCRIPT_ENTRIES_ABSENT."""
    events: list = []
    writer = make_capturing_writer(events)
    missing_path = str(tmp_path / "nonexistent-transcript.jsonl")

    with patch.object(hook_protocol, "_audit_writer_factory", return_value=writer):
        result = ssh._read_transcript_entries(missing_path)

    assert result == []
    matching = [e for e in events if e.event_type == "HOOK_TRANSCRIPT_ENTRIES_ABSENT"]
    assert matching, f"Expected HOOK_TRANSCRIPT_ENTRIES_ABSENT event; got {events}"
    assert matching[0].data["transcript_path"] == missing_path


def test_read_entries_unreadable_file_logs_hook_transcript_entries_unreadable(
    tmp_path,
):
    """Unreadable transcript (OSError/PermissionError) emits
    HOOK_TRANSCRIPT_ENTRIES_UNREADABLE with the error string attached."""
    events: list = []
    writer = make_capturing_writer(events)
    transcript_path = tmp_path / "agent.jsonl"
    transcript_path.write_text('{"message": {}}\n')

    with (
        patch.object(hook_protocol, "_audit_writer_factory", return_value=writer),
        patch("builtins.open", side_effect=OSError("boom")),
    ):
        result = ssh._read_transcript_entries(str(transcript_path))

    assert result == []
    matching = [
        e for e in events if e.event_type == "HOOK_TRANSCRIPT_ENTRIES_UNREADABLE"
    ]
    assert matching, f"Expected HOOK_TRANSCRIPT_ENTRIES_UNREADABLE event; got {events}"
    assert matching[0].data["transcript_path"] == str(transcript_path)
    assert "boom" in matching[0].data["error"]
