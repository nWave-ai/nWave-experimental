"""Codex exec_command envelopes reach the shared Bash safety authority."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import hook_router


def test_claude_bash_envelope_remains_byte_identical() -> None:
    payload = '{ "tool_name": "Bash", "tool_input": {"command": "echo ok"} }\n'

    assert (
        hook_router.normalize_exec_command_envelope("pre-tool-use", payload) == payload
    )


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}),
        json.dumps({"tool_name": "exec_command"}),
        json.dumps({"tool_name": "exec_command", "tool_input": []}),
        json.dumps({"tool_name": "exec_command", "tool_input": {"cmd": 42}}),
    ],
)
def test_malformed_or_unrelated_envelope_is_left_unchanged(payload: str) -> None:
    assert (
        hook_router.normalize_exec_command_envelope("pre-tool-use", payload) == payload
    )


def test_exec_command_cmd_is_normalized_before_worktree_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    destination = tmp_path / "ephemeral-lane"
    payload = {
        "tool_name": "exec_command",
        "tool_input": {"cmd": f"git worktree add {destination}"},
        "cwd": str(repo),
        "session_id": "codex-installed-proof",
    }
    monkeypatch.setattr(sys, "argv", ["hook-adapter", "pre-tool-use"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as stopped:
        hook_router.main()

    assert stopped.value.code == 2
    decision = json.loads(capsys.readouterr().out)
    assert decision["decision"] == "block"
    assert "worktree-admit" in decision["reason"]
