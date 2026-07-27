"""Regression: DES module uninstall must agree with install's location choice.

Bug (techdebt drain, shard B): `DESPlugin.uninstall()` and
`NWaveUninstaller.remove_lib_python()` each independently hardcoded
`<claude_dir>/lib/python/des` as THE location of the installed DES module,
ignoring `DESPlugin._runtime_python_dir` / `_secondary_runtime_python_dir`
(the install-time logic that picks `host_neutral_runtime_dir()/des` for any
target that isn't Claude-only, and mirrors into BOTH locations for a mixed
claude_code + codex/copilot/opencode target). For any non-Claude-only or
mixed target, the two hardcoded uninstall paths either silently removed
nothing (guarded by `.exists()`) or missed the host-neutral location
entirely, orphaning the module on disk after "uninstall".

Fix: `DESPlugin.resolve_des_module_locations(context)` is the single shared
helper -- built directly on the existing `_runtime_python_dir` /
`_secondary_runtime_python_dir` -- that both `DESPlugin.uninstall()` and
`NWaveUninstaller.remove_lib_python()` now call. These tests prove: (a)
Claude-only removes only the Claude path, (b) a host-neutral-only target
removes only `host_neutral_runtime_dir()/des`, (c) a mixed target removes
BOTH, and (d) the two call paths agree on the same locations for the same
platform set (the parity check that proves the divergence is closed).
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install.install_utils import Logger
from scripts.install.plugins.base import InstallContext, PluginResult
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.install.uninstall_nwave import NWaveUninstaller


def _make_context(
    target_platforms: set[str], claude_dir: Path, logger=None
) -> InstallContext:
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=claude_dir / "scripts",
        templates_dir=claude_dir / "templates",
        logger=logger or logging.getLogger("test.des_module_uninstall"),
        target_platforms=target_platforms,
    )


def _make_uninstaller(claude_dir: Path, dry_run: bool = False) -> NWaveUninstaller:
    """Build an NWaveUninstaller without going through __init__'s real
    PathUtils.get_claude_config_dir() lookup -- point it at a tmp dir instead.
    """
    uninstaller = NWaveUninstaller.__new__(NWaveUninstaller)
    uninstaller.backup_before_removal = False
    uninstaller.force = True
    uninstaller.dry_run = dry_run
    uninstaller.claude_config_dir = claude_dir
    uninstaller.logger = Logger(log_file=None, silent=True)
    return uninstaller


class TestResolveDesModuleLocations:
    """`DESPlugin.resolve_des_module_locations` -- the shared SSOT helper."""

    def test_claude_only_target_resolves_to_claude_scoped_path_only(
        self, tmp_path: Path
    ):
        claude_dir = tmp_path / ".claude"
        context = _make_context({"claude_code"}, claude_dir)

        locations = DESPlugin.resolve_des_module_locations(context)

        assert locations == [claude_dir / "lib" / "python" / "des"]

    def test_host_neutral_only_target_resolves_to_host_neutral_path_only(
        self, tmp_path: Path
    ):
        claude_dir = tmp_path / ".claude"
        neutral_dir = tmp_path / "neutral_runtime"
        context = _make_context({"codex"}, claude_dir)

        with patch(
            "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
            return_value=neutral_dir,
        ):
            locations = DESPlugin.resolve_des_module_locations(context)

        assert locations == [neutral_dir / "des"]

    def test_mixed_target_resolves_to_both_locations(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        neutral_dir = tmp_path / "neutral_runtime"
        context = _make_context({"claude_code", "codex"}, claude_dir)

        with patch(
            "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
            return_value=neutral_dir,
        ):
            locations = DESPlugin.resolve_des_module_locations(context)

        assert set(locations) == {
            claude_dir / "lib" / "python" / "des",
            neutral_dir / "des",
        }
        assert len(locations) == 2


class TestDesPluginUninstallRemovesResolvedLocations:
    """`DESPlugin.uninstall()` step 2 must remove every resolved location."""

    def test_claude_only_removes_only_claude_scoped_module(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_des = claude_dir / "lib" / "python" / "des"
        claude_des.mkdir(parents=True)
        (claude_des / "marker.py").write_text("# des module\n")
        neutral_des = tmp_path / "neutral_runtime" / "des"
        neutral_des.mkdir(parents=True)
        (neutral_des / "marker.py").write_text("# des module\n")

        context = _make_context({"claude_code"}, claude_dir)
        plugin = DESPlugin()

        with (
            patch.object(
                plugin,
                "_uninstall_des_hooks",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch(
                "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
                return_value=tmp_path / "neutral_runtime",
            ),
        ):
            result = plugin.uninstall(context)

        assert result.success is True
        assert not claude_des.exists()
        assert neutral_des.exists()  # untouched: not a Claude target

    def test_host_neutral_only_removes_only_host_neutral_module(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_des = claude_dir / "lib" / "python" / "des"
        claude_des.mkdir(parents=True)
        (claude_des / "marker.py").write_text("# des module\n")
        neutral_dir = tmp_path / "neutral_runtime"
        neutral_des = neutral_dir / "des"
        neutral_des.mkdir(parents=True)
        (neutral_des / "marker.py").write_text("# des module\n")

        context = _make_context({"codex"}, claude_dir)
        plugin = DESPlugin()

        with (
            patch.object(
                plugin,
                "_uninstall_des_hooks",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch(
                "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
                return_value=neutral_dir,
            ),
        ):
            result = plugin.uninstall(context)

        assert result.success is True
        assert not neutral_des.exists()
        assert claude_des.exists()  # untouched: not a Claude target here

    def test_mixed_target_removes_both_locations(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_des = claude_dir / "lib" / "python" / "des"
        claude_des.mkdir(parents=True)
        (claude_des / "marker.py").write_text("# des module\n")
        neutral_dir = tmp_path / "neutral_runtime"
        neutral_des = neutral_dir / "des"
        neutral_des.mkdir(parents=True)
        (neutral_des / "marker.py").write_text("# des module\n")

        context = _make_context({"claude_code", "codex"}, claude_dir)
        plugin = DESPlugin()

        with (
            patch.object(
                plugin,
                "_uninstall_des_hooks",
                return_value=PluginResult(
                    success=True, plugin_name="des", message="ok"
                ),
            ),
            patch(
                "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
                return_value=neutral_dir,
            ),
        ):
            result = plugin.uninstall(context)

        assert result.success is True
        assert not claude_des.exists()
        assert not neutral_des.exists()


class TestRemoveLibPythonAgreesWithDesPluginUninstall:
    """Regression: `NWaveUninstaller.remove_lib_python()` and
    `DESPlugin.uninstall()` must resolve the SAME locations for the SAME
    platform set -- the parity check that proves the two independently
    hardcoded uninstall paths (issue: des-module-uninstall-path-divergence)
    no longer disagree.
    """

    @pytest.mark.parametrize(
        "detected_platform_values",
        [
            {"claude_code"},
            {"codex"},
            {"claude_code", "codex"},
            {"copilot"},
        ],
    )
    def test_remove_lib_python_matches_des_plugin_resolved_locations(
        self, tmp_path: Path, detected_platform_values: set[str]
    ):
        claude_dir = tmp_path / ".claude"
        neutral_dir = tmp_path / "neutral_runtime"

        # Seed both possible locations so removal is observable either way.
        claude_des = claude_dir / "lib" / "python" / "des"
        claude_des.mkdir(parents=True)
        (claude_des / "marker.py").write_text("# des module\n")
        neutral_des = neutral_dir / "des"
        neutral_des.mkdir(parents=True)
        (neutral_des / "marker.py").write_text("# des module\n")

        class _FakeTargetPlatform:
            def __init__(self, value: str) -> None:
                self.value = value

        detected = {_FakeTargetPlatform(v) for v in detected_platform_values}

        expected_context = _make_context(detected_platform_values, claude_dir)
        with patch(
            "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
            return_value=neutral_dir,
        ):
            expected_locations = set(
                DESPlugin.resolve_des_module_locations(expected_context)
            )

        uninstaller = _make_uninstaller(claude_dir)

        with (
            patch(
                "scripts.install.context_detector.detect_target_platforms",
                return_value=detected,
            ),
            patch(
                "scripts.install.plugins.des_plugin.host_neutral_runtime_dir",
                return_value=neutral_dir,
            ),
        ):
            uninstaller.remove_lib_python()

        # Every expected location was actually removed by remove_lib_python.
        for location in expected_locations:
            assert not location.exists(), (
                f"remove_lib_python() did not remove {location}, which "
                f"DESPlugin.resolve_des_module_locations() resolved for "
                f"target_platforms={detected_platform_values}"
            )

        # Any location NOT in the resolved set must survive untouched.
        all_seeded = {claude_des, neutral_des}
        for location in all_seeded - expected_locations:
            assert location.exists(), (
                f"remove_lib_python() removed {location}, which is NOT in "
                f"the resolved location set for "
                f"target_platforms={detected_platform_values} -- "
                f"over-deletion regression"
            )
