"""Unit tests for `agent_role_already_dispatched` (K4 role-session gate).

The predicate keys on a COMPLETED dispatch result (a real `tool_result`
entry whose `toolUseResult.agentType` matches the role), never on a bare
`Agent` tool_use -- a PreToolUse-blocked call must not consume the role's
single pass. A completed result counts even when its outcome is a refusal.
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


def _completed_result(role: str, outcome: str = "SUCCESS") -> dict:
    return {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": outcome}]},
        "toolUseResult": {"agentType": role, "outcome": outcome},
    }


def _bare_tool_use(role: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Agent", "input": {"subagent_type": role}}
            ]
        },
    }


@pytest.mark.parametrize(
    ("lines", "role", "expected", "case"),
    [
        ([], "crafter", False, "empty transcript"),
        ([_completed_result("crafter")], "crafter", True, "completed same role"),
        (
            [_completed_result("crafter", outcome="AUTHORITY_REFUSED")],
            "crafter",
            True,
            "completed refused result still consumes the pass",
        ),
        (
            [_bare_tool_use("crafter")],
            "crafter",
            False,
            "blocked/never-ran tool_use alone never consumes the pass",
        ),
        ([_completed_result("reviewer")], "crafter", False, "different role"),
        (
            [
                {
                    "type": "user",
                    "message": {"content": [{"type": "text", "text": "done"}]},
                    "toolUseResult": {"agentType": "crafter"},
                }
            ],
            "crafter",
            False,
            "forged toolUseResult without a real tool_result content block",
        ),
        (
            [
                {
                    "type": "system",
                    "message": {"content": [{"type": "tool_result", "content": "x"}]},
                    "toolUseResult": {"agentType": "crafter"},
                }
            ],
            "crafter",
            False,
            "forged system-type entry is not a real user tool-result turn",
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
    transcript_path = _write(tmp_path, [_completed_result("crafter")])
    assert agent_role_already_dispatched(transcript_path, "") is False
