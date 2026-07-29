"""Regression ATs: every audit-log entry carries a DECLARED `run_context`.

The audit log mixes events born in different contexts -- a test run, a real
gate firing, an interactive session, CI -- and nothing distinguishes them.
Any downstream count ("how many times did this gate reject?") sums real
rejections together with rejections manufactured by the tests that verify the
gate. The number is wrong by construction and looks like a number.

Measured anchor (`src/des/runtime/freshness.py:141`):
`HEALTH_GATE_INSTALL_FRESHNESS_STALE` fired 14,378 times over 8 days -- those
were per-subprocess emissions, not real events. Without `run_context` that
distinction is not recoverable after the fact.

Contract under test:
- The context is a DECLARED fact (the `NWAVE_RUN_CONTEXT` environment
  variable), NEVER inferred from an ambiguous signal like "am I running
  under pytest?".
- An undeclared context is the explicit third state `unknown`, NEVER an
  absent field -- an absent field reproduces the same hole one level down.
- The declared context is authoritative: an event `data` payload cannot
  shadow it.
"""

from __future__ import annotations

import json
from typing import Any

from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.domain.run_context import (
    RUN_CONTEXT_ENV,
    UNKNOWN_RUN_CONTEXT,
    resolve_run_context,
)
from des.ports.driven_ports.audit_log_writer import AuditEvent


def _write_one(tmp_path, event: AuditEvent, monkeypatch, env: dict[str, str]) -> Any:
    """Write one event under an explicit environment and return its JSON entry."""
    monkeypatch.delenv(RUN_CONTEXT_ENV, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    writer = JsonlAuditLogWriter(log_dir=tmp_path / "logs")
    writer.log_event(event)
    lines = [
        line for line in writer._get_log_file().read_text().splitlines() if line.strip()
    ]
    assert len(lines) == 1, f"expected exactly one JSONL line, got {len(lines)}"
    return json.loads(lines[0])


def _event(**overrides: Any) -> AuditEvent:
    payload: dict[str, Any] = {
        "event_type": "HOOK_PRE_TOOL_USE_ALLOWED",
        "timestamp": "2026-07-28T12:00:00.000Z",
    }
    payload.update(overrides)
    return AuditEvent(**payload)


class TestAuditEntryCarriesDeclaredRunContext:
    """The declared run context reaches the serialized entry verbatim."""

    def test_declared_run_context_is_written_at_json_root_level(
        self, tmp_path, monkeypatch
    ):
        entry = _write_one(tmp_path, _event(), monkeypatch, {RUN_CONTEXT_ENV: "gate"})

        assert entry.get("run_context") == "gate"

    def test_declared_run_context_is_written_for_every_event_type(
        self, tmp_path, monkeypatch
    ):
        entry = _write_one(
            tmp_path,
            _event(event_type="HEALTH_GATE_INSTALL_FRESHNESS_STALE"),
            monkeypatch,
            {RUN_CONTEXT_ENV: "ci"},
        )

        assert entry.get("run_context") == "ci"


class TestUndeclaredRunContextIsExplicitNotAbsent:
    """The third state is a value, not a missing key."""

    def test_writer_never_omits_the_run_context_field_when_undeclared(
        self, tmp_path, monkeypatch
    ):
        entry = _write_one(tmp_path, _event(), monkeypatch, {})

        assert "run_context" in entry, (
            "an undeclared context must serialize as the explicit "
            f"{UNKNOWN_RUN_CONTEXT!r} value, never as an absent field -- "
            "an absent field reproduces the same counting hole one level down"
        )
        assert entry.get("run_context") == UNKNOWN_RUN_CONTEXT

    def test_writer_does_not_emit_an_empty_run_context_for_a_blank_declaration(
        self, tmp_path, monkeypatch
    ):
        entry = _write_one(tmp_path, _event(), monkeypatch, {RUN_CONTEXT_ENV: "   "})

        assert entry.get("run_context") == UNKNOWN_RUN_CONTEXT


class TestRunContextIsNeverInferred:
    """Declared fact only -- no ambient signal may substitute for it."""

    def test_writer_never_infers_run_context_from_the_pytest_environment(
        self, tmp_path, monkeypatch
    ):
        # These tests themselves run under pytest, so PYTEST_CURRENT_TEST is
        # already live; CI is set explicitly to stack the ambient signals.
        entry = _write_one(tmp_path, _event(), monkeypatch, {"CI": "true"})

        assert entry.get("run_context") == UNKNOWN_RUN_CONTEXT, (
            "the context must be DECLARED; inferring 'test'/'ci' from ambient "
            "signals is exactly the ambiguity this field exists to remove"
        )

    def test_resolver_never_reads_an_environment_key_other_than_the_declared_one(self):
        ambient = {
            "CI": "true",
            "PYTEST_CURRENT_TEST": "tests/x.py::test_y (call)",
            "GITHUB_ACTIONS": "true",
            "DES_ENV": "production",
        }

        assert resolve_run_context(ambient) == UNKNOWN_RUN_CONTEXT

    def test_resolver_reads_the_declared_key_verbatim(self):
        assert resolve_run_context({RUN_CONTEXT_ENV: "interactive"}) == "interactive"


class TestEventPayloadCannotShadowTheDeclaredContext:
    """The declared context wins over anything an event carries."""

    def test_event_data_does_not_override_the_declared_run_context(
        self, tmp_path, monkeypatch
    ):
        entry = _write_one(
            tmp_path,
            _event(data={"run_context": "spoofed"}),
            monkeypatch,
            {RUN_CONTEXT_ENV: "gate"},
        )

        assert entry.get("run_context") == "gate", (
            "an event payload must not be able to relabel the run context; "
            "the declared environment fact is authoritative"
        )
