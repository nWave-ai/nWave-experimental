"""JsonlLogAdapter — D4 Phase 3 slice-04 production.

Per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3.

Two-tier JSONL persistence:
  per-feature path: `.nwave/telemetry/atdd-pure/{feature_id}.jsonl`
  singleton common: `.nwave/audit/atdd-pure-events.jsonl`

When fanout=True (the shipped default in
`nWave/data/log-persistence-defaults.yaml`), a single `emit(event)` call
writes BOTH targets atomically. This closes friction #36 (common-log
walking-skel partial-ship) STRUCTURALLY because a gate cannot "forget" to
write the common log -- the adapter does, the gate doesn't know.

Fail-OPEN contract (INV-3): a sink write failure (OSError, permission denied,
disk full) MUST NOT raise; the gate's verdict already stands and the audit
log is best-effort. The adapter records the failure to stderr.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from des.application.log_persistence import GateLogEvent


class JsonlLogAdapter:
    """Two-tier JSONL adapter with optional fanout to per-feature + common log.

    Constructor parameters per the `nWave/data/log-persistence-defaults.yaml`
    `adapters.jsonl` schema:
      per_feature_template -- str template with `{feature_id}` placeholder.
      common_log_path      -- str absolute or repo-relative path.
      fanout               -- True writes BOTH paths; False writes per-feature
                              only.
      fail_open            -- True swallows OSError + writes stderr diagnostic;
                              False re-raises (NEVER set False in production).
      repo_root            -- Path resolving the path-template placeholders.
    """

    def __init__(
        self,
        *,
        per_feature_template: str,
        common_log_path: str,
        fanout: bool,
        fail_open: bool,
        repo_root: Path,
    ) -> None:
        self._per_feature_template = per_feature_template
        self._common_log_path = common_log_path
        self._fanout = fanout
        self._fail_open = fail_open
        self._repo_root = repo_root

    def emit(self, event: GateLogEvent) -> None:
        line = _serialise_event(event)
        per_feature_path = self._repo_root / self._per_feature_template.format(
            feature_id=event.feature_id
        )
        self._append_line(per_feature_path, line, event)
        if self._fanout:
            common_path = self._repo_root / self._common_log_path
            self._append_line(common_path, line, event)

    def _append_line(self, path: Path, line: str, event: GateLogEvent) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            if not self._fail_open:
                raise
            sys.stderr.write(
                f"[log_persistence] failed to append event_id={event.event_id} "
                f"gate_id={event.gate_id} to {path}: {exc}\n"
            )


def _serialise_event(event: GateLogEvent) -> str:
    """Serialise a GateLogEvent to a single JSON line.

    Module-scope helper so the per-feature + common-log writes share one
    encoder and the contract test for line shape has a single import.
    """
    record = asdict(event)
    record["timestamp"] = _iso8601(event.timestamp)
    return json.dumps(record, separators=(",", ":"), sort_keys=True)


def _iso8601(value: datetime) -> str:
    """Render a datetime as ISO8601. Module-scope so adapters can share."""
    return value.isoformat()
