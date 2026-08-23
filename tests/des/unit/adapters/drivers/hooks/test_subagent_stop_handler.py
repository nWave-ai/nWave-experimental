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


class TestNamedInProcessTeammatesAreResolvedToTheirRealRole:
    """A NAMED in-process teammate's `agent_type` is its LANE NAME, not its role.

    Verified on two independent axes against Claude Code 2.1.239:

    1. The installed CLI's own in-process-teammate agent definition sets
       ``agentType: t.agentName`` and stashes the real role separately as
       ``customAgentType`` in the teammate metadata; the SubagentStop
       hookInput then carries ``agent_type: a ?? ""`` sourced from that same
       ``agentType`` -- i.e. the lane name.
    2. Empirically, in session
       ``e203e35d-491c-430b-94cc-2cc7748446f4`` every named lane's sidecar
       ``agent-<id>.meta.json`` reads ``{"agentType": "<lane-name>",
       "customAgentType": "nw-troubleshooter", "taskKind":
       "in_process_teammate"}``, while every UNNAMED Agent-tool dispatch
       reads ``{"agentType": "nw-troubleshooter-reviewer"}``. Only the
       unnamed ones ever produced a durable receipt.

    Consequence before this fix: a bare ``agent_type.startswith("nw-")``
    gate silently no-ops for EVERY named nWave lane -- exactly the silence
    this handler exists to make unrepresentable.

    The role is recovered from the sidecar metadata file that sits next to
    the transcript the platform itself hands us in
    ``agent_transcript_path`` (``<transcript-stem>.meta.json``). Fail-open:
    an absent/unreadable/roleless sidecar degrades to today's behaviour.
    """

    @staticmethod
    def _teammate_transcript(tmp_path: Path, agent_id: str, custom_type: str) -> Path:
        transcript = tmp_path / f"agent-{agent_id}.jsonl"
        transcript.write_text("", encoding="utf-8")
        (tmp_path / f"agent-{agent_id}.meta.json").write_text(
            json.dumps(
                {
                    "agentType": agent_id.lstrip("a").rsplit("-", 1)[0],
                    "taskKind": "in_process_teammate",
                    "customAgentType": custom_type,
                }
            ),
            encoding="utf-8",
        )
        return transcript

    def test_named_lane_gets_a_receipt_under_its_real_role_marker(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        agent_id = "aspeedfix-6c5c7f8505b9e7dd"
        transcript = self._teammate_transcript(tmp_path, agent_id, "nw-troubleshooter")
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="speedfix",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="ho finito il lavoro",
            ),
        )

        assert exit_code == 0
        assert payload is not None
        assert "NW-TROUBLESHOOTER-RESULT" in payload["additionalContext"]
        assert "INDETERMINATE" in payload["additionalContext"]
        written = (result_dir / f"{agent_id}.txt").read_text(encoding="utf-8")
        assert "NW-TROUBLESHOOTER-RESULT" in written

    def test_receipt_is_also_addressable_by_the_lane_name_the_root_knows(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        """The root dispatches by NAME and never learns the opaque hex suffix.

        `nWave/skills/nw-auto/SKILL.md` tells the root to read
        ``.nwave/des/subagent-results/<the dispatched agent-id>.txt`` when a
        role returns no terminal line -- but for a named lane the id is
        ``a<name>-<16 hex>``, a value the root never sees. A receipt only
        the writer can address is not a receipt.
        """
        agent_id = "arca-trailer-bad32bb962c324bc"
        transcript = self._teammate_transcript(tmp_path, agent_id, "nw-troubleshooter")
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="rca-trailer",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="report inviato",
            ),
        )

        by_name = result_dir / "rca-trailer.txt"
        assert by_name.is_file(), "lane-name-keyed receipt missing"
        assert by_name.read_text(encoding="utf-8") == (
            result_dir / f"{agent_id}.txt"
        ).read_text(encoding="utf-8")

    def test_unnamed_agent_id_never_produces_a_name_keyed_alias(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        """An UNNAMED dispatch's id is ``a`` + 16 hex with no dash -- there is
        no lane name to alias, and inventing one would collide."""
        agent_id = "a09b7cdf582976f8d"
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="nw-troubleshooter-reviewer",
                agent_id=agent_id,
                last_assistant_message="",
            ),
        )

        assert (result_dir / f"{agent_id}.txt").is_file()
        assert sorted(p.name for p in result_dir.iterdir()) == [f"{agent_id}.txt"]

    def test_non_nwave_teammate_stays_untouched(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        """Resolution widens WHICH nWave roles are seen, never the population.

        A named lane whose real role is not an ``nw-*`` agent must still be a
        no-op: this hook is installed globally, so a widened gate would start
        writing files under every unrelated project."""
        agent_id = "aworker-1111222233334444"
        transcript = self._teammate_transcript(tmp_path, agent_id, "general-purpose")
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="worker",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="done",
            ),
        )

        assert exit_code == 0
        assert payload is None
        assert not result_dir.exists()

    def test_missing_sidecar_degrades_to_no_op_without_raising(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="speedfix",
                agent_id="aspeedfix-6c5c7f8505b9e7dd",
                agent_transcript_path=str(tmp_path / "agent-absent.jsonl"),
                last_assistant_message="x",
            ),
        )

        assert exit_code == 0
        assert payload is None
        assert not result_dir.exists()

    def test_named_lane_that_did_emit_its_terminal_line_writes_nothing(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        agent_id = "aspeedfix-6c5c7f8505b9e7dd"
        transcript = self._teammate_transcript(tmp_path, agent_id, "nw-troubleshooter")
        result_dir = tmp_path / ".nwave" / "des" / "subagent-results"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(subagent_stop_handler, "_SUBAGENT_RESULT_DIR", result_dir)

        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _real_shaped_payload(
                agent_type="speedfix",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="NW-TROUBLESHOOTER-RESULT: verdict PASS",
            ),
        )

        assert exit_code == 0
        assert payload is None
        assert not result_dir.exists()
