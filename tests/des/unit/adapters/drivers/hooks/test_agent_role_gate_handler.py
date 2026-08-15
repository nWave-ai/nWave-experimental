"""Handler-boundary tests for Auto's nWave-role ownership gate.

Role identity is deliberately not run identity: a prior successful dispatch
of the same canonical role must not prevent a later delivery unit from using
that role again. Auto still refuses non-nWave role escape.
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


def _bare_agent_call(role: str, tool_use_id: str = "T1") -> dict:
    content = [
        {
            "type": "tool_use",
            "id": tool_use_id,
            "name": "Agent",
            "input": {"subagent_type": role},
        }
    ]
    return {"type": "assistant", "message": {"content": content}}


def _dispatched_agent(role: str, tool_use_id: str = "T1") -> list[dict]:
    return [
        _bare_agent_call(role, tool_use_id),
        {
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
            "toolUseResult": {"status": "async_launched", "agentId": "agent-xyz"},
        },
    ]


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


def test_same_nwave_role_can_serve_a_later_delivery_unit(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = [_skill("nw-auto"), *_dispatched_agent("nw-crafter")]
    transcript_path = _transcript(tmp_path, prior)

    exit_code, output = _run(monkeypatch, transcript_path, "nw-crafter")

    assert exit_code == 0
    assert all(json.loads(item).get("decision") != "block" for item in output)


@pytest.mark.parametrize(
    ("prior", "role", "expected_exit", "case"),
    [
        ([_skill("nw-auto")], "general-purpose", 2, "non-nw role blocked"),
        ([_skill("nw-auto")], "Explore", 2, "non-nw role blocked (other name)"),
        ([_skill("nw-auto")], "nw-crafter", 0, "nw-* role first dispatch allowed"),
        ([], "general-purpose", 0, "no authentic nw-auto: ungated"),
    ],
)
def test_agent_non_nwave_role_gate_handler_boundary(
    tmp_path, monkeypatch: pytest.MonkeyPatch, prior, role, expected_exit, case
) -> None:
    """K4 ownership-escape gate: nw-auto restricts Agent dispatch to nw-* roles."""
    transcript_path = _transcript(tmp_path, prior)
    exit_code, output = _run(monkeypatch, transcript_path, role)

    assert exit_code == expected_exit, case
    if expected_exit == 2:
        payload = json.loads(output[0])
        assert payload["decision"] == "block"
        reason = payload["reason"]
        for token in ("Auto-root", role, "WHY", "HOW", "nw-"):
            assert token in reason, case
