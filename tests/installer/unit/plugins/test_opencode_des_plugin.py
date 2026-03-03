"""Unit tests for OpenCode DES installer plugin.

Tests validate that:
- install() copies the TypeScript DES plugin to OpenCode plugins directory
- install() writes a .nwave-des-manifest.json tracking the installed file
- install() handles missing source gracefully (returns success with skip message)
- verify() passes after successful install (file exists + content check)
- verify() fails when the plugin file is missing
- verify() content check detects "tool.execute.before"
- uninstall() removes only manifest-tracked files
- uninstall() handles missing manifest with fallback to known path
- _create_plugin_registry includes opencode-des when opencode platform detected
- _create_plugin_registry excludes opencode-des when opencode platform not detected
- Topological order: opencode-des after opencode-commands, before des

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_des_plugin import (
    OpenCodeDESPlugin,
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal DES source layout.

    Returns:
        Tuple of (context, des_source_dir, opencode_plugins_target)
    """
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    des_source = project_root / "src" / "des"
    des_source.mkdir(parents=True)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    logger = MagicMock()

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logger,
        project_root=project_root,
        framework_source=framework_source,
    )

    opencode_plugins_target = tmp_path / "home" / ".config" / "opencode" / "plugins"

    return context, des_source, opencode_plugins_target


_SAMPLE_TS_CONTENT = """\
// nWave DES Plugin for OpenCode
// Deterministic Execution System

import type { Plugin } from "@opencode-ai/plugin"

// Hook handlers
const plugin: Plugin = {
  name: "nwave-des",
  hooks: {
    "tool.execute.before": async (input, output) => {
      // Phase enforcement logic
      return { allow: true }
    },
  },
}

export default plugin
"""


class TestInstall:
    """Test that install() copies TS file and writes manifest."""

    def test_install_copies_file_and_writes_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: src/des/opencode-plugin.ts exists in the source tree
        WHEN: install() runs
        THEN: the file is copied to ~/.config/opencode/plugins/nwave-des.ts
              and a .nwave-des-manifest.json is written tracking the installed file
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source TS file
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        plugin = OpenCodeDESPlugin()
        result = plugin.install(context)

        assert result.success is True

        # Verify file was copied with correct name
        installed_file = target / "nwave-des.ts"
        assert installed_file.exists(), "Expected nwave-des.ts to exist in plugins dir"
        assert installed_file.read_text() == _SAMPLE_TS_CONTENT

        # Verify manifest was written
        manifest_path = target / ".nwave-des-manifest.json"
        assert manifest_path.exists(), "Expected manifest to be written"
        manifest = json.loads(manifest_path.read_text())
        assert "installed_files" in manifest
        assert "nwave-des.ts" in manifest["installed_files"]


