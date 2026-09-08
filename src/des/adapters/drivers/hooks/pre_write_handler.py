"""PreWrite/PreEdit handler — refuses writes to the retired execution log."""

import contextlib
import io
import json
import time
import uuid

from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import des_task_signal, hook_protocol
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.ports.driven_ports.audit_log_writer import AuditEvent


def _log_pre_write_decision(
    hook_id: str,
    event_type: str,
    file_path: str,
    reason: str,
) -> None:
    """Log a HOOK_PRE_WRITE_ALLOWED or HOOK_PRE_WRITE_BLOCKED diagnostic event."""
    try:
        audit_writer = hook_protocol.get_audit_writer()
        audit_writer.log_event(
            AuditEvent(
                event_type=event_type,
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={
                    "hook_id": hook_id,
                    "file_path": file_path,
                    "reason": reason,
                },
            )
        )
    except Exception:
        pass  # Diagnostic logging must never break the hook


def handle_pre_write() -> int:
    """Handle PreToolUse for Write/Edit."""
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin(
                "pre_write",
                json_error_fallback="allow",
            )

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                # Write/Edit fails open on parse errors
                return 0

            hook_input = stdin_result.hook_input

            # Extract file path from tool_input
            tool_input = hook_input.get("tool_input", {})
            file_path = tool_input.get("file_path", "")

            # --- Execution log guard: always block direct writes ---
            if file_path and file_path.endswith("execution-log.json"):
                block_reason = (
                    "execution-log.json belongs to a retired workflow and cannot be "
                    "created or modified.\n\n"
                    "Use the current atdd_pure delivery inputs: the selected feature "
                    "delta and its acceptance tests. Do not recreate retired phase records."
                )
                _log_pre_write_decision(
                    hook_id=hook_id,
                    event_type="HOOK_PRE_WRITE_BLOCKED",
                    file_path=file_path,
                    reason="execution_log_direct_write",
                )
                print(json.dumps({"decision": "block", "reason": block_reason}))
                return 2

            log_hook_invoked(
                "pre_write",
                {
                    "file_path": file_path,
                    "des_task_active": des_task_signal.DES_TASK_ACTIVE_FILE.exists(),
                },
                hook_id=hook_id,
            )
            _log_pre_write_decision(
                hook_id=hook_id,
                event_type="HOOK_PRE_WRITE_ALLOWED",
                file_path=file_path,
                reason="ordinary_write",
            )
            exit_code = 0
            return exit_code

    except Exception as e:
        # Fail-open for Write/Edit (unlike Task which is fail-closed)
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error(
            "pre_write",
            e,
            stderr_capture,
        )
        exit_code = 0
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="pre_write",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
        )
