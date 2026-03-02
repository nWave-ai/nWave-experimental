"""
Plugin for installing nWave Skills into OpenCode's SKILL.md format.

OpenCode expects skills at: ~/.config/opencode/skills/{skill-name}/SKILL.md
Each skill lives in its own directory with a single SKILL.md file.

When a skill name appears in multiple agent groups (e.g. critique-dimensions
exists in software-crafter, agent-builder, etc.), the skill directory is
prefixed with the agent group name to avoid collisions.

A manifest file (.nwave-manifest.json) tracks which skills nWave installed,
so uninstall() can remove only nWave skills without touching user-created ones.
"""

import json
import re
import shutil
from collections import Counter
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)


_MANIFEST_FILENAME = ".nwave-manifest.json"
_SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_FRONTMATTER_NAME_PATTERN = re.compile(r"^(name:\s*).+$", re.MULTILINE)
_MAX_SKILL_NAME_LENGTH = 64


def _opencode_skills_dir() -> Path:
    """Return the OpenCode skills target directory.

    Returns:
        Path to ~/.config/opencode/skills/
    """
    return Path.home() / ".config" / "opencode" / "skills"


def _find_skills_source(context: InstallContext) -> Path | None:
    """Locate the skills source directory from dist or project layout.

    Args:
        context: InstallContext with framework_source and project_root

    Returns:
        Path to the skills source directory, or None if not found
    """
    dist_skills = context.framework_source / "skills" / "nw"
    if dist_skills.exists():
        return dist_skills

    project_skills = context.project_root / "nWave" / "skills"
    if project_skills.exists():
        return project_skills

    return None


def _collect_skill_entries(skills_source: Path) -> list[tuple[str, str, Path]]:
    """Collect all (agent_name, skill_name, file_path) triples from source.

    Args:
        skills_source: Path to the skills source directory

    Returns:
        List of (agent_name, skill_name, file_path) tuples
    """
    entries = []
    for agent_dir in sorted(skills_source.iterdir()):
        if not agent_dir.is_dir():
            continue
        for skill_file in sorted(agent_dir.glob("*.md")):
            entries.append((agent_dir.name, skill_file.stem, skill_file))
    return entries


def _detect_duplicate_names(
    entries: list[tuple[str, str, Path]],
) -> set[str]:
    """Find skill names that appear in more than one agent group.

    Args:
        entries: List of (agent_name, skill_name, file_path) tuples

    Returns:
        Set of skill names that have collisions across agent groups
    """
    name_counts = Counter(skill_name for _, skill_name, _ in entries)
    return {name for name, count in name_counts.items() if count > 1}


def _resolve_target_name(
    agent_name: str,
    skill_name: str,
    duplicate_names: set[str],
) -> str:
    """Compute the target directory name for a skill, prefixing if needed.

    Args:
        agent_name: Agent group name (e.g. 'software-crafter')
        skill_name: Skill name without extension (e.g. 'critique-dimensions')
        duplicate_names: Set of skill names that collide across groups

    Returns:
        Resolved directory name (e.g. 'software-crafter-critique-dimensions'
        for duplicates, or 'tdd-methodology' for unique names)
    """
    if skill_name in duplicate_names:
        return f"{agent_name}-{skill_name}"
    return skill_name


def _validate_skill_name(name: str) -> bool:
    """Validate a skill name against OpenCode's naming requirements.

    OpenCode requires: ^[a-z0-9]+(-[a-z0-9]+)*$ with max 64 chars.

    Args:
        name: Skill directory name to validate

    Returns:
        True if the name is valid
    """
    return (
        len(name) <= _MAX_SKILL_NAME_LENGTH
        and _SKILL_NAME_PATTERN.match(name) is not None
    )


def _rewrite_frontmatter_name(content: str, new_name: str) -> str:
    """Replace the name field in YAML frontmatter with a new value.

    OpenCode uses the frontmatter name: field to identify skills, not the
    directory name. When a skill is prefixed to avoid collisions, the
    frontmatter must match.

    Args:
        content: Full file content with YAML frontmatter
        new_name: The new skill name to set

    Returns:
        Content with the name: field updated
    """
    return _FRONTMATTER_NAME_PATTERN.sub(rf"\g<1>{new_name}", content, count=1)


def _write_manifest(
    target_dir: Path,
    installed_skill_names: list[str],
) -> None:
    """Write the manifest file tracking nWave-installed skills.

    Args:
        target_dir: OpenCode skills directory
        installed_skill_names: List of installed skill directory names
    """
    manifest = {
        "installed_skills": sorted(installed_skill_names),
        "version": "1.0",
    }
    manifest_path = target_dir / _MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _read_manifest(target_dir: Path) -> dict | None:
    """Read the manifest file if it exists.

    Args:
        target_dir: OpenCode skills directory

    Returns:
        Parsed manifest dict, or None if not found
    """
    manifest_path = target_dir / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())


