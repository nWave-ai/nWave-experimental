"""Unit tests for JsonlAuditLogReader's UTC-midnight file-rotation boundary.

`read_last_entry` computes "today" (UTC) at read time and opens ONLY
`audit-{today}.log` -- no fallback to yesterday's file. The writer rotates on
the same UTC-date basis independently at write time. If a SubagentStop hook
writes at 23:59:59 UTC and PostToolUse reads at 00:00:01 UTC, the write lands
in day D's file and the read opens day D+1's file: a real, just-written entry
is reported as `None`, indistinguishable from "nothing happened" (GDP-6).

These tests reproduce the boundary using REAL relative UTC dates (yesterday
computed the same way the reader would), not a mocked clock -- the reader has
no injectable clock, so the fixture writes to the actual "yesterday" file on
disk and asserts the reader still finds it.

Test Budget: 2 behaviors (falls back to yesterday when today has no match;
still prefers today's own entry when both exist) x 2 = 4 max. Using 3.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from des.adapters.driven.logging.jsonl_audit_log_reader import JsonlAuditLogReader


def _write_log(log_dir, date_str: str, entries: list[dict]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"audit-{date_str}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestUtcMidnightBoundary:
    """read_last_entry must not lose entries written just before UTC midnight."""

    def test_finds_entry_in_yesterdays_file_when_todays_file_is_absent(self, tmp_path):
        """A write at 23:59:59 UTC followed by a read at 00:00:01 UTC must not
        be reported as `None` just because today's log file doesn't exist yet."""
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        _write_log(
            tmp_path,
            yesterday,
            [{"event": "HOOK_SUBAGENT_STOP_PASSED", "step_id": "01-01"}],
        )
        # today's file deliberately does NOT exist.

        reader = JsonlAuditLogReader(log_dir=tmp_path)
        entry = reader.read_last_entry(
            event_type="HOOK_SUBAGENT_STOP_PASSED", step_id="01-01"
        )

        assert entry is not None
        assert entry["step_id"] == "01-01"

    def test_prefers_todays_entry_over_yesterdays_when_both_match(self, tmp_path):
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        _write_log(
            tmp_path,
            yesterday,
            [{"event": "HOOK_SUBAGENT_STOP_PASSED", "step_id": "01-01", "n": "old"}],
        )
        _write_log(
            tmp_path,
            today,
            [{"event": "HOOK_SUBAGENT_STOP_PASSED", "step_id": "01-01", "n": "new"}],
        )

        reader = JsonlAuditLogReader(log_dir=tmp_path)
        entry = reader.read_last_entry(
            event_type="HOOK_SUBAGENT_STOP_PASSED", step_id="01-01"
        )

        assert entry is not None
        assert entry["n"] == "new"

    def test_returns_none_when_neither_file_has_a_match(self, tmp_path):
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        _write_log(tmp_path, today, [{"event": "SOME_OTHER_EVENT", "step_id": "01-01"}])

        reader = JsonlAuditLogReader(log_dir=tmp_path)
        entry = reader.read_last_entry(
            event_type="HOOK_SUBAGENT_STOP_PASSED", step_id="01-01"
        )

        assert entry is None
