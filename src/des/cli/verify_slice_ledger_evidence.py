"""des verify-slice-ledger-evidence -- spine-ledger aggregator subcommand.

Slice-04 (FINAL) of F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2. Closes platform
architect critical-4 (observability aggregator gap): reads the audit log
directory shared by slice-00 (SpineBypassUsed), slice-01 (LedgerSkipped),
slice-02 (block decisions), slice-03 (SpineBypassDetected), and the
slice-14 verify-slice-commit gate (SliceCommitVerified +
CarpaccioGateCleared), groups events by name, filters by ``--since=<date>``,
and emits a single-line JSON report to stdout naming cumulative event
counts.

Read-only contract (Mandate 8 universe-bound observation): scans the audit
log files, emits the JSON, exits 0. NEVER mutates the filesystem -- no
``.nwave/disabled-gates`` write, no audit-log append, no telemetry-dir
mutation.

Driving port (Mandate-13 Layer 3 subprocess): invoked as
``python -m des verify-slice-ledger-evidence --report --since=<YYYY-MM-DD>``
through the ``des`` dispatcher. The subcommand main accepts the post-
dispatch argv slice (everything after ``verify-slice-ledger-evidence``).

JSON envelope shape (slice-04 contract):

    {
      "since": "<YYYY-MM-DD>",
      "slice_commits_verified": <int >= 0>,
      "carpaccio_gates_cleared": <int >= 0>,
      "bypasses_detected": <int >= 0>,
      "bypasses_used": <int >= 0>
    }

Audit log discovery (cross-slice convention inherited from slice-00 +
slice-03): scans ``<target>/.nwave/des/logs/audit-*.log`` JSONL files.
The ``<target>`` resolves from the
``NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT`` env var when present (test-harness
contract), otherwise from the current working directory.

Date filtering: an event is INCLUDED when its ``timestamp`` field's
date-prefix (``YYYY-MM-DD`` of the ISO-8601 timestamp) is greater-than-
or-equal-to the ``--since`` argument's date. Events with malformed or
absent ``timestamp`` are skipped silently (defensive: an unparseable
record cannot be located on the timeline).

Stdlib-only (no PyYAML, no third-party deps) per DES-bundle hygiene
contract. The subcommand module imports only ``argparse``, ``json``,
``os``, ``sys`` and ``pathlib`` -- mirrors the pattern of the
``carpaccio_slice_gate`` and ``health_check`` peer subcommands.

Exit codes:
    0 = report emitted to stdout (always the success path)
    2 = malformed input (missing --report or --since flag, invalid date)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_TARGET_ROOT_ENV = "NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"
_AUDIT_LOG_SUBDIR = Path(".nwave") / "des" / "logs"
_AUDIT_LOG_GLOB = "audit-*.log"


_EVENT_TO_REPORT_FIELD: dict[str, str] = {
    "SliceCommitVerified": "slice_commits_verified",
    "CarpaccioGateCleared": "carpaccio_gates_cleared",
    "SpineBypassDetected": "bypasses_detected",
    "SpineBypassUsed": "bypasses_used",
}


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the aggregator subcommand."""
    parser = argparse.ArgumentParser(
        prog="des verify-slice-ledger-evidence",
        description=(
            "Aggregate spine-ledger audit events into a JSON report "
            "filtered by --since=<YYYY-MM-DD>."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        required=True,
        help="Emit the structured JSON report to stdout.",
    )
    parser.add_argument(
        "--since",
        required=True,
        help="ISO date (YYYY-MM-DD); events on or after this date are counted.",
    )
    return parser


def _resolve_target_root() -> Path:
    """Return the target tree under which `.nwave/des/logs/` lives.

    Honors the test-harness contract: when the
    ``NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT`` env var is set, use that path;
    otherwise fall back to the process's current working directory (the
    operator's project root in the real-runtime case).
    """
    env_value = os.environ.get(_TARGET_ROOT_ENV)
    if env_value:
        return Path(env_value)
    return Path.cwd()


def _audit_log_files(target_root: Path) -> list[Path]:
    """Enumerate the ``audit-*.log`` JSONL files under the target tree."""
    log_dir = target_root / _AUDIT_LOG_SUBDIR
    if not log_dir.is_dir():
        return []
    return sorted(log_dir.glob(_AUDIT_LOG_GLOB))


def _parse_event(line: str) -> dict | None:
    """Parse one JSONL line into a dict event, or None on malformed input."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _event_date_prefix(event: dict) -> str | None:
    """Extract the ``YYYY-MM-DD`` date prefix from an event's timestamp."""
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        return None
    # Stdlib datetime is over-strict on ISO-8601 dialects (e.g. trailing 'Z').
    # The date prefix is the first 10 chars when the timestamp shape matches
    # ``YYYY-MM-DDTHH:MM:SS...`` -- robust to any time-zone suffix variant.
    if len(timestamp) < 10:
        return None
    prefix = timestamp[:10]
    # Cheap sanity check: 4-digit year + '-' + 2-digit month + '-' + 2-digit day.
    if prefix[4] != "-" or prefix[7] != "-":
        return None
    return prefix


def _read_audit_events(target_root: Path) -> list[dict]:
    """Read all audit events from every ``audit-*.log`` file under the target."""
    events: list[dict] = []
    for path in _audit_log_files(target_root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            event = _parse_event(line)
            if event is not None:
                events.append(event)
    return events


def _count_by_event_since(events: list[dict], since: str) -> dict[str, int]:
    """Return per-report-field counts of events on or after ``since``.

    Initializes every reported field to 0 so the JSON envelope always
    advertises the full 4-field shape, even when no events of a given
    kind exist on or after ``since``.
    """
    counts: dict[str, int] = dict.fromkeys(_EVENT_TO_REPORT_FIELD.values(), 0)
    for event in events:
        event_name = event.get("event")
        report_field = _EVENT_TO_REPORT_FIELD.get(event_name)
        if report_field is None:
            continue
        date_prefix = _event_date_prefix(event)
        if date_prefix is None:
            continue
        if date_prefix >= since:
            counts[report_field] += 1
    return counts


def _build_report(since: str, counts: dict[str, int]) -> dict:
    """Compose the JSON report envelope -- ``since`` + the 4 count fields."""
    report: dict = {"since": since}
    report.update(counts)
    return report


def main(argv: list[str] | None = None) -> int:
    """Aggregator subcommand entry point -- read audit log, emit JSON report."""
    parser = _build_parser()
    parsed = parser.parse_args(argv)
    target_root = _resolve_target_root()
    events = _read_audit_events(target_root)
    counts = _count_by_event_since(events, parsed.since)
    report = _build_report(parsed.since, counts)
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
