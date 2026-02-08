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
from pathlib import Path


# Add project root to sys.path for standalone script execution
if __name__ == "__main__":
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from des.adapters.driven.hooks.yaml_execution_log_reader import (
    YamlExecutionLogReader,
)
from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.driven.validation.git_scope_checker import GitScopeChecker
from des.application.pre_tool_use_service import PreToolUseService
from des.application.subagent_stop_service import SubagentStopService
from des.application.validator import TemplateValidator
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.max_turns_policy import MaxTurnsPolicy
from des.domain.step_completion_validator import StepCompletionValidator
from des.domain.tdd_schema import get_tdd_schema
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


def create_pre_tool_use_service() -> PreToolUseService:
    """Create PreToolUseService with production dependencies.

    Returns:
        PreToolUseService configured for production use
    """
    time_provider = SystemTimeProvider()
    audit_writer = JsonlAuditLogWriter()

    return PreToolUseService(
        max_turns_policy=MaxTurnsPolicy(),
        marker_parser=DesMarkerParser(),
        prompt_validator=TemplateValidator(),
        audit_writer=audit_writer,
        time_provider=time_provider,
    )


def create_subagent_stop_service() -> SubagentStopService:
    """Create SubagentStopService with production dependencies.

    Returns:
        SubagentStopService configured for production use
    """
    time_provider = SystemTimeProvider()
    audit_writer = JsonlAuditLogWriter()
    schema = get_tdd_schema()

    return SubagentStopService(
        log_reader=YamlExecutionLogReader(),
        completion_validator=StepCompletionValidator(schema=schema),
        scope_checker=GitScopeChecker(),
        audit_writer=audit_writer,
        time_provider=time_provider,
    )


def handle_pre_tool_use() -> int:
    """Handle PreToolUse command: validate Task tool invocation.

    Protocol translation only -- all decisions delegated to PreToolUseService.

    Returns:
        0 if validation passes (allow)
        1 if error occurs (fail-closed)
        2 if validation fails (block)
    """
    try:
        # Read JSON from stdin
        input_data = sys.stdin.read()

        if not input_data or not input_data.strip():
            response = {"status": "error", "reason": "Missing stdin input"}
            print(json.dumps(response))
            return 1

        # Parse JSON
        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError as e:
            response = {"status": "error", "reason": f"Invalid JSON: {e!s}"}
            print(json.dumps(response))
            return 1

        # Extract protocol fields
        # Claude Code sends: {"tool_name": "Task", "tool_input": {...}, ...}
        tool_input = hook_input.get("tool_input", {})
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
            from des.ports.driven_ports.audit_log_writer import (
                AuditEvent as PortAuditEvent,
            )

            audit_writer = JsonlAuditLogWriter()
            audit_writer.log_event(
                PortAuditEvent(
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

    except (OSError, PermissionError):
        return None

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

The step validation failed. You MUST fix these issues before proceeding."""

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
        input_data = sys.stdin.read()

        if not input_data or not input_data.strip():
            response = {"status": "error", "reason": "Missing stdin input"}
            print(json.dumps(response))
            return 1

        try:
            hook_input = json.loads(input_data)
        except json.JSONDecodeError as e:
            response = {"status": "error", "reason": f"Invalid JSON: {e!s}"}
            print(json.dumps(response))
            return 1

        # Resolve DES context from either protocol
        result = _resolve_des_context(hook_input)
        if result[0] is None:
            # Error or non-DES passthrough
            _, response, exit_code = result
            print(json.dumps(response))
            return exit_code
        execution_log_path, project_id, step_id = result

        # Delegate to application service
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        stop_hook_active = bool(hook_input.get("stop_hook_active", False))
        service = create_subagent_stop_service()
        decision = service.validate(
            SubagentStopContext(
                execution_log_path=execution_log_path,
                project_id=project_id,
                step_id=step_id,
                stop_hook_active=stop_hook_active,
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
            from des.ports.driven_ports.audit_log_writer import (
                AuditEvent as PortAuditEvent,
            )

            audit_writer = JsonlAuditLogWriter()
            audit_writer.log_event(
                PortAuditEvent(
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
        # Read JSON from stdin
        input_data = sys.stdin.read()

        if not input_data or not input_data.strip():
            # Non-DES or missing input: passthrough
            print(json.dumps({}))
            return 0

        # Parse JSON (ignore parse errors gracefully)
        try:
            json.loads(input_data)
        except json.JSONDecodeError:
            print(json.dumps({}))
            return 0

        # Delegate to PostToolUseService
        from des.adapters.driven.logging.jsonl_audit_log_reader import (
            JsonlAuditLogReader,
        )
        from des.application.post_tool_use_service import PostToolUseService

        reader = JsonlAuditLogReader()
        service = PostToolUseService(audit_reader=reader)
        additional_context = service.check_completion_status()

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
            from des.ports.driven_ports.audit_log_writer import (
                AuditEvent as PortAuditEvent,
            )

            audit_writer = JsonlAuditLogWriter()
            audit_writer.log_event(
                PortAuditEvent(
                    event_type="HOOK_ERROR",
                    timestamp=SystemTimeProvider().now_utc().isoformat(),
                    data={"error": str(e), "handler": "post_tool_use"},
                )
            )
        except Exception:
            pass  # Don't let audit logging failure mask the original error
        print(json.dumps({}))
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
    else:
        print(json.dumps({"status": "error", "reason": f"Unknown command: {command}"}))
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
