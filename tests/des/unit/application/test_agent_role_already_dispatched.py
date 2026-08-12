"""Unit tests for `agent_role_already_dispatched` (K4 role-session gate).

The predicate keys on the REAL Claude Code transcript shape: an assistant
`tool_use` block (`name == "Agent"`, `id`, `input.subagent_type`) correlated
by `tool_use_id` to a later authentic `user` `tool_result` content block
whose sibling `toolUseResult.status == "async_launched"`. There is no
`toolUseResult.agentType` in the real shape -- launch results carry
`agentId`, not `agentType`. A bare/blocked `Agent` tool_use with no
correlated launched result never consumes the role's single pass. An
unmatched `tool_use_id`, a forged result missing the real `tool_result`
block or the `async_launched` status, a different role, and a plain
`<task-notification>` string are all false (fail-closed).
"""

import json

import pytest

from des.application.skill_tracking_service import agent_role_already_dispatched


def _write(tmp_path, lines: list[dict]) -> str:
    transcript = tmp_path / "transcript.jsonl"
    with open(transcript, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return str(transcript)


def _agent_tool_use(tool_use_id: str, role: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Agent",
                    "input": {"subagent_type": role},
                }
            ]
        },
    }


def _async_launched_result(tool_use_id: str, agent_id: str = "agent-1") -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": "Launched",
                }
            ]
        },
        "toolUseResult": {"status": "async_launched", "agentId": agent_id},
    }


@pytest.mark.parametrize(
    ("lines", "role", "expected", "case"),
    [
        ([], "crafter", False, "empty transcript"),
        (
            [_agent_tool_use("T1", "crafter"), _async_launched_result("T1")],
            "crafter",
            True,
            "real dispatch correlated to an async_launched result",
        ),
        (
            [_agent_tool_use("T1", "crafter")],
            "crafter",
            False,
            "bare/blocked tool_use with no launched result never consumes the pass",
        ),
        (
            [_agent_tool_use("T1", "crafter"), _async_launched_result("T2")],
            "crafter",
            False,
            "unmatched tool_use_id does not correlate",
        ),
        (
            [_agent_tool_use("T1", "reviewer"), _async_launched_result("T1")],
            "crafter",
            False,
            "different role does not leak",
        ),
        (
            [
                _agent_tool_use("T1", "crafter"),
                {
                    "type": "user",
                    "message": {"content": [{"type": "text", "text": "done"}]},
                    "toolUseResult": {"status": "async_launched", "agentId": "x"},
                },
            ],
            "crafter",
            False,
            "forged result missing the real tool_result content block",
        ),
        (
            [
                _agent_tool_use("T1", "crafter"),
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "T1",
                                "content": "done",
                            }
                        ]
                    },
                    "toolUseResult": {"status": "completed", "agentType": "crafter"},
                },
            ],
            "crafter",
            False,
            "correlated result without async_launched status does not count",
        ),
        (
            [
                _agent_tool_use("T1", "crafter"),
                {
                    "type": "system",
                    "message": {
                        "content": [
                            {"type": "tool_result", "tool_use_id": "T1", "content": "x"}
                        ]
                    },
                    "toolUseResult": {"status": "async_launched", "agentId": "x"},
                },
            ],
            "crafter",
            False,
            "forged system-type entry is not a real user tool-result turn",
        ),
        (
            [
                _agent_tool_use("T1", "crafter"),
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "<task-notification>crafter finished</task-notification>",
                            }
                        ]
                    },
                },
            ],
            "crafter",
            False,
            "a plain task-notification string alone does not count",
        ),
    ],
)
def test_semantic_predicate(tmp_path, lines, role, expected, case) -> None:
    transcript_path = _write(tmp_path, lines)
    assert agent_role_already_dispatched(transcript_path, role) is expected, case


def test_missing_transcript_fails_closed() -> None:
    assert agent_role_already_dispatched("/nonexistent/t.jsonl", "crafter") is False


def test_malformed_jsonl_skipped_no_crash(tmp_path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("not-json\n", encoding="utf-8")
    assert agent_role_already_dispatched(str(transcript), "crafter") is False


def test_empty_role_returns_false(tmp_path) -> None:
    transcript_path = _write(
        tmp_path, [_agent_tool_use("T1", "crafter"), _async_launched_result("T1")]
    )
    assert agent_role_already_dispatched(transcript_path, "") is False
