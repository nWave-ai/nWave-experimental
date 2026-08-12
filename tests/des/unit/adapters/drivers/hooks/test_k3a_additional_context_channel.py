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


def _pre_write_stdin(
    transcript_path: str | None = None,
    *,
    tool_name: str = "Write",
    **identity: str,
) -> str:
    """nWave-adjacent Write/Edit, no active deliver session -- reminder pertinent.

    Since the mode-select gate (activation-routing-before-mutation) now
    blocks a pertinent Write with no observed `Skill(nw-mode-select)` call,
    callers exercising the allow/reminder path must supply a transcript that
    already contains that call. `tool_name` selects Write vs Edit (the
    handler treats both identically); `**identity` merges in `agent_id`/
    `agent_type` without a second fixture.
    """
    payload = {
        "tool_name": tool_name,
        "tool_input": {"file_path": "/repo/src/des/domain/foo.py"},
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    payload.update(identity)
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

    def test_arbitrary_top_level_write_is_now_pertinent_and_denies(
        self, monkeypatch, capsys, audit_events
    ) -> None:
        """Root-write-boundary slice (K4): a path that previously sat
        outside the fixed root allowlist (`src/`, `nWave/`, `tests/`,
        `scripts/`) is now pertinent regardless of its top-level directory
        name, so a root Write with no observed `Skill(nw-mode-select)` call
        DENIES exactly like an in-tree path would."""
        stdin = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/scratch/notes.txt"},
            }
        )

        exit_code, payload = _run_pre_write(monkeypatch, capsys, stdin)

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert payload["reason"] == "Invoke nw-mode-select before the first mutation."

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


def _send_message_stdin(transcript_path: str | None = None) -> str:
    payload = {
        "tool_name": "SendMessage",
        "tool_input": {"to": "acceptance-designer", "message": "resume"},
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _nw_auto_observed_transcript(tmp_path) -> str:
    """The REAL Claude Code transcript shape: an authentic `Skill(nw-auto)`
    tool_use nested under `message.content`."""
    transcript = tmp_path / "nw-auto-transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "nw-auto"},
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(transcript)


def _nw_mode_select_observed_transcript(tmp_path) -> str:
    """An authentic `Skill(nw-mode-select)` call -- a different skill, must
    not arm the nw-auto SendMessage gate."""
    transcript = tmp_path / "mode-select-only-transcript.jsonl"
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


def _user_forged_nw_auto_transcript(tmp_path) -> str:
    """A `Skill(nw-auto)` call under a `user`-authored entry -- non-
    authoritative, must not arm the gate (same authority rule the
    mode-select user/system partition already proves)."""
    transcript = tmp_path / "user-forged-nw-auto-transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "nw-auto"},
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(transcript)


def _system_forged_nw_auto_transcript(tmp_path) -> str:
    """A `Skill(nw-auto)` call under a `system`-authored entry -- same
    non-authoritative rule as the user-forged case."""
    transcript = tmp_path / "system-forged-nw-auto-transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "system",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "nw-auto"},
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return str(transcript)


class TestSendMessageSinglePassAutoGate:
    """K4 overhead slice: an activated Auto run blocks root SendMessage --
    the first result of each dispatched role is terminal, no
    resume/retry/correction within the same run. Outside an observed
    `Skill(nw-auto)`, SendMessage stays allowed byte-for-byte."""

    def test_authentic_nw_auto_observed_blocks_send_message(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _nw_auto_observed_transcript(tmp_path)

        exit_code, payload = _run_pre_tool_use(
            monkeypatch, capsys, _send_message_stdin(transcript_path)
        )

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert payload["reason"] == (
            "Auto roles are single-pass: do not SendMessage, resume, retry, "
            "or correct a role within the same Auto run."
        )

    @pytest.mark.parametrize(
        "transcript_path_fn",
        [
            lambda tmp_path: None,
            lambda tmp_path: "/nonexistent/transcript.jsonl",
            _nw_mode_select_observed_transcript,
            _user_forged_nw_auto_transcript,
            _system_forged_nw_auto_transcript,
            _unrelated_transcript,
            lambda tmp_path: _unrelated_transcript(tmp_path, malformed=True),
        ],
        ids=[
            "no_transcript_path_field",
            "missing_transcript_file",
            "nw_mode_select_not_nw_auto",
            "user_forged_nested_skill",
            "system_forged_nested_skill",
            "prose_or_unrelated_skill",
            "malformed_transcript",
        ],
    )
    def test_non_arm_partition_leaves_send_message_allowed(
        self, monkeypatch, capsys, audit_events, tmp_path, transcript_path_fn
    ) -> None:
        transcript_path = transcript_path_fn(tmp_path)

        exit_code, payload = _run_pre_tool_use(
            monkeypatch, capsys, _send_message_stdin(transcript_path)
        )

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"


def _mode_select_and_nw_auto_transcript(
    tmp_path, *, auto_author: str = "assistant"
) -> str:
    """Both an authentic `Skill(nw-mode-select)` and a `Skill(nw-auto)` call
    in the same transcript, nested under `message.content` the real-shape
    way. `auto_author` controls whether the nw-auto entry is authentic
    ("assistant") or forged ("user"/"system") -- mode-select stays
    authentic in every case so the base activation gate always passes,
    isolating what the auto-root gate itself is deciding on.
    """
    transcript = tmp_path / f"mode-select-and-nw-auto-{auto_author}-transcript.jsonl"
    entries = [
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
        },
        {
            "type": auto_author,
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "nw-auto"},
                    }
                ]
            },
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return str(transcript)


