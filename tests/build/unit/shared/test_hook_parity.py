"""Tests for hook parity between plugin builder and installer paths.

Driving port: build_plugin.generate_hook_config() and DESPlugin._install_des_hooks()
via the shared hook_definitions.generate_hook_config().

Both distribution paths (plugin build and custom installer) must produce
structurally identical hook configurations. This test prevents the divergence
bug where one path had stale matchers or missing hooks.

Test Budget: 4 distinct behaviors x 2 = 8 max unit tests.
Behaviors:
  1. Both paths produce hooks for all 5 event types
  2. Both paths produce 5 PreToolUse entries with identical matchers
     (post slice-02 of atdd-spine-ledger-enforcement-gate-v2: Bash matcher
     hosts BOTH the execution-log guard AND the spine-ledger pre-commit
     hook; Claude Code permits multiple entries per (event, matcher))
  3. The (event, matcher, action) triples are identical between plugin and installer
  4. Write/Edit hooks use guard commands in both paths
"""

from __future__ import annotations

import pytest

from scripts.build_plugin import generate_hook_config as plugin_generate_hook_config
from scripts.shared.hook_definitions import (
    HOOK_EVENT_TYPES,
)
from scripts.shared.hook_definitions import (
    generate_hook_config as shared_generate_hook_config,
)


def _stub_command(action: str) -> str:
    """Stub command function for installer path (mimics DESPlugin._generate_hook_command)."""
    return f"PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter {action}"


def _stub_guard_command(action: str) -> str:
    """Stub guard command for installer path (mimics DESPlugin guard)."""
    from scripts.shared.hook_definitions import build_guard_command

    python_cmd = _stub_command(action)
    return build_guard_command(python_cmd)


def _extract_event_matcher_pairs(config: dict) -> set[tuple[str, str | None]]:
    """Extract the set of (event, matcher) pairs from a hook config."""
    pairs: set[tuple[str, str | None]] = set()
    for event, entries in config.items():
        for entry in entries:
            matcher = entry.get("matcher")
            pairs.add((event, matcher))
    return pairs


class TestHookParityPluginVsInstaller:
    """Verify plugin builder and installer produce equivalent hook coverage.

    The original bug: build_plugin.py and des_plugin.py had independent hook
    definitions. One had stale 'Task' matcher, the other was missing Write/Edit
    guards. Now both use shared hook_definitions -- these tests prevent
    regression if either path diverges from the shared definitions.
    """

    @pytest.fixture
    def plugin_config(self) -> dict:
        """Hook config from plugin builder path."""
        return plugin_generate_hook_config()

    @pytest.fixture
    def installer_config(self) -> dict:
        """Hook config from installer path (using shared generate_hook_config)."""
        return shared_generate_hook_config(
            _stub_command, guard_command_fn=_stub_guard_command
        )

    def test_both_paths_cover_all_five_event_types(
        self, plugin_config: dict, installer_config: dict
    ):
        """Both distribution paths produce hooks for all 5 event types."""
        assert set(plugin_config.keys()) == HOOK_EVENT_TYPES
        assert set(installer_config.keys()) == HOOK_EVENT_TYPES

    def test_both_paths_produce_six_pretooluse_entries(
        self, plugin_config: dict, installer_config: dict
    ):
        """Both paths produce 8 PreToolUse entries: Agent, Write, Edit, Bash x 5.

        slice-02 of atdd-spine-ledger-enforcement-gate-v2 added a NEW Bash
        entry (spine-ledger PreToolUse hook, dev-mode form) adjacent to the
        execution-log guard. slice-04 added a SECOND spine-ledger Bash entry
        (gate-installed form, calling the gate script directly). slice-01 of
        fix-crafter-stash-structural-mitigation added a FOURTH Bash entry
        (git-stash guard). 817a7b21e wired a FIFTH Bash entry (the --no-verify
        reminder guard, ``pre-bash-no-verify-reminder``). Claude Code's
        PreToolUse protocol permits multiple registrations per (event, matcher)
        tuple; execution is registration-ordered; "any block wins" semantic. All
        five Bash entries appear in registration order: execution-log guard,
        spine-ledger dev-mode, spine-ledger gate-installed, git-stash guard,
        no-verify reminder.
        """
        plugin_matchers = [e.get("matcher") for e in plugin_config["PreToolUse"]]
        installer_matchers = [e.get("matcher") for e in installer_config["PreToolUse"]]
        expected = [
            "Agent",
            "Write",
            "Edit",
            "Bash",
            "Bash",
            "Bash",
            "Bash",
            "Bash",
        ]
        assert plugin_matchers == expected
        assert installer_matchers == expected

    def test_event_matcher_pairs_identical_between_paths(
        self, plugin_config: dict, installer_config: dict
    ):
        """The set of (event, matcher) pairs must be identical."""
        plugin_pairs = _extract_event_matcher_pairs(plugin_config)
        installer_pairs = _extract_event_matcher_pairs(installer_config)
        assert plugin_pairs == installer_pairs, (
            f"Hook parity violation! "
            f"Plugin-only: {plugin_pairs - installer_pairs}, "
            f"Installer-only: {installer_pairs - plugin_pairs}"
        )

    def test_write_and_edit_hooks_have_guard_commands_in_both_paths(
        self, plugin_config: dict, installer_config: dict
    ):
        """Write and Edit hooks contain fast-path guard (deliver-session.json check)."""
        for config, path_name in [
            (plugin_config, "plugin"),
            (installer_config, "installer"),
        ]:
            for matcher in ("Write", "Edit"):
                entry = next(
                    e for e in config["PreToolUse"] if e.get("matcher") == matcher
                )
                command = entry["hooks"][0]["command"]
                assert "deliver-session.json" in command, (
                    f"{path_name} path: {matcher} hook missing guard command "
                    f"(no deliver-session.json check)"
                )

    def test_no_task_matcher_in_either_path(
        self, plugin_config: dict, installer_config: dict
    ):
        """Neither path uses legacy 'Task' matcher (Claude Code v2.1.63+ uses 'Agent')."""
        for config, path_name in [
            (plugin_config, "plugin"),
            (installer_config, "installer"),
        ]:
            for event, entries in config.items():
                for entry in entries:
                    assert entry.get("matcher") != "Task", (
                        f"{path_name} path has stale 'Task' matcher in {event}"
                    )
