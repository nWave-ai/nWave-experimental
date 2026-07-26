"""Plugin for installing nWave Skills into Codex CLI's SKILL.md format.

Codex CLI expects skills at: $HOME/.agents/skills/{skill-name}/SKILL.md
Each skill lives in its own directory with a single SKILL.md file.

This is distinct from OpenCode (~/.config/opencode/skills/) and Claude Code
(~/.claude/skills/). The Codex skills path is under $HOME/.agents/, not
under ~/.codex/ -- per official Codex CLI documentation.

A manifest file (.nwave-manifest.json) tracks which skills nWave installed,
so uninstall() can remove only nWave skills without touching user-created ones.
"""

import json
import os
import shutil
from hashlib import sha256
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.shared.agent_catalog import detect_command_skills, load_public_agents
from scripts.shared.platform_contracts import CODEX_SKILL_FORBIDDEN_FIELDS
from scripts.shared.skill_distribution import (
    enumerate_skills,
    filter_public_skills,
)
from scripts.shared.skill_path_rewrite import rewrite_host_paths


_MANIFEST_FILENAME = ".nwave-manifest.json"

# The first public Codex installer (manifest version 1.0) omitted these two
# command skills.  This is deliberately a closed historical set: newly added
# commands must never become implicitly adoptable merely because their name
# starts with ``nw-``.  The digests are of the Codex rendering written by that
# installer, not of the Claude source asset.
_V1_OMITTED_PUBLIC_COMMAND_SKILL_DIGESTS = {
    "nw-design": "9ff2358b5b9f27b4dcd0cbb77f9b90b91913fe6ba6614f7bfb79c6b2027875b3",
    "nw-deliver": "4b24054d706d03fc6f8d84c156f07690a7151dca35c3de054f74a89b4f64b7f0",
}

# A separate public v1 bootstrap wrote an incomplete 174-skill manifest while
# installing this exact 27-skill command profile.  These are intentionally
# pinned Codex-rendered bytes, captured from that candidate representation;
# they must never be regenerated from today's source tree.  It remains a
# separate profile from the two-skill bridge above because the historical
# renderings for their overlapping names differ.
_V1_INCOMPLETE_MANIFEST_SKILL_DIGESTS = {
    "nw-buddy": "bc0d60b68de55abc36e8e273e729a36887f3808b4b6369ba58dbced76df2d0bb",
    "nw-bugfix": "0ca4c2438ded122439db8ead2abbaf0f5522ba35e5fd091855e866476a328b55",
    "nw-continue": "1fe801835ab0800b9e9c8fde3bef10b561aab9e84c55079acd888b526b24d86a",
    "nw-deliver": "ac8def71068d07bd072f9a18317ded0a206d77797335a38e77489d29d4ddfd8c",
    "nw-design": "b7b43b7189cff072c94517a8fab3e5b2688ec8386e7bbd0d4fb15b2553ded306",
    "nw-devops": "a902b5d9b876411f2b73cf1fec3f6fb8681f70ec19155d500290eeaa8eb49f71",
    "nw-diagram": "5e4f3231f3b68ba4d1af796ff31c7fc80d6db2d7cc8f0558e2fb6a3f98d0bd98",
    "nw-discover": "98daa12c8ffdc3dae9c3e5b3452f9afc107207e568ee495a8ea8f95bfdaa3b7f",
    "nw-discuss": "93d94f1d5a02293eab210028c0eb1fc4a143924dc7fd0e2c6331022a83d8f2fa",
    "nw-diverge": "95de6f0a9ab9235768bf902c0726d1284127796ce10e6377e71f2870bec114c3",
    "nw-document": "df6ddadeee36257d79806da2349a442f18c4597e39dbd2fe0f7ee8e1905e0be0",
    "nw-execute": "12472465a632d881592b391d4665ab48231ecbc0d3527898e53c5c65527402dd",
    "nw-fast-forward": "3c5c450e4b1a07ff5f886c40c6cc8b4db3abfaa227acfb2a4f3c39ff46e8d68f",
    "nw-finalize": "8e92edd03e10e14b3795714fc24bcfd8ac1c87e7d4c05a7865e4008cfe21a47b",
    "nw-forge": "019ec548e58da0640d82b989365041bfb079ada2e9396c781f7a4de500bc399a",
    "nw-hotspot": "94c30ad58319bddf587a65696d269184fb5ab336584e3a4d1763a3a2e760f546",
    "nw-mikado": "9279af248efa74789f1ebf03d3ecd97bacd96c77adbd60dfe86ac30bb06fe7e9",
    "nw-new": "0747cf3379c1f311fa5ddfdcb4f16c62320995cca997e0c07256caa3729c75c9",
    "nw-optimize-tests": "051b21677ae1506852393832c0903e1b9b34a658ea9fde3ad1db3ac5d3338e21",
    "nw-research": "87be14adc1430ddd1b042f41023799a2b2f87c57d0e08fdfb6fbad1d821902be",
    "nw-review": "e5233e5218bdc2d9408b81e9c0dbfd57939ad8b3ca7a280945eb9d7de7c24623",
    "nw-rigor": "f0683d0c8118c189bc6d3b2c1f5499e4dd2ae8c310fc43a2ed69b809f18f219b",
    "nw-roadmap": "afbe4234a6d4c4c40a96c336e0b85528e968f258922af3021050b3dfd6c248f2",
    "nw-root-why": "3e3f460531b46c3e780cc992f81d8bb229784983a01f49c766d75e9b94b07f68",
    "nw-spike": "51f0c0b27c941ef1f2e3613aecde8afad3db6e60c44b1f49fe2219d05598868c",
    "nw-throughput": "6fbe991edc39410df327803ceb3a1c5e48f9e55e08573de1870ff71b6378cfed",
    "nw-update": "c6c39bac491e1fc852c06e3e760c36ea992d62cb617f2c41a11fff3048d2060a",
}

