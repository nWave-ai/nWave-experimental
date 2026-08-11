"""Handler-boundary tests for the K4 same-role Agent gate (PreToolUse/Agent).

Falsifies the wiring in `pre_tool_use_handler.handle_pre_tool_use`: without
these, `agent_role_already_dispatched` could be reverted from the Agent path
and the pure-helper unit tests would stay green.
"""

import io
import json

import pytest


def _transcript(tmp_path, lines: list[dict]) -> str:
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return str(path)


def _skill(name: str) -> dict:
    content = [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}]
    return {"type": "assistant", "message": {"content": content}}


def _completed_agent(role: str) -> dict:
    content = [{"type": "tool_result", "content": "done"}]
    return {
        "type": "user",
        "message": {"content": content},
        "toolUseResult": {"agentType": role},
    }


def _bare_agent_call(role: str) -> dict:
    content = [{"type": "tool_use", "name": "Agent", "input": {"subagent_type": role}}]
    return {"type": "assistant", "message": {"content": content}}


def _run(monkeypatch, transcript_path: str, role: str):
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    stdin = json.dumps(
        {
            "tool_name": "Agent",
            "transcript_path": transcript_path,
            "tool_input": {"prompt": "Do the work", "subagent_type": role},
        }
    )
    captured: list[str] = []
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    monkeypatch.setattr(
        "builtins.print", lambda *a, **kw: captured.append(" ".join(map(str, a)))
    )
    return adapter.handle_pre_tool_use(), captured


@pytest.mark.parametrize(
    ("prior", "role", "expected_exit", "case"),
    [
        (
            [_skill("nw-auto"), _completed_agent("crafter")],
            "crafter",
            2,
            "completed same-role result blocks the repeat",
        ),
        (
            [_skill("nw-auto"), _bare_agent_call("crafter")],
            "crafter",
            0,
            "a blocked/never-ran tool_use alone must not consume the pass",
        ),
        (
            [_skill("nw-auto"), _completed_agent("reviewer")],
            "crafter",
            0,
            "a different role's completed result does not block this role",
        ),
        (
            [_completed_agent("crafter")],
            "crafter",
            0,
            "no authentic nw-auto: gate never fires (pre-K4 behavior)",
        ),
    ],
)
def test_agent_role_gate_handler_boundary(
    tmp_path, monkeypatch: pytest.MonkeyPatch, prior, role, expected_exit, case
) -> None:
    transcript_path = _transcript(tmp_path, prior)
    exit_code, output = _run(monkeypatch, transcript_path, role)

    assert exit_code == expected_exit, case
    if expected_exit == 2:
        payload = json.loads(output[0])
        assert payload["decision"] == "block"
        assert role in payload["reason"]
