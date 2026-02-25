"""Unit tests for DES hook installer (DESPlugin-based)."""

import json
import logging
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures shared by test classes
# ---------------------------------------------------------------------------


@pytest.fixture
def _test_logger() -> logging.Logger:
    return logging.getLogger("test.des_hooks_unit")


@pytest.fixture
def _install_context(tmp_path: Path, _test_logger: logging.Logger):
    """InstallContext wired to a temp ~/.claude directory."""
    from scripts.install.plugins.base import InstallContext

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    project_root = Path(__file__).resolve().parents[4]
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=_test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )


# ---------------------------------------------------------------------------
# Step 03-03 — TestSessionStartHookRegistration
# Test budget: 4 distinct behaviors x 2 = 8 max unit tests (using 4)
# ---------------------------------------------------------------------------


class TestSessionStartHookRegistration:
    """SessionStart hook is registered in settings.json with matcher 'startup'."""

    def _install_hooks(self, context) -> dict:
        """Helper: run _install_des_hooks and return parsed settings.json."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        result = plugin._install_des_hooks(context)
        assert result.success, f"Hook install failed: {result.message}"
        settings_file = context.claude_dir / "settings.json"
        return json.loads(settings_file.read_text())

    def test_session_start_hook_registered_in_settings(self, _install_context):
        """After install, settings.json contains a SessionStart entry."""
        config = self._install_hooks(_install_context)

        assert "hooks" in config
        assert "SessionStart" in config["hooks"], (
            "SessionStart key missing from hooks after install"
        )
        assert len(config["hooks"]["SessionStart"]) >= 1

    def test_session_start_hook_uses_startup_matcher(self, _install_context):
        """SessionStart hook entry has matcher='startup'."""
        config = self._install_hooks(_install_context)

        session_hooks = config["hooks"]["SessionStart"]
        startup_entry = next(
            (h for h in session_hooks if h.get("matcher") == "startup"), None
        )
        assert startup_entry is not None, (
            "No SessionStart hook with matcher='startup' found"
        )

    def test_session_start_hook_command_uses_home_based_pythonpath(
        self, _install_context
    ):
        """SessionStart hook command uses $HOME-based PYTHONPATH (portable)."""
        config = self._install_hooks(_install_context)

        session_hooks = config["hooks"]["SessionStart"]
        startup_entry = next(h for h in session_hooks if h.get("matcher") == "startup")
        inner_hooks = startup_entry.get("hooks", [])
        assert len(inner_hooks) >= 1
        command = inner_hooks[0]["command"]
        assert "$HOME/.claude/lib/python" in command, (
            "Command must use $HOME-based PYTHONPATH for portability"
        )
        assert "session-start" in command, (
            "Command must pass 'session-start' action to hook adapter"
        )

    def test_session_start_install_is_idempotent(self, _install_context):
        """Re-running install does not duplicate SessionStart hook entries."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        plugin._install_des_hooks(_install_context)
        plugin._install_des_hooks(_install_context)

        settings_file = _install_context.claude_dir / "settings.json"
        config = json.loads(settings_file.read_text())

        session_hooks = config["hooks"]["SessionStart"]
        startup_entries = [h for h in session_hooks if h.get("matcher") == "startup"]
        assert len(startup_entries) == 1, (
            f"Expected 1 SessionStart/startup entry after idempotent install, "
            f"got {len(startup_entries)}"
        )

    def test_uninstall_removes_session_start_hook(self, _install_context):
        """Uninstall removes SessionStart hook while preserving other settings."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        plugin._install_des_hooks(_install_context)

        # Add a non-DES key to verify preservation
        settings_file = _install_context.claude_dir / "settings.json"
        config = json.loads(settings_file.read_text())
        config["someOtherKey"] = "preserved"
        settings_file.write_text(json.dumps(config, indent=2))

        plugin._uninstall_des_hooks(_install_context)

        config_after = json.loads(settings_file.read_text())
        # Other settings preserved
        assert config_after.get("someOtherKey") == "preserved"
        # SessionStart DES hooks removed
        session_hooks = config_after.get("hooks", {}).get("SessionStart", [])
        des_session_hooks = [
            h
            for h in session_hooks
            if any(
                "claude_code_hook_adapter" in sub.get("command", "")
                for sub in h.get("hooks", [])
            )
        ]
        assert len(des_session_hooks) == 0, (
            "DES SessionStart hook should be removed by uninstall"
        )

    def test_existing_hook_types_unaffected_by_session_start_addition(
        self, _install_context
    ):
        """PreToolUse, SubagentStop, PostToolUse hooks still registered correctly."""
        config = self._install_hooks(_install_context)

        hooks = config["hooks"]
        assert "PreToolUse" in hooks and len(hooks["PreToolUse"]) >= 1
        assert "SubagentStop" in hooks and len(hooks["SubagentStop"]) >= 1
        assert "PostToolUse" in hooks and len(hooks["PostToolUse"]) >= 1


# ---------------------------------------------------------------------------
# Step 04-01 — TestSubagentStartHookRegistration
# Test budget: 4 distinct behaviors x 2 = 8 max unit tests (using 5)
# ---------------------------------------------------------------------------


class TestSubagentStartHookRegistration:
    """SubagentStart hook is registered in settings.json with no matcher."""

    def _install_hooks(self, context) -> dict:
        """Helper: run _install_des_hooks and return parsed settings.json."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        result = plugin._install_des_hooks(context)
        assert result.success, f"Hook install failed: {result.message}"
        settings_file = context.claude_dir / "settings.json"
        return json.loads(settings_file.read_text())

    def test_subagent_start_hook_registered_in_settings(self, _install_context):
        """After install, settings.json contains a SubagentStart entry."""
        config = self._install_hooks(_install_context)

        assert "hooks" in config
        assert "SubagentStart" in config["hooks"], (
            "SubagentStart key missing from hooks after install"
        )
        assert len(config["hooks"]["SubagentStart"]) >= 1

    def test_subagent_start_hook_has_no_matcher(self, _install_context):
        """SubagentStart hook entry has no matcher — fires for all agent types."""
        config = self._install_hooks(_install_context)

        subagent_start_hooks = config["hooks"]["SubagentStart"]
        assert len(subagent_start_hooks) >= 1
        entry = subagent_start_hooks[0]
        assert "matcher" not in entry, (
            "SubagentStart hook must have no matcher (fires for all agents)"
        )

    def test_subagent_start_hook_command_uses_subagent_start_action(
        self, _install_context
    ):
        """SubagentStart hook command passes 'subagent-start' action to adapter."""
        config = self._install_hooks(_install_context)

        subagent_start_hooks = config["hooks"]["SubagentStart"]
        entry = subagent_start_hooks[0]
        inner_hooks = entry.get("hooks", [])
        assert len(inner_hooks) >= 1
        command = inner_hooks[0]["command"]
        assert "$HOME/.claude/lib/python" in command, (
            "Command must use $HOME-based PYTHONPATH for portability"
        )
        assert "subagent-start" in command, (
            "Command must pass 'subagent-start' action to hook adapter"
        )

    def test_subagent_start_install_is_idempotent(self, _install_context):
        """Re-running install does not duplicate SubagentStart hook entries."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        plugin._install_des_hooks(_install_context)
        plugin._install_des_hooks(_install_context)

        settings_file = _install_context.claude_dir / "settings.json"
        config = json.loads(settings_file.read_text())

        subagent_start_hooks = config["hooks"]["SubagentStart"]
        assert len(subagent_start_hooks) == 1, (
            f"Expected 1 SubagentStart entry after idempotent install, "
            f"got {len(subagent_start_hooks)}"
        )

    def test_uninstall_removes_subagent_start_hook(self, _install_context):
        """Uninstall removes SubagentStart hook while preserving other settings."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        plugin._install_des_hooks(_install_context)

        # Add a non-DES key to verify preservation
        settings_file = _install_context.claude_dir / "settings.json"
        config = json.loads(settings_file.read_text())
        config["someOtherKey"] = "preserved"
        settings_file.write_text(json.dumps(config, indent=2))

        plugin._uninstall_des_hooks(_install_context)

        config_after = json.loads(settings_file.read_text())
        # Other settings preserved
        assert config_after.get("someOtherKey") == "preserved"
        # SubagentStart DES hooks removed
        subagent_start_hooks = config_after.get("hooks", {}).get("SubagentStart", [])
        des_subagent_start_hooks = [
            h
            for h in subagent_start_hooks
            if any(
                "claude_code_hook_adapter" in sub.get("command", "")
                for sub in h.get("hooks", [])
            )
        ]
        assert len(des_subagent_start_hooks) == 0, (
            "DES SubagentStart hook should be removed by uninstall"
        )


