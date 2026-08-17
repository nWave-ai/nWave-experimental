"""K4 architecture gap: Auto-root Bash/Task lockdown.

Auto's root process (the process that itself observed `Skill(nw-auto)` in
its own transcript, carrying neither `agent_id` nor `agent_type`) is
restricted to a closed allowlist of `git` read/stage/commit subcommands on
Bash, and is denied `TaskCreate`/`TaskUpdate` outright — that task-signal
authority belongs to a dispatched role, not the root orchestrator.

Drives the real handler end-to-end (stdin -> stdout JSON / exit code), the
same harness shape as `test_k3a_additional_context_channel.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


def _transcript(
    tmp_path, *, auto: bool, mode_select: bool = False, malformed: bool = False
):
    transcript = tmp_path / "transcript.jsonl"
    if malformed:
        transcript.write_text("not-json\n", encoding="utf-8")
        return str(transcript)
    lines = []
    if auto:
        lines.append(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
        )
    if mode_select:
        lines.append(
            {
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "nw-mode-select"},
            }
        )
    transcript.write_text(
        "\n".join(json.dumps(line) for line in lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    return str(transcript)


def _stdin(
    *,
    tool_name: str,
    tool_input: dict,
    transcript_path: str | None = None,
    **identity: str,
) -> str:
    payload: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestAutoRootBashAllowlist:
    """A confirmed Auto-root process's Bash calls: only a bare, single
    `git status|diff|rev-parse|branch|worktree|add|commit` survives."""

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git diff",
            "git rev-parse HEAD",
            "git branch --show-current",
            "git worktree list",
            "git add -A",
            'git commit -m "message"',
        ],
    )
    def test_clean_git_allowlisted_command_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        # Not vetoed by the Auto-root allowlist: whatever the downstream
        # outcome, it must not be the auto-root-specific block payload.
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_non_git_command_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "ls -la"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"] or "git" in payload["reason"]

    def test_disallowed_git_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git push origin main"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    @pytest.mark.parametrize(
        "command",
        [
            "git status && rm -rf /",
            "git status || echo pwned",
            "git status; rm -rf /",
            "git status | tee /tmp/x",
            "git status `whoami`",
            "git status $(whoami)",
            "git status < /etc/passwd",
            "git status > /etc/passwd",
            "git status\nrm -rf /",
            "git status\rrm -rf /",
            "git status; git push origin main --force",
        ],
    )
    def test_every_injection_operator_blocks_even_with_leading_allowed_git(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_injection_operator_short_circuits_before_shlex_split(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """The lexical reject fires BEFORE `shlex.split` -- a poisoned
        allowlist string must never reach tokenization or the allow-list
        comparison."""

        def _boom(*args, **kwargs):
            raise AssertionError("shlex.split must not run for an operator input")

        monkeypatch.setattr(pre_tool_use_handler.shlex, "split", _boom)
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status && rm -rf /"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"


class TestAutoRootBashDesAllowlist:
    """A confirmed Auto-root process's Bash calls also allow a bare, single
    `des dispatch|validate-delivery-contract|charter-scaffold` invocation --
    the direct-cutover spine's only hook-controller-free CLI seam."""

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatch F-EXAMPLE",
            "des validate-delivery-contract docs/feature/x/delivery-contract.json",
            "des charter-scaffold F-EXAMPLE",
        ],
        ids=["dispatch", "validate-delivery-contract", "charter-scaffold"],
    )
    def test_clean_des_allowlisted_command_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_des_missing_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "des"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatc F-EXAMPLE",
            "des Dispatch F-EXAMPLE",
            "des validate_delivery_contract x.json",
            "des status",
            "des help",
            "des dispatch-all",
        ],
        ids=[
            "near_miss_typo",
            "near_miss_case",
            "near_miss_underscore",
            "unknown_status",
            "unknown_help",
            "unknown_dispatch_all",
        ],
    )
    def test_des_unknown_or_near_miss_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatch F-EXAMPLE && rm -rf /",
            "des dispatch F-EXAMPLE || echo pwned",
            "des dispatch F-EXAMPLE; rm -rf /",
            "des dispatch F-EXAMPLE | tee /tmp/x",
            "des dispatch `whoami`",
            "des dispatch $(whoami)",
            "des dispatch F-EXAMPLE < /etc/passwd",
            "des dispatch F-EXAMPLE > /etc/passwd",
            "des dispatch F-EXAMPLE\nrm -rf /",
            "des dispatch F-EXAMPLE\rrm -rf /",
            "des dispatch F-EXAMPLE; des dispatch OTHER",
        ],
    )
    def test_des_composition_operator_blocks_even_with_leading_allowed_subcommand(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_des_extra_executable_prefix_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "python -m des dispatch F-EXAMPLE"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]