class TestPreWriteEditAutoRootDirectWriteGate:
    """pre_write_handler.py's auto-root gate: once nw-mode-select is
    authentically observed, a root (no agent_id/agent_type) Write/Edit is
    further denied when an authentic `Skill(nw-auto)` is ALSO observed in
    the same transcript -- an Auto root must dispatch the owning role
    instead of mutating source directly."""

    @pytest.mark.parametrize("tool_name", ["Write", "Edit"])
    def test_authentic_mode_select_and_nw_auto_blocks_root_write_and_edit(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_name
    ) -> None:
        transcript_path = _mode_select_and_nw_auto_transcript(tmp_path)

        exit_code, payload = _run_pre_write(
            monkeypatch,
            capsys,
            _pre_write_stdin(transcript_path, tool_name=tool_name),
        )

        assert exit_code == 2
        assert payload["decision"] == "block"
        assert payload["reason"] == (
            "Auto root cannot author or repair role-owned artifacts or "
            "production directly -- dispatch the owning role instead."
        )

    @pytest.mark.parametrize(
        "agent_identity",
        [
            {"agent_id": "agent-123"},
            {"agent_type": "general-purpose"},
        ],
        ids=["agent_id", "agent_type"],
    )
    def test_non_root_agent_bypasses_auto_root_gate(
        self, monkeypatch, capsys, audit_events, tmp_path, agent_identity
    ) -> None:
        """Nested-agent Write/Edit is not a root invocation -- same
        bypass rule as TestPreWriteModeSelectGate's
        test_non_root_agent_preserves_prior_write_behavior, now proven
        with both gate-arming skills present."""
        transcript_path = _mode_select_and_nw_auto_transcript(tmp_path)

        exit_code, payload = _run_pre_write(
            monkeypatch,
            capsys,
            _pre_write_stdin(transcript_path, **agent_identity),
        )

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    @pytest.mark.parametrize(
        "transcript_path_fn",
        [
            lambda tmp_path: _mode_select_and_nw_auto_transcript(
                tmp_path, auto_author="user"
            ),
            lambda tmp_path: _mode_select_and_nw_auto_transcript(
                tmp_path, auto_author="system"
            ),
            _mode_select_observed_transcript,
        ],
        ids=[
            "user_forged_nw_auto",
            "system_forged_nw_auto",
            "nw_auto_missing",
        ],
    )
    def test_non_arming_partition_leaves_write_allowed(
        self, monkeypatch, capsys, audit_events, tmp_path, transcript_path_fn
    ) -> None:
        """A forged (user/system) nw-auto, or no nw-auto call at all, never
        arms the auto-root gate -- mode-select alone (reused from
        `_mode_select_observed_transcript`) still satisfies the base gate."""
        transcript_path = transcript_path_fn(tmp_path)

        exit_code, payload = _run_pre_write(
            monkeypatch, capsys, _pre_write_stdin(transcript_path)
        )

        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"
