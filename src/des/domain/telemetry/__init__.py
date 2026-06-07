"""Telemetry domain — event dataclasses for DES audit log writer."""

from __future__ import annotations

from des.domain.telemetry.documentation_density_event import (
    DocumentationDensityEvent,
)


# Event-type string constant (DDD-6). Exported here for discoverability and
# to give wave-skill emitters a single import point. The AuditLogWriter port
# accepts free-form event-type strings (open contract) — this constant is the
# canonical name for documentation-density choice events.
DOCUMENTATION_DENSITY_CHOICE = "DOCUMENTATION_DENSITY_CHOICE"


__all__ = [
    "DOCUMENTATION_DENSITY_CHOICE",
    "DocumentationDensityEvent",
]