class TestInstallHandlesMissingSourceGracefully:
    """Test that install() handles missing source gracefully."""

    def test_install_missing_source_returns_success_with_skip(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: No opencode-plugin.ts exists in any source location
        WHEN: install() runs
        THEN: Returns success with a skip message (not failure)
        """
        context, _des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Don't create source TS file -- it's missing

        plugin = OpenCodeDESPlugin()
        result = plugin.install(context)

        assert result.success is True
        assert "not found" in result.message.lower() or "skip" in result.message.lower()


class TestVerifyPassesAfterSuccessfulInstall:
    """Test that verify() passes after a successful install."""

    def test_verify_passes_after_install(self, tmp_path, monkeypatch):
        """
        GIVEN: A successful installation (nwave-des.ts exists with correct content)
        WHEN: verify() runs
        THEN: It confirms nwave-des.ts exists and contains 'tool.execute.before'
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source and install
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        plugin = OpenCodeDESPlugin()
        plugin.install(context)

        # Now verify
        result = plugin.verify(context)

        assert result.success is True
        assert result.errors == []


class TestVerifyFailsWhenFileMissing:
    """Test that verify() fails when the plugin file is missing."""

    def test_verify_fails_when_file_missing(self, tmp_path, monkeypatch):
        """
        GIVEN: nwave-des.ts does NOT exist in the plugins directory
        WHEN: verify() runs
        THEN: Returns failure indicating the file is missing
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source so plugin knows it should be installed
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        # Don't install -- file should be missing
        target.mkdir(parents=True, exist_ok=True)

        plugin = OpenCodeDESPlugin()
        result = plugin.verify(context)

        assert result.success is False


class TestVerifyDetectsMissingPluginFile:
    """Test that verify() fails when manifest exists but plugin file was deleted."""

    def test_verify_fails_when_manifest_present_but_file_deleted(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: plugin installed (file + manifest exist)
        AND: plugin file manually deleted
        WHEN: verify() runs
        THEN: reports failure
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source TS file
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        plugin = OpenCodeDESPlugin()
        plugin.install(context)

        # Verify install succeeded
        assert (target / "nwave-des.ts").exists()

        # Manually delete the plugin file (simulating corruption/manual removal)
        (target / "nwave-des.ts").unlink()

        # Verify should now fail
        result = plugin.verify(context)

        assert result.success is False


class TestUninstallRemovesOnlyManifestTrackedFiles:
    """Test that uninstall() removes only manifest-tracked files."""

    def test_uninstall_removes_only_manifest_files(self, tmp_path, monkeypatch):
        """
        GIVEN: .nwave-des-manifest.json exists tracking nwave-des.ts
        WHEN: uninstall() runs
        THEN: Only nwave-des.ts and the manifest are removed;
              other user files in the plugins directory remain
        """
        context, _des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        target.mkdir(parents=True, exist_ok=True)

        # Create the nWave-installed plugin file
        nwave_file = target / "nwave-des.ts"
        nwave_file.write_text(_SAMPLE_TS_CONTENT)

        # Create a user-owned plugin file (NOT in manifest)
        user_file = target / "my-custom-plugin.ts"
        user_file.write_text("// User plugin")

        # Write manifest tracking only nwave-des.ts
        manifest = {"installed_files": ["nwave-des.ts"], "version": "1.0"}
        (target / ".nwave-des-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeDESPlugin()
        result = plugin.uninstall(context)

        assert result.success is True
        assert not nwave_file.exists(), "nwave-des.ts should be removed"
        assert not (target / ".nwave-des-manifest.json").exists(), (
            "manifest should be removed"
        )
        assert user_file.exists(), "User plugin must remain untouched"


class TestUninstallHandlesMissingManifestGracefully:
    """Test that uninstall() handles missing manifest with fallback."""

    def test_uninstall_fallback_removes_known_file(self, tmp_path, monkeypatch):
        """
        GIVEN: No .nwave-des-manifest.json exists but nwave-des.ts is present
        WHEN: uninstall() runs
        THEN: Falls back to removing the known file nwave-des.ts
        """
        context, _des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        target.mkdir(parents=True, exist_ok=True)

        # File exists but no manifest
        known_file = target / "nwave-des.ts"
        known_file.write_text(_SAMPLE_TS_CONTENT)

        plugin = OpenCodeDESPlugin()
        result = plugin.uninstall(context)

        assert result.success is True
        assert not known_file.exists(), "Known file should be removed in fallback"

    def test_uninstall_no_manifest_no_file_returns_success(self, tmp_path, monkeypatch):
        """
        GIVEN: Neither manifest nor nwave-des.ts exists
        WHEN: uninstall() runs
        THEN: Returns success (nothing to uninstall)
        """
        context, _des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        plugin = OpenCodeDESPlugin()
        result = plugin.uninstall(context)

        assert result.success is True


class TestVerifyContentCheck:
    """Test that verify() checks for 'tool.execute.before' in content."""

    def test_verify_fails_when_content_missing_hook_string(self, tmp_path, monkeypatch):
        """
        GIVEN: nwave-des.ts exists but does NOT contain 'tool.execute.before'
        WHEN: verify() runs
        THEN: Returns failure indicating content check failed
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source so plugin knows it should be installed
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        target.mkdir(parents=True, exist_ok=True)

        # Write file with WRONG content (no hook string)
        (target / "nwave-des.ts").write_text("// empty plugin, no hooks")

        # Write manifest
        manifest = {"installed_files": ["nwave-des.ts"], "version": "1.0"}
        (target / ".nwave-des-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeDESPlugin()
        result = plugin.verify(context)

        assert result.success is False
        assert any("tool.execute.before" in err for err in result.errors), (
            f"Expected content check error, got: {result.errors}"
        )


class TestInstallVerifyUninstallCycle:
    """Acceptance test: full install -> verify -> uninstall cycle."""

    def test_full_cycle(self, tmp_path, monkeypatch):
        """
        GIVEN: src/des/opencode-plugin.ts exists in the source tree
        WHEN: install() -> verify() -> uninstall() are called in sequence
        THEN: install copies the file and writes manifest,
              verify confirms everything is correct,
              uninstall removes only tracked files and manifest
        """
        context, des_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_des_plugin._opencode_plugins_dir",
            lambda: target,
        )

        # Create source TS file
        (des_source / "opencode-plugin.ts").write_text(_SAMPLE_TS_CONTENT)

        plugin = OpenCodeDESPlugin()

        # --- INSTALL ---
        install_result = plugin.install(context)
        assert install_result.success is True
        assert (target / "nwave-des.ts").exists()
        assert (target / ".nwave-des-manifest.json").exists()

        # --- VERIFY ---
        verify_result = plugin.verify(context)
        assert verify_result.success is True

        # --- UNINSTALL ---
        uninstall_result = plugin.uninstall(context)
        assert uninstall_result.success is True
        assert not (target / "nwave-des.ts").exists()
        assert not (target / ".nwave-des-manifest.json").exists()


# ---------------------------------------------------------------------------
# Registry integration tests
# ---------------------------------------------------------------------------


def _build_installer():
    """Build an NWaveInstaller with mocked filesystem paths.

    Returns:
        NWaveInstaller configured for testing (dry_run=True).
    """
    with (
        patch(
            "scripts.install.install_nwave.PathUtils.get_claude_config_dir"
        ) as mock_config,
        patch("scripts.install.install_nwave.PathUtils.get_project_root") as mock_root,
    ):
        mock_config.return_value = Path("/fake/.claude")
        mock_root.return_value = Path("/fake/project")
        from scripts.install.install_nwave import NWaveInstaller

        installer = NWaveInstaller(dry_run=True)
    return installer


class TestRegistryIncludesOpencodeDes:
    """Test that _create_plugin_registry registers opencode-des for opencode platform."""

    def test_registry_includes_opencode_des_when_opencode_platform_detected(self):
        """
        GIVEN: target_platforms contains 'opencode'
        WHEN: _create_plugin_registry() executes
        THEN: OpenCodeDESPlugin is registered with name 'opencode-des'
              and depends on 'opencode-commands'
        """
        installer = _build_installer()

        registry = installer._create_plugin_registry(
            silent=True, target_platforms={"opencode"}
        )

        assert "opencode-des" in registry.plugins, (
            "opencode-des should be registered when opencode platform detected"
        )
        plugin = registry.plugins["opencode-des"]
        assert "opencode-commands" in plugin.get_dependencies(), (
            "opencode-des should depend on opencode-commands"
        )


class TestRegistryExcludesOpencodeDesWithoutPlatform:
    """Test that _create_plugin_registry excludes opencode-des without opencode platform."""

    def test_registry_excludes_opencode_des_without_opencode_platform(self):
        """
        GIVEN: target_platforms does NOT contain 'opencode'
        WHEN: _create_plugin_registry() executes
        THEN: OpenCodeDESPlugin is NOT registered
        """
        installer = _build_installer()

        registry = installer._create_plugin_registry(
            silent=True, target_platforms={"claude_code"}
        )

        assert "opencode-des" not in registry.plugins, (
            "opencode-des should NOT be registered without opencode platform"
        )

    def test_registry_excludes_opencode_des_with_no_platforms(self):
        """
        GIVEN: target_platforms is None
        WHEN: _create_plugin_registry() executes
        THEN: OpenCodeDESPlugin is NOT registered
        """
        installer = _build_installer()

        registry = installer._create_plugin_registry(silent=True, target_platforms=None)

        assert "opencode-des" not in registry.plugins, (
            "opencode-des should NOT be registered with no target platforms"
        )


class TestRegistryTopologicalOrder:
    """Test that topological sort places opencode-des correctly in execution order."""

    def test_opencode_des_after_opencode_commands_before_des(self):
        """
        GIVEN: Full plugin registry with opencode platform
        WHEN: Topological sort resolves execution order
        THEN: opencode-des runs after opencode-commands (dependency)
              and before des (priority 39 < 50)
        """
        installer = _build_installer()

        registry = installer._create_plugin_registry(
            silent=True, target_platforms={"opencode"}
        )
        execution_order = registry.get_execution_order()

        assert "opencode-des" in execution_order, (
            "opencode-des should be in execution order"
        )
        opencode_des_idx = execution_order.index("opencode-des")
        opencode_commands_idx = execution_order.index("opencode-commands")
        des_idx = execution_order.index("des")

        assert opencode_des_idx > opencode_commands_idx, (
            f"opencode-des (idx={opencode_des_idx}) should run after "
            f"opencode-commands (idx={opencode_commands_idx})"
        )
        assert opencode_des_idx < des_idx, (
            f"opencode-des (idx={opencode_des_idx}) should run before "
            f"des (idx={des_idx})"
        )
