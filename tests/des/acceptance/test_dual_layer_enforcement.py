"""Acceptance coverage for PostToolUse notification outcomes."""

from __future__ import annotations

from typing import Any

from des.application.post_tool_use_service import PostToolUseService
from des.ports.driven_ports.audit_log_reader import AuditLogReader


class InMemoryAuditLogReader(AuditLogReader):
    """In-memory audit-log reader for PostToolUse acceptance coverage."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._entries = entries or []

    def read_last_entry(
        self,
        event_type: str | None = None,
        feature_name: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any] | None:
        for entry in reversed(self._entries):
            if event_type and entry.get("event") != event_type:
                continue
            if feature_name and entry.get("feature_name") != feature_name:
                continue
            if step_id and entry.get("step_id") != step_id:
                continue
            return entry
        return None


def _build_post_tool_use_service(
    entries: list[dict[str, Any]] | None = None,
) -> PostToolUseService:
    return PostToolUseService(audit_reader=InMemoryAuditLogReader(entries))


class TestPostToolUseEnforcement:
    """Acceptance tests through the PostToolUse driving port."""

    def test_post_tool_use_detects_failed_audit(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_FAILED",
                    "timestamp": "2026-02-06T10:00:00+00:00",
                    "feature_name": "test-project",
                    "step_id": "01-01",
                    "validation_errors": ["Missing phases: GREEN, REVIEW, COMMIT"],
                    "allowed_despite_failure": True,
                }
            ]
        )
        additional_context = service.check_completion_status(is_des_task=True)
        assert additional_context is not None, "Expected additionalContext"
        assert "FAILED" in additional_context or "failed" in additional_context.lower()

    def test_post_tool_use_passes_through_on_passed(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_PASSED",
                    "timestamp": "2026-02-06T10:00:00+00:00",
                    "feature_name": "test-project",
                    "step_id": "01-01",
                }
            ]
        )
        assert service.check_completion_status(is_des_task=False) is None

    def test_post_tool_use_passes_through_for_non_des(self):
        assert (
            _build_post_tool_use_service().check_completion_status(is_des_task=False)
            is None
        )

    def test_post_tool_use_additional_context_has_recovery_details(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_FAILED",
                    "timestamp": "2026-02-06T10:00:00+00:00",
                    "feature_name": "auth-upgrade",
                    "step_id": "02-03",
                    "validation_errors": ["Missing phases: GREEN, COMMIT"],
                    "allowed_despite_failure": True,
                }
            ]
        )
        ctx = service.check_completion_status(is_des_task=True)
        assert ctx is not None
        assert "auth-upgrade" in ctx and "02-03" in ctx
        assert "Missing phases" in ctx or "GREEN" in ctx

    def test_missing_audit_log_graceful_passthrough(self):
        assert (
            _build_post_tool_use_service().check_completion_status(is_des_task=False)
            is None
        )

    def test_post_tool_use_injects_continuation_on_des_passed(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_PASSED",
                    "timestamp": "2026-02-09T10:00:00+00:00",
                    "feature_name": "auth-upgrade",
                    "step_id": "01-01",
                }
            ]
        )
        ctx = service.check_completion_status(is_des_task=True)
        assert ctx is not None
        for token in (
            "COMPLETED",
            "auth-upgrade",
            "01-01",
            "DES-VALIDATION",
            "DES-PROJECT-ID",
            "DES-STEP-ID",
            "execute.md",
        ):
            assert token in ctx, f"Expected {token!r} in continuation context: {ctx}"

    def test_post_tool_use_failure_includes_des_reminder_for_des_task(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_FAILED",
                    "timestamp": "2026-02-09T10:00:00+00:00",
                    "feature_name": "auth-upgrade",
                    "step_id": "02-01",
                    "validation_errors": ["Missing phases: GREEN, COMMIT"],
                    "allowed_despite_failure": True,
                }
            ]
        )
        ctx = service.check_completion_status(is_des_task=True)
        assert ctx is not None
        for token in (
            "FAILED",
            "auth-upgrade",
            "02-01",
            "DES-VALIDATION",
            "execute.md",
        ):
            assert token in ctx, f"Expected {token!r} in failure context: {ctx}"

    def test_post_tool_use_non_des_task_no_continuation_despite_passed_audit(self):
        service = _build_post_tool_use_service(
            entries=[
                {
                    "event": "HOOK_SUBAGENT_STOP_PASSED",
                    "timestamp": "2026-02-09T10:00:00+00:00",
                    "feature_name": "auth-upgrade",
                    "step_id": "01-01",
                }
            ]
        )
        assert service.check_completion_status(is_des_task=False) is None
