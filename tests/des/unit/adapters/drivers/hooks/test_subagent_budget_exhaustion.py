"""Run 8: subagent budget-exhaustion guard.

Vera (nw-user-examiner) hit `maxTurns: 40` exactly, mid-work, with ZERO
terminal result -- the same silent-kill class ATD hit in run 3. A
dispatched nw-* subagent's own declared `maxTurns` is a hard boundary
Claude Code enforces by simply stopping the agent; root then cannot tell
"silently killed" apart from "still working". A subagent must never be
killed silently: once its own transcript shows its budget nearly
exhausted, every further tool call is denied so its NEXT turn has no
option left but the terminal text result.

Drives the real handler end-to-end (stdin -> stdout JSON / exit code),
the same harness shape as `test_nwave_subagent_host_scan_lockdown.py`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


REPO_ROOT = Path(__file__).resolve().parents[6]

# nw-user-examiner's own checked-in spec declares `maxTurns: 40` -- the
# real value this guard's threshold (N-2 = 38) is computed against, never
# a value hand-picked to make these tests pass.
_EXAMINER_MAX_TURNS = 40

# Structurally faithful, content-shortened copy of the run 8 evidence
# transcript: /tmp/nwave-k4-ee2b23ec4/.../subagents/agent-afcea072da342be9e.jsonl
# (attributionAgent nw-user-examiner). Same line-by-line entry-type
# sequence (thinking/tool_use/text assistant messages, tool_result user
# messages) as the real killed transcript; only text/thinking/tool-input
# payloads are truncated. The real transcript's own tool_result usage
# metadata reports `tool_uses: 40` for this exact agent -- the ground
# truth this guard's counting logic is calibrated against.
_RUN8_EXAMINER_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "run8_examiner_killed_transcript_trimmed.jsonl"
)

# Verbatim copy of run 9's REAL `subagents/agent-a84319ed68b17f632.meta.json`
# sidecar (nw-user-examiner, "Source-blind examine of maintenance windows
# feature") -- confirmed universal across every captured K4 run on this box
# (this one, and independently a nw-software-crafter dispatch from an
# unrelated run): the platform writes `{"agentType": "nw-...", ...}` once at
# spawn time, co-located next to the subagent's own `.jsonl` transcript.
_META_SIDECAR_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "subagent_meta_sidecar_nw_user_examiner.json"
)

# nw-software-crafter's own checked-in spec declares `maxTurns: 45` -- the
# real value run 10's threshold (N-2 = 43) is computed against.
_CRAFTER_MAX_TURNS = 45

# Structurally faithful, content-shortened copy of the run 10 evidence
# transcript: agent-a9783006eb9c709dd.jsonl under
# /tmp/nwave-k4-a9360df05/k4-root/.claude-k4/projects/**/subagents/ --
# nw-software-crafter, 54 real tool calls (24 Bash/15 Read/11 Edit/4 Skill),
# maxTurns 45, ZERO guard denials despite crossing the threshold at call 43
# and making 10 further Bash calls after it. Same line-by-line entry-type
# sequence as the real transcript; only text/thinking/tool-input payloads
# are truncated.
_RUN10_CRAFTER_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "run10_crafter_killed_transcript_trimmed.jsonl"
)

# Verbatim copy of run 10's REAL `subagents/agent-a9783006eb9c709dd.meta.json`
# sidecar (nw-software-crafter, "Implement maintenance windows delivery
# contract").
_CRAFTER_META_SIDECAR_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "subagent_meta_sidecar_nw_software_crafter.json"
)


def _transcript_with_assistant_turns(tmp_path: Path, count: int) -> str:
    """`count` synthetic assistant turns, each carrying exactly ONE
    `tool_use` content block -- calibrated shape (see
    `_subagent_transcript_turn_count`'s docstring): the guard counts
    `tool_use` BLOCKS, not bare assistant-type entries, so a fixture with
    empty `content` would silently count zero regardless of `count`."""
    transcript = tmp_path / "transcript.jsonl"
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"toolu_{i}",
                            "name": "Read",
                            "input": {"file_path": "/tmp/x"},
                        }
                    ]
                },
            }
        )
        for i in range(count)
    ]
    transcript.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return str(transcript)


def _stdin(
    *,
    tool_name: str,
    tool_input: dict,
    transcript_path: str,
    cwd: str,
    **identity: str,
) -> str:
    payload: dict[str, object] = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "transcript_path": transcript_path,
        "cwd": cwd,
    }
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestSubagentBudgetExhaustionDenies:
    @pytest.mark.parametrize(
        "turn_count", [38, 39, 45], ids=["exactly_n_minus_2", "n_minus_1", "past_n"]
    )
    def test_at_or_past_max_turns_minus_two_denies(
        self, monkeypatch, capsys, audit_events, tmp_path, turn_count
    ) -> None:
        transcript_path = _transcript_with_assistant_turns(tmp_path, turn_count)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x.py"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        reason = payload["reason"]
        assert "WHAT:" in reason and "WHY:" in reason and "HOW:" in reason
        assert "NW-USER-EXAMINER-RESULT" in reason
        assert "INDETERMINATE" in reason
        assert str(_EXAMINER_MAX_TURNS) in reason

    def test_applies_regardless_of_tool_name(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript_with_assistant_turns(
            tmp_path, _EXAMINER_MAX_TURNS
        )
        for tool_name, tool_input in (
            ("Bash", {"command": "ls"}),
            ("Write", {"file_path": "/tmp/x", "content": "x"}),
            ("Grep", {"pattern": "x"}),
            ("Skill", {"skill": "nw-code-analysis-port"}),
        ):
            exit_code, payload = _run(
                monkeypatch,
                capsys,
                _stdin(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    transcript_path=transcript_path,
                    cwd=str(REPO_ROOT),
                    agent_type="nw-user-examiner",
                ),
            )
            assert exit_code == 2, tool_name
            assert payload["decision"] == "block", tool_name


class TestSubagentBudgetExhaustionAllows:
    @pytest.mark.parametrize(
        "turn_count", [0, 1, 37], ids=["zero", "one", "exactly_n_minus_3"]
    )
    def test_below_max_turns_minus_two_allows(
        self, monkeypatch, capsys, audit_events, tmp_path, turn_count
    ) -> None:
        transcript_path = _transcript_with_assistant_turns(tmp_path, turn_count)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x.py"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()

    def test_root_is_never_gated(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript_with_assistant_turns(tmp_path, 500)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            json.dumps(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/tmp/x"},
                    "transcript_path": transcript_path,
                    "cwd": str(REPO_ROOT),
                }
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()

    def test_role_with_no_resolvable_spec_is_never_gated(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        # Every checked-in nw-* agent spec today declares a maxTurns, so
        # this exercises the "no declared budget" path the only way it can
        # currently occur: a role name with no spec file at all --
        # `resolve_declared_max_turns` returns None, and this guard must
        # never invent a default budget for it.
        transcript_path = _transcript_with_assistant_turns(tmp_path, 500)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-does-not-exist-role",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()

    def test_non_nwave_agent_type_is_never_gated(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript_with_assistant_turns(tmp_path, 500)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="some-other-agent",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()

    def test_missing_transcript_fails_open_never_a_new_block(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        missing_path = str(tmp_path / "does-not-exist.jsonl")
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x"},
                transcript_path=missing_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()


class TestSubagentBudgetExhaustionOnARealKilledTranscript:
    """Not a synthetic fixture: a structurally faithful, content-shortened
    copy of the ACTUAL run 8 nw-user-examiner transcript that was really
    killed at `maxTurns: 40` with zero terminal result. Proves the guard
    would have intervened BEFORE that real kill point -- a prefix cut well
    short of the full 124-line transcript already trips the deny, at the
    exact tool_use counts (37, 38) the calibration measured."""

    @staticmethod
    def _prefix_transcript(tmp_path: Path, line_count: int) -> str:
        real_lines = _RUN8_EXAMINER_FIXTURE.read_text(encoding="utf-8").splitlines()
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            "\n".join(real_lines[:line_count]) + "\n", encoding="utf-8"
        )
        return str(transcript)

    def test_full_real_transcript_denies(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = self._prefix_transcript(tmp_path, 124)
        assert (
            pre_tool_use_handler._subagent_transcript_turn_count(transcript_path)
            == _EXAMINER_MAX_TURNS
        )
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x.py"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "NW-USER-EXAMINER-RESULT" in payload["reason"]

    def test_deny_fires_before_the_real_kill_point(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """A 117-line prefix -- 7 lines short of the real 124-line kill
        point -- already carries `tool_use` count 38 (calibration measured
        the exact line), the guard's own deny threshold. If this fired
        live, root would see the INDETERMINATE request BEFORE the agent
        was ever silently killed, not after."""
        transcript_path = self._prefix_transcript(tmp_path, 117)
        assert (
            pre_tool_use_handler._subagent_transcript_turn_count(transcript_path)
            == _EXAMINER_MAX_TURNS - 2
        )
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x.py"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_one_turn_earlier_still_allows(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """A 114-line prefix carries `tool_use` count 37 -- one below the
        deny threshold -- and must still be allowed: the guard is not
        firing early out of over-caution."""
        transcript_path = self._prefix_transcript(tmp_path, 114)
        assert (
            pre_tool_use_handler._subagent_transcript_turn_count(transcript_path)
            == _EXAMINER_MAX_TURNS - 3
        )
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "/tmp/x.py"},
                transcript_path=transcript_path,
                cwd=str(REPO_ROOT),
                agent_type="nw-user-examiner",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "budget" not in payload.get("reason", "").lower()


class TestSubagentBudgetExhaustionWithoutALiveAgentTypeField:
    """Run 9 root cause: Vera made 44 real tool calls (36 Bash, matcher-
    eligible) with the guard denying NONE of them -- `hook_input.get(
    "agent_type")` read `None` on every one of her OWN PreToolUse calls
    (the CLI's own hooks reference documents `agent_id`/`agent_type` as
    SubagentStart/SubagentStop-specific fields, never as part of the
    generic PreToolUse envelope). This class drives the SAME real,
    calibrated run-8/9-shape transcript (`_RUN8_EXAMINER_FIXTURE`) through
    a hook_input payload that OMITS `agent_type` entirely -- the exact
    real-world envelope shape -- relying only on `transcript_path` pointing
    into a real `subagents/agent-<id>.jsonl` layout with its co-located
    `.meta.json` sidecar (`_META_SIDECAR_FIXTURE`) for identity. Proves the
    fix, not just the symptom: before it, `_is_nwave_subagent` returned
    False here and the guard never engaged at any turn count."""

    @staticmethod
    def _prefix_transcript_in_subagents_dir(tmp_path: Path, line_count: int) -> str:
        real_lines = _RUN8_EXAMINER_FIXTURE.read_text(encoding="utf-8").splitlines()
        subagents_dir = tmp_path / "subagents"
        subagents_dir.mkdir()
        transcript = subagents_dir / "agent-a84319ed68b17f632.jsonl"
        transcript.write_text(
            "\n".join(real_lines[:line_count]) + "\n", encoding="utf-8"
        )
        meta_sidecar_text = _META_SIDECAR_FIXTURE.read_text(encoding="utf-8")
        (subagents_dir / "agent-a84319ed68b17f632.meta.json").write_text(
            meta_sidecar_text, encoding="utf-8"
        )
        return str(transcript)

    def test_deny_fires_at_calibrated_threshold_with_no_agent_type_in_envelope(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = self._prefix_transcript_in_subagents_dir(tmp_path, 117)
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "transcript_path": transcript_path,
                "cwd": str(REPO_ROOT),
                # No "agent_type" key at all -- the real PreToolUse shape.
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        exit_code = pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        assert exit_code == 2
        assert payload_out["decision"] == "block"
        assert "NW-USER-EXAMINER-RESULT" in payload_out["reason"]

    def test_one_turn_earlier_still_allows_with_no_agent_type_in_envelope(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = self._prefix_transcript_in_subagents_dir(tmp_path, 114)
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "transcript_path": transcript_path,
                "cwd": str(REPO_ROOT),
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        if payload_out is not None and payload_out.get("decision") == "block":
            assert "budget" not in payload_out.get("reason", "").lower()

    def test_flat_transcript_path_outside_a_subagents_dir_never_gates(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """Root's own transcript never sits inside a `subagents/` directory
        -- the sidecar fallback must never mistake a flat, non-nested
        transcript path (root's own shape) for a subagent's."""
        real_lines = _RUN8_EXAMINER_FIXTURE.read_text(encoding="utf-8").splitlines()
        transcript = tmp_path / "root_own_transcript.jsonl"
        transcript.write_text("\n".join(real_lines[:117]) + "\n", encoding="utf-8")
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "transcript_path": str(transcript),
                "cwd": str(REPO_ROOT),
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        if payload_out is not None and payload_out.get("decision") == "block":
            assert "budget" not in payload_out.get("reason", "").lower()


class TestSubagentBudgetExhaustionWithTranscriptPathNamingTheParentSession:
    """Run 10 root cause: a real nw-software-crafter (maxTurns 45) made 54
    real tool calls (24 Bash) with the guard denying NONE of them, even
    after the run 9 fix (agent_type resolved via the transcript
    meta-sidecar). Live repro against the real installed hook confirmed the
    reason: her OWN PreToolUse `transcript_path` did not point at her
    dedicated `subagents/agent-<id>.jsonl` file the way run 9's fix assumed
    -- it named the PARENT/root session's own top-level `<session-id>.jsonl`
    log instead (a real, different file). `resolve_subagent_agent_type`'s
    sidecar lookup silently found nothing there (`path.parent.name !=
    "subagents"`), for both identity AND turn-counting.

    This class drives the exact real shape: `transcript_path` names a
    ROOT-shaped sibling file (`<session-id>.jsonl`, next to a real
    `<session-id>/subagents/` directory -- the same structural pattern
    verified on every captured K4 run), plus `agent_id` (the field
    `resolve_subagent_own_transcript_path` derives the subagent's own file
    from), no `agent_type` key at all."""

    @staticmethod
    def _crafter_transcript_and_root_path(tmp_path: Path, line_count: int) -> str:
        """Builds `<tmp>/session/subagents/agent-<id>.jsonl` (the real
        subagent shape, populated from the trimmed run 10 fixture) plus its
        `.meta.json` sidecar, and returns the ROOT-shaped sibling path
        (`<tmp>/session.jsonl`) a caller should pass as `transcript_path` --
        mirroring the real `<session-id>.jsonl` next to `<session-id>/
        subagents/` layout. The root-shaped file itself need not exist:
        `resolve_subagent_own_transcript_path` only uses its PATH structure
        (parent + stem) to derive the real subagent file, then verifies
        THAT one exists on disk."""
        real_lines = _RUN10_CRAFTER_FIXTURE.read_text(encoding="utf-8").splitlines()
        session_dir = tmp_path / "session"
        subagents_dir = session_dir / "subagents"
        subagents_dir.mkdir(parents=True)
        transcript = subagents_dir / "agent-run10-crafter-probe.jsonl"
        transcript.write_text(
            "\n".join(real_lines[:line_count]) + "\n", encoding="utf-8"
        )
        meta_sidecar_text = _CRAFTER_META_SIDECAR_FIXTURE.read_text(encoding="utf-8")
        (subagents_dir / "agent-run10-crafter-probe.meta.json").write_text(
            meta_sidecar_text, encoding="utf-8"
        )
        return str(tmp_path / "session.jsonl")

    def test_deny_fires_at_calibrated_threshold_via_derived_transcript_path(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        root_shaped_transcript_path = self._crafter_transcript_and_root_path(
            tmp_path, 113
        )
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git diff --stat"},
                "transcript_path": root_shaped_transcript_path,
                "agent_id": "run10-crafter-probe",
                "cwd": str(REPO_ROOT),
                # No "agent_type" key at all -- the real PreToolUse shape.
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        exit_code = pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        assert exit_code == 2
        assert payload_out["decision"] == "block"
        assert "NW-SOFTWARE-CRAFTER-RESULT" in payload_out["reason"]
        assert str(_CRAFTER_MAX_TURNS) in payload_out["reason"]

    def test_one_turn_earlier_still_allows_via_derived_transcript_path(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        root_shaped_transcript_path = self._crafter_transcript_and_root_path(
            tmp_path, 110
        )
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git diff --stat"},
                "transcript_path": root_shaped_transcript_path,
                "agent_id": "run10-crafter-probe",
                "cwd": str(REPO_ROOT),
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        if payload_out is not None and payload_out.get("decision") == "block":
            assert "budget" not in payload_out.get("reason", "").lower()

    def test_no_agent_id_and_root_shaped_path_never_gates(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """Without `agent_id`, a root-shaped `transcript_path` cannot be
        derived into any subagent file at all -- must never guess, must
        stay allowed (this is root's own genuinely root-shaped call)."""
        root_shaped_transcript_path = self._crafter_transcript_and_root_path(
            tmp_path, 113
        )
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git diff --stat"},
                "transcript_path": root_shaped_transcript_path,
                "cwd": str(REPO_ROOT),
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        pre_tool_use_handler.handle_pre_tool_use()
        out = capsys.readouterr().out.strip()
        payload_out = json.loads(out) if out else None
        if payload_out is not None and payload_out.get("decision") == "block":
            assert "budget" not in payload_out.get("reason", "").lower()
