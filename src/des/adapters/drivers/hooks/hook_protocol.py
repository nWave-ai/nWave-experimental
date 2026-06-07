"""Shared hook protocol infrastructure.

Provides the common building blocks used by all hook handlers:
- Audit writer factory
- Stdin parsing with protocol anomaly logging
- Diagnostic event loggers (invoked, completed, error, anomaly)
- Protocol constants (exit codes, thresholds)

All audit-aware functions accept an ``audit_writer_factory`` callable so the
caller can control which writer is used.  This enables tests that patch
``adapter._create_audit_writer`` to inject spy writers without coupling
function globals to a specific module.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition (step 4a).
"""

import json
import sys
from collections.abc import Callable

from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter


# ---------------------------------------------------------------------------
# Audit writer factory (default implementation)
# ---------------------------------------------------------------------------


def create_audit_writer() -> AuditLogWriter:
    """Create appropriate AuditLogWriter based on DES configuration.

    Returns JsonlAuditLogWriter by default,
    NullAuditLogWriter when explicitly disabled in .nwave/des-config.json.
    """
    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter

    config = DESConfig()
    if not config.audit_logging_enabled:
        return NullAuditLogWriter()
    return JsonlAuditLogWriter()


# Type alias for the factory callable accepted by all audit-aware functions
AuditWriterFactory = Callable[[], AuditLogWriter]

# Module-level factory variable — the single patch point for tests.
# Tests patch ``hook_protocol._audit_writer_factory`` to inject spy writers.
_audit_writer_factory: AuditWriterFactory = create_audit_writer


def get_audit_writer() -> AuditLogWriter:
    """Get an audit writer using the currently registered factory."""
    return _audit_writer_factory()


def _get_nwave_log_writer(config: object) -> object:
    """Create appropriate NWaveLogWriter based on DES configuration.

    Returns JsonlNWaveLogWriter when logging is enabled,
    NullNWaveLogWriter otherwise.
    """
    from des.adapters.driven.logging.jsonl_nwave_log_writer import (
        JsonlNWaveLogWriter,
    )
    from des.adapters.driven.logging.null_nwave_log_writer import NullNWaveLogWriter
    from des.ports.driven_ports.nwave_log_writer import LogLevel

    if not config.log_enabled:
        return NullNWaveLogWriter()

    level_str = config.log_level.upper()
    level = LogLevel[level_str] if level_str in LogLevel.__members__ else LogLevel.WARN
    return JsonlNWaveLogWriter(level=level)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Threshold in milliseconds above which a hook is considered slow
SLOW_HOOK_THRESHOLD_MS = 5000.0

# Maximum characters to capture from stderr in HOOK_ERROR events
STDERR_CAPTURE_MAX_CHARS = 1000

EXIT_CODE_TO_DECISION = {
    0: "allow",
    1: "error",
    2: "block",
}


# ---------------------------------------------------------------------------
# Stdin parsing
# ---------------------------------------------------------------------------


class StdinParseResult:
    """Result of reading and parsing JSON from stdin.

    Encapsulates three outcomes: empty stdin, JSON parse error, or success.
    """

    __slots__ = ("hook_input", "is_empty", "parse_error")

    def __init__(
        self,
        hook_input: dict | None = None,
        is_empty: bool = False,
        parse_error: str | None = None,
    ) -> None:
        self.hook_input = hook_input
        self.is_empty = is_empty
        self.parse_error = parse_error

    @property
    def ok(self) -> bool:
        """True when stdin was parsed successfully into a dict."""
        return self.hook_input is not None


def read_and_parse_stdin(
    handler: str,
    json_error_fallback: str = "error",
    *,
    audit_writer_factory: AuditWriterFactory | None = None,
) -> StdinParseResult:
    """Read JSON from stdin with protocol anomaly logging.

    Handles the two protocol-level anomalies (empty stdin, malformed JSON)
    that every hook handler must deal with identically.

    Args:
        handler: Name of the calling handler for anomaly log context.
        json_error_fallback: Fallback action to log for JSON parse errors.
            Fail-closed handlers pass "error", fail-open handlers pass "allow".
        audit_writer_factory: Callable returning an AuditLogWriter.
            Falls back to ``create_audit_writer`` if None.

    Returns:
        StdinParseResult with either parsed hook_input, is_empty flag,
        or parse_error string.
    """
    factory = audit_writer_factory or _audit_writer_factory
    input_data = sys.stdin.read()

    if not input_data or not input_data.strip():
        log_protocol_anomaly(
            handler=handler,
            anomaly_type="empty_stdin",
            detail="No input data received on stdin",
            fallback_action="allow",
            audit_writer_factory=factory,
        )
        return StdinParseResult(is_empty=True)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError as e:
        log_protocol_anomaly(
            handler=handler,
            anomaly_type="json_parse_error",
            detail=f"Invalid JSON: {e!s}",
            fallback_action=json_error_fallback,
            audit_writer_factory=factory,
        )
        return StdinParseResult(parse_error=f"Invalid JSON: {e!s}")

    return StdinParseResult(hook_input=hook_input)


