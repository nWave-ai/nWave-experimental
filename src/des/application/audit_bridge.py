"""Audit logging bridge for DES orchestrator.

Drop-in replacement for the legacy ``log_audit_event()`` convenience function
that was removed together with ``audit_logger.py``.

Extracted from orchestrator.py as part of P3 decomposition.
"""

from __future__ import annotations

from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.ports.driven_ports.audit_log_writer import AuditEvent as PortAuditEvent


def log_audit_event(event_type: str, **kwargs: object) -> None:
    """Log an audit event using JsonlAuditLogWriter.

    ``feature_name`` and ``step_id`` are extracted from *kwargs* and passed
    as direct :class:`PortAuditEvent` fields for structured traceability.
    All remaining kwargs are placed in the ``data`` dict.
    """
    from des.adapters.driven.time.system_time import SystemTimeProvider

    feature_name = kwargs.pop("feature_name", None)
    step_id = kwargs.pop("step_id", None)

    writer = JsonlAuditLogWriter()
    timestamp = SystemTimeProvider().now_utc().isoformat()
    writer.log_event(
        PortAuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            feature_name=feature_name,
            step_id=step_id,
            data={k: v for k, v in kwargs.items() if v is not None},
        )
    )
