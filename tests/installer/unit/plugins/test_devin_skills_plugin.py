"""Unit tests for Devin CLI skills installer plugin.

Author: Mani Sarkar
Created: 2026-10-11
Scope: DevinSkillsPlugin install / uninstall / verify lifecycle, path isolation,
       manifest ownership, foreign-collision refusal, and prerequisite detection.

Tests validate that:
- validate_prerequisites() skips gracefully when Devin CLI is not detected
- validate_prerequisites() proceeds when Devin config dir exists
- install() copies SKILL.md files into ~/.config/devin/skills/{name}/SKILL.md
- install() rewrites host paths for Devin
- install() writes a manifest tracking installed skill names
- verify() returns success after a successful install
- uninstall() removes only nWave-installed skills, preserving user-created ones

State-delta discipline: install/uninstall tests assert filesystem state (present
/ absent bytes), never log messages. Ownership is manifest-driven; foreign and
private entries survive untouched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.devin_skills_plugin import (
    DevinSkillsPlugin,
    _find_skills_source,
)
from scripts.shared.install_paths import devin_skills_dir


@pytest.fixture(autouse=True)
def _isolated_devin_home(monkeypatch, tmp_path):
    """Pin every Devin path resolver to an isolated fake home via DEVIN_CONFIG_DIR."""
    devin_config = tmp_path / "devin_config"
    devin_config.mkdir()
    monkeypatch.setenv("DEVIN_CONFIG_DIR", str(devin_config))
    return devin_config


class _Logger:
    """Minimal logger recording info/error lines for assertions."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        self.lines.append(str(message))

    def error(self, message: str) -> None:
        self.lines.append(str(message))

    def warn(self, message: str) -> None:
        self.lines.append(str(message))


def _make_context(
    tmp_path: Path,
    *,
    dev_mode: bool = True,
    project_root: Path | None = None,
) -> tuple[InstallContext, Path, Path]:
    """Create an InstallContext with a minimal skill source layout.

    The project layout mirrors a real checkout: <project>/nWave/skills holds
    skill dirs. dev_mode=True bypasses public-agent filtering so all skills
    are treated as installable.

    Returns:
        Tuple of (context, skills_source, target_dir).
    """
    project = project_root if project_root is not None else tmp_path / "project"
    nwave_root = project / "nWave"
    skills_source = nwave_root / "skills"
    skills_source.mkdir(parents=True, exist_ok=True)
    agents_dir = nwave_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    if not dev_mode:
        (agents_dir / "nw-sample.md").write_text(
            "---\nname: nw-sample\ndescription: Sample role.\n"
            "skills:\n  - nw-sample-skill\n---\n\nSample body.\n",
            encoding="utf-8",
        )
        (nwave_root / "framework-catalog.yaml").write_text(
            "version: 1\nagents:\n  sample:\n    public: true\n",
            encoding="utf-8",
        )

    context = InstallContext(
        claude_dir=tmp_path / "claude",
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=_Logger(),
        project_root=project,
        framework_source=nwave_root,
        dev_mode=dev_mode,
        target_platforms={"devin"},
    )
    return context, skills_source, devin_skills_dir()


def _create_skill(
    skills_source: Path,
    name: str,
    description: str = "Sample skill.",
    *,
    user_invocable: bool = False,
) -> Path:
    """Write a minimal skill directory with SKILL.md into skills_source."""
    skill_dir = skills_source / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    extra = "\nuser-invocable: true" if user_invocable else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}{extra}\n---\n\n"
        f"Read ~/.claude/skills/{name}/references for details.\n",
        encoding="utf-8",
    )
    return skill_dir


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------


