"""Tests for plugin build hook correctness.

Driving port: build_plugin.generate_hook_config() and build_plugin.build()
Tests verify the plugin build output has correct hooks for current
Claude Code version (v2.1.63+: Agent matcher, Write/Edit guards).

These tests would have caught the original bug where:
- PreToolUse used stale "Task" matcher instead of "Agent"
- Write and Edit guard hooks were missing entirely

Test Budget: 3 distinct behaviors x 2 = 6 max unit tests.
Behaviors:
  1. Plugin hooks cover all required event types with correct matchers.
  2. Plugin hooks use "Agent" matcher, never "Task"
  3. Plugin Write/Edit hooks have guard commands
"""

from __future__ import annotations

import pytest

from scripts.build_plugin import generate_hook_config
from scripts.shared.hook_definitions import HOOK_EVENT_TYPES, HOOK_EVENTS


_EXPECTED_PRETOOLUSE_MATCHERS = [
    h.matcher for h in HOOK_EVENTS if h.event == "PreToolUse"
]


class TestPluginHookCorrectness:
    """Verify plugin build produces correct hooks for Claude Code v2.1.63+."""

    @pytest.fixture
    def hook_config(self) -> dict:
        """Generate plugin hook config using default plugin paths."""
        return generate_hook_config()

    def test_all_five_event_types_present(self, hook_config: dict):
        """Plugin hooks cover all 5 event types."""
        assert set(hook_config.keys()) == HOOK_EVENT_TYPES

    def test_pretooluse_has_agent_write_edit_bash_matchers(self, hook_config: dict):
        """PreToolUse matches the HOOK_EVENTS-declared sequence (not Task)."""
        pre_tool_use = hook_config["PreToolUse"]
        assert len(pre_tool_use) == len(_EXPECTED_PRETOOLUSE_MATCHERS)
        matchers = [e.get("matcher") for e in pre_tool_use]
        assert matchers == _EXPECTED_PRETOOLUSE_MATCHERS

    @pytest.mark.parametrize("matcher", ["Write", "Edit"])
    def test_guard_hooks_contain_session_check(self, hook_config: dict, matcher: str):
        """Write and Edit hooks contain deliver-session.json fast-path guard."""
        entry = next(
            e for e in hook_config["PreToolUse"] if e.get("matcher") == matcher
        )
        command = entry["hooks"][0]["command"]
        assert "deliver-session.json" in command, (
            f"{matcher} hook missing guard command"
        )

    def test_no_task_matcher_anywhere(self, hook_config: dict):
        """No hook uses legacy 'Task' matcher."""
        all_matchers = [
            entry.get("matcher")
            for entries in hook_config.values()
            for entry in entries
        ]
        assert "Task" not in all_matchers, "Found stale 'Task' matcher in plugin hooks"
