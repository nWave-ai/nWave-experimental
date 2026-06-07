"""DocumentationDensityEvent — telemetry event for lean-wave-documentation.

Per DDD-6 + D4:
- Domain dataclass lives in DES domain (no port change).
- Mapped to AuditEvent via to_audit_event() — the boundary translator
  from domain event to the AuditLogWriter port DTO.
- event_type string: "DOCUMENTATION_DENSITY_CHOICE" (open string per port
  contract; matches the L1 AGENT_USAGE_OBSERVED precedent from PR #13).

The five D4 schema fields (feature_id, wave, expansion_id, choice, timestamp)
all live in AuditEvent.data so they appear as top-level keys in the JSONL
line emitted by JsonlAuditLogWriter (which flattens .data via entry.update).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from des.ports.driven_ports.audit_log_writer import AuditEvent


if TYPE_CHECKING:
    from datetime import datetime


WaveName = Literal["DISCOVER", "DISCUSS", "DESIGN", "DEVOPS", "DISTILL", "DELIVER"]
ChoiceValue = Literal["expand", "skip"]


@dataclass(frozen=True)
class DocumentationDensityEvent:
    """A wave-end documentation density choice event.

    Fields per D4 telemetry schema:
        feature_id: Feature identifier (e.g., "small-feat-x").
        wave: Wave that emitted the event (one of the six canonical waves).
        expansion_id: Expansion identifier (e.g., "jtbd-narrative") or "*"
            when the user picked "skip all" at the wave-end menu.
        choice: Either "expand" or "skip".
        timestamp: When the choice was recorded (timezone-aware datetime).
    """

    feature_id: str
    wave: WaveName
    expansion_id: str
    choice: ChoiceValue
    timestamp: datetime

    def to_audit_event(self) -> AuditEvent:
        """Map this domain event to an AuditEvent for JsonlAuditLogWriter.

        Pure function — no I/O. The AuditLogWriter port consumer is
        responsible for the actual write.

        Returns:
            AuditEvent with event_type "DOCUMENTATION_DENSITY_CHOICE",
            ISO 8601 timestamp string, and the four payload fields packed
            into the open `data` dict.
        """
        return AuditEvent(
            event_type="DOCUMENTATION_DENSITY_CHOICE",
            timestamp=self.timestamp.isoformat(),
            data={
                "feature_id": self.feature_id,
                "wave": self.wave,
                "expansion_id": self.expansion_id,
                "choice": self.choice,
            },
        )
