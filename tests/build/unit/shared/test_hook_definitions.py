"""Tests for the shared hook definitions module.

Driving port: hook_definitions module (pure functions).
Tests verify the canonical hook definitions produce correct configs
for both distribution paths (plugin and installer).

Test Budget: 8 distinct behaviors x 2 = 16 max unit tests.
Behaviors:
  1. Hook events define the fixed independent registrations.
  2. Hook event types cover all 6 distinct event types
  3. generate_hook_config produces correct structure for standard hooks
  4. generate_hook_config uses guard_command_fn for guard hooks
  5. generate_hook_config uses shell_command verbatim for Bash hooks
  6. build_guard_command produces shell fast-path with correct structure
  7. is_des_hook_entry detects DES hooks in all formats (Python + shell)
"""

from __future__ import annotations

import pytest

from scripts.shared.hook_definitions import (
    HOOK_EVENT_TYPES,
    HOOK_EVENTS,
    build_guard_command,
    generate_hook_config,
    is_des_hook_entry,
)


class TestHookEventDefinitions:
    """Verify the canonical hook event definitions are complete and correct."""

    def test_defines_independent_hook_registrations(self):
        """The shared definition contains only the current independent hooks."""
        assert len(HOOK_EVENTS) == 9

        # Verify exact event/matcher/action triples
        events_matchers = [(h.event, h.matcher, h.action) for h in HOOK_EVENTS]
        assert ("PreToolUse", "Agent", "pre-task") in events_matchers
        # K4 overhead slice: SendMessage routes to the existing portable
        # pre-tool-use action -- exactly one registration, no new action.
        assert ("PreToolUse", "SendMessage", "pre-tool-use") in events_matchers
        send_message_entries = [
            (h.event, h.matcher, h.action)
            for h in HOOK_EVENTS
            if h.event == "PreToolUse" and h.matcher == "SendMessage"
        ]
        assert send_message_entries == [("PreToolUse", "SendMessage", "pre-tool-use")]
        # K4 task-boundary slice: TaskCreate/TaskUpdate combine into a single
        # matcher routed to the existing portable pre-tool-use action --
        # exactly one registration, no new action.
        task_boundary_triple = ("PreToolUse", "TaskCreate|TaskUpdate", "pre-tool-use")
        assert events_matchers.count(task_boundary_triple) == 1
        assert ("PreToolUse", "Write", "pre-write") in events_matchers
        assert ("PreToolUse", "Edit", "pre-edit") in events_matchers
        assert ("PreToolUse", "Bash", "pre-bash") not in events_matchers
        # fix-execution-log-bash-guard-consolidation follow-on: the
        # standalone git-stash / worktree-removal Bash registrations are
        # retired -- the universal `pre-tool-use` action now evaluates both
        # decisions inline.
        assert ("PreToolUse", "Bash", "pre-bash-git-stash-guard") not in events_matchers
        assert (
            "PreToolUse",
            "Bash",
            "pre-bash-worktree-removal-guard",
        ) not in events_matchers
        assert ("PreToolUse", "Bash", "pre-tool-use") in events_matchers
        bash_entries = [
            (h.event, h.matcher, h.action)
            for h in HOOK_EVENTS
            if h.event == "PreToolUse" and h.matcher == "Bash"
        ]
        assert bash_entries == [("PreToolUse", "Bash", "pre-tool-use")]
        assert ("PostToolUse", "Agent", "post-tool-use") in events_matchers
        assert ("SubagentStop", None, "subagent-stop") in events_matchers
        assert ("SubagentStop", None, "deliver-progress") not in events_matchers
        assert ("SessionStart", "startup", "session-start") not in events_matchers
        assert ("SubagentStart", None, "subagent-start") in events_matchers
        assert ("UserPromptSubmit", None, "user-prompt-submit") not in events_matchers
        assert not any(event == "SessionStart" for event, _, _ in events_matchers)

    def test_hook_event_types_excludes_retired_session_and_prompt_hooks(self):
        """Only active hook events are registered by the installer."""
        assert (
            frozenset(
                {
                    "PreToolUse",
                    "PostToolUse",
                    "SubagentStop",
                    "SubagentStart",
                }
            )
            == HOOK_EVENT_TYPES
        )

    def test_write_and_edit_hooks_are_guards(self):
        """Write and Edit hooks are guards; Bash is NOT (it uses shell_command)."""
        guards = [h for h in HOOK_EVENTS if h.is_guard]
        assert len(guards) == 2
        guard_matchers = {h.matcher for h in guards}
        assert guard_matchers == {"Write", "Edit"}

    def test_agent_matcher_not_task(self):
        """PreToolUse uses 'Agent' matcher, not legacy 'Task' (Claude Code v2.1.63+)."""
        pre_tool_agent = [
            h for h in HOOK_EVENTS if h.event == "PreToolUse" and h.matcher == "Agent"
        ]
        assert len(pre_tool_agent) == 1
        # Verify no 'Task' matcher anywhere
        task_matchers = [h for h in HOOK_EVENTS if h.matcher == "Task"]
        assert len(task_matchers) == 0


