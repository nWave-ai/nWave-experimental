"""SubagentStop hook handler: cleanup wiring, receipt synthesis retired.

Drives the real handler end-to-end (stdin -> exit code / cleanup calls),
the same harness shape as the other hook handler suites. Payload shape
is the REAL one recovered from the installed `claude` CLI binary's own
hookInput-construction code (SubagentStop branch, `strings` extraction) --
see `subagent_stop_handler.py`'s own module docstring for the full
citation:

    {..., hook_event_name: "SubagentStop", stop_hook_active: <bool>,
     agent_id: <str>, agent_transcript_path: <str>, agent_type: <str, ""
     if unknown>, last_assistant_message: <str>, background_tasks: [...],
     session_crons: [...]}

Notably: no `stop_reason` field anywhere in that real payload -- every
test below constructs payloads WITHOUT one, matching the verified real
shape.

The receipt-synthesis test classes this file used to carry (terminal-
result grammar, synthesized-INDETERMINATE content, per-agent durable
files) are removed WITH the code they protected -- see git history for
the removal commit. What remains observable from this handler is:
non-nWave agents are never touched, and cleanup (`des_task_signal.
remove_signal`, `skill_tracking_hooks.maybe_track_skill_loads`) fires for
a resolved nWave agent, including a NAMED in-process teammate whose real
role is recovered from its sidecar -- never for one that isn't.
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


def _run(monkeypatch, stdin: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return subagent_stop_handler.handle_subagent_stop()


class TestNonNwaveAgentsAreNeverTouched:
    def test_missing_agent_type_is_a_noop(self, monkeypatch) -> None:
        exit_code = _run(
            monkeypatch,
            json.dumps({"hook_event_name": "SubagentStop", "agent_id": "x"}),
        )
        assert exit_code == 0

    def test_empty_agent_type_is_a_noop(self, monkeypatch) -> None:
        """The REAL payload's own `agent_type: a ?? ""` fallback -- empty
        string, never absent -- must be treated the same as absent."""
        exit_code = _run(monkeypatch, _real_shaped_payload(agent_type=""))
        assert exit_code == 0

    def test_non_nwave_agent_type_is_a_noop(self, monkeypatch) -> None:
        exit_code = _run(monkeypatch, _real_shaped_payload(agent_type="Explore"))
        assert exit_code == 0


class TestMalformedInputFailsOpen:
    def test_unparsable_stdin_exits_zero(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
        exit_code = subagent_stop_handler.handle_subagent_stop()
        assert exit_code == 0

    def test_empty_stdin_exits_zero(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        exit_code = subagent_stop_handler.handle_subagent_stop()
        assert exit_code == 0


class TestCleanupIsWiredButNeverBlocking:
    def test_remove_signal_and_skill_tracking_are_called_for_an_nwave_agent(
        self, monkeypatch, tmp_path: Path
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
        transcript = tmp_path / "agent-z.jsonl"
        transcript.write_text("", encoding="utf-8")
        exit_code = _run(
            monkeypatch,
            _real_shaped_payload(
                agent_type="nw-software-crafter",
                agent_transcript_path=str(transcript),
            ),
        )
        assert exit_code == 0
        assert "remove_signal" in calls
        assert any(c.startswith("track:") for c in calls)

    def test_cleanup_never_fires_for_a_non_nwave_agent(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        calls: list[str] = []
        from des.adapters.drivers.hooks import des_task_signal

        monkeypatch.setattr(
            des_task_signal, "remove_signal", lambda: calls.append("remove_signal")
        )
        exit_code = _run(monkeypatch, _real_shaped_payload(agent_type="Explore"))
        assert exit_code == 0
        assert calls == []

    def test_cleanup_exception_never_breaks_fail_open_contract(
        self, monkeypatch
    ) -> None:
        from des.adapters.drivers.hooks import des_task_signal

        def _boom():
            raise RuntimeError("boom")

        monkeypatch.setattr(des_task_signal, "remove_signal", _boom)
        exit_code = _run(
            monkeypatch, _real_shaped_payload(agent_type="nw-software-crafter")
        )
        assert exit_code == 0


class TestNamedInProcessTeammatesAreResolvedToTheirRealRole:
    """A NAMED in-process teammate's `agent_type` is its LANE NAME, not its
    role. Verified against Claude Code 2.1.239: the installed CLI's own
    in-process-teammate agent definition sets ``agentType: t.agentName``
    and stashes the real role separately as ``customAgentType`` in the
    teammate metadata; the SubagentStop hookInput's ``agent_type`` is
    sourced from the former. A bare ``startswith("nw-")`` gate therefore
    silently no-ops for EVERY named nWave lane -- the exact silence this
    resolution exists to close, so that lane's cleanup still fires.

    The role is recovered from the sidecar metadata file that sits next to
    the transcript the platform hands us in ``agent_transcript_path``
    (``<transcript-stem>.meta.json``). Fail-open: an absent/unreadable/
    roleless sidecar degrades to no-op.
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

    def test_named_lane_with_an_nwave_real_role_gets_cleanup(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        agent_id = "aspeedfix-6c5c7f8505b9e7dd"
        transcript = self._teammate_transcript(tmp_path, agent_id, "nw-troubleshooter")
        calls: list[str] = []
        from des.adapters.drivers.hooks import des_task_signal

        monkeypatch.setattr(
            des_task_signal, "remove_signal", lambda: calls.append("remove_signal")
        )

        exit_code = _run(
            monkeypatch,
            _real_shaped_payload(
                agent_type="speedfix",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="ho finito il lavoro",
            ),
        )

        assert exit_code == 0
        assert "remove_signal" in calls

    def test_named_lane_whose_real_role_is_not_nwave_gets_no_cleanup(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Resolution widens WHICH nWave roles are seen, never the
        population. A named lane whose real role is not an ``nw-*`` agent
        must still be a no-op."""
        agent_id = "aworker-1111222233334444"
        transcript = self._teammate_transcript(tmp_path, agent_id, "general-purpose")
        calls: list[str] = []
        from des.adapters.drivers.hooks import des_task_signal

        monkeypatch.setattr(
            des_task_signal, "remove_signal", lambda: calls.append("remove_signal")
        )

        exit_code = _run(
            monkeypatch,
            _real_shaped_payload(
                agent_type="worker",
                agent_id=agent_id,
                agent_transcript_path=str(transcript),
                last_assistant_message="done",
            ),
        )

        assert exit_code == 0
        assert calls == []

    def test_missing_sidecar_degrades_to_no_op_without_raising(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        exit_code = _run(
            monkeypatch,
            _real_shaped_payload(
                agent_type="speedfix",
                agent_id="aspeedfix-6c5c7f8505b9e7dd",
                agent_transcript_path=str(tmp_path / "agent-absent.jsonl"),
                last_assistant_message="x",
            ),
        )
        assert exit_code == 0
