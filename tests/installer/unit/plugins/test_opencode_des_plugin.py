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
- _find_des_source() prefers dist over project layout

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
"""

import json
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_des_plugin import (
    OpenCodeDESPlugin,
    _find_des_source,
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal DES source layout.

    Returns:
        Tuple of (context, des_source_dir, opencode_plugins_target)
    """
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    des_source = project_root / "nWave" / "des"
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


class TestInstallCopiesFileAndWritesManifest:
    """Test that install() copies TS file and writes manifest."""

    def test_install_copies_file_and_writes_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: nWave/des/opencode-plugin.ts exists in the source tree
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


class TestFindDesSourcePrefersDist:
    """Test that _find_des_source() prefers dist over project layout."""

    def test_find_des_source_prefers_dist(self, tmp_path):
        """
        GIVEN: Both dist and project source locations contain opencode-plugin.ts
        WHEN: _find_des_source() is called
        THEN: Returns the dist path (framework_source), not the project path
        """
        project_root = tmp_path / "project"
        framework_source = tmp_path / "framework"

        # Create both locations
        dist_des = framework_source / "des"
        dist_des.mkdir(parents=True)
        (dist_des / "opencode-plugin.ts").write_text("// dist version")

        proj_des = project_root / "nWave" / "des"
        proj_des.mkdir(parents=True)
        (proj_des / "opencode-plugin.ts").write_text("// project version")

        context = InstallContext(
            claude_dir=tmp_path / ".claude",
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=MagicMock(),
            project_root=project_root,
            framework_source=framework_source,
        )

        result = _find_des_source(context)

        assert result is not None
        assert "framework" in str(result), "Should prefer dist (framework_source)"

    def test_find_des_source_falls_back_to_project(self, tmp_path):
        """
        GIVEN: Only project source location contains opencode-plugin.ts
        WHEN: _find_des_source() is called
        THEN: Returns the project path
        """
        project_root = tmp_path / "project"
        framework_source = tmp_path / "framework"

        # Only create project location
        proj_des = project_root / "nWave" / "des"
        proj_des.mkdir(parents=True)
        (proj_des / "opencode-plugin.ts").write_text("// project version")

        context = InstallContext(
            claude_dir=tmp_path / ".claude",
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=MagicMock(),
            project_root=project_root,
            framework_source=framework_source,
        )

        result = _find_des_source(context)

        assert result is not None
        assert "project" in str(result), "Should fall back to project"

    def test_find_des_source_returns_none_when_missing(self, tmp_path):
        """
        GIVEN: No source location contains opencode-plugin.ts
        WHEN: _find_des_source() is called
        THEN: Returns None
        """
        context = InstallContext(
            claude_dir=tmp_path / ".claude",
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=MagicMock(),
            project_root=tmp_path / "project",
            framework_source=tmp_path / "framework",
        )

        result = _find_des_source(context)

        assert result is None


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
        GIVEN: nWave/des/opencode-plugin.ts exists in the source tree
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