class TestGenerateHookConfig:
    """Verify hook config generation produces valid Claude Code hooks.json structure."""

    @staticmethod
    def _simple_command(action: str) -> str:
        return f"python3 -m des.hook {action}"

    def test_produces_entries_for_all_five_event_types(self):
        """Config has entries for all 5 event types."""
        config = generate_hook_config(self._simple_command)
        assert set(config.keys()) == HOOK_EVENT_TYPES

    def test_pretooluse_has_independent_entries(self):
        """PreToolUse has Agent, SendMessage, the combined TaskCreate/
        TaskUpdate matcher, Write, Edit and one universal Bash hook. The
        combined TaskCreate|TaskUpdate matcher routes to the same portable
        `pre-tool-use` command used elsewhere -- no new action."""
        config = generate_hook_config(self._simple_command)
        pre_tool_use = config["PreToolUse"]
        assert len(pre_tool_use) == 6
        matchers = [e.get("matcher") for e in pre_tool_use]
        assert matchers == [
            "Agent",
            "SendMessage",
            "TaskCreate|TaskUpdate",
            "Write",
            "Edit",
            "Bash",
        ]
        entry = next(
            e for e in pre_tool_use if e.get("matcher") == "TaskCreate|TaskUpdate"
        )
        assert entry["hooks"][0]["command"] == "python3 -m des.hook pre-tool-use"

    def test_neutral_bash_reaches_portable_pre_tool_use_handler(self):
        """Installed config binds Bash to the shipped module handler.

        CONTRACT_SHAPE: bounded-change
        """
        config = generate_hook_config(self._simple_command)

        portable_root_gates = [
            entry
            for entry in config["PreToolUse"]
            if entry.get("matcher") == "Bash"
            and entry["hooks"][0]["command"] == "python3 -m des.hook pre-tool-use"
        ]

        assert len(portable_root_gates) == 1
        assert "scripts.hooks" not in portable_root_gates[0]["hooks"][0]["command"]

    def test_each_entry_has_hooks_array_with_command(self):
        """Every entry has a hooks array with type=command and non-empty command."""
        config = generate_hook_config(self._simple_command)
        for event, entries in config.items():
            for entry in entries:
                hooks_list = entry["hooks"]
                assert len(hooks_list) == 1
                hook = hooks_list[0]
                assert hook["type"] == "command"
                assert len(hook["command"]) > 0

    def test_uses_guard_command_fn_for_guard_hooks(self):
        """Guard hooks (Write/Edit) use guard_command_fn when provided."""
        guard_calls = []

        def guard_fn(action: str) -> str:
            guard_calls.append(action)
            return f"GUARD:{action}"

        config = generate_hook_config(self._simple_command, guard_command_fn=guard_fn)

        # Write and Edit should use guard_fn
        write_entry = next(
            e for e in config["PreToolUse"] if e.get("matcher") == "Write"
        )
        edit_entry = next(e for e in config["PreToolUse"] if e.get("matcher") == "Edit")

        assert write_entry["hooks"][0]["command"] == "GUARD:pre-write"
        assert edit_entry["hooks"][0]["command"] == "GUARD:pre-edit"

        # Agent should NOT use guard_fn
        agent_entry = next(
            e for e in config["PreToolUse"] if e.get("matcher") == "Agent"
        )
        assert agent_entry["hooks"][0]["command"] == "python3 -m des.hook pre-task"

    def test_bash_hook_is_sole_universal_pre_tool_use_and_ignores_guard_command_fn(
        self,
    ):
        """The sole generated Bash entry is the universal `pre-tool-use`
        command, never routed through `scripts.hooks`, and unaffected by
        `guard_command_fn` even when one is supplied."""

        def guard_fn(action: str) -> str:
            return f"GUARD:{action}"

        config = generate_hook_config(self._simple_command, guard_command_fn=guard_fn)
        bash_entries = [e for e in config["PreToolUse"] if e.get("matcher") == "Bash"]
        commands = [e["hooks"][0]["command"] for e in bash_entries]
        assert commands == ["python3 -m des.hook pre-tool-use"]
        assert "scripts.hooks" not in commands[0]

    def test_entries_without_matcher_omit_matcher_key(self):
        """Subagent lifecycle entries have no matcher key."""
        config = generate_hook_config(self._simple_command)
        for event in ("SubagentStop", "SubagentStart"):
            for entry in config[event]:
                assert "matcher" not in entry


