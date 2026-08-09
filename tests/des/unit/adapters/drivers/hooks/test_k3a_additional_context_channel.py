"""K3-A root reminder channel and activation-routing mutation gate.

`docs/analysis/2026-08-07-k3a-root-activation-evidence-report.md` Section 4.2:
the Agent-dispatch path must inject its reminder through `additionalContext`,
the only documented model-context channel. The Write/Edit path is instead a
one-time boundary: it denies mutation until a real `Skill(nw-mode-select)` is
observed, then allows silently without repeating the reminder on every write.

The installed runtime's own hook documentation states:

    - `additionalContext` - Text injected into model context
    - `permissionDecision` - "allow", "deny", or "ask" (PreToolUse only)
    - `permissionDecisionReason` - Reason for the permission decision (PreToolUse only)

These tests drive the real handlers end-to-end (stdin -> stdout JSON), the
same harness shape as
`tests/des/unit/adapters/drivers/hooks/test_hook_completed_event.py`, and
assert both the Agent reminder channel and the Write/Edit gate transition.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks.root_activation_context import (
    ROOT_MODE_SELECT_REMINDER,
)


def _pre_write_stdin(transcript_path: str | None = None) -> str:
    """nWave-adjacent Write, no active deliver session -- reminder pertinent.

    Since the mode-select gate (activation-routing-before-mutation) now
    blocks a pertinent Write with no observed `Skill(nw-mode-select)` call,
    callers exercising the allow/reminder path must supply a transcript that
    already contains that call.
    """
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/des/domain/foo.py"},
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _mode_select_observed_transcript(tmp_path) -> str:
    """A transcript with an actual `Skill(nw-mode-select)` tool_use entry."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "nw-mode-select"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(transcript)


def _pre_tool_use_agent_stdin() -> str:
    """Agent dispatch to a nw-* subagent, no mode/wave declared -- pertinent."""
    return json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "Fix the flaky assertion in the login test.",
                "subagent_type": "nw-crafter",
            },
        }
    )


def _hook_specific_output_from(
    monkeypatch, capsys, handler_name: str, stdin: str
) -> dict:
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = getattr(adapter, handler_name)()
    assert exit_code == 0

    out = capsys.readouterr().out.strip()
    assert out, f"{handler_name} produced no stdout for a pertinent K3-A dispatch"
    payload = json.loads(out)
    return payload["hookSpecificOutput"]