class TestFindSkillsSource:
    """_find_skills_source: resolves from project checkout layout."""

    def test_finds_project_skills_dir(self, tmp_path):
        """
        Scenario: Devin skills source resolves correctly from a checkout layout.
        Slice: source resolution. Given a context pointing at a project with
        nWave/skills/, when _find_skills_source() is called, then it returns
        that directory.
        """
        ### Given
        context, skills_source, _ = _make_context(tmp_path)

        ### When
        result = _find_skills_source(context)

        ### Then
        assert result == skills_source

    def test_returns_none_when_absent(self, tmp_path):
        """
        Scenario: No source directory means no skills to install.
        Slice: source resolution. Given a context pointing at a project with no
        nWave/skills/, when _find_skills_source() is called, then it returns None.
        """
        ### Given
        context = InstallContext(
            claude_dir=tmp_path,
            scripts_dir=tmp_path,
            templates_dir=tmp_path,
            logger=_Logger(),
            project_root=tmp_path / "empty",
            framework_source=tmp_path / "dist",
        )

        ### When
        result = _find_skills_source(context)

        ### Then
        assert result is None


# ---------------------------------------------------------------------------
# Prerequisite detection
# ---------------------------------------------------------------------------


class TestValidatePrerequisites:
    """validate_prerequisites: skip vs proceed based on Devin detection."""

    def test_skips_gracefully_when_devin_not_detected(self, tmp_path, monkeypatch):
        """
        Scenario: Devin is absent from the system — install skips without error.
        Slice: prerequisite detection. Given DEVIN_CONFIG_DIR does not exist AND
        no devin binary is in PATH AND devin is not in target_platforms, when
        validate_prerequisites() is called, then it returns success with a skip
        message.
        """
        ### Given
        context = InstallContext(
            claude_dir=tmp_path,
            scripts_dir=tmp_path,
            templates_dir=tmp_path,
            logger=_Logger(),
            project_root=tmp_path / "proj",
            framework_source=tmp_path / "dist",
            target_platforms={"claude_code"},
        )
        absent_dir = tmp_path / "no_devin_config"
        monkeypatch.setenv("DEVIN_CONFIG_DIR", str(absent_dir))
        monkeypatch.setattr(
            "scripts.install.plugins.devin_skills_plugin._which",
            lambda _name: None,
        )

        ### When
        result = DevinSkillsPlugin().validate_prerequisites(context)

        ### Then
        assert result.success is True
        assert (
            "skip" in result.message.lower() or "not detected" in result.message.lower()
        )

    def test_proceeds_when_devin_config_dir_exists(self, tmp_path):
        """
        Scenario: Devin config directory is present — install can proceed.
        Slice: prerequisite detection. Given DEVIN_CONFIG_DIR exists, when
        validate_prerequisites() is called, then it returns success with a
        non-skip message.
        """
        ### Given
        context, _, _ = _make_context(tmp_path)

        ### When
        result = DevinSkillsPlugin().validate_prerequisites(context)

        ### Then
        assert result.success is True
        assert "validated" in result.message.lower()

    def test_proceeds_when_devin_in_target_platforms(self, tmp_path, monkeypatch):
        """
        Scenario: Devin was explicitly targeted — install proceeds regardless.
        Slice: prerequisite detection. Given devin is in target_platforms and no
        config dir exists, when validate_prerequisites() is called, then it
        proceeds and returns validated.
        """
        ### Given
        absent_dir = tmp_path / "no_devin_config"
        monkeypatch.setenv("DEVIN_CONFIG_DIR", str(absent_dir))
        context = InstallContext(
            claude_dir=tmp_path,
            scripts_dir=tmp_path,
            templates_dir=tmp_path,
            logger=_Logger(),
            project_root=tmp_path / "proj",
            framework_source=tmp_path / "dist",
            target_platforms={"devin"},
        )

        ### When
        result = DevinSkillsPlugin().validate_prerequisites(context)

        ### Then
        assert result.success is True
        assert "validated" in result.message.lower()


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


