"""AC-2 acceptance test -- Codex skills per-host skill-path rewrite.

Feature: installer-per-host-skill-path-portability.

A composing-core skill body whose loading table references ~/.claude/skills/
must, after Codex install, reference the Codex skill base (~/.agents/skills/),
NOT ~/.claude/skills/. The source SKILL.md on disk must be byte-unchanged.

ACTIVE-RED (atdd_pure): the codex_skills plugin does NOT yet rewrite body
paths (design.md: "Path rewrite today: NONE (bug)") -> AssertionError.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin


_SKILL_WITH_SKILL_PATHS = (
    "---\n"
    "name: nw-bar\n"
    "description: A composing-core skill\n"
    "user-invocable: true\n"
    "---\n"
    "\n"
    "# nw-bar\n"
    "\n"
    "## Skill Loading\n"
    "\n"
    "| Skill | Trigger |\n"
    "| `~/.claude/skills/nw-bar/SKILL.md` | always |\n"
    "| `~/.claude/skills/nw-distill/SKILL.md` | DISTILL |\n"
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal flat skill source layout."""
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    skill_dir = project_root / "nWave" / "skills" / "nw-bar"
    skill_dir.mkdir(parents=True)
    source_file = skill_dir / "SKILL.md"
    source_file.write_text(_SKILL_WITH_SKILL_PATHS)

    (project_root / "nWave" / "framework-catalog.yaml").write_text("agents: {}\n")

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
        dev_mode=True,
    )

    codex_skills_target = tmp_path / "home" / ".agents" / "skills"
    return context, source_file, codex_skills_target


def _force_codex_present(monkeypatch, target):
    monkeypatch.setattr(
        "scripts.install.plugins.codex_skills_plugin._codex_skills_dir",
        lambda: target,
    )
    monkeypatch.setattr(
        "scripts.install.plugins.codex_skills_plugin._codex_config_dir",
        lambda: target.parent.parent / ".codex",
    )
    (target.parent.parent / ".codex").mkdir(parents=True, exist_ok=True)


class TestCodexSkillBodyHasCodexSkillPaths:
    """Skill installed for Codex must reference ~/.agents/skills/."""

    def test_codex_skill_body_has_codex_skill_paths(self, tmp_path, monkeypatch):
        """
        GIVEN: A composing-core skill whose body references ~/.claude/skills/
        WHEN: The Codex skills plugin installs it
        THEN: $HOME/.agents/skills/nw-bar/SKILL.md body contains
              ~/.agents/skills/ AND NO ~/.claude/skills/.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, _source, target = _make_context(tmp_path)
        _force_codex_present(monkeypatch, target)

        result = CodexSkillsPlugin().install(context)
        assert result.success is True

        installed = (target / "nw-bar" / "SKILL.md").read_text()
        assert "~/.agents/skills/" in installed, (
            "Installed Codex skill body must use Codex skill paths"
        )
        assert "~/.claude/skills/" not in installed, (
            "Installed Codex skill body must NOT contain Claude Code skill paths"
        )

    def test_codex_skill_source_byte_unchanged(self, tmp_path, monkeypatch):
        """
        GIVEN: A skill source with ~/.claude/skills/ paths
        WHEN: The Codex skills plugin installs it
        THEN: The SOURCE SKILL.md on disk is byte-unchanged.

        CONTRACT_SHAPE: unbounded-preservation
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, source, target = _make_context(tmp_path)
        _force_codex_present(monkeypatch, target)

        before = source.read_bytes()
        CodexSkillsPlugin().install(context)

        # Source unchanged is true today; pair with the rewrite assertion so
        # this module's RED is anchored on the missing rewrite, not on source.
        assert source.read_bytes() == before, "Source skill file must NOT be mutated"
        installed = (target / "nw-bar" / "SKILL.md").read_text()
        assert "~/.claude/skills/" not in installed, (
            "Installed Codex skill body must NOT contain Claude Code skill paths"
        )