# ---------------------------------------------------------------------------
# Step 03-04 — TestBootstrapUpdateCheckConfig
# Test budget: 3 distinct behaviors x 2 = 6 max unit tests (using 4)
# ---------------------------------------------------------------------------


class TestBootstrapUpdateCheckConfig:
    """_bootstrap_des_config includes update_check defaults in des-config.json."""

    def _run_bootstrap(self, context, project_root_override=None):
        """Helper: run _bootstrap_des_config and return parsed config dict."""
        from scripts.install.plugins.des_plugin import DESPlugin

        plugin = DESPlugin()
        if project_root_override is not None:
            context.project_root = project_root_override
        result = plugin._bootstrap_des_config(context)
        assert result.success, f"Bootstrap failed: {result.message}"
        config_file = (
            (context.project_root or Path.cwd()) / ".nwave" / "des-config.json"
        )
        return json.loads(config_file.read_text())

    def test_new_config_contains_update_check_frequency_daily(
        self, _install_context, tmp_path
    ):
        """Newly created des-config.json contains update_check.frequency='daily'."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        config = self._run_bootstrap(
            _install_context, project_root_override=project_root
        )

        assert "update_check" in config, "update_check key missing from new config"
        assert config["update_check"]["frequency"] == "daily"

    def test_new_config_contains_empty_skipped_versions(
        self, _install_context, tmp_path
    ):
        """Newly created des-config.json has skipped_versions as empty list."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        config = self._run_bootstrap(
            _install_context, project_root_override=project_root
        )

        assert config["update_check"]["skipped_versions"] == []

    def test_existing_config_missing_update_check_receives_key(
        self, _install_context, tmp_path
    ):
        """Existing des-config.json without update_check gets the key on next install."""
        from scripts.install.plugins.des_plugin import DESPlugin

        project_root = tmp_path / "project"
        project_root.mkdir()
        nwave_dir = project_root / ".nwave"
        nwave_dir.mkdir()
        config_file = nwave_dir / "des-config.json"
        existing = {"audit_logging_enabled": True, "audit_log_dir": ".nwave/des/logs"}
        config_file.write_text(json.dumps(existing, indent=2))

        plugin = DESPlugin()
        _install_context.project_root = project_root
        result = plugin._bootstrap_des_config(_install_context)
        assert result.success

        config = json.loads(config_file.read_text())
        assert "update_check" in config, (
            "update_check not added to existing config missing the key"
        )
        assert config["update_check"]["frequency"] == "daily"
        # Original keys preserved
        assert config["audit_logging_enabled"] is True

    def test_existing_config_with_update_check_not_overwritten(
        self, _install_context, tmp_path
    ):
        """Existing update_check key is not overwritten by reinstall."""
        from scripts.install.plugins.des_plugin import DESPlugin

        project_root = tmp_path / "project"
        project_root.mkdir()
        nwave_dir = project_root / ".nwave"
        nwave_dir.mkdir()
        config_file = nwave_dir / "des-config.json"
        existing = {
            "audit_logging_enabled": True,
            "update_check": {"frequency": "weekly", "skipped_versions": ["1.2.3"]},
        }
        config_file.write_text(json.dumps(existing, indent=2))

        plugin = DESPlugin()
        _install_context.project_root = project_root
        result = plugin._bootstrap_des_config(_install_context)
        assert result.success

        config = json.loads(config_file.read_text())
        assert config["update_check"]["frequency"] == "weekly", (
            "Existing update_check.frequency should not be overwritten"
        )
        assert config["update_check"]["skipped_versions"] == ["1.2.3"], (
            "Existing skipped_versions should not be overwritten"
        )