class TestBuildGuardCommand:
    """Verify the shell fast-path guard command generation."""

    def test_guard_command_contains_fast_path_check(self):
        """Guard command checks for deliver-session.json before spawning Python."""
        cmd = build_guard_command("python3 -m des.hook pre-write")
        assert "deliver-session.json" in cmd
        assert "exit 0" in cmd

    def test_guard_command_checks_execution_log(self):
        """Guard command unconditionally invokes Python for execution-log.json targets."""
        cmd = build_guard_command("python3 -m des.hook pre-write")
        assert "execution-log" in cmd

    def test_guard_command_uses_activation_marker_existence_not_path_regex(self):
        """Root-write-boundary slice: the shell candidate-existence check
        replaces the old product-directory path regex. The shell tests only
        for `.nwave/local-config.json`'s EXISTENCE -- it must never parse
        the marker's JSON content (`enabled_for_repo`) or grep the
        `file_path` itself; that semantic interpretation is Python-only
        (`activation_gate.apply_gate`)."""
        cmd = build_guard_command("python3 -m des.hook pre-write")
        assert "test -f .nwave/local-config.json" in cmd
        assert "/src/" not in cmd
        assert "/nWave/" not in cmd
        assert "/tests/" not in cmd
        assert "/scripts/" not in cmd
        assert "file_path" not in cmd
        assert "enabled_for_repo" not in cmd

    def test_guard_command_buffers_stdin_without_the_dash_unsafe_echo_reemission(self):
        """Guard command captures stdin into INPUT once, then re-emits it to
        the downstream command.

        Was pinned to `'echo "$INPUT"' in cmd` -- i.e. to the literal
        re-emission mechanism that WAS the D1 defect
        (k3a-hook-payload-dash-safety): dash's builtin `echo` expands
        backslash escapes in its argument, so a real Edit's `old_string`/
        `new_string` (riddled with `\\n`) got corrupted before any handler
        saw it. That assertion could never fail no matter how badly `$INPUT`
        was re-emitted, as long as SOME `echo "$INPUT"` text existed in the
        template -- pinning the vulnerable string is how this class stayed
        invisible. Now asserts the property (INPUT captured once, still
        referenced downstream) plus a regression guard against
        REINTRODUCING the known-vulnerable form, rather than pinning one
        specific safe implementation forever. Byte-preservation itself is
        proven by execution under real `/bin/sh` in
        `tests/hooks/test_dash_shell_json_corruption_regression.py`
        (`TestBuildGuardCommandBytePreservation`), which this static check
        does not attempt to duplicate.
        """
        cmd = build_guard_command("python3 -m des.hook pre-write")
        assert "INPUT=$(cat)" in cmd
        assert '"$INPUT"' in cmd
        assert 'echo "$INPUT"' not in cmd, (
            'guard command re-introduced the dash-unsafe `echo "$INPUT"` '
            "re-emission -- see k3a-hook-payload-dash-safety D1"
        )