# ---------------------------------------------------------------------------
# Diagnostic event loggers
# ---------------------------------------------------------------------------


def log_hook_invoked(
    handler: str,
    summary: dict | None = None,
    hook_id: str | None = None,
    *,
    audit_writer_factory: AuditWriterFactory | None = None,
) -> None:
    """Log a HOOK_INVOKED diagnostic event at handler entry.

    This confirms the hook was actually called by Claude Code.
    Without this, silent passthrough is indistinguishable from hook-not-firing.

    Args:
        handler: Name of the handler being invoked.
        summary: Optional dict of input summary fields.
        hook_id: Optional UUID4 correlation ID. When provided, included in event data.
            When None, the field is omitted (backward compatible).
        audit_writer_factory: Callable returning an AuditLogWriter.
    """
    try:
        factory = audit_writer_factory or _audit_writer_factory
        audit_writer = factory()
        data: dict = {"handler": handler}
        if hook_id is not None:
            data["hook_id"] = hook_id
        if summary:
            data["input_summary"] = summary
        audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_INVOKED",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data=data,
            )
        )
    except Exception:
        pass  # Diagnostic logging must never break the hook


def log_hook_completed(
    hook_id: str,
    handler: str,
    exit_code: int,
    decision: str,
    duration_ms: float,
    task_correlation_id: str | None = None,
    turns_used: int | None = None,
    tokens_used: int | None = None,
    *,
    audit_writer_factory: AuditWriterFactory | None = None,
) -> None:
    """Log a HOOK_COMPLETED diagnostic event at handler exit.

    Emitted in a finally block so it fires on allow, block, AND error paths.
    Wrapped in try/except so logging never breaks the hook.

    Args:
        hook_id: UUID4 correlation ID matching the HOOK_INVOKED event.
        handler: Name of the handler that completed.
        exit_code: Process exit code (0=allow, 1=error, 2=block).
        decision: Human-readable decision string.
        duration_ms: Wall-clock duration of the handler in milliseconds.
        task_correlation_id: Optional UUID4 linking events across the DES task lifecycle.
        turns_used: Optional number of turns used by the subagent.
        tokens_used: Optional number of tokens used by the subagent.
        audit_writer_factory: Callable returning an AuditLogWriter.
    """
    try:
        factory = audit_writer_factory or _audit_writer_factory
        audit_writer = factory()
        data: dict = {
            "hook_id": hook_id,
            "handler": handler,
            "exit_code": exit_code,
            "decision": decision,
            "duration_ms": duration_ms,
        }
        if duration_ms > SLOW_HOOK_THRESHOLD_MS:
            data["slow_hook"] = True
        if task_correlation_id is not None:
            data["task_correlation_id"] = task_correlation_id
        if turns_used is not None:
            data["turns_used"] = turns_used
        if tokens_used is not None:
            data["tokens_used"] = tokens_used
        audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_COMPLETED",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data=data,
            )
        )
    except Exception:
        pass  # Diagnostic logging must never break the hook


def log_protocol_anomaly(
    handler: str,
    anomaly_type: str,
    detail: str,
    fallback_action: str,
    *,
    audit_writer_factory: AuditWriterFactory | None = None,
) -> None:
    """Log a HOOK_PROTOCOL_ANOMALY diagnostic event for early-return paths.

    Args:
        handler: Name of the handler (e.g., 'pre_tool_use', 'subagent_stop').
        anomaly_type: Classification of the anomaly ('empty_stdin' or 'json_parse_error').
        detail: Human-readable description of what happened.
        fallback_action: What the handler did ('allow' or 'error').
        audit_writer_factory: Callable returning an AuditLogWriter.
    """
    try:
        factory = audit_writer_factory or _audit_writer_factory
        audit_writer = factory()
        audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_PROTOCOL_ANOMALY",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={
                    "handler": handler,
                    "anomaly_type": anomaly_type,
                    "detail": detail,
                    "fallback_action": fallback_action,
                },
            )
        )
    except Exception:
        pass  # Anomaly logging must never break the handler


def log_hook_error(
    handler: str,
    error: Exception,
    stderr_capture: str,
    *,
    audit_writer_factory: AuditWriterFactory | None = None,
) -> None:
    """Log a HOOK_ERROR audit event for unhandled exceptions in handlers.

    Args:
        handler: Name of the handler that raised the exception.
        error: The unhandled exception.
        stderr_capture: Captured stderr content (already truncated by caller).
        audit_writer_factory: Callable returning an AuditLogWriter.
    """
    try:
        factory = audit_writer_factory or _audit_writer_factory
        audit_writer = factory()
        audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_ERROR",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={
                    "error": str(error),
                    "handler": handler,
                    "error_type": type(error).__name__,
                    "stderr_capture": stderr_capture,
                },
            )
        )
    except Exception:
        pass  # Don't let audit logging failure mask the original error
