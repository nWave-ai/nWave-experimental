"""Unit tests for the P1-C settings-provenance receipt (des_plugin.py).

Exercises `_record_settings_receipt` / `_restore_settings_from_receipt` /
`_clear_settings_receipt` through the public `_install_des_hooks` /
`_update_path_in_settings` / `_uninstall_des_hooks` entry points -- no
method is bypassed or mocked. Assertions compare receipt/settings
byte-state, never timestamps.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.des_plugin_settings_provenance")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def plugin() -> DESPlugin:
    """Provide a fresh DESPlugin instance."""
    return DESPlugin()


def _make_context(
    tmp_path: Path, logger: logging.Logger, dir_name: str = ".claude"
) -> InstallContext:
    """Create InstallContext with a temporary claude_dir under `tmp_path`."""
    claude_dir = tmp_path / dir_name
    claude_dir.mkdir(parents=True, exist_ok=True)
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "unused-scripts",
        templates_dir=tmp_path / "unused-templates",
        logger=logger,
        dry_run=False,
    )


@pytest.fixture
def install_context(tmp_path: Path, test_logger: logging.Logger) -> InstallContext:
    return _make_context(tmp_path, test_logger)


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Recursive file-content snapshot of `root`, relative-path keyed."""
    return {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


@patch.object(DESPlugin, "_resolve_python_path", return_value="python3")
class TestSettingsProvenance:
    """Behaviors owed by the P1-C settings-provenance receipt."""

    def test_first_receipt_wins_across_repeated_installs(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """A v2 install must not overwrite the receipt's `_before` anchor,
        but MUST update `_written` to the latest value it actually wrote --
        that is the fact restore compares against, not a recomputed version."""
        receipt_path = plugin._settings_receipt_path(install_context)

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="1.0.0"
        ):
            result_v1 = plugin._install_des_hooks(install_context)
        assert result_v1.success, result_v1.message
        receipt_v1 = json.loads(receipt_path.read_text())
        assert receipt_v1["nwave_hook_version_before"] is None
        assert receipt_v1["nwave_hook_version_written"] == "1.0.0"

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="2.0.0"
        ):
            result_v2 = plugin._install_des_hooks(install_context)
        assert result_v2.success, result_v2.message
        receipt_v2 = json.loads(receipt_path.read_text())

        assert receipt_v2["nwave_hook_version_before"] is None, (
            "first-receipt-wins violated on the `_before` anchor"
        )
        assert receipt_v2["nwave_hook_version_written"] == "2.0.0", (
            "receipt must track the exact version nWave most recently wrote"
        )
        settings = json.loads(
            (install_context.claude_dir / "settings.json").read_text()
        )
        assert settings["nwave_hook_version"] == "2.0.0"

    @pytest.mark.parametrize(
        "original_version, uninstall_resolves_drifted_version, "
        "user_edited_post_install_version",
        [
            (None, False, None),
            ("0.9.0", False, None),
            ("0.9.0", True, None),
            ("0.9.0", False, "3.0.0"),
        ],
        ids=[
            "absent-original",
            "present-original",
            "present-original-uninstall-time-version-drifted",
            "user-edited-post-install",
        ],
    )
    def test_hook_version_restore_absent_and_present_originals(
        self,
        _mock_python,
        plugin: DESPlugin,
        install_context: InstallContext,
        original_version: str | None,
        uninstall_resolves_drifted_version: bool,
        user_edited_post_install_version: str | None,
    ):
        """Uninstall must restore the exact pre-nWave `nwave_hook_version`
        state by comparing against the receipt's recorded `_written` value --
        never by recomputing the package version, which may have changed
        (upgrade/downgrade) between install and uninstall. A value the user
        edits by hand after install no longer matches the receipt's
        `_written` anchor and must survive uninstall untouched. The unrelated
        `SLASH_COMMAND_TOOL_CHAR_BUDGET` key, which this installer does not
        own for rollback purposes, must stay byte-identical throughout."""
        settings_file = install_context.claude_dir / "settings.json"
        if original_version is not None:
            settings_file.write_text(
                json.dumps({"nwave_hook_version": original_version})
            )

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="1.2.3"
        ):
            install_result = plugin._install_des_hooks(install_context)
            assert install_result.success, install_result.message
            settings = json.loads(settings_file.read_text())
            assert settings["nwave_hook_version"] == "1.2.3"
            budget_after_install = settings["env"]["SLASH_COMMAND_TOOL_CHAR_BUDGET"]

        if user_edited_post_install_version is not None:
            settings = json.loads(settings_file.read_text())
            settings["nwave_hook_version"] = user_edited_post_install_version
            settings_file.write_text(json.dumps(settings))

        uninstall_version = "9.9.9" if uninstall_resolves_drifted_version else "1.2.3"
        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value=uninstall_version
        ):
            uninstall_result = plugin._uninstall_des_hooks(install_context)
            assert uninstall_result.success, uninstall_result.message

        settings = json.loads(settings_file.read_text())
        if user_edited_post_install_version is not None:
            assert settings["nwave_hook_version"] == user_edited_post_install_version
        elif original_version is None:
            assert "nwave_hook_version" not in settings
        else:
            assert settings["nwave_hook_version"] == original_version
        assert settings["env"]["SLASH_COMMAND_TOOL_CHAR_BUDGET"] == (
            budget_after_install
        ), "installer must never claim or roll back the token budget"

    def test_profile_isolated_receipt_paths(
        self,
        _mock_python,
        plugin: DESPlugin,
        tmp_path: Path,
        test_logger: logging.Logger,
    ):
        """Two profiles sharing a parent directory must never collide on a receipt."""
        context_a = _make_context(tmp_path, test_logger, ".claude")
        context_b = _make_context(tmp_path, test_logger, ".claude-alt")
        (context_a.claude_dir / "settings.json").write_text(
            json.dumps({"nwave_hook_version": "profile-a-original"})
        )
        (context_b.claude_dir / "settings.json").write_text(
            json.dumps({"nwave_hook_version": "profile-b-original"})
        )

        assert plugin._settings_receipt_path(
            context_a
        ) != plugin._settings_receipt_path(context_b)

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="9.9.9"
        ):
            for context in (context_a, context_b):
                result = plugin._install_des_hooks(context)
                assert result.success, result.message

        receipt_a = json.loads(plugin._settings_receipt_path(context_a).read_text())
        receipt_b = json.loads(plugin._settings_receipt_path(context_b).read_text())
        assert receipt_a["nwave_hook_version_before"] == "profile-a-original"
        assert receipt_b["nwave_hook_version_before"] == "profile-b-original"

    @pytest.mark.parametrize(
        "settings_file_present_at_uninstall",
        [True, False],
        ids=["settings-present", "settings-absent"],
    )
    def test_receipt_cleared_after_successful_uninstall(
        self,
        _mock_python,
        plugin: DESPlugin,
        install_context: InstallContext,
        settings_file_present_at_uninstall: bool,
    ):
        """A successful uninstall must delete the receipt so reinstall is
        first-ever again -- even when settings.json itself is already gone,
        which must not leave a stale receipt to poison a future install."""
        receipt_path = plugin._settings_receipt_path(install_context)
        settings_file = install_context.claude_dir / "settings.json"

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="1.0.0"
        ):
            plugin._install_des_hooks(install_context)
            assert receipt_path.exists()

            if not settings_file_present_at_uninstall:
                settings_file.unlink()

            uninstall_result = plugin._uninstall_des_hooks(install_context)

        assert uninstall_result.success, uninstall_result.message
        assert not receipt_path.exists()

    @pytest.mark.parametrize(
        "scenario",
        [
            "receipt-matches-segment-removed",
            "path-edited-since-install",
            "no-receipt-ever-written",
        ],
    )
    def test_uninstall_preserves_user_modified_path(
        self,
        _mock_python,
        plugin: DESPlugin,
        install_context: InstallContext,
        scenario: str,
    ):
        """Uninstall removes nWave's exact bin segment ONLY when a receipt
        proves this install wrote the current PATH value verbatim. Any edit
        since that write, or the total absence of a receipt, must leave
        PATH completely untouched -- including a segment that merely looks
        like nWave's own."""
        des_bin_path = str(install_context.claude_dir / "bin")
        settings_file = install_context.claude_dir / "settings.json"
        original_path = "/home/user/.local/bin:/usr/bin:/usr/local/bin"

        if scenario == "receipt-matches-segment-removed":
            settings_file.write_text(json.dumps({"env": {"PATH": original_path}}))
            plugin._update_path_in_settings(install_context, des_bin_path)
            expected_path = original_path
        elif scenario == "path-edited-since-install":
            settings_file.write_text(json.dumps({"env": {"PATH": original_path}}))
            plugin._update_path_in_settings(install_context, des_bin_path)
            edited_path = f"{des_bin_path}:{original_path}:/opt/mytool/bin"
            settings = json.loads(settings_file.read_text())
            settings["env"]["PATH"] = edited_path
            settings_file.write_text(json.dumps(settings))
            expected_path = edited_path
        else:  # no-receipt-ever-written
            existing_path = f"{des_bin_path}:{original_path}"
            settings_file.write_text(json.dumps({"env": {"PATH": existing_path}}))
            expected_path = existing_path

        result = plugin._uninstall_des_hooks(install_context)
        assert result.success, result.message

        settings = json.loads(settings_file.read_text())
        assert settings["env"]["PATH"] == expected_path

    def test_dry_run_writes_no_receipt_and_no_settings_file(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """A dry-run install must not create settings.json or a receipt --
        preview only, zero on-disk side effects."""
        install_context.dry_run = True
        settings_file = install_context.claude_dir / "settings.json"
        receipt_path = plugin._settings_receipt_path(install_context)

        with patch.object(
            DESPlugin, "_resolve_nwave_hook_version", return_value="1.0.0"
        ):
            result = plugin._install_des_hooks(install_context)

        assert result.success, result.message
        assert not settings_file.exists()
        assert not receipt_path.exists()

    def test_receipt_recorded_when_path_already_contains_segment(
        self, _mock_python, plugin: DESPlugin, install_context: InstallContext
    ):
        """Upgrade from a pre-receipt installer: PATH already contains the
        nWave bin segment, so there is nothing to change on disk -- but the
        receipt must still be recorded, otherwise a later uninstall has no
        anchor to remove the installer-owned segment."""
        des_bin_path = str(install_context.claude_dir / "bin")
        settings_file = install_context.claude_dir / "settings.json"
        existing_path = f"{des_bin_path}:/usr/bin:/usr/local/bin"
        settings_file.write_text(json.dumps({"env": {"PATH": existing_path}}))
        receipt_path = plugin._settings_receipt_path(install_context)
        assert not receipt_path.exists()

        plugin._update_path_in_settings(install_context, des_bin_path)

        assert receipt_path.exists(), "no-op PATH branch must still record provenance"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["path_before"] == existing_path
        assert receipt["path_written"] == existing_path

    def test_real_home_untouched_when_claude_dir_is_a_temp_target(
        self,
        _mock_python,
        plugin: DESPlugin,
        tmp_path: Path,
        test_logger: logging.Logger,
    ):
        """A DESPlugin driven with a temp/custom claude_dir must never read
        or write anything under the developer's real home, even when
        Path.home() resolves there -- receipt location and PATH's $HOME
        normalization must derive solely from `context.claude_dir`."""
        sentinel_home = tmp_path / "sentinel-real-home"
        (sentinel_home / ".claude").mkdir(parents=True)
        (sentinel_home / ".claude" / "settings.json").write_text(
            json.dumps({"nwave_hook_version": "real-home-untouched"})
        )
        (sentinel_home / ".nwave" / "install-receipts").mkdir(parents=True)
        (sentinel_home / ".nwave" / "install-receipts" / "marker.json").write_text(
            '{"canary": true}'
        )
        before = _tree_snapshot(sentinel_home)

        custom_target = tmp_path / "custom-install-target" / ".claude"
        custom_target.mkdir(parents=True)
        des_bin_path = str(custom_target / "bin")
        (custom_target / "settings.json").write_text(
            json.dumps({"env": {"PATH": "$HOME/bin:/usr/bin"}})
        )
        custom_context = InstallContext(
            claude_dir=custom_target,
            scripts_dir=tmp_path / "unused-scripts",
            templates_dir=tmp_path / "unused-templates",
            logger=test_logger,
            dry_run=False,
        )

        with patch.object(Path, "home", return_value=sentinel_home):
            with patch.object(
                DESPlugin, "_resolve_nwave_hook_version", return_value="1.0.0"
            ):
                install_result = plugin._install_des_hooks(custom_context)
                assert install_result.success, install_result.message
            plugin._update_path_in_settings(custom_context, des_bin_path)
            uninstall_result = plugin._uninstall_des_hooks(custom_context)
            assert uninstall_result.success, uninstall_result.message

        after = _tree_snapshot(sentinel_home)
        assert after == before, "real-home tree must stay byte-identical"
