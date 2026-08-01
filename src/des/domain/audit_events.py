"""Audit event vocabulary -- the domain-layer SSOT for ``EventType`` / ``AuditEvent``.

techdebt drain (application-layer-imports-adapters-directly): these two types
are pure value objects (an ``Enum`` of event-name strings and a ``dataclass``
DTO with a ``to_dict()``/``from_dict()`` helper) with zero I/O -- they carry no
adapter behaviour, only vocabulary. They previously lived under
``des.adapters.driven.logging.audit_events``, which forced the application
layer (``des.application.orchestrator``) to import from the adapters package
to build an audit event, violating the hexagonal layering rule (CLAUDE.md:
"Application layer should depend ONLY on ports, never adapters").

This module is now the canonical SSOT. ``des.adapters.driven.logging.audit_events``
re-imports and re-exports both names (mirroring the AD-02 DIP-fix pattern
already used for the feature-end event-name constants in
``des.ports.driven_ports.at_completion_ledger_port``) so every existing
importer that reads them off the adapter module stays unbroken.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class EventType(Enum):
    """Audit event type categories."""

    # TASK_INVOCATION events
    TASK_INVOCATION_STARTED = "TASK_INVOCATION_STARTED"
    TASK_INVOCATION_VALIDATED = "TASK_INVOCATION_VALIDATED"

    # PHASE events
    PHASE_STARTED = "PHASE_STARTED"

    # SUBAGENT_STOP events
    SUBAGENT_STOP_VALIDATION = "SUBAGENT_STOP_VALIDATION"

    # HOOK events
    HOOK_PRE_TASK_PASSED = "HOOK_PRE_TASK_PASSED"
    HOOK_PRE_TASK_BLOCKED = "HOOK_PRE_TASK_BLOCKED"
    HOOK_SUBAGENT_STOP_PASSED = "HOOK_SUBAGENT_STOP_PASSED"
    HOOK_SUBAGENT_STOP_FAILED = "HOOK_SUBAGENT_STOP_FAILED"

    # AGENT_USAGE events (L1 token instrumentation)
    AGENT_USAGE_OBSERVED = "AGENT_USAGE_OBSERVED"

    # HEALTH_GATE events (DV-5 — install-freshness dual-emit, KPI-1 sink)
    HEALTH_GATE_INSTALL_FRESHNESS_STALE = "HEALTH_GATE_INSTALL_FRESHNESS_STALE"
    # SYS-4 / AD-27 — shipped config-asset drift (lib/nWave/) dual-emit
    HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT = (
        "HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT"
    )


@dataclass
class AuditEvent:
    """Structured audit event with complete execution context."""

    timestamp: str  # ISO 8601 format: YYYY-MM-DDTHH:MM:SS.sssZ
    event: str  # Event type from EventType enum
    feature_name: str | None = None  # Feature name from step file
    step_id: str | None = None  # Step identifier (e.g., "01-02")
    phase_name: str | None = None  # Name of the TDD phase
    status: str | None = None  # Phase status: IN_PROGRESS, EXECUTED, SKIPPED
    reason: str | None = None  # Reason for failure/rejection
    commit_hash: str | None = None  # Git commit hash (for COMMIT events)
    rejection_reason: str | None = None  # Detailed rejection reason
    extra_context: dict[str, Any] | None = None  # Additional contextual data

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Excludes None values for cleaner JSONL output.
        """
        data = asdict(self)
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AuditEvent:
        """Create AuditEvent from dictionary.

        Args:
            data: Dictionary with event data

        Returns:
            AuditEvent instance
        """
        return AuditEvent(**data)


__all__ = ["AuditEvent", "EventType"]