_V1_OMITTED_SKILL_PROFILES = (
    _V1_OMITTED_PUBLIC_COMMAND_SKILL_DIGESTS,
    _V1_INCOMPLETE_MANIFEST_SKILL_DIGESTS,
)


def legacy_v1_omitted_command_skills(
    skills_dir: Path, manifest: object
) -> set[str] | None:
    """Return the exact, byte-proven v1 omissions, or refuse the witness.

    A legacy manifest is only a catalogue witness when it retains its exact
    three-field v1 shape.  Each omitted skill must be one of the closed
    historical set and its complete on-disk tree must be the single trusted
    ``SKILL.md`` asset with the pinned Codex-rendered digest.  This prevents a
    future command, an added sidecar file, a symlink, or a local edit from
    acquiring installer ownership through a name-shaped rule.
    """
    if not (
        isinstance(manifest, dict)
        and set(manifest) == {"installed_skills", "version"}
        and manifest.get("version") == "1.0"
        and isinstance(manifest.get("installed_skills"), list)
        and all(
            isinstance(name, str) and name.startswith("nw-") and Path(name).name == name
            for name in manifest["installed_skills"]
        )
        and len(manifest["installed_skills"]) == len(set(manifest["installed_skills"]))
    ):
        return None

    listed = set(manifest["installed_skills"])
    candidates = {
        candidate.name: candidate
        for candidate in skills_dir.glob("nw-*")
        if candidate.name not in listed
    }

    # Exact membership is part of each fingerprint.  A small test/bootstrap
    # manifest may already list a member of the historical profile, but the
    # complete profile must still be present and byte-proven before any of its
    # remaining members are adopted.  This never promotes a discovered name:
    # the only returned names are the static profile's unlisted members.
    for profile in _V1_OMITTED_SKILL_PROFILES:
        unlisted_profile = set(profile) - listed
        if not unlisted_profile or set(candidates) != unlisted_profile:
            continue
        for name, expected_digest in profile.items():
            candidate = skills_dir / name
            skill = candidate / "SKILL.md"
            try:
                trusted = (
                    not candidate.is_symlink()
                    and candidate.is_dir()
                    and list(candidate.iterdir()) == [skill]
                    and not skill.is_symlink()
                    and skill.is_file()
                    and sha256(skill.read_bytes()).hexdigest() == expected_digest
                )
            except OSError:
                trusted = False
            if not trusted:
                break
        else:
            return unlisted_profile
    return None


