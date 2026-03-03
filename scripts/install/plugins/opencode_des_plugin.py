"""
Plugin for installing the nWave DES TypeScript plugin into OpenCode's plugins directory.

OpenCode expects plugins at: ~/.config/opencode/plugins/
The DES plugin enforces TDD phase discipline via tool.execute.before hooks.

A manifest file (.nwave-des-manifest.json) tracks which files nWave installed,
so uninstall() can remove only nWave files without touching user-created ones.
"""

import json
import shutil
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)


_MANIFEST_FILENAME = ".nwave-des-manifest.json"

_MANIFEST_VERSION = "1.0"

_TARGET_FILENAME = "nwave-des.ts"

# Hook event name -- proves the file is a valid DES plugin
_CONTENT_CHECK_STRING = "tool.execute.before"


def _opencode_plugins_dir() -> Path:
    """Return the OpenCode plugins target directory.

    Returns:
        Path to ~/.config/opencode/plugins/
    """
    return Path.home() / ".config" / "opencode" / "plugins"


def _find_des_source(context: InstallContext) -> Path | None:
    """Locate the DES plugin TypeScript source from dist or project layout.

    Prefers dist (framework_source) over project layout.

    Args:
        context: InstallContext with framework_source and project_root

    Returns:
        Path to the opencode-plugin.ts source file, or None if not found
    """
    dist_source = context.framework_source / "des" / "opencode-plugin.ts"
    if dist_source.exists():
        return dist_source

    project_source = context.project_root / "src" / "des" / "opencode-plugin.ts"
    if project_source.exists():
        return project_source

    return None


def _write_manifest(target_dir: Path, installed_filename: str) -> None:
    """Write the manifest file tracking the nWave-installed DES plugin.

    Args:
        target_dir: OpenCode plugins directory
        installed_filename: Name of the installed file (e.g. 'nwave-des.ts')
    """
    manifest = {
        "installed_files": [installed_filename],
        "version": _MANIFEST_VERSION,
    }
    manifest_path = target_dir / _MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _read_manifest(target_dir: Path) -> dict | None:
    """Read the manifest file if it exists.

    Args:
        target_dir: OpenCode plugins directory

    Returns:
        Parsed manifest dict, or None if not found
    """
    manifest_path = target_dir / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())


class OpenCodeDESPlugin(InstallationPlugin):
    """Plugin for installing the nWave DES TypeScript plugin into OpenCode."""

    def __init__(self):
        """Initialize OpenCode DES plugin with name and priority."""
        # After opencode-commands (38), before des (50)
        super().__init__(name="opencode-des", priority=39)

    def install(self, context: InstallContext) -> PluginResult:
        """Install the DES TypeScript plugin to OpenCode's plugins directory.

        Locates the source opencode-plugin.ts, copies it as nwave-des.ts,
        and writes a manifest for safe uninstallation.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  \U0001f4e6 Installing OpenCode DES plugin...")

            source_file = _find_des_source(context)
            if source_file is None:
                context.logger.info(
                    "  \u23ed\ufe0f No DES plugin source found, skipping"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No DES plugin to install (source not found)",
                )

            target_dir = _opencode_plugins_dir()
            target_dir.mkdir(parents=True, exist_ok=True)

            target_file = target_dir / _TARGET_FILENAME
            shutil.copy2(source_file, target_file)

            _write_manifest(target_dir, _TARGET_FILENAME)

            context.logger.info("  \u2705 OpenCode DES plugin installed")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="OpenCode DES plugin installed successfully",
                installed_files=[target_file],
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to install OpenCode DES plugin: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode DES plugin installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall only nWave-installed DES plugin using manifest.

        Reads the manifest to determine which files were installed by nWave.
        Falls back to checking the known path if no manifest exists.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info(
                "  \U0001f5d1\ufe0f Uninstalling OpenCode DES plugin..."
            )

            target_dir = _opencode_plugins_dir()
            manifest = _read_manifest(target_dir)

            if manifest is not None:
                installed_files = manifest.get("installed_files", [])
                removed_count = 0

                for filename in installed_files:
                    file_path = target_dir / filename
                    if file_path.exists():
                        file_path.unlink()
                        removed_count += 1

                manifest_path = target_dir / _MANIFEST_FILENAME
                if manifest_path.exists():
                    manifest_path.unlink()

                context.logger.info(
                    f"  \U0001f5d1\ufe0f Removed {removed_count} DES plugin file(s)"
                )

                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message=f"OpenCode DES plugin uninstalled ({removed_count} removed)",
                )

            # Fallback: no manifest, check known path
            known_file = target_dir / _TARGET_FILENAME
            if known_file.exists():
                known_file.unlink()
                context.logger.warning(
                    "  \u26a0\ufe0f Removed nwave-des.ts (manifest was missing)"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="OpenCode DES plugin uninstalled (fallback, no manifest)",
                )

            context.logger.info("  \u23ed\ufe0f No OpenCode DES plugin found, skipping")
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="No OpenCode DES plugin to uninstall",
            )
        except Exception as e:
            context.logger.error(
                f"  \u274c Failed to uninstall OpenCode DES plugin: {e}"
            )
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode DES plugin uninstallation failed: {e!s}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify the OpenCode DES plugin was installed correctly.

        Checks that nwave-des.ts exists, the manifest is present,
        and the file contains the expected hook string 'tool.execute.before'.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            context.logger.info("  \U0001f50e Verifying OpenCode DES plugin...")

            target_dir = _opencode_plugins_dir()
            target_file = target_dir / _TARGET_FILENAME

            # If source doesn't exist, nothing to verify
            source_file = _find_des_source(context)
            if source_file is None:
                context.logger.info(
                    "  \u23ed\ufe0f No DES plugin source configured, verification skipped"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No DES plugin configured, verification skipped",
                )

            errors = []

            # Check file exists
            if not target_file.exists():
                errors.append(f"{_TARGET_FILENAME} not found in plugins directory")

            # Check manifest exists
            manifest = _read_manifest(target_dir)
            if manifest is None:
                errors.append(f"Manifest file {_MANIFEST_FILENAME} not found")

            # Content check: verify hook string present
            if target_file.exists():
                content = target_file.read_text()
                if _CONTENT_CHECK_STRING not in content:
                    errors.append(
                        f"{_TARGET_FILENAME} does not contain "
                        f"'{_CONTENT_CHECK_STRING}' hook registration"
                    )

            if errors:
                context.logger.error(
                    f"  \u274c OpenCode DES plugin verification failed: "
                    f"{len(errors)} issue(s)"
                )
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message=(
                        f"OpenCode DES plugin verification failed: "
                        f"{len(errors)} issue(s)"
                    ),
                    errors=errors,
                )

            context.logger.info("  \u2705 Verified OpenCode DES plugin")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="OpenCode DES plugin verification passed",
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to verify OpenCode DES plugin: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode DES plugin verification failed: {e!s}",
                errors=[str(e)],
            )
