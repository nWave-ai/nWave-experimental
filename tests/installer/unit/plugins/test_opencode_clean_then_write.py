"""Clean-then-write across the whole OpenCode asset population.

The Codex/OpenCode *agents* plugins learned clean-then-write in c7c138efa.
The same defect class survived in the two families that plugin did not
touch: OpenCode **skills** (directories, key ``installed_skills``) and
OpenCode **commands** (flat ``.md``, unprefixed names, key
``installed_commands``). A ``--dev`` install writes the private-owned
population, the next public install rewrites the manifest to the narrower
set and -- without this -- leaves everything it no longer writes on disk.

Each family asserts the same three properties:
  1. an asset the PREVIOUS manifest owns, absent from this run, is removed;
  2. an asset absent from that manifest survives (name-is-not-ownership);
  3. the manifest written equals the population actually on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.install.plugins.opencode_common import remove_manifest_owned_assets


def _write_manifest(target: Path, filename: str, key: str, names: list[str]) -> None:
    (target / filename).write_text(
        json.dumps({key: sorted(names), "version": "1.0"}, indent=2) + "\n",
        encoding="utf-8",
    )


class TestSkillsFamilyDirectoryAssets:
    """Skills are DIRECTORIES -- the suffix-based file path cannot reach them."""

    @pytest.fixture
    def target(self, tmp_path: Path) -> Path:
        target = tmp_path / "skills"
        target.mkdir()
        for name in ("nw-pricing-frameworks", "nw-voss-negotiation", "nw-discover"):
            skill = target / name
            skill.mkdir()
            (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        _write_manifest(
            target,
            ".nwave-manifest.json",
            "installed_skills",
            ["nw-pricing-frameworks", "nw-voss-negotiation", "nw-discover"],
        )
        return target

    def test_manifest_owned_private_skill_directory_is_removed(self, target: Path):
        removed = remove_manifest_owned_assets(
            target, ".nwave-manifest.json", None, manifest_key="installed_skills"
        )

        assert "nw-pricing-frameworks" in removed
        assert "nw-voss-negotiation" in removed
        assert not (target / "nw-pricing-frameworks").exists()
        assert not (target / "nw-voss-negotiation").exists()

    def test_unmanifested_nw_skill_directory_survives(self, target: Path):
        foreign = target / "nw-user-authored"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("mine\n", encoding="utf-8")

        removed = remove_manifest_owned_assets(
            target, ".nwave-manifest.json", None, manifest_key="installed_skills"
        )

        assert "nw-user-authored" not in removed
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "mine\n"

    def test_foreign_non_nw_directory_survives(self, target: Path):
        other = target / "my-own-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep\n", encoding="utf-8")

        remove_manifest_owned_assets(
            target, ".nwave-manifest.json", None, manifest_key="installed_skills"
        )

        assert (other / "SKILL.md").read_text(encoding="utf-8") == "keep\n"

    def test_wrong_manifest_key_removes_nothing(self, target: Path):
        """installed_agents is not the skills family's key -- no blind reuse."""
        removed = remove_manifest_owned_assets(target, ".nwave-manifest.json", None)

        assert removed == []
        assert (target / "nw-discover").is_dir()


class TestCommandsFamilyUnprefixedFiles:
    """OpenCode commands are ``deliver.md``/``distill.md`` -- no nw- prefix."""

    @pytest.fixture
    def target(self, tmp_path: Path) -> Path:
        target = tmp_path / "commands"
        target.mkdir()
        for name in ("deliver", "rigor", "stabilize"):
            (target / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
        _write_manifest(
            target,
            ".nwave-commands-manifest.json",
            "installed_commands",
            ["deliver", "rigor", "stabilize"],
        )
        return target

    def test_manifest_owned_retired_command_is_removed(self, target: Path):
        removed = remove_manifest_owned_assets(
            target,
            ".nwave-commands-manifest.json",
            ".md",
            manifest_key="installed_commands",
            required_prefix="",
        )

        assert removed == ["deliver", "rigor", "stabilize"]
        assert not (target / "rigor.md").exists()

    def test_unmanifested_command_survives(self, target: Path):
        (target / "my-command.md").write_text("mine\n", encoding="utf-8")

        removed = remove_manifest_owned_assets(
            target,
            ".nwave-commands-manifest.json",
            ".md",
            manifest_key="installed_commands",
            required_prefix="",
        )

        assert "my-command" not in removed
        assert (target / "my-command.md").read_text(encoding="utf-8") == "mine\n"

    def test_default_nw_prefix_guard_would_remove_nothing(self, target: Path):
        """RED witness: the agents-shaped call is inert on this family."""
        removed = remove_manifest_owned_assets(
            target,
            ".nwave-commands-manifest.json",
            ".md",
            manifest_key="installed_commands",
        )

        assert removed == []


class TestAgentsFamilyCallSiteUnchanged:
    """The c7c138efa behaviour must survive the generalisation."""

    def test_agents_default_key_and_prefix_still_remove(self, tmp_path: Path):
        target = tmp_path / "agents"
        target.mkdir()
        (target / "nw-private.toml").write_text("x\n", encoding="utf-8")
        (target / "nw-unmanifested.toml").write_text("y\n", encoding="utf-8")
        _write_manifest(
            target, ".nwave-agents-manifest.json", "installed_agents", ["nw-private"]
        )

        removed = remove_manifest_owned_assets(
            target, ".nwave-agents-manifest.json", ".toml"
        )

        assert removed == ["nw-private"]
        assert (target / "nw-unmanifested.toml").exists()


# ---------------------------------------------------------------------------
# Plugin-level: the real install() path, not just the shared helper
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_commands_plugin import (
    OpenCodeCommandsPlugin,
)
from scripts.install.plugins.opencode_skills_plugin import (
    OpenCodeSkillsPlugin,
)


def _context(tmp_path: Path) -> InstallContext:
    project_root = tmp_path / "project"
    (project_root / "nWave").mkdir(parents=True)
    (project_root / "nWave" / "framework-catalog.yaml").write_text(
        "agents: {}\n", encoding="utf-8"
    )
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=tmp_path / "framework",
    )


