"""Regression: a non-Claude target must not gain a Claude discovery surface.

`DESPlugin.install()` had an early-return for the host-neutral DES runtime
that required BOTH "codex" in the requested platforms AND "claude_code" NOT
in them. A Copilot-only or OpenCode-only target satisfies neither half of
that AND, falls through the guard, and gets the full Claude-scoped install
(data/templates/hooks/shims/config all written under context.claude_dir) --
a pure non-Claude target creating a Claude discovery surface it never asked
for (fix-non-claude-target-still-creates-claude-surface).

The fix widens the guard to key on the one property that actually matters:
"claude_code" not requested at all, regardless of which other platform(s)
are.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.des_plugin import DESPlugin


def _make_context(target_platforms: set[str], claude_dir: Path) -> InstallContext:
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=Path("/unused"),
        templates_dir=Path("/unused"),
        logger=logging.getLogger("test"),
        target_platforms=target_platforms,
    )


def _module_only_success() -> PluginResult:
    return PluginResult(success=True, plugin_name="des", message="module installed")


class TestNonClaudeTargetSkipsClaudeScopedSteps:
    """Any target lacking "claude_code" must short-circuit before the
    Claude-scoped steps (data/templates/hooks/shims/config), regardless of
    whether "codex" happens to also be in the target set.
    """

    def test_copilot_only_never_calls_claude_scoped_installers(self, tmp_path: Path):
        """
        GIVEN: target_platforms={"copilot"} (no "codex", no "claude_code")
        WHEN: install() runs
        THEN: succeeds with the host-neutral message, and none of the
              Claude-scoped installer steps are ever invoked
        """
        plugin = DESPlugin()
        context = _make_context({"copilot"}, tmp_path / ".claude")

        with (
            patch.object(
                plugin,
                "validate_prerequisites",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch.object(
                plugin, "_install_des_module", return_value=_module_only_success()
            ),
            patch.object(plugin, "_install_des_data") as mock_data,
            patch.object(plugin, "_install_des_hooks") as mock_hooks,
            patch.object(plugin, "_install_des_shims") as mock_shims,
            patch.object(plugin, "_install_des_templates") as mock_templates,
            patch.object(plugin, "_install_des_scripts") as mock_scripts,
            patch.object(plugin, "_install_des_hook_scripts") as mock_hook_scripts,
            patch.object(plugin, "_bootstrap_des_config") as mock_config,
        ):
            result = plugin.install(context)

        assert result.success is True
        assert "host-neutral" in result.message
        mock_data.assert_not_called()
        mock_hooks.assert_not_called()
        mock_shims.assert_not_called()
        mock_templates.assert_not_called()
        mock_scripts.assert_not_called()
        mock_hook_scripts.assert_not_called()
        mock_config.assert_not_called()

    def test_opencode_only_never_calls_claude_scoped_installers(self, tmp_path: Path):
        """Same guard, OpenCode-only target -- the other non-Claude host."""
        plugin = DESPlugin()
        context = _make_context({"opencode"}, tmp_path / ".claude")

        with (
            patch.object(
                plugin,
                "validate_prerequisites",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch.object(
                plugin, "_install_des_module", return_value=_module_only_success()
            ),
            patch.object(plugin, "_install_des_data") as mock_data,
        ):
            result = plugin.install(context)

        assert result.success is True
        mock_data.assert_not_called()

    def test_codex_only_still_uses_the_guard(self, tmp_path: Path):
        """
        GIVEN: target_platforms={"codex"} (the case the original guard
               already handled)
        WHEN: install() runs
        THEN: still succeeds with the host-neutral message -- the widened
              condition must not regress the case it already covered
        """
        plugin = DESPlugin()
        context = _make_context({"codex"}, tmp_path / ".claude")

        with (
            patch.object(
                plugin,
                "validate_prerequisites",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch.object(
                plugin, "_install_des_module", return_value=_module_only_success()
            ),
            patch.object(plugin, "_install_des_data") as mock_data,
        ):
            result = plugin.install(context)

        assert result.success is True
        mock_data.assert_not_called()

    def test_claude_code_target_still_runs_claude_scoped_steps(self, tmp_path: Path):
        """
        GIVEN: target_platforms={"claude_code"} (the default, real-user case)
        WHEN: install() runs
        THEN: the Claude-scoped steps DO run -- the widened guard must not
              accidentally skip them when Claude actually is requested
        """
        plugin = DESPlugin()
        context = _make_context({"claude_code"}, tmp_path / ".claude")

        with (
            patch.object(
                plugin,
                "validate_prerequisites",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch.object(
                plugin, "_install_des_module", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_install_des_scripts", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_install_des_hook_scripts", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_install_des_data", return_value=_module_only_success()
            ) as mock_data,
            patch.object(
                plugin, "_install_des_templates", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_install_des_hooks", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_install_des_shims", return_value=_module_only_success()
            ),
            patch.object(
                plugin, "_bootstrap_des_config", return_value=_module_only_success()
            ),
        ):
            result = plugin.install(context)

        assert result.success is True
        mock_data.assert_called_once()