def _run_pre_write(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    """Drive handle_pre_write end-to-end; return (exit_code, parsed stdout or None)."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = adapter.handle_pre_write()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


def _unrelated_transcript(tmp_path, *, malformed: bool = False) -> str:
    transcript = tmp_path / "transcript.jsonl"
    if malformed:
        transcript.write_text("not-json\nalso not json\n", encoding="utf-8")
    else:
        transcript.write_text(
            "\n".join(
                json.dumps(line)
                for line in [
                    {"type": "text", "text": "I will invoke nw-mode-select next."},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {
                            "file_path": "/repo/nWave/skills/nw-mode-select/SKILL.md"
                        },
                    },
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "nw-bugfix"},
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return str(transcript)


class TestPreWriteModeSelectGate:
    """activation-routing-before-mutation: an activated root Write/Edit with
    no observed `Skill(nw-mode-select)` call is DENIED, not merely reminded."""

    def test_neutral_first_write_denies(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        exit_code, payload = _run_pre_write(monkeypatch, capsys, _pre_write_stdin())

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert payload["reason"] == "Invoke nw-mode-select before the first mutation."

    def test_prior_mode_select_call_allows_existing_path(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _mode_select_observed_transcript(tmp_path)

        exit_code, payload = _run_pre_write(
            monkeypatch, capsys, _pre_write_stdin(transcript_path)
        )

        assert exit_code == 0
        assert payload is None

    def test_prose_mention_and_unrelated_skill_do_not_satisfy_the_gate(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _unrelated_transcript(tmp_path)

        exit_code, payload = _run_pre_write(
            monkeypatch, capsys, _pre_write_stdin(transcript_path)
        )

        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_unreadable_malformed_transcript_denies_at_activated_root(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _unrelated_transcript(tmp_path, malformed=True)

        exit_code, payload = _run_pre_write(
            monkeypatch, capsys, _pre_write_stdin(transcript_path)
        )

        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_missing_transcript_path_denies_at_activated_root(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        exit_code, payload = _run_pre_write(
            monkeypatch, capsys, _pre_write_stdin("/nonexistent/transcript.jsonl")
        )

        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_non_activated_project_write_is_unaffected(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        """A file outside the nWave-adjacent roots never reaches the gate --
        same allow outcome as before this change, no transcript needed."""
        stdin = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/scratch/notes.txt"},
            }
        )

        exit_code, payload = _run_pre_write(monkeypatch, capsys, stdin)

        assert exit_code == 0
        assert payload is None or "decision" not in payload

    @pytest.mark.parametrize(
        "agent_identity",
        [
            {"agent_id": "agent-123"},
            {"agent_type": "general-purpose"},
        ],
        ids=["agent_id", "agent_type"],
    )
    def test_non_root_agent_preserves_prior_write_behavior(
        self,
        monkeypatch,
        capsys,
        audit_events,
        agent_identity: dict[str, str],
    ) -> None:
        """Nested-agent Write/Edit bypasses the root-only activation gate.

        CONTRACT_SHAPE: bounded-change
        """
        payload = json.loads(_pre_write_stdin())
        payload.update(agent_identity)

        exit_code, output = _run_pre_write(monkeypatch, capsys, json.dumps(payload))

        assert exit_code == 0
        assert output is None or output.get("decision") != "block"

    def test_established_deliver_session_is_unaffected(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """A live deliver session means mode/wave is already engaged
        elsewhere -- the gate must not re-demand nw-mode-select."""
        from des.adapters.drivers.hooks import des_task_signal

        session_file = tmp_path / "deliver-session.json"
        session_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(des_task_signal, "DES_DELIVER_SESSION_FILE", session_file)
        # SessionGuardPolicy also blocks src/ writes during an active session
        # unless a DES subagent is running -- unrelated to the mode-select
        # gate under test, so satisfy it via des_task_active.
        task_active_file = tmp_path / "des-task-active"
        task_active_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(des_task_signal, "DES_TASK_ACTIVE_FILE", task_active_file)

        stdin = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/repo/src/des/domain/foo.py"},
            }
        )
        exit_code, payload = _run_pre_write(monkeypatch, capsys, stdin)

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"


class TestPreToolUseReminderReachesAdditionalContext:
    def test_pre_tool_use_root_reminder_uses_additional_context_channel(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        hook_specific = _hook_specific_output_from(
            monkeypatch, capsys, "handle_pre_tool_use", _pre_tool_use_agent_stdin()
        )
        assert hook_specific.get("additionalContext") == ROOT_MODE_SELECT_REMINDER, (
            "D2: the K3-A root reminder must reach the model via "
            "additionalContext -- permissionDecisionReason only explains a "
            "permission decision and is not documented to enter model context"
        )

    def test_pre_tool_use_still_carries_a_permission_decision(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        hook_specific = _hook_specific_output_from(
            monkeypatch, capsys, "handle_pre_tool_use", _pre_tool_use_agent_stdin()
        )
        assert hook_specific.get("permissionDecision") == "allow"


def _run_pre_tool_use(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    """Drive handle_pre_tool_use end-to-end; return (exit_code, parsed stdout)."""
    from des.adapters.drivers.hooks import claude_code_hook_adapter as adapter

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = adapter.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


def _bash_stdin(transcript_path: str | None = None) -> str:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _real_nested_mode_select_transcript(tmp_path) -> str:
    """The REAL Claude Code transcript shape: tool_use nested under
    `message.content`, never a bare top-level `tool_use` entry."""
    transcript = tmp_path / "real-nested-transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "nw-mode-select"},
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(transcript)


class TestPreToolUseBashModeSelectGate:
    """activation-routing-before-mutation extends to Bash (blocker #2): a
    real falsifier starts with Bash, which PreWrite alone cannot close."""

    def test_neutral_first_bash_denies(self, monkeypatch, capsys, audit_events) -> None:
        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, _bash_stdin())

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert (
            payload["reason"]
            == "Invoke nw-mode-select before the first Bash/Write/Edit."
        )

    @pytest.mark.parametrize(
        "agent_identity",
        [
            {"agent_id": "agent-123"},
            {"agent_type": "general-purpose"},
        ],
        ids=["agent_id", "agent_type"],
    )
    def test_non_root_agent_preserves_prior_bash_behavior(
        self, monkeypatch, capsys, audit_events, agent_identity: dict[str, str]
    ) -> None:
        payload = json.loads(_bash_stdin())
        payload.update(agent_identity)

        exit_code, output = _run_pre_tool_use(monkeypatch, capsys, json.dumps(payload))

        assert exit_code == 0
        assert output is None or output.get("decision") != "block"

    def test_real_nested_transcript_mode_select_unlocks_bash(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _real_nested_mode_select_transcript(tmp_path)

        exit_code, payload = _run_pre_tool_use(
            monkeypatch, capsys, _bash_stdin(transcript_path)
        )

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    def test_prose_mention_and_unrelated_skill_do_not_unlock_bash(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _unrelated_transcript(tmp_path)

        exit_code, payload = _run_pre_tool_use(
            monkeypatch, capsys, _bash_stdin(transcript_path)
        )

        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_established_deliver_session_leaves_bash_unaffected(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        from des.adapters.drivers.hooks import des_task_signal

        session_file = tmp_path / "deliver-session.json"
        session_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(des_task_signal, "DES_DELIVER_SESSION_FILE", session_file)

        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, _bash_stdin())

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    def test_missing_transcript_never_blocks_the_skill_tool_itself(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        """Only Bash/Write/Edit consume the mode-select gate -- a Skill
        invocation (e.g. nw-mode-select itself) must never be blocked for
        lacking a transcript, or the gate could never be satisfied."""
        stdin = json.dumps(
            {"tool_name": "Skill", "tool_input": {"skill": "nw-mode-select"}}
        )

        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, stdin)

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"


class TestPreToolUseUniversalBashGuardsReachHandler:
    """The consolidated `_evaluate_bash_guards` boundary is wired into the
    PRIMARY installed `handle_pre_tool_use()` path (blocker: no test drove
    this after the standalone git_stash/worktree_removal hook registrations
    were retired). Non-root agent identity sidesteps the unrelated
    mode-select gate without bypassing `_evaluate_bash_guards` itself."""

    def test_git_stash_push_blocks_with_stash_reason(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        stdin = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git stash push"},
                "agent_id": "agent-123",
            }
        )

        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, stdin)

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "git stash is forbidden" in payload["reason"]

    def test_git_stash_list_is_allowed_and_silent(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        stdin = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git stash list"},
                "agent_id": "agent-123",
            }
        )

        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, stdin)

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    def test_git_worktree_remove_blocks_via_universal_decision(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        """Patches only the triage boundary (`collect_worktree_triage_receipt`)
        to a deterministic non-CLEAN receipt, so no real git/filesystem
        mutation occurs while still exercising the real
        `evaluate_worktree_remove_command` decision path inside the
        handler."""
        from des.application import worktree_triage_collector
        from des.domain.worktree_anti_rot_triage import TriageState

        class _FakeReceipt:
            state = TriageState.LIVE
            evidence: list = []
            actions: list[str] = []
            how = "test-forced-non-clean"
            unavailable_evidence: list[str] = []

        monkeypatch.setattr(
            worktree_triage_collector,
            "collect_worktree_triage_receipt",
            lambda **kwargs: _FakeReceipt(),
        )

        stdin = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git worktree remove /tmp/example"},
                "agent_id": "agent-123",
            }
        )

        exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, stdin)

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "WORKTREE REMOVAL REFUSED" in payload["reason"]
