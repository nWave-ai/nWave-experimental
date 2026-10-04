"""Unit tests for the OMP skills installer plugin.

State-delta discipline: every install/uninstall test asserts the resulting
filesystem state (present/absent bytes), never a log message. Ownership is
manifest-driven; foreign and private entries must survive untouched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.omp_common import OmpProfileNotSupported
from scripts.install.plugins.omp_skills_plugin import (
    OmpSkillsPlugin,
    _find_skills_source,
)
from scripts.shared.install_paths import omp_skills_dir


@pytest.fixture(autouse=True)
def _isolated_omp_home(monkeypatch, tmp_path):
    """Pin every omp path resolver to an isolated fake home."""
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path))
    monkeypatch.delenv("PI_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OMP_PROFILE", raising=False)
    monkeypatch.delenv("PI_PROFILE", raising=False)
    return tmp_path


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
    dev_mode: bool = False,
    project_root: Path | None = None,
) -> tuple[InstallContext, Path, Path]:
    """Create an InstallContext with a minimal skill source layout.

    The project layout mirrors a real checkout: <project>/nWave/skills holds
    skill dirs; framework-catalog.yaml and agent frontmatter decide the
    public filter.
    """
    project = project_root if project_root is not None else tmp_path / "project"
    skills_source = project / "nWave" / "skills"
    skills_source.mkdir(parents=True, exist_ok=True)
    agents_dir = project / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    # The public filter is ownership-driven: a knowledge skill is public only
    # when a catalogued public agent declares it in frontmatter ``skills:``.
    (agents_dir / "nw-sample.md").write_text(
        "---\nname: nw-sample\ndescription: Sample role.\n"
        "skills:\n  - nw-sample-skill\n---\n\nSample body.\n",
        encoding="utf-8",
    )
    (project / "nWave" / "framework-catalog.yaml").write_text(
        "version: 1\nagents:\n  sample:\n    public: true\n",
        encoding="utf-8",
    )
    context = InstallContext(
        claude_dir=tmp_path / "claude",
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=_Logger(),
        project_root=project,
        framework_source=tmp_path / "dist",
        dev_mode=dev_mode,
        target_platforms={"omp"},
    )
    return context, skills_source, omp_skills_dir()


def _create_skill(
    skills_source: Path,
    name: str,
    description: str = "Sample skill.",
    *,
    user_invocable: bool = False,
) -> Path:
    skill_dir = skills_source / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    extra = "\nuser-invocable: true" if user_invocable else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}{extra}\n---\n\n"
        f"Read ~/.claude/skills/{name}/references for details.\n",
        encoding="utf-8",
    )
    return skill_dir


class TestFindSkillsSource:
    """Source resolution: project checkout layout."""

    def test_finds_project_skills_dir(self, tmp_path):
        context, skills_source, _ = _make_context(tmp_path)
        assert _find_skills_source(context) == skills_source

    def test_returns_none_when_absent(self, tmp_path):
        context = InstallContext(
            claude_dir=tmp_path,
            scripts_dir=tmp_path,
            templates_dir=tmp_path,
            logger=_Logger(),
            project_root=tmp_path / "empty",
            framework_source=tmp_path / "dist",
        )
        assert _find_skills_source(context) is None


class TestInstallCreatesSkillDirs:
    """install() copies public skills into the OMP native tree."""

    def test_install_writes_skill_and_rewrites_paths(self, tmp_path):
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        installed = target_dir / "nw-sample-skill" / "SKILL.md"
        assert installed.is_file()
        content = installed.read_text(encoding="utf-8")
        assert "~/.omp/agent/skills/nw-sample-skill/references" in content
        assert "~/.claude/skills/" not in content

    def test_install_keeps_unknown_frontmatter_keys(self, tmp_path):
        """OMP preserves unknown metadata; the copy must not strip nWave keys."""
        context, skills_source, target_dir = _make_context(tmp_path)
        skill_dir = _create_skill(skills_source, "nw-sample-skill")
        (skill_dir / "SKILL.md").write_text(
            "---\nname: nw-sample-skill\ndescription: Sample.\n"
            "user-invocable: false\ndisable-model-invocation: true\n---\n\nBody.\n",
            encoding="utf-8",
        )

        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        content = (target_dir / "nw-sample-skill" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "user-invocable: false" in content
        assert "disable-model-invocation: true" in content

    def test_install_deslib_path_not_rewritten(self, tmp_path):
        """The DES runtime path keeps its pointer scheme on OMP too."""
        context, skills_source, target_dir = _make_context(tmp_path)
        skill_dir = _create_skill(skills_source, "nw-sample-skill")
        (skill_dir / "SKILL.md").write_text(
            "---\nname: nw-sample-skill\ndescription: Sample.\n---\n\n"
            "Runtime: ~/.claude/lib/python/des\n",
            encoding="utf-8",
        )

        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        content = (target_dir / "nw-sample-skill" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "~/.claude/lib/python/des" in content

    def test_install_writes_manifest(self, tmp_path):
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        OmpSkillsPlugin().install(context)

        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest == {
            "installed_skills": ["nw-sample-skill"],
            "version": "1.0",
        }

    def test_second_install_is_idempotent(self, tmp_path):
        """Installing twice leaves the same owned tree and manifest."""
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        first = OmpSkillsPlugin().install(context)
        second = OmpSkillsPlugin().install(context)

        assert first.success and second.success
        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["installed_skills"] == ["nw-sample-skill"]
        assert (target_dir / "nw-sample-skill" / "SKILL.md").is_file()

    def test_install_prunes_previously_owned_stale_skill(self, tmp_path):
        """A skill the new catalog dropped is removed on refresh."""
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        _create_skill(skills_source, "nw-old-skill", user_invocable=True)

        assert OmpSkillsPlugin().install(context).success
        assert (target_dir / "nw-old-skill").is_dir()

        shutil.rmtree(skills_source / "nw-old-skill")
        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        assert not (target_dir / "nw-old-skill").exists()
        manifest = json.loads(
            (target_dir / ".nwave-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["installed_skills"] == ["nw-sample-skill"]

    def test_install_refuses_foreign_nw_collision(self, tmp_path):
        """A foreign nw-* directory is refused, never adopted or replaced."""
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        target_dir.mkdir(parents=True, exist_ok=True)
        foreign = target_dir / "nw-foreign"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("user bytes\n", encoding="utf-8")

        result = OmpSkillsPlugin().install(context)

        assert not result.success
        assert "foreign or untracked OMP skill collision" in result.message
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "user bytes\n"

    def test_install_preserves_private_symlinks(self, tmp_path):
        """Non-nw entries (private user symlinks) are untouched by install."""
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        target_dir.mkdir(parents=True, exist_ok=True)
        private_target = tmp_path / "private-skill"
        private_target.mkdir()
        symlink = target_dir / "personal-agent"
        symlink.symlink_to(private_target)

        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        assert symlink.is_symlink()
        assert symlink.resolve() == private_target.resolve()


class TestUninstallRemovesOnlyOwned:
    """uninstall() removes manifest-owned skills and nothing else."""

    def test_uninstall_removes_owned_keeps_foreign_and_private(self, tmp_path):
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        plugin = OmpSkillsPlugin()
        assert plugin.install(context).success

        foreign = target_dir / "nw-foreign"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("user bytes\n", encoding="utf-8")
        private_target = tmp_path / "private-skill"
        private_target.mkdir()
        symlink = target_dir / "external-user-skill"
        symlink.symlink_to(private_target)

        result = plugin.uninstall(context)

        assert result.success, result.message
        assert not (target_dir / "nw-sample-skill").exists()
        assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "user bytes\n"
        assert symlink.is_symlink()
        assert not (target_dir / ".nwave-manifest.json").exists()

    def test_uninstall_without_manifest_is_noop(self, tmp_path):
        context, _skills_source, target_dir = _make_context(tmp_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        stranger = target_dir / "nw-stranger"
        stranger.mkdir()

        result = OmpSkillsPlugin().uninstall(context)

        assert result.success
        assert stranger.is_dir()


class TestVerify:
    """verify() checks manifest-listed trees exist, symlink-free."""

    def test_verify_passes_after_install(self, tmp_path):
        context, skills_source, _target = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        assert OmpSkillsPlugin().install(context).success
        result = OmpSkillsPlugin().verify(context)

        assert result.success, result.message

    def test_verify_fails_on_missing_skill(self, tmp_path):
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")

        assert OmpSkillsPlugin().install(context).success
        import shutil

        shutil.rmtree(target_dir / "nw-sample-skill")

        result = OmpSkillsPlugin().verify(context)

        assert not result.success


class TestNamedProfileRefusal:
    """A named OMP profile is refused, never silently served at the default."""

    @pytest.mark.parametrize("env_name", ["OMP_PROFILE", "PI_PROFILE"])
    def test_install_refuses_named_profile(self, monkeypatch, tmp_path, env_name):
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        monkeypatch.delenv("OMP_PROFILE", raising=False)
        monkeypatch.delenv("PI_PROFILE", raising=False)
        monkeypatch.setenv(env_name, "work")

        result = OmpSkillsPlugin().install(context)

        assert not result.success
        assert "profile" in result.message.lower()
        assert not target_dir.exists()

    def test_empty_omp_profile_selects_default(self, monkeypatch, tmp_path):
        """OMP_PROFILE='' explicitly names the default profile: install runs."""
        context, skills_source, target_dir = _make_context(tmp_path)
        _create_skill(skills_source, "nw-sample-skill")
        monkeypatch.setenv("OMP_PROFILE", "")
        monkeypatch.delenv("PI_PROFILE", raising=False)

        result = OmpSkillsPlugin().install(context)

        assert result.success, result.message
        assert (target_dir / "nw-sample-skill" / "SKILL.md").is_file()


def test_profile_guard_raises_with_profile_name(tmp_path, monkeypatch):
    """OmpProfileNotSupported names the offending selector."""
    monkeypatch.setenv("PI_PROFILE", "deep-work")
    monkeypatch.delenv("OMP_PROFILE", raising=False)

    with pytest.raises(OmpProfileNotSupported, match="deep-work"):
        from scripts.install.plugins.omp_common import require_default_profile

        require_default_profile()