class TestInstallCreatesSkillDirs:
    """install(): copies public skills into ~/.config/devin/skills/."""

    def test_install_writes_skill_and_rewrites_paths(self, tmp_path):
        """
        Scenario: Skill body with ~/.claude/ paths is rewritten for Devin.
        Slice: Devin skills install. Given a skill whose SKILL.md references
        ~/.claude/skills/, when install() is called, then the installed copy
        rewrites that path and the original source is unchanged.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        ### When
        result = DevinSkillsPlugin().install(context)

        ### Then
        assert result.success, result.message
        installed = target_dir / "nw-sample-skill" / "SKILL.md"
        assert installed.is_file()
        content = installed.read_text(encoding="utf-8")
        assert "~/.claude/skills/" not in content

    def test_install_preserves_unknown_frontmatter_keys(self, tmp_path):
        """
        Scenario: Devin preserves extra frontmatter; nWave keys must survive the
        copy.
        Slice: frontmatter passthrough. Given a skill with user-invocable and
        disable-model-invocation keys, when installed, then both are in the
        installed file.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        skill_dir = _create_skill(skills_source, "nw-sample-skill")
        (skill_dir / "SKILL.md").write_text(
            "---\nname: nw-sample-skill\ndescription: Sample.\n"
            "user-invocable: false\ndisable-model-invocation: true\n---\n\nBody.\n",
            encoding="utf-8",
        )

        ### When
        result = DevinSkillsPlugin().install(context)

        ### Then
        assert result.success, result.message
        content = (target_dir / "nw-sample-skill" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "user-invocable: false" in content
        assert "disable-model-invocation: true" in content

    def test_install_writes_manifest(self, tmp_path):
        """
        Scenario: Manifest is written after install for ownership tracking.
        Slice: Devin skills manifest. Given a project skill, when install() runs,
        then .nwave-manifest.json is created with the expected structure.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        ### When
        DevinSkillsPlugin().install(context)

        ### Then
        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest == {
            "installed_skills": ["nw-sample-skill"],
            "version": "1.0",
        }

    def test_second_install_is_idempotent(self, tmp_path):
        """
        Scenario: Re-running install leaves the same owned tree and manifest.
        Slice: idempotence. Given a first successful install, when install() runs
        again, then the manifest and skill dirs are unchanged.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        ### When
        first = DevinSkillsPlugin().install(context)
        second = DevinSkillsPlugin().install(context)

        ### Then
        assert first.success and second.success
        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["installed_skills"] == ["nw-sample-skill"]
        assert (target_dir / "nw-sample-skill" / "SKILL.md").is_file()

    def test_install_prunes_previously_owned_stale_skill(self, tmp_path):
        """
        Scenario: A skill dropped from the catalog is removed on the next install.
        Slice: stale pruning. Given an initial install with two skills, when the
        second skill is removed from the source and install() is re-run, then the
        stale skill directory is gone and the manifest reflects only the remaining
        skill.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        _create_skill(skills_source, "nw-old-skill")

        assert DevinSkillsPlugin().install(context).success
        assert (target_dir / "nw-old-skill").is_dir()

        shutil.rmtree(skills_source / "nw-old-skill")

        ### When
        result = DevinSkillsPlugin().install(context)

        ### Then
        assert result.success, result.message
        assert not (target_dir / "nw-old-skill").exists()
        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["installed_skills"] == ["nw-sample-skill"]

    def test_install_refuses_foreign_nw_collision(self, tmp_path):
        """
        Scenario: A foreign nw-* directory must never be silently adopted.
        Slice: collision safety. Given a foreign nw-foreign directory in the
        target, when install() runs, then it returns failure and the foreign
        directory's content is untouched.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        target_dir.mkdir(parents=True, exist_ok=True)
        foreign = target_dir / "nw-foreign"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("user bytes\n", encoding="utf-8")

        ### When
        result = DevinSkillsPlugin().install(context)

        ### Then
        assert not result.success
        assert "foreign or untracked Devin skill collision" in result.message
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "user bytes\n"

    def test_install_preserves_non_nw_user_content(self, tmp_path):
        """
        Scenario: User-created skills not prefixed with nw- are never touched.
        Slice: user content preservation. Given a user skill directory my-custom
        alongside the target, when install() runs, then my-custom is untouched.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        target_dir.mkdir(parents=True, exist_ok=True)
        user_skill = target_dir / "my-custom"
        user_skill.mkdir()
        (user_skill / "SKILL.md").write_text("my content\n", encoding="utf-8")

        ### When
        result = DevinSkillsPlugin().install(context)

        ### Then
        assert result.success, result.message
        assert (user_skill / "SKILL.md").read_text(encoding="utf-8") == "my content\n"


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


class TestUninstallRemovesOnlyOwned:
    """uninstall(): removes manifest-owned skills and nothing else."""

    def test_uninstall_removes_owned_keeps_foreign_and_private(self, tmp_path):
        """
        Scenario: Uninstall removes only what the manifest claims ownership of.
        Slice: uninstall ownership. Given an install followed by a foreign nw-*
        entry and a user-created non-nw entry, when uninstall() runs, then only
        the manifest-owned skill is gone.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        plugin = DevinSkillsPlugin()
        assert plugin.install(context).success

        foreign = target_dir / "nw-foreign"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("user bytes\n", encoding="utf-8")
        user_skill = target_dir / "my-personal-skill"
        user_skill.mkdir()

        ### When
        result = plugin.uninstall(context)

        ### Then
        assert result.success, result.message
        assert not (target_dir / "nw-sample-skill").exists()
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "user bytes\n"
        assert user_skill.is_dir()
        assert not (target_dir / ".nwave-manifest.json").exists()

    def test_uninstall_without_manifest_is_noop(self, tmp_path):
        """
        Scenario: Uninstall with no prior manifest is safe and returns success.
        Slice: uninstall noop. Given a target directory with no manifest, when
        uninstall() is called, then it returns success and leaves the directory
        untouched.
        """
        ### Given
        context, _skills_source, target_dir = _make_context(tmp_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        stranger = target_dir / "nw-stranger"
        stranger.mkdir()

        ### When
        result = DevinSkillsPlugin().uninstall(context)

        ### Then
        assert result.success
        assert stranger.is_dir()


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


class TestVerify:
    """verify(): checks manifest-listed skill trees exist, symlink-free."""

    def test_verify_passes_after_install(self, tmp_path):
        """
        Scenario: A clean install is fully verifiable.
        Slice: verify post-install. Given a successful install, when verify() is
        called, then it returns success.
        """
        ### Given
        context, skills_source, _ = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        assert DevinSkillsPlugin().install(context).success

        ### When
        result = DevinSkillsPlugin().verify(context)

        ### Then
        assert result.success, result.message

    def test_verify_fails_on_missing_skill(self, tmp_path):
        """
        Scenario: A manually removed skill directory causes verification failure.
        Slice: verify missing file. Given a successful install followed by manual
        deletion of a skill directory, when verify() is called, then it returns
        failure and names the missing skill.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        assert DevinSkillsPlugin().install(context).success
        shutil.rmtree(target_dir / "nw-sample-skill")

        ### When
        result = DevinSkillsPlugin().verify(context)

        ### Then
        assert not result.success
        assert "nw-sample-skill" in str(result.errors)

    def test_verify_fails_on_missing_manifest(self, tmp_path):
        """
        Scenario: Missing manifest is a verification failure.
        Slice: verify no manifest. Given a target directory with a skill dir but
        no manifest file, when verify() is called with a skills source present,
        then it returns failure.
        """
        ### Given
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "nw-sample-skill").mkdir()
        (target_dir / "nw-sample-skill" / "SKILL.md").write_text(
            "---\nname: nw-sample-skill\n---\n\nBody.\n", encoding="utf-8"
        )
        # No manifest written

        ### When
        result = DevinSkillsPlugin().verify(context)

        ### Then
        assert not result.success

    def test_verify_passes_when_nothing_configured(self, tmp_path):
        """
        Scenario: No source and no manifest means nothing to verify — not an error.
        Slice: verify empty. Given no skills source and no target dir, when
        verify() is called, then it returns success with an informational message.
        """
        ### Given
        context = InstallContext(
            claude_dir=tmp_path,
            scripts_dir=tmp_path,
            templates_dir=tmp_path,
            logger=_Logger(),
            project_root=tmp_path / "empty",
            framework_source=tmp_path / "dist",
        )

        ### When
        result = DevinSkillsPlugin().verify(context)

        ### Then
        assert result.success
        assert "nothing to verify" in result.message.lower() or "not configured" in result.message.lower()
