"""StdoutLogAdapter — D4 Phase 3 slice-04 production.

Per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3.

Emits gate events as one JSON line per emit. Stream selectable (stderr by
default per the shipped `nWave/data/log-persistence-defaults.yaml` config:
gate events go to stderr per current convention; stdout is reserved for the
gate's own JSON verdict line).

Use cases:
  - Operator-direct CLI invocation: `des <gate> --emit-stdout` for live debug.
  - CI/CD pipeline integration where the pipeline log file is the audit sink.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TextIO

from des.application.log_persistence import GateLogEvent


class StdoutLogAdapter:
    """JSON-line emit on a writable text stream.

    Constructor parameters per `nWave/data/log-persistence-defaults.yaml`
    `adapters.stdout` schema:
      stream             -- TextIO object (e.g. sys.stderr); default-resolution
                            from "stderr" / "stdout" string lives in the
                            factory wiring, not the adapter.
      include_timestamp  -- True includes event.timestamp ISO8601 in the JSON
                            line; False omits (smaller payload).
    """

    def __init__(self, *, stream: TextIO, include_timestamp: bool = True) -> None:
        self._stream = stream
        self._include_timestamp = include_timestamp

    def emit(self, event: GateLogEvent) -> None:
        record = asdict(event)
        if self._include_timestamp:
            record["timestamp"] = event.timestamp.isoformat()
        else:
            record.pop("timestamp", None)
        line = json.dumps(record, separators=(",", ":"), sort_keys=True)
        try:
            self._stream.write(line + "\n")
            self._stream.flush()
        except (OSError, ValueError):
            # Fail-OPEN per INV-3: BrokenPipeError / closed-stream ValueError
            # MUST NOT raise; the gate verdict already stands.
            pass