def _codex_skills_dir() -> Path:
    """Return the Codex CLI skills target directory.

    Codex skills live at $HOME/.agents/skills/ -- note this is NOT under
    ~/.codex/; it is a sibling of ~/.codex/ at the $HOME level.
    CODEX_HOME only overrides ~/.codex/ (config dir); it has no effect on
    the skills path.

    For testing isolation the env var NWAVE_AGENTS_HOME overrides the
    resolved $HOME in the returned path.  Production code never sets this
    variable, so production semantics are always $HOME/.agents/skills/.

    Returns:
        Path to $HOME/.agents/skills/ (or $NWAVE_AGENTS_HOME/.agents/skills/)
    """
    agents_home_override = os.environ.get("NWAVE_AGENTS_HOME")
    if agents_home_override:
        return Path(agents_home_override) / ".agents" / "skills"
    return Path.home() / ".agents" / "skills"


def _codex_config_dir() -> Path:
    """Return the Codex CLI configuration directory.

    Returns:
        Path to ~/.codex/ (or $CODEX_HOME if set)
    """
    override = os.environ.get("CODEX_HOME")
    return Path(override) if override else Path.home() / ".codex"


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


def _strip_forbidden_fields(content: str) -> str:
    """Remove Claude Code-only frontmatter fields from skill content.

    Strips YAML frontmatter fields listed in CODEX_SKILL_FORBIDDEN_FIELDS.
    Only operates within the frontmatter block (between --- delimiters).
    Body content is never modified.

    Args:
        content: Full skill file content with YAML frontmatter

    Returns:
        Content with forbidden fields removed from frontmatter
    """
    if not content.startswith("---"):
        return content

    end_index = content.find("---", 3)
    if end_index == -1:
        return content

    frontmatter = content[4:end_index]
    body = content[end_index:]

    filtered_lines = [
        line
        for line in frontmatter.splitlines(keepends=True)
        if not any(
            line.startswith(f"{field}:") for field in CODEX_SKILL_FORBIDDEN_FIELDS
        )
    ]

    return "---\n" + "".join(filtered_lines) + body


def _write_manifest(target_dir: Path, installed_skill_names: list[str]) -> None:
    """Write the manifest file tracking nWave-installed skills.

    Args:
        target_dir: Codex skills directory
        installed_skill_names: List of installed skill directory names
    """
    manifest = {
        "installed_skills": sorted(installed_skill_names),
        "version": "1.0",
    }
    manifest_path = target_dir / _MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _read_manifest(target_dir: Path) -> dict | None:
    """Read the manifest file if it exists.

    Args:
        target_dir: Codex skills directory

    Returns:
        Parsed manifest dict, or None if not found
    """
    manifest_path = target_dir / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


