"""SubagentStop hook handler: terminal-by-construction subagent results.

Stable-design report 2026-08-19 §1.1. Drives the real handler end-to-end
(stdin -> stdout JSON / exit code / durable file), the same harness shape
as `test_subagent_start_handler.py`. Payload shape is the REAL one
recovered from the installed `claude` CLI binary's own hookInput-
construction code (SubagentStop branch, `strings` extraction) -- see
`subagent_stop_handler.py`'s own module docstring for the full citation:

    {..., hook_event_name: "SubagentStop", stop_hook_active: <bool>,
     agent_id: <str>, agent_transcript_path: <str>, agent_type: <str, ""
     if unknown>, last_assistant_message: <str>, background_tasks: [...],
     session_crons: [...]}

Notably: no `stop_reason` field anywhere in that real payload -- every
test below constructs payloads WITHOUT one, matching the verified real
shape (the exact class of vacuous-test risk `root_activation_context.py`'s
own Run 9/10 correction notes warn about: a synthetic payload proving the
wrong thing).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from des.adapters.drivers.hooks import subagent_stop_handler


def _real_shaped_payload(
    *,
    agent_type: str = "",
    agent_id: str = "agent123",
    agent_transcript_path: str | None = None,
    last_assistant_message: str = "",
) -> str:
    """The REAL SubagentStop envelope shape -- no `stop_reason` key, ever."""
    payload: dict[str, object] = {
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "last_assistant_message": last_assistant_message,
        "background_tasks": [],
        "session_crons": [],
    }
    if agent_transcript_path is not None:
        payload["agent_transcript_path"] = agent_transcript_path
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = subagent_stop_handler.handle_subagent_stop()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestNonNwaveAgentsAreNeverTouched:
    def test_missing_agent_type_is_a_noop(self, monkeypatch, capsys, tmp_path) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            json.dumps({"hook_event_name": "SubagentStop", "agent_id": "x"}),
        )
        assert exit_code == 0
        assert payload is None

    def test_empty_agent_type_is_a_noop(self, monkeypatch, capsys) -> None:
        """The REAL payload's own `agent_type: a ?? ""` fallback -- empty
        string, never absent -- must be treated the same as absent."""
        exit_code, payload = _run(
            monkeypatch, capsys, _real_shaped_payload(agent_type="")
        )
        assert exit_code == 0
        assert payload is None

    def test_non_nwave_agent_type_is_a_noop(self, monkeypatch, capsys) -> None:
        exit_code, payload = _run(
            monkeypatch, capsys, _real_shaped_payload(agent_type="Explore")
        )
        assert exit_code == 0
        assert payload is None


class TestTerminalResultAlreadyPresent:
    def test_marker_in_last_assistant_message_is_a_noop(
        self, monkeypatch, capsys
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-software-crafter",
                last_assistant_message=(
                    "Here is my summary.\n"
                    "NW-SOFTWARE-CRAFTER-RESULT: PASS verdict details..."
                ),
            ),
        )
        assert exit_code == 0
        assert payload is None

    def test_marker_found_via_transcript_scan_when_message_empty(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "agent-x.jsonl"
        transcript.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [{"type": "text", "text": "working..."}]
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "NW-USER-EXAMINER-RESULT: PASS",
                                    }
                                ]
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-user-examiner",
                agent_transcript_path=str(transcript),
                last_assistant_message="",
            ),
        )
        assert exit_code == 0
        assert payload is None


class TestSilentStopSynthesizesATerminalResult:
    def test_no_marker_anywhere_synthesizes_indeterminate(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "agent-y.jsonl"
        transcript.write_text(
            "\n".join(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [{"type": "tool_use", "name": "Bash", "id": "t"}]
                        },
                    }
                )
                for _ in range(5)
            )
            + "\n",
            encoding="utf-8",
        )
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-software-crafter",
                agent_id="crafter-42",
                agent_transcript_path=str(transcript),
                last_assistant_message="",
            ),
        )
        assert exit_code == 0
        assert payload is not None
        additional_context = payload["additionalContext"]
        assert "NW-SOFTWARE-CRAFTER-RESULT" in additional_context
        assert "INDETERMINATE" in additional_context
        # Honest per the module docstring: no platform stop-cause field
        # exists, so the synthesized text must never claim a specific
        # platform-sourced cause like "max_turns".
        assert "stop_reason" not in additional_context.lower()

        result_file = result_dir / "crafter-42.txt"
        assert result_file.is_file()
        written = result_file.read_text(encoding="utf-8")
        assert "NW-SOFTWARE-CRAFTER-RESULT" in written
        assert "INDETERMINATE" in written

    def test_no_marker_and_no_transcript_path_still_synthesizes(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-acceptance-designer",
                agent_id="atd-1",
                last_assistant_message="",
            ),
        )
        assert exit_code == 0
        assert payload is not None
        assert "NW-ACCEPTANCE-DESIGNER-RESULT" in payload["additionalContext"]
        assert "INDETERMINATE" in payload["additionalContext"]


class TestCleanupIsWiredButNeverBlocking:
    def test_remove_signal_and_skill_tracking_are_called_on_synthesis(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        calls: list[str] = []
        from des.adapters.drivers.hooks import des_task_signal

        monkeypatch.setattr(
            des_task_signal, "remove_signal", lambda: calls.append("remove_signal")
        )
        from des.adapters.drivers.hooks import skill_tracking_hooks

        monkeypatch.setattr(
            skill_tracking_hooks,
            "maybe_track_skill_loads",
            lambda path: calls.append(f"track:{path}"),
        )
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)
        transcript = tmp_path / "agent-z.jsonl"
        transcript.write_text("", encoding="utf-8")
        exit_code, _payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-software-crafter",
                agent_transcript_path=str(transcript),
                last_assistant_message="",
            ),
        )
        assert exit_code == 0
        assert "remove_signal" in calls
        assert any(c.startswith("track:") for c in calls)

    def test_cleanup_exception_never_breaks_fail_open_contract(
        self, monkeypatch, capsys
    ) -> None:
        from des.adapters.drivers.hooks import des_task_signal

        def _boom():
            raise RuntimeError("boom")

        monkeypatch.setattr(des_task_signal, "remove_signal", _boom)
        exit_code, _payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-software-crafter",
                last_assistant_message="NW-SOFTWARE-CRAFTER-RESULT: PASS",
            ),
        )
        assert exit_code == 0


class TestMalformedInputFailsOpen:
    def test_unparsable_stdin_exits_zero(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
        exit_code = subagent_stop_handler.handle_subagent_stop()
        assert exit_code == 0

    def test_empty_stdin_exits_zero(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        exit_code = subagent_stop_handler.handle_subagent_stop()
        assert exit_code == 0