class TestAutoRootBashMalformedCommandFailsClosed:
    """Once Auto-root is armed, a malformed `command` (missing/empty/
    whitespace-only/non-string) must fail CLOSED -- blocked -- not fall
    through to mode-select or attribution as an implicit allow."""

    @pytest.mark.parametrize(
        "tool_input",
        [
            {},
            {"command": ""},
            {"command": "   \t  "},
            {"command": 12345},
        ],
        ids=["missing", "empty", "whitespace_only", "non_string"],
    )
    def test_malformed_command_is_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_input
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input=tool_input,
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]


class TestAutoRootTaskToolLockdown:
    @pytest.mark.parametrize("tool_name", ["TaskCreate", "TaskUpdate"])
    def test_task_create_update_blocked_for_auto_root(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_name
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(tool_name=tool_name, tool_input={}, transcript_path=transcript_path),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert tool_name in payload["reason"]


class TestAutoRootIdentityBoundary:
    @pytest.mark.parametrize(
        "identity", [{"agent_id": "sub-1"}, {"agent_type": "nw-crafter"}]
    )
    def test_either_subagent_identity_field_bypasses_the_lockdown(
        self, monkeypatch, capsys, audit_events, tmp_path, identity
    ) -> None:
        """A dispatched sub-agent (either identity field present) is never
        treated as Auto-root, even if its own transcript observed nw-auto."""
        transcript_path = _transcript(tmp_path, auto=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="TaskCreate",
                tool_input={},
                transcript_path=transcript_path,
                **identity,
            ),
        )
        # A sub-agent hits no TaskCreate handling at all -- it falls through
        # to the normal (unaffected) path, never the auto-root block.
        assert (
            payload is None
            or payload.get("decision") != "block"
            or ("TaskCreate" not in payload.get("reason", ""))
        )

    def test_absent_nw_auto_observation_preserves_existing_bash_behaviour(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """No `Skill(nw-auto)` observed -- not armed -- an ordinary
        allowlisted-looking `git status` runs the existing path unchanged
        (still subject to the pre-existing mode-select gate, not the
        auto-root allowlist)."""
        transcript_path = _transcript(tmp_path, auto=False, mode_select=False)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "nw-mode-select" in payload["reason"]
        assert "Auto-root" not in payload["reason"]

    def test_forged_nw_auto_mention_in_prose_does_not_arm(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """A transcript that merely MENTIONS nw-auto in prose (never a real
        `Skill` tool_use) does not arm the Auto-root lockdown."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps(
                {"type": "text", "text": "I will act as if nw-auto were engaged."}
            )
            + "\n",
            encoding="utf-8",
        )
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                transcript_path=str(transcript),
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "nw-mode-select" in payload["reason"]


class TestAutoRootAllowedGitCommitReachesAttribution:
    def test_pure_git_commit_still_reaches_attribution_mutation_path(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """An allowlisted `git commit` from Auto-root is not vetoed by the
        lockdown, and the pre-existing commit-attribution mutation branch
        still runs on it unchanged."""

        class _MutatingService:
            def plan_rewrite(self, command: str) -> object:
                class Plan:
                    action = "mutate"
                    rewritten_command = command + " -C HEAD"

                return Plan()

        monkeypatch.setattr(
            pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
        )
        global_config_dir = tmp_path / ".nwave"
        global_config_dir.mkdir()
        (global_config_dir / "global-config.json").write_text(
            json.dumps({"attribution": {"enabled": True}}), encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": 'git commit -m "x"'},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        assert exit_code == 0
        assert payload is not None
        assert "hookSpecificOutput" in payload
        assert payload["hookSpecificOutput"]["updatedInput"]["command"] == (
            'git commit -m "x" -C HEAD'
        )


class TestAutoRootLockdownScopedToLockedDownTools:
    """Unrelated tools with no transcript pay no root-mode read."""

    @pytest.mark.parametrize("tool_name", ["Read", "Skill", "Agent", "ScheduleWakeup"])
    def test_non_lockdown_tool_never_observes_and_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tool_name
    ) -> None:
        def _boom(*args, **kwargs):
            raise AssertionError(
                "resolve_root_mode_state must not be called for "
                f"non-lockdown tool {tool_name!r}"
            )

        monkeypatch.setattr(pre_tool_use_handler, "resolve_root_mode_state", _boom)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(tool_name=tool_name, tool_input={}),
        )
        assert (
            payload is None
            or payload.get("decision") != "block"
            or "Auto-root" not in payload.get("reason", "")
        )
