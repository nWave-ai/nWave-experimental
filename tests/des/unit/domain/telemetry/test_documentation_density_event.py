"""Unit tests for DocumentationDensityEvent (DDD-6 + D4).

Pure domain — no I/O. Tests the dataclass construction, immutability, and
the to_audit_event() boundary translator that maps domain event -> AuditEvent
(the format consumed by JsonlAuditLogWriter via the AuditLogWriter port).

Driving port for these unit tests is the function/dataclass public API itself
(per Outside-In TDD's port-to-port-at-domain-scope rule).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from des.domain.telemetry import (
    DOCUMENTATION_DENSITY_CHOICE,
    DocumentationDensityEvent,
)
from des.ports.driven_ports.audit_log_writer import AuditEvent


class TestDocumentationDensityEventConstruction:
    """The event accepts all D4 schema fields and stores them faithfully."""

    def test_constructs_with_all_required_fields(self) -> None:
        ts = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        event = DocumentationDensityEvent(
            feature_id="small-feat-x",
            wave="DISCUSS",
            expansion_id="jtbd-narrative",
            choice="expand",
            timestamp=ts,
        )

        assert event.feature_id == "small-feat-x"
        assert event.wave == "DISCUSS"
        assert event.expansion_id == "jtbd-narrative"
        assert event.choice == "expand"
        assert event.timestamp == ts

    def test_event_is_frozen(self) -> None:
        event = DocumentationDensityEvent(
            feature_id="small-feat-x",
            wave="DISCUSS",
            expansion_id="*",
            choice="skip",
            timestamp=datetime(2026, 4, 28, tzinfo=timezone.utc),
        )

        with pytest.raises(FrozenInstanceError):
            event.choice = "expand"  # type: ignore[misc]


class TestEventTypeConstant:
    """Pin the audit event type literal so downstream consumers don't drift."""

    def test_event_type_constant_value(self) -> None:
        """The DOCUMENTATION_DENSITY_CHOICE constant string is load-bearing —
        downstream JSONL consumers (dashboards, audit grep, future migrations)
        rely on this exact literal. Changing it is a breaking change.
        """
        assert DOCUMENTATION_DENSITY_CHOICE == "DOCUMENTATION_DENSITY_CHOICE"


class TestToAuditEventMapping:
    """The boundary translator from domain event -> AuditEvent (port DTO)."""

    def test_returns_audit_event_with_correct_event_type(self) -> None:
        event = DocumentationDensityEvent(
            feature_id="small-feat-x",
            wave="DISCUSS",
            expansion_id="jtbd-narrative",
            choice="expand",
            timestamp=datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc),
        )

        audit = event.to_audit_event()

        assert isinstance(audit, AuditEvent)
        assert audit.event_type == DOCUMENTATION_DENSITY_CHOICE

    def test_audit_event_data_carries_all_d4_keys(self) -> None:
        ts = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        event = DocumentationDensityEvent(
            feature_id="complex-feat-y",
            wave="DESIGN",
            expansion_id="*",
            choice="skip",
            timestamp=ts,
        )

        audit = event.to_audit_event()

        # Per @property scenario: every density event carries these keys
        # at the JSONL line level. The writer flattens AuditEvent.data
        # into the line, so feature_id/wave/expansion_id/choice live in data.
        assert audit.data == {
            "feature_id": "complex-feat-y",
            "wave": "DESIGN",
            "expansion_id": "*",
            "choice": "skip",
        }
        # Timestamp is serialized as ISO 8601 string (port contract).
        assert audit.timestamp == ts.isoformat()
