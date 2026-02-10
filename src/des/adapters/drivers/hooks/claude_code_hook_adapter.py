#!/usr/bin/env python3
"""Claude Code hook adapter with DES integration.

This adapter bridges Claude Code's hook protocol (JSON stdin/stdout, exit codes)
to DES application services (PreToolUseService, SubagentStopService, PostToolUseService).

Protocol-only: no business logic here. All decisions delegated to application layer.

Commands:
  python3 -m src.des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use
  python3 -m src.des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop
  python3 -m src.des.adapters.drivers.hooks.claude_code_hook_adapter post-tool-use

Exit Codes:
  0 = allow/continue
  1 = fail-closed error (BLOCKS execution)
  2 = block/reject (validation failed)

Protocol:
  - Input: JSON on stdin
  - Output: JSON on stdout
  - Fail-closed: Any error causes exit 1 (BLOCK)
"""

import json
import os
import sys
import uuid
from pathlib import Path


# Add project root to sys.path for standalone script execution
if __name__ == "__main__":
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from des.adapters.driven.git.git_commit_verifier import GitCommitVerifier
from des.adapters.driven.hooks.yaml_execution_log_reader import (
    YamlExecutionLogReader,
)
from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.driven.validation.git_scope_checker import GitScopeChecker
from des.application.pre_tool_use_service import PreToolUseService
from des.application.subagent_stop_service import SubagentStopService
from des.application.validator import TemplateValidator
from des.domain.des_enforcement_policy import DesEnforcementPolicy
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
from des.domain.max_turns_policy import MaxTurnsPolicy
from des.domain.session_guard_policy import SessionGuardPolicy
from des.domain.step_completion_validator import StepCompletionValidator
from des.domain.tdd_schema import get_tdd_schema
from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


def _create_audit_writer() -> AuditLogWriter:
    """Create appropriate AuditLogWriter based on DES configuration.

    Returns NullAuditLogWriter when audit logging is disabled (default),
    JsonlAuditLogWriter when explicitly enabled in .nwave/des-config.json.
    """
    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter

    config = DESConfig()
    if not config.audit_logging_enabled:
        return NullAuditLogWriter()
    return JsonlAuditLogWriter()


def create_pre_tool_use_service() -> PreToolUseService:
    """Create PreToolUseService with production dependencies.

    Returns:
        PreToolUseService configured for production use
    """
    time_provider = SystemTimeProvider()
    audit_writer = _create_audit_writer()

    return PreToolUseService(
        max_turns_policy=MaxTurnsPolicy(),
        marker_parser=DesMarkerParser(),
        prompt_validator=TemplateValidator(),
        audit_writer=audit_writer,
        time_provider=time_provider,
        enforcement_policy=DesEnforcementPolicy(),
        completeness_policy=MarkerCompletenessPolicy(),
    )


def create_subagent_stop_service() -> SubagentStopService:
    """Create SubagentStopService with production dependencies.

    Returns:
        SubagentStopService configured for production use
    """
    from des.domain.log_integrity_validator import LogIntegrityValidator

    time_provider = SystemTimeProvider()
    audit_writer = _create_audit_writer()
    schema = get_tdd_schema()

    return SubagentStopService(
        log_reader=YamlExecutionLogReader(),
        completion_validator=StepCompletionValidator(schema=schema),
        scope_checker=GitScopeChecker(),
        audit_writer=audit_writer,
        time_provider=time_provider,
        commit_verifier=GitCommitVerifier(),
        integrity_validator=LogIntegrityValidator(
            schema=schema, time_provider=time_provider
        ),
    )


def _log_hook_invoked(
    handler: str, summary: dict | None = None, hook_id: str | None = None
) -> None:
    """Log a HOOK_INVOKED diagnostic event at handler entry.

    This confirms the hook was actually called by Claude Code.
    Without this, silent passthrough is indistinguishable from hook-not-firing.

    Args:
        handler: Name of the handler being invoked.
        summary: Optional dict of input summary fields.
        hook_id: Optional UUID4 correlation ID. When provided, included in event data.
            When None, the field is omitted (backward compatible).
    """
    try:
        audit_writer = _create_audit_writer()
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


DES_SESSION_DIR = Path(".nwave") / "des"
DES_DELIVER_SESSION_FILE = DES_SESSION_DIR / "deliver-session.json"
DES_TASK_ACTIVE_FILE = DES_SESSION_DIR / "des-task-active"


