"""
Plugin for cleaning up legacy commands from ~/.claude/commands/nw/.

Commands have been migrated to skill format (nw-*/SKILL.md) as of v2.8.0.
This plugin now only removes the old commands directory during installation
to ensure a clean upgrade path.
"""

import shutil

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)


class CommandsPlugin(InstallationPlugin):
    """Plugin for cleaning up legacy commands during upgrade."""

    def __init__(self):
        """Initialize commands plugin with name and priority."""
        super().__init__(name="commands", priority=20)

    def install(self, context: InstallContext) -> PluginResult:
        """Remove legacy commands/nw/ directory if it exists.

        Commands are now installed as skills by the skills plugin.
        This plugin ensures old command files are cleaned up and
        detects cross-installation conflicts (CLI + plugin).

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure of cleanup
        """
        try:
            target_commands_dir = context.claude_dir / "commands" / "nw"
            messages = []

            if target_commands_dir.exists():
                count = len(list(target_commands_dir.glob("*.md")))
                shutil.rmtree(target_commands_dir)
                context.logger.info(
                    f"  \U0001f5d1\ufe0f Removed legacy commands/nw/ ({count} files)"
                )

                # Remove parent commands/ if empty
                commands_dir = context.claude_dir / "commands"
                if commands_dir.exists() and not any(commands_dir.iterdir()):
                    commands_dir.rmdir()

                messages.append(f"Legacy commands cleaned up ({count} files removed)")
            else:
                messages.append("No legacy commands to clean up")

            # Detect cross-installation: CLI commands (skills/nw-*) coexisting
            # with plugin-installed commands (plugins/nw/)
            cross_install_warning = self._detect_cross_install(context)
            if cross_install_warning:
                messages.append(cross_install_warning)

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=". ".join(messages),
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to clean up commands: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Commands cleanup failed: {e!s}",
                errors=[str(e)],
            )

    def _detect_cross_install(self, context: InstallContext) -> str | None:
        """Detect when both CLI and plugin command formats coexist.

        CLI commands appear as skills/nw-* directories.
        Plugin commands appear via plugins/nw/ directory.

        Returns:
            Warning message if both formats detected, None otherwise.
        """
        skills_dir = context.claude_dir / "skills"
        plugin_dir = context.claude_dir / "plugins" / "nw"

        has_cli_commands = skills_dir.exists() and any(
            d.is_dir() and d.name.startswith("nw-") for d in skills_dir.iterdir()
        )
        has_plugin = plugin_dir.exists()

        if has_cli_commands and has_plugin:
            context.logger.warning(
                "  \u26a0\ufe0f Cross-installation detected: both CLI (nw-*) "
                "and plugin (nw:*) commands are installed"
            )
            return (
                "Cross-install conflict: both CLI (nw-*) and plugin (nw:*) "
                "commands detected. Please remove one installation method "
                "to avoid duplicate commands"
            )
        return None

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify legacy commands directory is gone.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        target_commands_dir = context.claude_dir / "commands" / "nw"

        if target_commands_dir.exists():
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message="Legacy commands/nw/ still exists after cleanup",
                errors=["Legacy commands directory not removed"],
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="No legacy commands present (migrated to skills)",
        )
