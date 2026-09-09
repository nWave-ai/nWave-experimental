"""
Audit event type definitions and AuditEvent dataclass.

``EventType`` and ``AuditEvent`` are re-exported from ``des.domain.audit_events``
(the SSOT, moved there by the techdebt drain of
``application-layer-imports-adapters-directly`` -- both are pure value objects
with zero I/O, so the application layer can depend on their domain-layer home
without crossing the hexagonal ports/adapters boundary). Kept importable from
here so every existing caller of this adapter module stays unbroken.
"""

from des.domain.audit_events import AuditEvent, EventType


__all__ = ["AuditEvent", "EventType"]
