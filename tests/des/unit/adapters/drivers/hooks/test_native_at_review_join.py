"""Fable-5 foreground-Agent result reader falsifiers.

The fixture is sanitized from Claude Code 2.1.241's foreground ``Agent``
shape. It intentionally contains no task notification, sidecar, or child
transcript: those are not this boundary's carrier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.native_agent_result import completed_agent_results


_ROLE = "nw-acceptance-designer-reviewer"
_PROMPT = "THIN-DELIVERY-CONTRACT: c.json\nreview this closure"
_TERMINAL = "AT-REVIEW\nverdict: APPROVE\ncontract: c.json@sha256:digest"


def _records(*, mutate: str | None = None) -> list[dict[str, object]]:
    call: dict[str, object] = {
        "type": "assistant",
        "uuid": "assistant-source-uuid",
        "sessionId": "session-1",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_foreground",
                    "name": "Agent",
                    "input": {
                        "subagent_type": _ROLE,
                        "run_in_background": False,
                        "prompt": _PROMPT,
                    },
                }
            ]
        },
    }
    result: dict[str, object] = {
        "type": "user",
        "sessionId": "session-1",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_foreground",
                    "content": "Agent completed; display and usage are non-authoritative.",
                }
            ]
        },
        "toolUseResult": {
            "status": "completed",
            "prompt": _PROMPT,
            "agentId": "agent-17",
            "agentType": _ROLE,
            "content": [{"type": "text", "text": _TERMINAL}],
        },
        "sourceToolAssistantUUID": "assistant-source-uuid",
    }
    if mutate == "wrong-prompt":
        result["toolUseResult"]["prompt"] = "stale prompt"  # type: ignore[index]
    elif mutate == "wrong-role":
        result["toolUseResult"]["agentType"] = "nw-software-crafter"  # type: ignore[index]
    elif mutate == "wrong-uuid":
        result["sourceToolAssistantUUID"] = "other-assistant"
    elif mutate == "wrong-session":
        result["sessionId"] = "other-session"
    elif mutate == "async":
        result["toolUseResult"]["status"] = "async_launched"  # type: ignore[index]
    elif mutate == "background":
        call["message"]["content"][0]["input"]["run_in_background"] = True  # type: ignore[index]
    elif mutate == "non-text":
        result["toolUseResult"]["content"] = [{"type": "tool_use", "name": "Bash"}]  # type: ignore[index]
    elif mutate == "multiple-content":
        result["toolUseResult"]["content"] = [  # type: ignore[index]
            {"type": "text", "text": _TERMINAL},
            {"type": "text", "text": "other terminal"},
        ]
    elif mutate == "duplicate-result":
        return [call, result, result]
    elif mutate == "duplicate-call":
        return [call, call, result]
    elif mutate == "notification-only":
        return [
            call,
            {
                "type": "queue-operation",
                "operation": "enqueue",
                "content": "<task-notification><status>completed</status></task-notification>",
            },
        ]
    return [call, result]


def _transcript(tmp_path: Path, *, mutate: str | None = None) -> Path:
    path = tmp_path / "parent.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in _records(mutate=mutate)) + "\n"
    )
    return path


def test_reads_one_completed_foreground_agent_result_from_the_parent_record(
    tmp_path: Path,
) -> None:
    result = completed_agent_results(
        _transcript(tmp_path), role=_ROLE, prompt_prefix="THIN-DELIVERY-CONTRACT:"
    )

    assert result is not None
    assert result.tool_use_id == "toolu_foreground"
    assert result.agent_id == "agent-17"
    assert result.agent_type == _ROLE
    assert result.applied_prompt == _PROMPT
    assert result.terminal_text == _TERMINAL
    assert result.source_tool_assistant_uuid == "assistant-source-uuid"
    assert result.session_id == "session-1"


@pytest.mark.parametrize(
    "mutate",
    [
        "wrong-prompt",
        "wrong-role",
        "wrong-uuid",
        "wrong-session",
        "async",
        "background",
        "non-text",
        "multiple-content",
        "duplicate-result",
        "duplicate-call",
        "notification-only",
    ],
)
def test_refuses_non_unique_or_non_foreground_or_non_authoritative_results(
    tmp_path: Path, mutate: str
) -> None:
    assert (
        completed_agent_results(
            _transcript(tmp_path, mutate=mutate),
            role=_ROLE,
            prompt_prefix="THIN-DELIVERY-CONTRACT:",
        )
        is None
    )


def test_refuses_a_completed_result_for_another_prompt_prefix(tmp_path: Path) -> None:
    assert (
        completed_agent_results(
            _transcript(tmp_path), role=_ROLE, prompt_prefix="candidate: git-sha1:"
        )
        is None
    )
