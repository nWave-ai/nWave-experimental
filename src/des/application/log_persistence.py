"""LogPersistencePort + GateLogEvent — D4 Phase 3 slice-04 production.

Per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3 + INV-3 (gate emits log
via adapter port; gate does NOT know where the log goes — the adapter resolves
destination from config per INV-9 config-as-driver).

This module ships the closed envelope (`GateLogEvent`), the sink-agnostic
Protocol (`LogPersistencePort`), and the config-driven factory
(`default_log_persistence_port`) that constructs the adapter instance the
shipped defaults select. The 17 gates' `_emit_*_event` migrate to
`port.emit(event)` in a successor caller-migration slice — that migration
closes friction #36 (common-log walking-skel partial-ship) STRUCTURALLY
because the JsonlLogAdapter fan-out writes BOTH per-feature AND common-log
paths atomically per the default config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class GateLogEvent:
    """Closed envelope every gate emits via LogPersistencePort.emit.

    Per INV-3: gate constructs this dataclass + calls emit(). Adapter resolves
    destination. Gate never references a filesystem path / sink / network.

    Fields per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3:
      event_id     -- closed namespace `gate.<gate-id>.<outcome>` (cross-checked
                       against `nWave/data/log-persistence-defaults.yaml`
                       `event_namespaces` list at install-time validation).
      gate_id      -- which gate emitted (cross-references
                       `nWave/gates/_catalog.yaml`).
      feature_id   -- correlation context (None for global gates like doctor).
      slice_id     -- correlation context (None for non-slice-scoped gates).
      payload      -- gate-specific data per the per-gate
                       `log_events[].payload_schema` declared in the gate YAML.
      timestamp    -- ISO8601 UTC.
      host         -- one of: claude-code | codex | opencode | cli.
    """

    event_id: str
    gate_id: str
    feature_id: str | None
    slice_id: str | None
    payload: dict[str, object]
    timestamp: datetime
    host: str


class LogPersistencePort(Protocol):
    """Sink-agnostic gate-log persistence port (INV-3).

    Adapter implementations resolve destination from config (INV-9). The gate
    has no knowledge of where events land. Fail-OPEN contract: a sink failure
    MUST NOT propagate; the gate's verdict already stands and audit is
    best-effort (per `feedback_earned_trust_mechanical_evidence_not_llm_verdict`:
    log failure must NOT change gate behavior).
    """

    def emit(self, event: GateLogEvent) -> None:
        """Best-effort emit. Adapter MUST NOT raise on sink failure."""
        ...


def default_log_persistence_port(
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> LogPersistencePort:
    """Construct the default LogPersistencePort per the shipped defaults.

    Reads `nWave/data/log-persistence-defaults.yaml` `active_adapter` row and
    returns the corresponding adapter instance configured with the per-adapter
    keys (per-feature path template, common-log path, fanout flag).

    Args:
      repo_root: filesystem root the adapter resolves relative paths against
        (defaults to the current working directory).
      config_path: path to the YAML defaults file (defaults to the shipped
        `nWave/data/log-persistence-defaults.yaml`).

    Per INV-10 NO env vars — adapter selection is config-driven, never
    environment-driven.

    Parser: stdlib-only YAML subset (`des._internal.subset_parser`)
    per the DES-bundle hygiene contract — the bundled module cannot import
    `yaml` / `pyyaml`. The defaults file uses only constructs the subset
    parser supports (scalars, nested mappings, string lists).
    """
    from des._internal import subset_parser
    from des.adapters.driven.log_persistence import (
        JsonlLogAdapter,
        SilentLogAdapter,
        StdoutLogAdapter,
    )

    resolved_root = repo_root if repo_root is not None else Path.cwd()
    resolved_config = (
        config_path
        if config_path is not None
        else resolved_root / "nWave" / "data" / "log-persistence-defaults.yaml"
    )
    config = subset_parser.load_file(resolved_config)
    active = config["active_adapter"]
    adapters = config["adapters"]
    if active == "jsonl":
        jsonl_cfg = adapters["jsonl"]
        return JsonlLogAdapter(
            per_feature_template=jsonl_cfg["per_feature_path"],
            common_log_path=jsonl_cfg["common_log_path"],
            fanout=jsonl_cfg["fanout"],
            fail_open=jsonl_cfg["fail_open"],
            repo_root=resolved_root,
        )
    if active == "stdout":
        import sys

        stdout_cfg = adapters["stdout"]
        stream = sys.stderr if stdout_cfg["stream"] == "stderr" else sys.stdout
        return StdoutLogAdapter(
            stream=stream,
            include_timestamp=stdout_cfg["include_timestamp"],
        )
    silent_cfg = adapters["silent"]
    return SilentLogAdapter(capture_in_memory=silent_cfg["capture_in_memory"])
