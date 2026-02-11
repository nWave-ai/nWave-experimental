"""
Plugin for installing Skills into ~/.claude/skills/nw/.

Skills provide on-demand deep knowledge that Claude Code loads progressively:
- Level 1: Skill description loaded with agent (~50 tokens each)
- Level 2: Full Skill content loaded when Claude determines relevance
- Level 3: Referenced files loaded as needed

The nw/ namespace separates nWave skills from other Claude Code skills.
"""

import shutil
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)


class SkillsPlugin(InstallationPlugin):
    """Plugin for installing Skills into the Claude Code skills directory."""

    def __init__(self):
        """Initialize skills plugin with name and priority."""
        super().__init__(name="skills", priority=35)

    def install(self, context: InstallContext) -> PluginResult:
        """Install skills from nWave/skills/ to ~/.claude/skills/nw/.

        Copies skill directories preserving structure. Each subdirectory
        under nWave/skills/ becomes a skill group under ~/.claude/skills/nw/.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  📦 Installing skills...")

            # dist/ layout: skills/nw/ (build_dist.py adds nw/ namespace)
            # source layout: nWave/skills/
            dist_skills = context.framework_source / "skills" / "nw"
            if dist_skills.exists():
                skills_source = dist_skills
            else:
                skills_source = context.project_root / "nWave" / "skills"

            if not skills_source.exists():
                context.logger.info("  ⏭️ No skills directory found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No skills to install (source directory not found)",
                )

            # Target: ~/.claude/skills/nw/
            skills_target = context.claude_dir / "skills" / "nw"
            skills_target.mkdir(parents=True, exist_ok=True)

            installed_files = []
            installed_count = 0

            # Copy each skill group directory
            for item in skills_source.iterdir():
                if not item.is_dir():
                    continue

                target_dir = skills_target / item.name

                # Remove existing and replace
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

                # Count installed files
                for skill_file in target_dir.rglob("*.md"):
                    installed_files.append(str(skill_file))
                    installed_count += 1

            context.logger.info(f"  ✅ Skills installed ({installed_count} files)")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Skills installed successfully ({installed_count} files)",
                installed_files=[Path(f) for f in installed_files],
            )
        except Exception as e:
            context.logger.error(f"  ❌ Failed to install skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Skills installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall skills by removing ~/.claude/skills/nw/.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  🗑️ Uninstalling skills...")

            skills_nw_dir = context.claude_dir / "skills" / "nw"

            if not skills_nw_dir.exists():
                context.logger.info("  ⏭️ No skills directory found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No skills to uninstall (directory not found)",
                )

            shutil.rmtree(skills_nw_dir)
            context.logger.info("  🗑️ Removed skills/nw directory")

            # Remove parent skills directory if empty
            skills_dir = context.claude_dir / "skills"
            if skills_dir.exists():
                try:
                    if not any(skills_dir.iterdir()):
                        skills_dir.rmdir()
                        context.logger.info("  🗑️ Removed empty skills directory")
                except OSError:
                    pass

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Skills uninstalled successfully",
            )
        except Exception as e:
            context.logger.error(f"  ❌ Failed to uninstall skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Skills uninstallation failed: {e!s}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify skills were installed correctly.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            context.logger.info("  🔎 Verifying skills...")

            skills_target = context.claude_dir / "skills" / "nw"

            if not skills_target.exists():
                # Skills are optional — if source didn't exist, target won't either
                dist_skills = context.framework_source / "skills" / "nw"
                skills_source = context.project_root / "nWave" / "skills"
                if not dist_skills.exists() and not skills_source.exists():
                    context.logger.info("  ⏭️ No skills to verify (none configured)")
                    return PluginResult(
                        success=True,
                        plugin_name=self.name,
                        message="No skills configured, verification skipped",
                    )

                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Skills verification failed: target directory not found",
                    errors=["Target directory not found"],
                )

            # Count skill files
            skill_files = list(skills_target.rglob("*.md"))

            if not skill_files:
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Skills verification failed: no skill files found",
                    errors=["No .md files in skills target directory"],
                )

            # List skill groups
            skill_groups = [d.name for d in skills_target.iterdir() if d.is_dir()]

            context.logger.info(
                f"  ✅ Verified {len(skill_files)} skill files "
                f"in {len(skill_groups)} groups: {', '.join(skill_groups)}"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Skills verification passed ({len(skill_files)} files in {len(skill_groups)} groups)",
            )
        except Exception as e:
            context.logger.error(f"  ❌ Failed to verify skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Skills verification failed: {e!s}",
                errors=[str(e)],
            )
