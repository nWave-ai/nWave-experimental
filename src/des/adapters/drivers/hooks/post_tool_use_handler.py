"""PostToolUse handler — injects failure notifications into parent conversation.

Reads the audit log for the most recent HOOK_SUBAGENT_STOP_FAILED entry.
If found, injects additionalContext so the orchestrator knows a sub-agent failed.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.
"""

import contextlib
import io
import json
import time
import uuid

from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import hook_protocol
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.skill_tracking_hooks import (
    maybe_track_skill_load as _maybe_track_skill_load,
)
from des.ports.driven_ports.audit_log_writer import AuditEvent


def _log_post_tool_use_decision(
    hook_id: str,
    event_type: str,
    is_des_task: bool,
    **extra: str,
) -> None:
    """Log a HOOK_POST_TOOL_USE_INJECTED or HOOK_POST_TOOL_USE_PASSTHROUGH event."""
    try:
        audit_writer = hook_protocol.get_audit_writer()
        data: dict = {
            "hook_id": hook_id,
            "is_des_task": is_des_task,
        }
        data.update(extra)
        audit_writer.log_event(
            AuditEvent(
                event_type=event_type,
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data=data,
            )
        )
    except Exception:
        pass  # Decision logging must never break the hook


def handle_post_tool_use() -> int:
    """Handle post-tool-use command: notify parent of sub-agent failures.

    Reads the audit log for the most recent HOOK_SUBAGENT_STOP_FAILED entry.
    If found, injects additionalContext into the parent's conversation so
    the orchestrator knows a sub-agent failed.

    Protocol translation only -- business logic in PostToolUseService.

    Returns:
        0 always (PostToolUse should never block)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin(
                "post_tool_use",
                json_error_fallback="allow",
            )

            if stdin_result.is_empty:
                print(json.dumps({}))
                return 0

            if stdin_result.parse_error:
                # PostToolUse fails open on parse errors
                print(json.dumps({}))
                return 0

            hook_input = stdin_result.hook_input

            # Diagnostic: confirm hook was invoked
            log_hook_invoked(
                "post_tool_use",
                {
                    "tool_name": hook_input.get("tool_name"),
                },
                hook_id=hook_id,
            )

            # Skill loading tracking (non-blocking, fail-open)
            _maybe_track_skill_load(hook_input)

            # Check if the just-completed Task was a DES task (had DES markers)
            tool_input = hook_input.get("tool_input", {})
            prompt = tool_input.get("prompt", "")
            is_des_task = "DES-VALIDATION" in prompt

            # Delegate to PostToolUseService
            from des.adapters.driven.logging.jsonl_audit_log_reader import (
                JsonlAuditLogReader,
            )
            from des.application.post_tool_use_service import PostToolUseService

            reader = JsonlAuditLogReader()
            service = PostToolUseService(audit_reader=reader)
            additional_context = service.check_completion_status(
                is_des_task=is_des_task,
            )

            if additional_context:
                # Determine context_type from content
                if "INCOMPLETE" in additional_context or "FAILED" in additional_context:
                    context_type = "failure_notification"
                else:
                    context_type = "continuation"
                _log_post_tool_use_decision(
                    hook_id=hook_id,
                    event_type="HOOK_POST_TOOL_USE_INJECTED",
                    is_des_task=is_des_task,
                    context_type=context_type,
                )
                response = {"additionalContext": additional_context}
            else:
                reason = "no_completion_status" if is_des_task else "non_des_task"
                _log_post_tool_use_decision(
                    hook_id=hook_id,
                    event_type="HOOK_POST_TOOL_USE_PASSTHROUGH",
                    is_des_task=is_des_task,
                    reason=reason,
                )
                response = {}

            print(json.dumps(response))
            return 0

    except Exception as e:
        # PostToolUse should never block - fail open
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error(
            "post_tool_use",
            e,
            stderr_capture,
        )
        print(json.dumps({}))
        return 0
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="post_tool_use",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
        )
