"""SilentLogAdapter — D4 Phase 3 slice-04 production.

Per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3.

No-op adapter for tests + dry-run replays. When `capture_in_memory=True`
(the shipped default per `nWave/data/log-persistence-defaults.yaml`
`adapters.silent.capture_in_memory: true`), every emitted event is appended
to an in-memory list the test fixture can introspect post-invocation.

Use cases:
  - Acceptance test fixtures that need deterministic gate behaviour without
    log file side effects (no tmp_path JSONL pollution; no stderr noise).
  - Dry-run replays where the gate runs but the log destination is
    intentionally absent (the test replays the gate without persisting).
"""

from __future__ import annotations

from des.application.log_persistence import GateLogEvent


class SilentLogAdapter:
    """No-op adapter; optionally captures events in-memory for introspection.

    Constructor parameter per `nWave/data/log-persistence-defaults.yaml`
    `adapters.silent` schema:
      capture_in_memory  -- True appends every emit to self._captured for
                            post-hoc introspection; False discards.

    `captured_events()` returns the list of events emitted since construction
    (test fixture pattern). The list is the captured order of emits — tests
    assert ordering, count, and per-event fields.
    """

    def __init__(self, *, capture_in_memory: bool = True) -> None:
        self._capture_in_memory = capture_in_memory
        self._captured: list[GateLogEvent] = []

    def emit(self, event: GateLogEvent) -> None:
        if self._capture_in_memory:
            self._captured.append(event)

    def captured_events(self) -> list[GateLogEvent]:
        return list(self._captured)