class TestIsDESHookEntry:
    """Verify DES hook detection in both old and new formats."""

    @pytest.mark.parametrize(
        "entry,expected",
        [
            # New nested format -- DES hook (Python)
            (
                {
                    "matcher": "Agent",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=... python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task",
                        }
                    ],
                },
                True,
            ),
            # Old flat format -- DES hook
            (
                {
                    "matcher": "Task",
                    "command": "python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task",
                },
                True,
            ),
            # Shell-based DES hook (Bash guard)
            (
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "# des-hook:pre-bash; INPUT=$(cat); ...",
                        }
                    ],
                },
                True,
            ),
            # Non-DES hook
            (
                {
                    "matcher": "Agent",
                    "hooks": [{"type": "command", "command": "some-other-hook"}],
                },
                False,
            ),
            # Empty entry
            ({}, False),
            # Issue97: bare mention of the module path, not an invocation --
            # must NOT be classified as a DES hook (would delete user command)
            (
                {
                    "matcher": "Bash",
                    "command": "echo des.adapters.drivers.hooks",
                },
                False,
            ),
            # Issue97: bare mention of the adapter name, not an invocation --
            # must NOT be classified as a DES hook (would delete user command)
            (
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "grep claude_code_hook_adapter .",
                        }
                    ],
                },
                False,
            ),
            # Legacy flat, path-style invocation (pre-`-m`), known action --
            # the exact historical shape WTBD-165 restores detection for.
            (
                {
                    "matcher": "Task",
                    "command": (
                        "python3 src/des/adapters/drivers/hooks/"
                        "claude_code_hook_adapter.py pre-task"
                    ),
                },
                True,
            ),
            # Same legacy shape via bare `python` (not `python3`).
            (
                {
                    "matcher": "SubagentStop",
                    "command": (
                        "python src/des/adapters/drivers/hooks/"
                        "claude_code_hook_adapter.py subagent-stop"
                    ),
                },
                True,
            ),
            # Legacy shape, nested format, another known action.
            (
                {
                    "matcher": "Agent",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "python3 src/des/adapters/drivers/hooks/"
                                "claude_code_hook_adapter.py post-tool-use"
                            ),
                        }
                    ],
                },
                True,
            ),
            # Near-miss: legacy script path but UNKNOWN action -- must not
            # match (not a positive structure the installer ever emitted).
            (
                {
                    "matcher": "Task",
                    "command": (
                        "python3 src/des/adapters/drivers/hooks/"
                        "claude_code_hook_adapter.py bogus-action"
                    ),
                },
                False,
            ),
            # Near-miss: legacy script path referenced mid-command (not
            # anchored at start) -- must not match a foreign wrapper.
            (
                {
                    "matcher": "Task",
                    "command": (
                        "echo running && python3 src/des/adapters/drivers/"
                        "hooks/claude_code_hook_adapter.py pre-task"
                    ),
                },
                False,
            ),
            # Near-miss: foreign echo mentioning the legacy script path and a
            # known action -- must not match (echo is not python invocation).
            (
                {
                    "matcher": "Task",
                    "command": (
                        "echo python3 src/des/adapters/drivers/hooks/"
                        "claude_code_hook_adapter.py pre-task"
                    ),
                },
                False,
            ),
            # Near-miss: foreign grep mentioning the legacy script path --
            # must not match.
            (
                {
                    "matcher": "Task",
                    "command": (
                        "grep -r 'claude_code_hook_adapter.py pre-task' "
                        "src/des/adapters/drivers/hooks/"
                    ),
                },
                False,
            ),
            # Near-miss: wrong script path (different module tree) with a
            # known action -- must not match.
            (
                {
                    "matcher": "Task",
                    "command": (
                        "python3 src/other/adapters/drivers/hooks/"
                        "claude_code_hook_adapter.py pre-task"
                    ),
                },
                False,
            ),
            # Near-miss: legacy path missing the `.py` suffix -- must not
            # match (not the exact historical structure).
            (
                {
                    "matcher": "Task",
                    "command": (
                        "python3 src/des/adapters/drivers/hooks/"
                        "claude_code_hook_adapter pre-task"
                    ),
                },
                False,
            ),
        ],
        ids=[
            "nested-des",
            "flat-des",
            "shell-des",
            "non-des",
            "empty",
            "issue97-module-path-substring-not-invocation",
            "issue97-adapter-name-substring-not-invocation",
            "legacy-flat-script-known-action-pre-task",
            "legacy-flat-script-bare-python-known-action",
            "legacy-flat-script-nested-known-action-post-tool-use",
            "legacy-flat-script-unknown-action-near-miss",
            "legacy-flat-script-not-anchored-at-start-near-miss",
            "legacy-flat-script-foreign-echo-near-miss",
            "legacy-flat-script-foreign-grep-near-miss",
            "legacy-flat-script-wrong-module-path-near-miss",
            "legacy-flat-script-missing-py-suffix-near-miss",
        ],
    )
    def test_detects_des_hooks(self, entry: dict, expected: bool):
        assert is_des_hook_entry(entry) == expected