class CodexSkillsPlugin(InstallationPlugin):
    """Plugin for installing nWave Skills into Codex CLI's SKILL.md format."""

    def __init__(self) -> None:
        """Initialize Codex skills plugin with name and priority."""
        super().__init__(name="codex-skills", priority=50)

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Check whether Codex CLI is present; skip gracefully if not.

        Detection: ~/.codex/ directory exists OR `codex` binary in PATH.
        If neither is found the plugin returns success with a skip message --
        the absence of Codex is not an error.

        Args:
            context: InstallContext (unused for detection, but required by ABC)

        Returns:
            PluginResult with success=True always (skip or proceed)
        """
        codex_dir = _codex_config_dir()
        codex_binary = shutil.which("codex") is not None
        if (
            "codex" not in context.target_platforms
            and not codex_dir.exists()
            and not codex_binary
        ):
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Codex CLI not detected, skipping skills installation",
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Codex CLI prerequisites validated",
        )

    def install(self, context: InstallContext) -> PluginResult:
        """Install skills from nWave/skills/ to $HOME/.agents/skills/.

        Copies each source SKILL.md to the Codex skills directory, stripping
        Claude Code-only frontmatter fields. A manifest tracks installed skill
        names for safe uninstallation.

        Walking-skeleton scope: copies ALL public skills with no name transform
        (flat namespace, no collision resolution needed for the skeleton).

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            # Check prerequisites first; skip if Codex not present
            prereq = self.validate_prerequisites(context)
            if "skip" in prereq.message.lower():
                return prereq

            context.logger.info("  Installing Codex skills...")

            skills_source = _find_skills_source(context)
            if skills_source is None:
                context.logger.info("  No skills directory found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No skills to install (source directory not found)",
                )

            target_dir = _codex_skills_dir()
            target_dir.mkdir(parents=True, exist_ok=True)

            public_agents = (
                set()
                if context.dev_mode
                else load_public_agents(context.project_root / "nWave")
            )

            from scripts.shared.agent_catalog import build_ownership_map

            agents_dir = context.project_root / "nWave" / "agents"
            ownership_map = (
                build_ownership_map(agents_dir) if agents_dir.exists() else {}
            )

            entries = enumerate_skills(skills_source)
            command_skills = (
                set() if context.dev_mode else detect_command_skills(skills_source)
            )
            entries = filter_public_skills(
                entries, public_agents, ownership_map, command_skills
            )

            installed_names: list[str] = []
            installed_files: list[Path] = []

            for entry in entries:
                skill_target_dir = target_dir / entry.name
                if skill_target_dir.exists():
                    shutil.rmtree(skill_target_dir)

                if entry.source_path.is_dir():
                    shutil.copytree(entry.source_path, skill_target_dir)
                    target_file = skill_target_dir / "SKILL.md"
                else:
                    skill_target_dir.mkdir(parents=True)
                    target_file = skill_target_dir / "SKILL.md"
                    shutil.copy2(entry.source_path, target_file)

                content = target_file.read_text(encoding="utf-8")
                content = _strip_forbidden_fields(content)
                content = rewrite_host_paths(content, "codex")
                target_file.write_text(content, encoding="utf-8")

                installed_names.append(entry.name)
                installed_files.append(target_file)

            _write_manifest(target_dir, installed_names)

            context.logger.info(
                f"  Codex skills installed ({len(installed_names)} skills)"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Codex skills installed successfully ({len(installed_names)} skills)",
                installed_files=installed_files,
            )

        except Exception as e:
            context.logger.error(f"  Failed to install Codex skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex skills installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall only nWave-installed Codex skills using manifest.

        Reads the manifest to determine which skills were installed by nWave,
        removes only those, and leaves user-created skills untouched.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  Uninstalling Codex skills...")

            target_dir = _codex_skills_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                context.logger.info("  No Codex skills manifest found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No Codex skills to uninstall (no manifest found)",
                )

            installed_skills = manifest.get("installed_skills", [])
            removed_count = 0

            for skill_name in installed_skills:
                skill_dir = target_dir / skill_name
                if skill_dir.exists():
                    shutil.rmtree(skill_dir)
                    removed_count += 1

            manifest_path = target_dir / _MANIFEST_FILENAME
            if manifest_path.exists():
                manifest_path.unlink()

            context.logger.info(f"  Removed {removed_count} Codex skills")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Codex skills uninstalled ({removed_count} removed)",
            )

        except Exception as e:
            context.logger.error(f"  Failed to uninstall Codex skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex skills uninstallation failed: {e!s}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify Codex skills were installed correctly.

        Checks that each skill listed in the manifest has a valid SKILL.md file.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            context.logger.info("  Verifying Codex skills...")

            target_dir = _codex_skills_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                skills_source = _find_skills_source(context)
                if skills_source is None:
                    context.logger.info("  No Codex skills to verify (none configured)")
                    return PluginResult(
                        success=True,
                        plugin_name=self.name,
                        message="No Codex skills configured, verification skipped",
                    )

                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Codex skills verification failed: manifest not found",
                    errors=["Manifest file .nwave-manifest.json not found"],
                )

            installed_skills = manifest.get("installed_skills", [])
            missing_skills: list[str] = []
            verified_count = 0

            for skill_name in installed_skills:
                skill_md = target_dir / skill_name / "SKILL.md"
                if not skill_md.exists():
                    missing_skills.append(f"{skill_name}/SKILL.md not found")
                else:
                    verified_count += 1

            if missing_skills:
                context.logger.error(
                    f"  Codex skills verification failed: {len(missing_skills)} missing"
                )
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message=(
                        f"Codex skills verification failed: "
                        f"{len(missing_skills)} skills missing SKILL.md"
                    ),
                    errors=missing_skills,
                )

            context.logger.info(f"  Verified {verified_count} Codex skills")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Codex skills verification passed ({verified_count} skills)",
            )

        except Exception as e:
            context.logger.error(f"  Failed to verify Codex skills: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex skills verification failed: {e!s}",
                errors=[str(e)],
            )