class OpenCodeSkillsPlugin(InstallationPlugin):
    """Plugin for installing nWave Skills into OpenCode's SKILL.md format."""

    def __init__(self):
        """Initialize OpenCode skills plugin with name and priority."""
        super().__init__(name="opencode-skills", priority=36)

    def install(self, context: InstallContext) -> PluginResult:
        """Install skills from nWave/skills/ as OpenCode SKILL.md files.

        Transforms each source skill file into the OpenCode directory layout:
        source: nWave/skills/{agent}/{skill}.md
        target: ~/.config/opencode/skills/{resolved-name}/SKILL.md

        Skills with duplicate names across agent groups are prefixed with
        the agent group name. A manifest tracks installed skills for safe
        uninstallation.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  \U0001f4e6 Installing OpenCode skills...")

            skills_source = _find_skills_source(context)
            if skills_source is None:
                context.logger.info(
                    "  \u23ed\ufe0f No skills directory found, skipping"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No skills to install (source directory not found)",
                )

            target_dir = _opencode_skills_dir()
            target_dir.mkdir(parents=True, exist_ok=True)

            entries = _collect_skill_entries(skills_source)
            duplicate_names = _detect_duplicate_names(entries)

            installed_names = []
            installed_files = []
            skipped = []

            for agent_name, skill_name, source_file in entries:
                resolved_name = _resolve_target_name(
                    agent_name, skill_name, duplicate_names
                )

                if not _validate_skill_name(resolved_name):
                    skipped.append(
                        f"{agent_name}/{skill_name} -> {resolved_name} "
                        f"(invalid OpenCode name)"
                    )
                    continue

                skill_target_dir = target_dir / resolved_name
                if skill_target_dir.exists():
                    shutil.rmtree(skill_target_dir)
                skill_target_dir.mkdir(parents=True)

                target_file = skill_target_dir / "SKILL.md"
                content = source_file.read_text()
                if resolved_name != skill_name:
                    content = _rewrite_frontmatter_name(content, resolved_name)
                target_file.write_text(content)

                installed_names.append(resolved_name)
                installed_files.append(target_file)

            _write_manifest(target_dir, installed_names)

            if skipped:
                for skip_msg in skipped:
                    context.logger.info(f"  \u26a0\ufe0f Skipped: {skip_msg}")

            context.logger.info(
                f"  \u2705 OpenCode skills installed ({len(installed_names)} skills)"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=(
                    f"OpenCode skills installed successfully "
                    f"({len(installed_names)} skills)"
                ),
                installed_files=installed_files,
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to install OpenCode skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode skills installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall only nWave-installed OpenCode skills using manifest.

        Reads the manifest to determine which skills were installed by nWave,
        removes only those, and leaves user-created skills untouched.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  \U0001f5d1\ufe0f Uninstalling OpenCode skills...")

            target_dir = _opencode_skills_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                context.logger.info(
                    "  \u23ed\ufe0f No OpenCode skills manifest found, skipping"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No OpenCode skills to uninstall (no manifest found)",
                )

            installed_skills = manifest.get("installed_skills", [])
            removed_count = 0

            for skill_name in installed_skills:
                skill_dir = target_dir / skill_name
                if skill_dir.exists():
                    shutil.rmtree(skill_dir)
                    removed_count += 1

            # Remove the manifest itself
            manifest_path = target_dir / _MANIFEST_FILENAME
            if manifest_path.exists():
                manifest_path.unlink()

            context.logger.info(
                f"  \U0001f5d1\ufe0f Removed {removed_count} OpenCode skills"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"OpenCode skills uninstalled ({removed_count} removed)",
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to uninstall OpenCode skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode skills uninstallation failed: {e!s}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify OpenCode skills were installed correctly.

        Checks that each skill listed in the manifest has a valid SKILL.md
        file with YAML frontmatter.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            context.logger.info("  \U0001f50e Verifying OpenCode skills...")

            target_dir = _opencode_skills_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                # Check if source exists to distinguish "nothing to install"
                # from "install was skipped/failed"
                skills_source = _find_skills_source(context)
                if skills_source is None:
                    context.logger.info(
                        "  \u23ed\ufe0f No OpenCode skills to verify (none configured)"
                    )
                    return PluginResult(
                        success=True,
                        plugin_name=self.name,
                        message=("No OpenCode skills configured, verification skipped"),
                    )

                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message=("OpenCode skills verification failed: manifest not found"),
                    errors=["Manifest file .nwave-manifest.json not found"],
                )

            installed_skills = manifest.get("installed_skills", [])
            missing_skills = []
            verified_count = 0

            for skill_name in installed_skills:
                skill_md = target_dir / skill_name / "SKILL.md"
                if not skill_md.exists():
                    missing_skills.append(f"{skill_name}/SKILL.md not found")
                else:
                    verified_count += 1

            if missing_skills:
                context.logger.error(
                    f"  \u274c OpenCode skills verification failed: "
                    f"{len(missing_skills)} missing"
                )
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message=(
                        f"OpenCode skills verification failed: "
                        f"{len(missing_skills)} skills missing SKILL.md"
                    ),
                    errors=missing_skills,
                )

            context.logger.info(f"  \u2705 Verified {verified_count} OpenCode skills")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=(
                    f"OpenCode skills verification passed ({verified_count} skills)"
                ),
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to verify OpenCode skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode skills verification failed: {e!s}",
                errors=[str(e)],
            )
