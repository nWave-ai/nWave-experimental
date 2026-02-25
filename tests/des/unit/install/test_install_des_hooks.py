"""Unit tests for DES hook installer."""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest


class TestInstallDESHooks:
    """Test installer merges DES hooks into settings.json."""

    def test_install_merges_hooks_into_existing_config(self, tmp_path):
        """Install merges DES hooks into existing .claude/settings.json."""
        # Given: existing .claude/settings.json with non-DES hooks
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_file = claude_dir / "settings.json"

        existing_config = {
            "hooks": {
                "PreToolUse": [{"matcher": "OtherTool", "command": "other_command"}],
                "SubagentStop": [{"command": "other_stop_command"}],
            }
        }
        settings_file.write_text(json.dumps(existing_config, indent=2))

        # When: run installer
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: installer succeeds
        assert result.returncode == 0, f"Installer failed: {result.stderr}"

        # And: DES hooks are added
        config = json.loads(settings_file.read_text())
        assert "hooks" in config
        assert "PreToolUse" in config["hooks"]
        assert "SubagentStop" in config["hooks"]
        assert "PostToolUse" in config["hooks"]

        # And: DES PreToolUse hook exists (nested format)
        des_pre_hook = next(
            (
                h
                for h in config["hooks"]["PreToolUse"]
                if any(
                    "claude_code_hook_adapter" in sub.get("command", "")
                    for sub in h.get("hooks", [])
                )
            ),
            None,
        )
        assert des_pre_hook is not None, "DES PreToolUse hook not found"
        assert des_pre_hook["matcher"] == "Task"

        # And: DES SubagentStop hook exists (nested format)
        des_stop_hook = next(
            (
                h
                for h in config["hooks"]["SubagentStop"]
                if any(
                    "claude_code_hook_adapter" in sub.get("command", "")
                    for sub in h.get("hooks", [])
                )
            ),
            None,
        )
        assert des_stop_hook is not None, "DES SubagentStop hook not found"

        # And: existing hooks preserved
        assert len(config["hooks"]["PreToolUse"]) == 2
        assert len(config["hooks"]["SubagentStop"]) == 2
        other_pre = next(
            h for h in config["hooks"]["PreToolUse"] if h.get("matcher") == "OtherTool"
        )
        assert other_pre["command"] == "other_command"

    def test_install_creates_settings_file_if_missing(self, tmp_path):
        """Install creates .claude/settings.json if it doesn't exist."""
        # Given: .claude directory exists but settings.json doesn't
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_file = claude_dir / "settings.json"

        # When: run installer
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: installer succeeds
        assert result.returncode == 0, f"Installer failed: {result.stderr}"

        # And: settings file created
        assert settings_file.exists()

        # And: DES hooks configured
        config = json.loads(settings_file.read_text())
        assert "hooks" in config
        assert len(config["hooks"]["PreToolUse"]) == 1
        assert len(config["hooks"]["SubagentStop"]) == 1
        assert len(config["hooks"]["PostToolUse"]) == 1

    def test_install_is_idempotent(self, tmp_path):
        """Install detects existing DES hooks and doesn't duplicate."""
        # Given: empty config dir
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run installer twice
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/install/install_des_hooks.py",
                    "--install",
                    "--config-dir",
                    str(claude_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Installer failed: {result.stderr}"

        # Then: no duplicate hooks created
        config = json.loads((claude_dir / "settings.json").read_text())
        assert len(config["hooks"]["PreToolUse"]) == 1
        assert len(config["hooks"]["SubagentStop"]) == 1
        assert len(config["hooks"]["PostToolUse"]) == 1

    def test_install_configures_pretooluse_hook_correctly(self, tmp_path):
        """Install configures PreToolUse hook with Task matcher and python3 -m command."""
        # Given: empty config
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run installer
        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: PreToolUse hook configured correctly (nested format)
        config = json.loads((claude_dir / "settings.json").read_text())
        pre_hook = config["hooks"]["PreToolUse"][0]

        assert pre_hook["matcher"] == "Task"
        assert "hooks" in pre_hook
        assert len(pre_hook["hooks"]) == 1

        inner = pre_hook["hooks"][0]
        assert inner["type"] == "command"
        assert "-m" in inner["command"]
        assert "claude_code_hook_adapter" in inner["command"]
        assert "pre-task" in inner["command"]

    def test_install_configures_agentstop_hook_correctly(self, tmp_path):
        """Install configures SubagentStop hook with python3 -m command."""
        # Given: empty config
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run installer
        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: SubagentStop hook configured correctly (nested format)
        config = json.loads((claude_dir / "settings.json").read_text())
        stop_hook = config["hooks"]["SubagentStop"][0]

        assert "hooks" in stop_hook
        assert len(stop_hook["hooks"]) == 1

        inner = stop_hook["hooks"][0]
        assert inner["type"] == "command"
        assert "-m" in inner["command"]
        assert "claude_code_hook_adapter" in inner["command"]
        assert "subagent-stop" in inner["command"]

    def test_install_configures_posttooluse_hook_correctly(self, tmp_path):
        """Install configures PostToolUse hook with Task matcher and python3 -m command."""
        # Given: empty config
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run installer
        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: PostToolUse hook configured correctly (nested format)
        config = json.loads((claude_dir / "settings.json").read_text())
        assert "PostToolUse" in config["hooks"]
        post_hook = config["hooks"]["PostToolUse"][0]

        assert post_hook["matcher"] == "Task"
        assert "hooks" in post_hook
        assert len(post_hook["hooks"]) == 1

        inner = post_hook["hooks"][0]
        assert inner["type"] == "command"
        assert "-m" in inner["command"]
        assert "claude_code_hook_adapter" in inner["command"]
        assert "post-tool-use" in inner["command"]

    def test_uninstall_removes_only_des_hooks(self, tmp_path):
        """Uninstall removes only DES hooks, preserves others."""
        # Given: settings with DES and non-DES hooks (install first, then add non-DES)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_file = claude_dir / "settings.json"

        # Install DES hooks first
        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Add non-DES hooks
        config = json.loads(settings_file.read_text())
        config["hooks"]["PreToolUse"].append(
            {"matcher": "OtherTool", "command": "other_command"}
        )
        config["hooks"]["SubagentStop"].append({"command": "other_stop_command"})
        settings_file.write_text(json.dumps(config, indent=2))

        # When: run uninstaller
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--uninstall",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: uninstaller succeeds
        assert result.returncode == 0, f"Uninstaller failed: {result.stderr}"

        # And: DES hooks removed
        config = json.loads(settings_file.read_text())
        des_pre = [
            h
            for h in config["hooks"]["PreToolUse"]
            if any(
                "claude_code_hook_adapter" in sub.get("command", "")
                for sub in h.get("hooks", [])
            )
        ]
        des_stop = [
            h
            for h in config["hooks"]["SubagentStop"]
            if any(
                "claude_code_hook_adapter" in sub.get("command", "")
                for sub in h.get("hooks", [])
            )
        ]
        des_post = [
            h
            for h in config["hooks"].get("PostToolUse", [])
            if any(
                "claude_code_hook_adapter" in sub.get("command", "")
                for sub in h.get("hooks", [])
            )
        ]
        assert len(des_pre) == 0
        assert len(des_stop) == 0
        assert len(des_post) == 0

        # And: other hooks preserved
        assert len(config["hooks"]["PreToolUse"]) == 1
        assert len(config["hooks"]["SubagentStop"]) == 1
        assert config["hooks"]["PreToolUse"][0]["matcher"] == "OtherTool"

    def test_uninstall_handles_missing_file_gracefully(self, tmp_path):
        """Uninstall succeeds when settings.json doesn't exist."""
        # Given: .claude directory exists but settings file doesn't
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run uninstaller
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--uninstall",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: uninstaller succeeds without error
        assert result.returncode == 0, f"Uninstaller failed: {result.stderr}"

    def test_merged_config_is_valid_json(self, tmp_path):
        """Merged configuration validates as valid JSON."""
        # Given: empty config
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run installer
        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: config file is valid JSON
        settings_file = claude_dir / "settings.json"
        config_text = settings_file.read_text()

        # Should not raise exception
        config = json.loads(config_text)
        assert isinstance(config, dict)

    def test_status_detects_installed_state(self, tmp_path):
        """Status command detects whether hooks are installed."""
        # Given: DES hooks installed
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--install",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # When: run status command
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--status",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: status reports installed
        assert result.returncode == 0
        assert "installed" in result.stdout.lower()

    def test_status_detects_not_installed_state(self, tmp_path):
        """Status command detects when hooks are not installed."""
        # Given: no DES hooks
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # When: run status command
        result = subprocess.run(
            [
                sys.executable,
                "scripts/install/install_des_hooks.py",
                "--status",
                "--config-dir",
                str(claude_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Then: status reports not installed
        assert result.returncode == 0
        assert "not installed" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Fixtures shared by new test classes
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
