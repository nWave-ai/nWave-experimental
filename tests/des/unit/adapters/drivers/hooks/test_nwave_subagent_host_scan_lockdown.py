"""K4 architecture gap: nWave subagent host-scan lockdown.

A running nWave subagent (`agent_type` starting with `nw-`) must not spend
its critical path scanning the whole host: a Bash `find`/`bfs` call whose
actual traversal root is the filesystem root itself (`/`, or an
option-prefixed equivalent like `find -H /`) is blocked. Root/user Bash (no
`agent_id`/`agent_type`) and non-nWave agents are untouched, and any
project-scoped traversal (repo path, `.`, an absolute AUTO-ARCHITECTURE-ROOT,
or a quoted mention inside an unrelated command) is untouched.

Drives the real handler end-to-end (stdin -> stdout JSON / exit code), the
same harness shape as `test_auto_root_bash_lockdown.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


def _stdin(*, tool_name: str, tool_input: dict, **identity: str) -> str:
    payload: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestNwaveSubagentHostScanBlocked:
    @pytest.mark.parametrize(
        "command",
        [
            "find / -iname '*.py'",
            "find / -path '*/src/*'",
            "bfs /",
            "find -H / -iname foo",
            "find -L / -iname foo",
            "find / /home -name x",
            "cd /tmp && find / -name x",
            'python3 -c "import sys; print(1)" 2>/dev/null; '
            "find / -iname cronsim-star -path '*/site-packages/*' 2>/dev/null | head",
        ],
    )
    def test_host_wide_find_or_bfs_is_blocked(
        self, monkeypatch, capsys, audit_events, command
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                agent_type="nw-solution-architect",
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "WHAT" in payload["reason"]
        assert "WHY" in payload["reason"]
        assert "HOW" in payload["reason"]


class TestNwaveSubagentHostScanAllowed:
    @pytest.mark.parametrize(
        "command",
        [
            "find /repo -iname '*.py'",
            "find /tmp/project -name x",
            "find . -name x",
            "find /tmp/nwave-k4-architect-search -maxdepth 2 -name x",
            'echo "please don\'t find / for files"',
            'git commit -m "find / stuff"',
            'python -c "import inspect,os; print(inspect.getsourcefile(os))"',
            'echo "safe; find /"',
        ],
    )
    def test_project_scoped_or_non_traversal_command_is_not_blocked(
        self, monkeypatch, capsys, audit_events, command
    ) -> None:
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                agent_type="nw-solution-architect",
            ),
        )
        assert (
            payload is None
            or payload.get("decision") != "block"
            or "traverses the filesystem root" not in payload.get("reason", "")
        )


class TestNwaveSubagentHostScanIdentityBoundary:
    def test_root_user_bash_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        """No `agent_id`/`agent_type` (root/user) issuing `find /` is
        untouched by this gate -- only a running nWave subagent is scoped."""
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(tool_name="Bash", tool_input={"command": "find / -name x"}),
        )
        assert (
            payload is None
            or payload.get("decision") != "block"
            or "traverses the filesystem root" not in payload.get("reason", "")
        )

    def test_non_nwave_agent_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "find / -name x"},
                agent_type="some-other-agent",
            ),
        )
        assert (
            payload is None
            or payload.get("decision") != "block"
            or "traverses the filesystem root" not in payload.get("reason", "")
        )

    def test_non_bash_tool_is_never_evaluated(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        def _boom(*args, **kwargs):
            raise AssertionError("host-scan classifier must not run for non-Bash tools")

        monkeypatch.setattr(
            pre_tool_use_handler, "_evaluate_nwave_subagent_host_scan", _boom
        )
        _exit_code, _payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/etc/passwd"},
                agent_type="nw-solution-architect",
            ),
        )
        assert pre_tool_use_handler._evaluate_nwave_subagent_host_scan is _boom


class TestNwaveSubagentHostScanWithoutALiveAgentTypeField:
    """Run 9/10 correction: every test above sets `agent_type` DIRECTLY in
    the payload -- a shape Claude Code's own hooks reference never
    documents for an ordinary PreToolUse envelope (only for
    SubagentStart/SubagentStop), and empirically absent from every one of
    run 9's real nw-user-examiner PreToolUse calls. Under the old
    `_is_nwave_subagent` (bare `hook_input.get("agent_type")` read), a real
    subagent's OWN `find /` call -- carrying only `transcript_path`, never
    `agent_type` -- would have sailed through this lockdown entirely. This
    class drives the same real shape: only `transcript_path`, pointing into
    a real `subagents/agent-<id>.jsonl` layout with its co-located
    `.meta.json` sidecar for identity."""

    @staticmethod
    def _subagent_transcript(tmp_path):
        subagents_dir = tmp_path / "subagents"
        subagents_dir.mkdir()
        transcript = subagents_dir / "agent-host-scan-probe.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": "find / -iname x"},
                            }
                        ]
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (subagents_dir / "agent-host-scan-probe.meta.json").write_text(
            json.dumps({"agentType": "nw-solution-architect", "spawnDepth": 1}),
            encoding="utf-8",
        )
        return str(transcript)

    def test_host_wide_find_is_blocked_with_no_agent_type_in_envelope(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = self._subagent_transcript(tmp_path)
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "find / -iname '*.py'"},
                "transcript_path": transcript_path,
                # No "agent_type" key at all -- the real PreToolUse shape.
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        exit_code = pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        assert exit_code == 2
        assert payload_out["decision"] == "block"
        assert "traverses the filesystem root" in payload_out["reason"]

    def test_repo_scoped_find_stays_allowed_with_no_agent_type_in_envelope(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = self._subagent_transcript(tmp_path)
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "find . -iname '*.py'"},
                "transcript_path": transcript_path,
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        assert (
            payload_out is None
            or payload_out.get("decision") != "block"
            or "traverses the filesystem root" not in payload_out.get("reason", "")
        )
