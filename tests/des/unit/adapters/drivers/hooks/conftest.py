"""Shared test infrastructure for hook adapter tests.

Provides:
- ``make_capturing_writer(events)`` — factory for audit writers that capture events
- ``audit_events`` — pytest fixture that patches hook_protocol._audit_writer_factory
"""

from unittest.mock import patch

import pytest

from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.ports.driven_ports.audit_log_writer import AuditEvent


def make_capturing_writer(events: list[AuditEvent]):
    """Create an AuditLogWriter that appends events to the given list."""

    class CapturingWriter(NullAuditLogWriter):
        def log_event(self, event: AuditEvent) -> None:
            events.append(event)

    return CapturingWriter()


@pytest.fixture
def audit_events():
    """Patch hook_protocol._audit_writer_factory and capture all audit events.

    Yields the list of captured AuditEvent objects.
    """
    from des.adapters.drivers.hooks import hook_protocol

    events: list[AuditEvent] = []
    writer = make_capturing_writer(events)
    with patch.object(hook_protocol, "_audit_writer_factory", return_value=writer):
        yield events
