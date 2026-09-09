"""Read one real foreground Claude Agent result from its parent transcript.

This boundary deliberately consumes only the platform's correlated parent
``tool_use``/``tool_result`` records. Child transcripts, task notifications,
queue operations and sidecars are neither inputs nor fallback carriers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentResult:
    """One uniquely correlated completed foreground Agent invocation."""

    tool_use_id: str
    agent_id: str
    agent_type: str
    applied_prompt: str
    terminal_text: str
    source_tool_assistant_uuid: str
    session_id: str


@dataclass(frozen=True, slots=True)
class _Invocation:
    tool_use_id: str
    role: str
    prompt: str
    source_uuid: str
    session_id: str


@dataclass(frozen=True, slots=True)
class _Completion:
    tool_use_id: str
    status: str
    prompt: str
    agent_id: str
    agent_type: str
    terminal_text: str
    source_uuid: str
    session_id: str


def _records(path: Path) -> list[dict[str, object]] | None:
    try:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return records if all(isinstance(record, dict) for record in records) else None


def _session(record: dict[str, object]) -> str | object:
    value = record.get("sessionId")
    return value if isinstance(value, str) and value else _INVALID


_INVALID = object()


def _content(record: dict[str, object]) -> list[dict[str, object]] | None:
    message = record.get("message")
    blocks = message.get("content") if isinstance(message, dict) else None
    if not isinstance(blocks, list) or not all(
        isinstance(block, dict) for block in blocks
    ):
        return None
    return blocks


def _foreground_invocations(
    records: list[dict[str, object]],
) -> dict[str, list[_Invocation]]:
    invocations: dict[str, list[_Invocation]] = {}
    for record in records:
        if record.get("type") != "assistant":
            continue
        uuid = record.get("uuid")
        session = _session(record)
        blocks = _content(record)
        if (
            not isinstance(uuid, str)
            or not uuid
            or session is _INVALID
            or blocks is None
        ):
            continue
        for block in blocks:
            if block.get("type") != "tool_use" or block.get("name") != "Agent":
                continue
            tool_use_id = block.get("id")
            input_value = block.get("input")
            role = (
                input_value.get("subagent_type")
                if isinstance(input_value, dict)
                else None
            )
            prompt = (
                input_value.get("prompt") if isinstance(input_value, dict) else None
            )
            foreground = (
                input_value.get("run_in_background")
                if isinstance(input_value, dict)
                else None
            )
            if (
                not isinstance(tool_use_id, str)
                or not tool_use_id
                or not isinstance(role, str)
                or not isinstance(prompt, str)
                or foreground is not False
            ):
                continue
            invocations.setdefault(tool_use_id, []).append(
                _Invocation(tool_use_id, role, prompt, uuid, session)
            )
    return invocations


def _terminal_text(content: object) -> str | None:
    """Accept exactly one platform-authoritative terminal text block."""
    if not isinstance(content, list) or len(content) != 1:
        return None
    block = content[0]
    if not isinstance(block, dict) or block.get("type") != "text":
        return None
    text = block.get("text")
    return text if isinstance(text, str) and text else None


def _completions(records: list[dict[str, object]]) -> dict[str, list[_Completion]]:
    completions: dict[str, list[_Completion]] = {}
    for record in records:
        if record.get("type") != "user":
            continue
        session = _session(record)
        blocks = _content(record)
        result = record.get("toolUseResult")
        if session is _INVALID or blocks is None or not isinstance(result, dict):
            continue
        status = result.get("status")
        prompt = result.get("prompt")
        agent_id = result.get("agentId")
        agent_type = result.get("agentType")
        terminal = _terminal_text(result.get("content"))
        source_uuid = record.get("sourceToolAssistantUUID")
        if (
            not isinstance(status, str)
            or not isinstance(prompt, str)
            or not isinstance(agent_id, str)
            or not agent_id
            or not isinstance(agent_type, str)
            or not isinstance(source_uuid, str)
            or not source_uuid
            or terminal is None
        ):
            continue
        for block in blocks:
            if block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id")
            if not isinstance(tool_use_id, str) or not tool_use_id:
                continue
            completions.setdefault(tool_use_id, []).append(
                _Completion(
                    tool_use_id,
                    status,
                    prompt,
                    agent_id,
                    agent_type,
                    terminal,
                    source_uuid,
                    session,
                )
            )
    return completions


def completed_agent_results(
    parent_transcript: Path | str, *, role: str, prompt_prefix: str
) -> AgentResult | None:
    """Return one completed foreground result, or ``None`` on any ambiguity.

    The caller supplies the role and a hook-owned prompt prefix. A result is
    usable only if exactly one foreground Agent invocation and exactly one
    parent ``tool_result`` share the same ``tool_use_id``, source assistant,
    applied prompt, role and (when both records carry it) session.
    """
    if not role:
        return None
    records = _records(Path(parent_transcript))
    if records is None:
        return None
    invocations = _foreground_invocations(records)
    completions = _completions(records)
    matched: list[AgentResult] = []
    for tool_use_id, calls in invocations.items():
        results = completions.get(tool_use_id, [])
        if len(calls) != 1 or len(results) != 1:
            continue
        call, completion = calls[0], results[0]
        if (
            call.role != role
            or not call.prompt.startswith(prompt_prefix)
            or completion.status != "completed"
            or completion.agent_type != role
            or completion.prompt != call.prompt
            or completion.source_uuid != call.source_uuid
            or call.session_id != completion.session_id
        ):
            continue
        matched.append(
            AgentResult(
                tool_use_id=tool_use_id,
                agent_id=completion.agent_id,
                agent_type=completion.agent_type,
                applied_prompt=completion.prompt,
                terminal_text=completion.terminal_text,
                source_tool_assistant_uuid=completion.source_uuid,
                session_id=call.session_id,
            )
        )
    return matched[0] if len(matched) == 1 else None