class TestSkillsPluginInstallIsCleanThenWrite:
    def test_stale_private_skill_from_a_previous_install_disappears(
        self, tmp_path: Path, monkeypatch
    ):
        """
        GIVEN: a target carrying a private-owned skill a --dev install wrote,
               recorded in that install's manifest
        WHEN:  a later install writes a narrower public population
        THEN:  the private skill is gone and the manifest matches the disk
        """
        context = _context(tmp_path)
        source = context.project_root / "nWave" / "skills"
        (source / "crafter").mkdir(parents=True)
        (source / "crafter" / "nw-public-skill.md").write_text(
            "---\nname: nw-public-skill\ndescription: d\n---\n\nbody\n",
            encoding="utf-8",
        )

        target = tmp_path / "home" / ".config" / "opencode" / "skills"
        target.mkdir(parents=True)
        leaked = target / "nw-pricing-frameworks"
        leaked.mkdir()
        (leaked / "SKILL.md").write_text("private IP\n", encoding="utf-8")
        foreign = target / "nw-user-authored"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("mine\n", encoding="utf-8")
        (target / ".nwave-manifest.json").write_text(
            json.dumps(
                {
                    "installed_skills": ["nw-pricing-frameworks"],
                    "version": "1.0",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: target,
        )

        result = OpenCodeSkillsPlugin().install(context)

        assert result.success
        assert not leaked.exists(), "private skill survived a public install"
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "mine\n"
        manifest = json.loads(
            (target / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        on_disk = {p.name for p in target.iterdir() if p.is_dir()}
        assert set(manifest["installed_skills"]) == on_disk - {"nw-user-authored"}


class TestCommandsPluginInstallIsCleanThenWrite:
    def test_retired_command_from_a_previous_install_disappears(
        self, tmp_path: Path, monkeypatch
    ):
        """
        GIVEN: a target carrying a command a previous install wrote and
               recorded, which the source no longer ships
        WHEN:  install() runs again
        THEN:  the retired command is gone and the manifest matches the disk
        """
        context = _context(tmp_path)
        source = context.project_root / "nWave" / "tasks" / "nw"
        source.mkdir(parents=True)
        (source / "deliver.md").write_text(
            "---\ndescription: d\n---\n\nbody\n", encoding="utf-8"
        )

        target = tmp_path / "home" / ".config" / "opencode" / "commands"
        target.mkdir(parents=True)
        (target / "rigor.md").write_text("retired\n", encoding="utf-8")
        (target / "my-command.md").write_text("mine\n", encoding="utf-8")
        (target / ".nwave-commands-manifest.json").write_text(
            json.dumps(
                {"installed_commands": ["deliver", "rigor"], "version": "1.0"}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_commands_plugin._opencode_commands_dir",
            lambda: target,
        )

        result = OpenCodeCommandsPlugin().install(context)

        assert result.success
        assert not (target / "rigor.md").exists(), "retired command still resolvable"
        assert (target / "my-command.md").read_text(encoding="utf-8") == "mine\n"
        manifest = json.loads(
            (target / ".nwave-commands-manifest.json").read_text(encoding="utf-8")
        )
        on_disk = {p.stem for p in target.glob("*.md")}
        assert set(manifest["installed_commands"]) == on_disk - {"my-command"}
