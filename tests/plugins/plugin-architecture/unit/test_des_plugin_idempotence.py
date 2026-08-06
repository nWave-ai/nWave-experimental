"""Unit tests for DES hook installation idempotence.

Verifies that running _install_des_hooks() twice produces identical
settings.json content -- no duplicate hooks, no missing hooks.

Bug: Running `nwave-ai install` twice caused DES hooks to be duplicated
in ~/.claude/settings.json.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.shared import hook_definitions as shared_hooks


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.des_plugin_idempotence")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def plugin() -> DESPlugin:
    """Provide a fresh DESPlugin instance."""
    return DESPlugin()


@pytest.fixture
def install_context(tmp_path: Path, test_logger: logging.Logger) -> InstallContext:
    """Create InstallContext with a temporary claude_dir."""
    project_root = Path(__file__).resolve().parents[4]
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )


def _count_all_hook_entries(settings: dict) -> int:
    """Count total hook entries across all event types."""
    total = 0
    for entries in settings.get("hooks", {}).values():
        if isinstance(entries, list):
            total += len(entries)
    return total


def _count_des_hook_entries(settings: dict) -> int:
    """Count DES-specific hook entries across all event types."""
    total = 0
    for entries in settings.get("hooks", {}).values():
        if isinstance(entries, list):
            total += sum(1 for e in entries if shared_hooks.is_des_hook_entry(e))
    return total


class TestDESHookIdempotence:
    """Installing DES hooks twice must produce identical settings.json."""

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_second_install_produces_same_hook_count(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Hook count after second install must equal hook count after first install."""
        # First install
        result1 = plugin._install_des_hooks(install_context)
        assert result1.success, f"First install failed: {result1.message}"

        settings_file = install_context.claude_dir / "settings.json"
        settings_after_first = json.loads(settings_file.read_text())
        count_after_first = _count_all_hook_entries(settings_after_first)

        # Second install
        result2 = plugin._install_des_hooks(install_context)
        assert result2.success, f"Second install failed: {result2.message}"

        settings_after_second = json.loads(settings_file.read_text())
        count_after_second = _count_all_hook_entries(settings_after_second)

        assert count_after_second == count_after_first, (
            f"Hook count changed: {count_after_first} -> {count_after_second}. "
            f"Duplicate hooks detected."
        )

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_install_replaces_legacy_flat_format_hooks(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Legacy flat-format hooks from earliest versions must be cleaned up on reinstall."""
        settings_file = install_context.claude_dir / "settings.json"

        # Pre-seed with legacy flat-format hooks (earliest DES plugin version)
        legacy_hooks = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Task",
                        "command": "python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py pre-task",
                    },
                ],
                "SubagentStop": [
                    {
                        "command": "python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py subagent-stop",
                    },
                ],
            }
        }
        settings_file.write_text(json.dumps(legacy_hooks, indent=2))

        # Install with current version
        result = plugin._install_des_hooks(install_context)
        assert result.success, f"Install failed: {result.message}"

        settings = json.loads(settings_file.read_text())

        # No legacy flat-format hooks should remain
        for event, entries in settings["hooks"].items():
            for entry in entries:
                assert "command" not in entry or not entry.get("command"), (
                    f"Legacy flat-format hook found in {event}: {entry}"
                )

        # DES hook count must match expected (no duplicates from legacy + new)
        des_count = _count_des_hook_entries(settings)
        expected_count = len(shared_hooks.HOOK_EVENTS)
        assert des_count == expected_count, (
            f"Expected {expected_count} DES hooks, found {des_count}. "
            f"Legacy hooks were not fully replaced."
        )

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_upgrade_removes_retired_spine_ledger_hooks_when_current_hooks_match(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Upgrade removes exact DES legacy payloads without claiming user hooks."""
        result = plugin._install_des_hooks(install_context)
        assert result.success, result.message

        settings_file = install_context.claude_dir / "settings.json"
        settings = json.loads(settings_file.read_text())
        lyra_entry = {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "# lyra-hook:protocol-observer\n"
                        "echo spine_ledger_gate "
                        "spine_ledger_pre_commit_hook "
                        "spine_ledger_subagent_stop_detector "
                        "pre-bash-spine-ledger subagent-stop-spine-detector"
                    ),
                }
            ],
        }
        settings["hooks"]["PreToolUse"].append(lyra_entry)
        settings["hooks"]["PreToolUse"].append(
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": plugin._RETIRED_HOOK_COMMANDS[0],
                    }
                ],
            }
        )
        settings_file.write_text(json.dumps(settings, indent=2))

        result = plugin._install_des_hooks(install_context)
        assert result.success, result.message
        reconciled = json.loads(settings_file.read_text())
        commands = [
            hook["command"]
            for entry in reconciled["hooks"]["PreToolUse"]
            for hook in entry.get("hooks", [])
        ]
        assert lyra_entry["hooks"][0]["command"] in commands
        assert plugin._RETIRED_HOOK_COMMANDS[0] not in commands

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_install_over_mixed_format_hooks_produces_no_duplicates(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Settings with mix of old flat + new nested DES hooks must converge to clean state."""
        settings_file = install_context.claude_dir / "settings.json"

        # Pre-seed with mixed formats: one flat (old), one nested (current)
        mixed_hooks = {
            "hooks": {
                "PreToolUse": [
                    # Old flat format
                    {
                        "matcher": "Agent",
                        "command": "PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task",
                    },
                    # Current nested format
                    {
                        "matcher": "Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'INPUT=$(cat); test -f .nwave/des/deliver-session.json || exit 0; echo "$INPUT" | PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-write',
                            }
                        ],
                    },
                ],
            }
        }
        settings_file.write_text(json.dumps(mixed_hooks, indent=2))

        # Install should clean up both formats and install fresh
        result = plugin._install_des_hooks(install_context)
        assert result.success, f"Install failed: {result.message}"

        settings = json.loads(settings_file.read_text())
        des_count = _count_des_hook_entries(settings)
        expected_count = len(shared_hooks.HOOK_EVENTS)
        assert des_count == expected_count, (
            f"Expected {expected_count} DES hooks, found {des_count}. "
            f"Mixed-format cleanup failed."
        )

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_second_install_preserves_non_des_hooks(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Non-DES hooks must survive a second DES install unchanged."""
        settings_file = install_context.claude_dir / "settings.json"

        # Pre-seed a non-DES hook
        non_des_hook = {
            "matcher": "SomeOtherTool",
            "hooks": [{"type": "command", "command": "echo non-des-hook"}],
        }
        settings_file.write_text(
            json.dumps({"hooks": {"PreToolUse": [non_des_hook]}}, indent=2)
        )

        # First install
        plugin._install_des_hooks(install_context)

        # Second install
        plugin._install_des_hooks(install_context)

        settings = json.loads(settings_file.read_text())
        pre_tool_use = settings["hooks"]["PreToolUse"]

        # The non-DES hook must still be there exactly once
        non_des_entries = [
            e for e in pre_tool_use if not shared_hooks.is_des_hook_entry(e)
        ]
        assert len(non_des_entries) == 1, (
            f"Expected 1 non-DES hook, found {len(non_des_entries)}"
        )
        assert non_des_entries[0]["matcher"] == "SomeOtherTool"

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_install_registers_user_prompt_submit_preserving_persona_entry(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """UserPromptSubmit registration is installed; pre-existing user entries survive.

        Regression AT for the wave-active anchor dormant-registration seam
        (slice-04 amendment of nwave-flow-v2-enforcement, post-install smoke
        finding #2): the handler module shipped but the installer never
        registered a UserPromptSubmit hook, so the anchor never fired. The
        merge must be ADDITIVE -- a user's own UserPromptSubmit entry (e.g.
        a persona loader) is preserved alongside the new DES entry.
        """
        settings_file = install_context.claude_dir / "settings.json"

        # Pre-seed a non-DES UserPromptSubmit entry (persona-loader shape)
        persona_entry = {
            "hooks": [
                {
                    "type": "command",
                    "command": "python3 $HOME/.claude/hooks/load_persona.py",
                }
            ]
        }
        settings_file.write_text(
            json.dumps({"hooks": {"UserPromptSubmit": [persona_entry]}}, indent=2)
        )

        result = plugin._install_des_hooks(install_context)
        assert result.success, f"Install failed: {result.message}"

        settings = json.loads(settings_file.read_text())
        entries = settings["hooks"]["UserPromptSubmit"]

        # Persona entry preserved exactly once
        non_des = [e for e in entries if not shared_hooks.is_des_hook_entry(e)]
        assert len(non_des) == 1, f"Expected 1 preserved user entry, got {non_des}"
        assert "load_persona.py" in non_des[0]["hooks"][0]["command"]

        # UserPromptSubmit is user-owned.  The installer must not recreate a
        # retired DES writer alongside the persona entry.
        des = [e for e in entries if shared_hooks.is_des_hook_entry(e)]
        assert not des

        # Idempotence: second install does not duplicate any entry
        plugin._install_des_hooks(install_context)
        settings = json.loads(settings_file.read_text())
        entries = settings["hooks"]["UserPromptSubmit"]
        assert entries == [persona_entry]

    @patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
    def test_install_after_python_path_change_replaces_hooks(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """When Python path changes between installs, old hooks must be replaced, not added."""
        settings_file = install_context.claude_dir / "settings.json"

        # First install with python3
        plugin._install_des_hooks(install_context)
        count_after_first = _count_all_hook_entries(
            json.loads(settings_file.read_text())
        )

        # Second install with different Python path
        _mock_python.return_value = "$HOME/.local/pipx/venvs/nwave-ai/bin/python3.12"
        plugin._install_des_hooks(install_context)
        count_after_second = _count_all_hook_entries(
            json.loads(settings_file.read_text())
        )

        assert count_after_second == count_after_first, (
            f"Hook count changed after Python path change: "
            f"{count_after_first} -> {count_after_second}. "
            f"Old hooks were not replaced."
        )


class TestIsDESHookEntryDetection:
    """is_des_hook_entry must detect all DES hook formats."""

    @pytest.mark.parametrize(
        "hook_entry,expected",
        [
            # New nested format with claude_code_hook_adapter
            (
                {
                    "matcher": "Agent",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task",
                        }
                    ],
                },
                True,
            ),
            # Old flat format
            (
                {
                    "command": "python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task",
                },
                True,
            ),
            # Shell-based hook with des-hook: marker
            (
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "# des-hook:pre-bash\nINPUT=$(cat); echo done",
                        }
                    ],
                },
                True,
            ),
            # Guard command containing claude_code_hook_adapter
            (
                {
                    "matcher": "Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'INPUT=$(cat); test -f .nwave/des/deliver-session.json || exit 0; echo "$INPUT" | PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-write',
                        }
                    ],
                },
                True,
            ),
            # Earliest flat format with .py extension and src/ prefix
            (
                {
                    "matcher": "Task",
                    "command": "python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py pre-task",
                },
                True,
            ),
            # Hook with PYTHONPATH pointing to lib/python/des (variant path)
            (
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=/home/user/.claude/lib/python /home/user/.local/bin/python3.12 -m des.adapters.drivers.hooks.claude_code_hook_adapter session-start",
                        }
                    ],
                },
                True,
            ),
            # Non-DES hook -- must NOT match
            (
                {
                    "matcher": "SomeTool",
                    "hooks": [{"type": "command", "command": "echo hello"}],
                },
                False,
            ),
            # Empty hook entry -- must NOT match
            ({}, False),
        ],
        ids=[
            "nested-adapter",
            "flat-adapter",
            "shell-des-hook-marker",
            "guard-with-adapter",
            "earliest-flat-with-py-ext",
            "absolute-path-variant",
            "non-des-hook",
            "empty-entry",
        ],
    )
    def test_detects_des_hook_entry(self, hook_entry: dict, expected: bool):
        """is_des_hook_entry must correctly classify hook entries."""
        assert shared_hooks.is_des_hook_entry(hook_entry) is expected