def _signal_file_for(project_id: str, step_id: str) -> Path:
    """Return the namespaced signal file path for a project/step pair."""
    safe_name = f"{project_id}--{step_id}".replace("/", "_")
    return DES_SESSION_DIR / f"des-task-active-{safe_name}"


def _create_des_task_signal(step_id: str = "", project_id: str = "") -> None:
    """Create DES task active signal file, namespaced by project/step.

    Called when PreToolUse allows a DES-validated Task.
    Indicates a DES subagent is currently running.
    """
    try:
        DES_SESSION_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        signal = json.dumps(
            {
                "step_id": step_id,
                "project_id": project_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        signal_file = _signal_file_for(project_id, step_id)
        signal_file.write_text(signal)
        # Also write legacy singleton for backward compatibility
        DES_TASK_ACTIVE_FILE.write_text(signal)
    except Exception:
        pass  # Signal creation must never break the hook


def _read_des_task_signal(project_id: str = "", step_id: str = "") -> dict | None:
    """Read DES task active signal file before removal.

    Tries namespaced file first, falls back to legacy singleton.

    Returns:
        Signal data dict with step_id, project_id, and created_at, or None.
    """
    try:
        # Try namespaced signal first (race-condition resistant)
        if project_id and step_id:
            namespaced = _signal_file_for(project_id, step_id)
            if namespaced.exists():
                return json.loads(namespaced.read_text())
        # Fallback to legacy singleton
        if DES_TASK_ACTIVE_FILE.exists():
            return json.loads(DES_TASK_ACTIVE_FILE.read_text())
    except Exception:
        pass
    return None


def _remove_des_task_signal(project_id: str = "", step_id: str = "") -> None:
    """Remove DES task active signal file(s).

    Called when SubagentStop fires (DES task completed).
    Removes both namespaced and legacy singleton files.
    """
    try:
        if project_id and step_id:
            namespaced = _signal_file_for(project_id, step_id)
            if namespaced.exists():
                namespaced.unlink()
        if DES_TASK_ACTIVE_FILE.exists():
            DES_TASK_ACTIVE_FILE.unlink()
    except Exception:
        pass  # Signal cleanup must never break the hook


def handle_pre_tool_use() -> int:
    """Handle PreToolUse command: validate Task tool invocation.

    Protocol translation only -- all decisions delegated to PreToolUseService.

    Returns:
        0 if validation passes (allow)
        1 if error occurs (fail-closed)
        2 if validation fails (block)
    """
    try:
        hook_id = str(uuid.uuid4())

        # Read JSON from stdin
        input_data = sys.stdin.read()

        # Resilience 9a: empty stdin → allow passthrough (not fail-closed)
        if not input_data or not input_data.strip():
            print(json.dumps({"decision": "allow"}))
            return 0

        # Parse JSON
        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError as e:
            response = {"status": "error", "reason": f"Invalid JSON: {e!s}"}
            print(json.dumps(response))
            return 1

        # Diagnostic: confirm hook was invoked
        tool_input = hook_input.get("tool_input", {})
        _log_hook_invoked(
            "pre_tool_use",
            {
                "subagent_type": tool_input.get("subagent_type"),
                "has_max_turns": tool_input.get("max_turns") is not None,
            },
            hook_id=hook_id,
        )

        # Extract protocol fields
        # Claude Code sends: {"tool_name": "Task", "tool_input": {...}, ...}
        prompt = tool_input.get("prompt", "")
        max_turns = tool_input.get("max_turns")

        # Delegate to application service
        service = create_pre_tool_use_service()
        decision = service.validate(
            PreToolUseInput(
                prompt=prompt,
                max_turns=max_turns,
                subagent_type=tool_input.get("subagent_type"),
            )
        )

        # Translate HookDecision to protocol response
        if decision.action == "allow":
            # Create DES task signal if this is a DES-validated task
            if "DES-VALIDATION" in prompt:
                # Extract step-id and project-id from DES markers
                step_id_marker = ""
                project_id_marker = ""
                parser = DesMarkerParser()
                markers = parser.parse(prompt)
                if markers.step_id:
                    step_id_marker = markers.step_id
                if markers.project_id:
                    project_id_marker = markers.project_id
                _create_des_task_signal(
                    step_id=step_id_marker, project_id=project_id_marker
                )
            response = {"decision": "allow"}
            print(json.dumps(response))
            return 0
        else:
            response = {
                "decision": "block",
                "reason": decision.reason or "Validation failed",
            }
            print(json.dumps(response))
            return decision.exit_code

    except Exception as e:
        # Fail-closed: any error blocks execution
        # Log error to audit trail so it is visible in compliance logs
        try:
            audit_writer = _create_audit_writer()
            audit_writer.log_event(
                AuditEvent(
                    event_type="HOOK_ERROR",
                    timestamp=SystemTimeProvider().now_utc().isoformat(),
                    data={"error": str(e), "handler": "pre_tool_use"},
                )
            )
        except Exception:
            pass  # Don't let audit logging failure mask the original error
        response = {"status": "error", "reason": f"Unexpected error: {e!s}"}
        print(json.dumps(response))
        return 1


def extract_des_context_from_transcript(transcript_path: str) -> dict | None:
    """Extract DES markers from an agent's transcript file.

    Reads the JSONL transcript, finds the first user message (which contains
    the Task prompt), and extracts DES-PROJECT-ID and DES-STEP-ID markers.

    Args:
        transcript_path: Absolute path to the agent's transcript JSONL file

    Returns:
        dict with "project_id" and "step_id" if DES markers found, None otherwise
    """
    # Resilience 9c: missing transcript file → return None silently
    if not Path(transcript_path).exists():
        return None

    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Look for user messages containing DES markers
                message = entry.get("message", {})
                if not isinstance(message, dict):
                    continue

                content = message.get("content", "")

                # Handle content as string or list of text blocks
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    content = "\n".join(text_parts)

                if not isinstance(content, str) or "DES-VALIDATION" not in content:
                    continue

                # Found DES markers - parse them
                parser = DesMarkerParser()
                markers = parser.parse(content)

                if markers.is_des_task and markers.project_id and markers.step_id:
                    return {
                        "project_id": markers.project_id,
                        "step_id": markers.step_id,
                    }

                # DES marker present but missing project_id or step_id
                return None

    except (OSError, PermissionError) as e:
        # Log transcript read failure for diagnostics
        try:
            _create_audit_writer().log_event(
                AuditEvent(
                    event_type="HOOK_TRANSCRIPT_ERROR",
                    timestamp=SystemTimeProvider().now_utc().isoformat(),
                    data={"error": str(e), "transcript_path": transcript_path},
                )
            )
        except Exception:
            pass
        return None

    # No DES markers found in any message
    try:
        _create_audit_writer().log_event(
            AuditEvent(
                event_type="HOOK_TRANSCRIPT_NO_MARKERS",
                timestamp=SystemTimeProvider().now_utc().isoformat(),
                data={"transcript_path": transcript_path},
            )
        )
    except Exception:
        pass
    return None


def _resolve_des_context(
    hook_input: dict,
) -> tuple[str, str, str] | tuple[None, dict, int]:
    """Resolve DES context (execution_log_path, project_id, step_id) from hook input.

    Supports two protocols:
    1. Direct DES format (CLI testing): {"executionLogPath", "projectId", "stepId"}
    2. Claude Code protocol (live hooks): {"agent_transcript_path", "cwd", ...}

    Returns:
        On success: (execution_log_path, project_id, step_id)
        On error/passthrough: (None, response_dict, exit_code)
    """
    execution_log_path = hook_input.get("executionLogPath")
    project_id = hook_input.get("projectId")
    step_id = hook_input.get("stepId")

    uses_direct_des_protocol = execution_log_path or project_id or step_id

    if uses_direct_des_protocol:
        if not (execution_log_path and project_id and step_id):
            return (
                None,
                {
                    "status": "error",
                    "reason": "Missing required fields: executionLogPath, projectId, and stepId are all required",
                },
                1,
            )
        if not Path(execution_log_path).is_absolute():
            return (
                None,
                {
                    "status": "error",
                    "reason": f"executionLogPath must be absolute (got: {execution_log_path})",
                },
                1,
            )
        return execution_log_path, project_id, step_id

    # Claude Code protocol - extract DES context from transcript
    agent_transcript_path = hook_input.get("agent_transcript_path")
    cwd = hook_input.get("cwd", "")

    des_context = None
    if agent_transcript_path:
        des_context = extract_des_context_from_transcript(agent_transcript_path)

    if des_context is None:
        return None, {"decision": "allow"}, 0

    project_id = des_context["project_id"]
    step_id = des_context["step_id"]
    execution_log_path = os.path.join(
        cwd, "docs", "feature", project_id, "execution-log.yaml"
    )
    return execution_log_path, project_id, step_id


def _build_block_notification(
    project_id: str, step_id: str, execution_log_path: str, decision
) -> dict:
    """Build protocol response for a blocked subagent stop decision."""
    reason = decision.reason or "Validation failed"

    recovery_suggestions = decision.recovery_suggestions or []
    recovery_steps = "\n".join(
        [f"  {i + 1}. {s}" for i, s in enumerate(recovery_suggestions)]
    )

    notification = f"""STOP HOOK VALIDATION FAILED

Step: {project_id}/{step_id}
Execution Log: {execution_log_path}
Status: FAILED
Error: {reason}

RECOVERY REQUIRED:
{recovery_steps}

The step validation failed. You MUST fix these issues before proceeding.

IMPORTANT: Only the executing agent may write to execution-log.yaml.
The orchestrator must RE-DISPATCH the agent to execute missing phases.
Never write log entries for phases that were not actually executed."""

    return {
        "decision": "block",
        "reason": notification,
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": notification,
        },
        "systemMessage": f"DES STEP INCOMPLETE [{project_id}/{step_id}]: {reason}",
    }


def handle_subagent_stop() -> int:
    """Handle subagent-stop command: validate step completion.

    Protocol translation only -- all decisions delegated to SubagentStopService.

    Claude Code sends: {"agent_id", "agent_type", "agent_transcript_path", "cwd", ...}
    DES context (project_id, step_id) is extracted from the agent's transcript.
    Non-DES agents (no markers in transcript) are allowed through.

    Returns:
        0 if gate passes or non-DES agent
        1 if error occurs (fail-closed)
        2 if gate fails (BLOCKS orchestrator)
    """
    try:
        hook_id = str(uuid.uuid4())

        input_data = sys.stdin.read()

        # Resilience 9a: empty stdin → allow passthrough (not fail-closed)
        if not input_data or not input_data.strip():
            print(json.dumps({"decision": "allow"}))
            return 0

        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError as e:
            response = {"status": "error", "reason": f"Invalid JSON: {e!s}"}
            print(json.dumps(response))
            return 1

        # Diagnostic: confirm hook was invoked with agent details
        _log_hook_invoked(
            "subagent_stop",
            {
                "agent_type": hook_input.get("agent_type"),
                "agent_id": hook_input.get("agent_id"),
                "has_transcript": hook_input.get("agent_transcript_path") is not None,
            },
            hook_id=hook_id,
        )

        # Resolve DES context from either protocol
        result = _resolve_des_context(hook_input)
        if result[0] is None:
            # Error or non-DES passthrough — log it for diagnostics
            _, response, exit_code = result
            _log_hook_invoked(
                "subagent_stop_passthrough",
                {
                    "reason": "non_des_or_error",
                    "agent_type": hook_input.get("agent_type"),
                    "agent_id": hook_input.get("agent_id"),
                    "has_transcript": hook_input.get("agent_transcript_path")
                    is not None,
                    "transcript_path": hook_input.get("agent_transcript_path"),
                    "exit_code": exit_code,
                },
                hook_id=hook_id,
            )
            print(json.dumps(response))
            return exit_code
        execution_log_path, project_id, step_id = result

        # Read task_start_time from signal BEFORE removing it
        task_start_time = ""
        signal_data = _read_des_task_signal(project_id=project_id, step_id=step_id)
        if signal_data:
            task_start_time = signal_data.get("created_at", "")

        # Clean up DES task signal (subagent finished)
        _remove_des_task_signal(project_id=project_id, step_id=step_id)

        # Delegate to application service
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        stop_hook_active = bool(hook_input.get("stop_hook_active", False))
        # Pass cwd for commit verification from both protocols.
        # Claude Code sends cwd in hook input JSON.
        cwd = hook_input.get("cwd", "")
        service = create_subagent_stop_service()
        decision = service.validate(
            SubagentStopContext(
                execution_log_path=execution_log_path,
                project_id=project_id,
                step_id=step_id,
                stop_hook_active=stop_hook_active,
                cwd=cwd,
                task_start_time=task_start_time,
            )
        )

        # Translate HookDecision to protocol response
        if decision.action == "allow":
            print(json.dumps({"decision": "allow"}))
            return 0

        response = _build_block_notification(
            project_id, step_id, execution_log_path, decision
        )
        print(json.dumps(response))
        # Exit 0 so Claude Code processes the JSON (exit 2 ignores stdout)
        return 0

    except Exception as e:
        # Fail-closed: any error blocks execution via stderr + exit 1
        # Log error to audit trail so it is visible in compliance logs
        try:
            audit_writer = _create_audit_writer()
            audit_writer.log_event(
                AuditEvent(
                    event_type="HOOK_ERROR",
                    timestamp=SystemTimeProvider().now_utc().isoformat(),
                    data={"error": str(e), "handler": "subagent_stop"},
                )
            )
        except Exception:
            pass  # Don't let audit logging failure mask the original error
        print(f"SubagentStop hook error: {e!s}", file=sys.stderr)
        return 1


def handle_post_tool_use() -> int:
    """Handle post-tool-use command: notify parent of sub-agent failures.

    Reads the audit log for the most recent HOOK_SUBAGENT_STOP_FAILED entry.
    If found, injects additionalContext into the parent's conversation so
    the orchestrator knows a sub-agent failed.

    Protocol translation only -- business logic in PostToolUseService.

    Returns:
        0 always (PostToolUse should never block)
    """
    try:
        hook_id = str(uuid.uuid4())

        # Read JSON from stdin
        input_data = sys.stdin.read()

        if not input_data or not input_data.strip():
            # Non-DES or missing input: passthrough
            print(json.dumps({}))
            return 0

        # Parse JSON (ignore parse errors gracefully)
        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError:
            print(json.dumps({}))
            return 0

        # Diagnostic: confirm hook was invoked
        _log_hook_invoked(
            "post_tool_use",
            {
                "tool_name": hook_input.get("tool_name"),
            },
            hook_id=hook_id,
        )

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
            response = {"additionalContext": additional_context}
        else:
            response = {}

        print(json.dumps(response))
        return 0

    except Exception as e:
        # PostToolUse should never block - fail open
        # Log error to audit trail so it is visible in compliance logs
        try:
            audit_writer = _create_audit_writer()
            audit_writer.log_event(
                AuditEvent(
                    event_type="HOOK_ERROR",
                    timestamp=SystemTimeProvider().now_utc().isoformat(),
                    data={"error": str(e), "handler": "post_tool_use"},
                )
            )
        except Exception:
            pass  # Don't let audit logging failure mask the original error
        print(json.dumps({}))
        return 0


def handle_pre_write() -> int:
    """Handle PreToolUse for Write/Edit: guard source writes during deliver.

    Shell fast-path: the hook command tests for deliver-session.json BEFORE
    invoking Python. This handler only runs during active deliver sessions.

    Returns:
        0 if write is allowed
        2 if write is blocked (source file during deliver without DES task)
    """
    try:
        hook_id = str(uuid.uuid4())

        input_data = sys.stdin.read()

        if not input_data or not input_data.strip():
            # No input = allow (fail-open for Write/Edit)
            print(json.dumps({"decision": "allow"}))
            return 0

        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError:
            print(json.dumps({"decision": "allow"}))
            return 0

        # Extract file path from tool_input
        tool_input = hook_input.get("tool_input", {})

        # Diagnostic: confirm hook was invoked
        _log_hook_invoked(
            "pre_write",
            {
                "file_path": tool_input.get("file_path"),
            },
            hook_id=hook_id,
        )
        file_path = tool_input.get("file_path", "")

        # Check session and signal state
        session_active = DES_DELIVER_SESSION_FILE.exists()
        des_task_active = DES_TASK_ACTIVE_FILE.exists()

        policy = SessionGuardPolicy()
        result = policy.check(
            file_path=file_path,
            session_active=session_active,
            des_task_active=des_task_active,
        )

        if result.blocked:
            response = {
                "decision": "block",
                "reason": result.reason or "Source write blocked during deliver",
            }
            print(json.dumps(response))
            return 2
        else:
            print(json.dumps({"decision": "allow"}))
            return 0

    except Exception:
        # Fail-open for Write/Edit (unlike Task which is fail-closed)
        print(json.dumps({"decision": "allow"}))
        return 0


def main() -> None:
    """Hook adapter entry point - routes command to appropriate handler."""
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "status": "error",
                    "reason": "Missing command argument (pre-tool-use or subagent-stop)",
                }
            )
        )
        sys.exit(1)

    command = sys.argv[1]

    if command in ("pre-tool-use", "pre-task"):
        # "pre-task" accepted for backward compatibility
        exit_code = handle_pre_tool_use()
    elif command == "subagent-stop":
        exit_code = handle_subagent_stop()
    elif command == "post-tool-use":
        exit_code = handle_post_tool_use()
    elif command in ("pre-write", "pre-edit"):
        exit_code = handle_pre_write()
    else:
        print(json.dumps({"status": "error", "reason": f"Unknown command: {command}"}))
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
