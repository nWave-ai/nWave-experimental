"""AC-5 acceptance test -- Claude + Codex + OpenCode coexistence.

Feature: installer-per-host-skill-path-portability.

One machine may host Claude, Codex, AND OpenCode simultaneously. The SAME
source skill, installed for all three, yields three copies each pointing at
ITS OWN host base:
  - Claude   copy keeps ~/.claude/skills/        (canonical no-op host)
  - Codex    copy has  ~/.agents/skills/
  - OpenCode copy has  ~/.config/opencode/skills/
No collision (each writes its own dir), no shared mutable state.

ACTIVE-RED (atdd_pure): codex_skills + opencode_skills do NOT yet rewrite body
paths, so their copies still contain ~/.claude/skills/ -> AssertionError.
The Claude leg passes today (no-op host) and pins the invariant that the
canonical token survives.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin
from scripts.install.plugins.opencode_skills_plugin import OpenCodeSkillsPlugin
from scripts.install.plugins.skills_plugin import SkillsPlugin


_SKILL_WITH_SKILL_PATHS = (
    "---\n"
    "name: nw-foo\n"
    "description: A coexisting skill\n"
    "user-invocable: true\n"
    "---\n"
    "\n"
    "# nw-foo\n"
    "\n"
    "Load `~/.claude/skills/nw-foo/SKILL.md`.\n"
)


def _make_context(tmp_path):
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    skill_dir = project_root / "nWave" / "skills" / "nw-foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(_SKILL_WITH_SKILL_PATHS)

    (project_root / "nWave" / "framework-catalog.yaml").write_text("agents: {}\n")

    claude_dir = tmp_path / "home" / ".claude"
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
    return context


class TestMultiHostSkillPathCoexistence:
    """Three host copies of one skill, each with its own skill base."""

    def test_three_hosts_each_keep_their_own_skill_base(self, tmp_path, monkeypatch):
        """
        GIVEN: One source skill referencing ~/.claude/skills/ AND a machine
               with Claude + Codex + OpenCode targets
        WHEN: All three skills plugins install it
        THEN: Claude copy keeps ~/.claude/skills/; Codex copy has
              ~/.agents/skills/; OpenCode copy has ~/.config/opencode/skills/;
              each copy is free of the OTHER hosts' bases.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context = _make_context(tmp_path)

        codex_target = tmp_path / "home" / ".agents" / "skills"
        opencode_target = tmp_path / "home" / ".config" / "opencode" / "skills"

        monkeypatch.setattr(
            "scripts.install.plugins.codex_skills_plugin._codex_skills_dir",
            lambda: codex_target,
        )
        monkeypatch.setattr(
            "scripts.install.plugins.codex_skills_plugin._codex_config_dir",
            lambda: tmp_path / "home" / ".codex",
        )
        (tmp_path / "home" / ".codex").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_skills_plugin._opencode_skills_dir",
            lambda: opencode_target,
        )

        assert SkillsPlugin().install(context).success is True
        assert CodexSkillsPlugin().install(context).success is True
        assert OpenCodeSkillsPlugin().install(context).success is True

        # Claude leg must be GENUINELY exercised: SkillsPlugin enumerates by
        # filesystem walk (detect_layout over nWave/skills/), so the source
        # nw-foo/SKILL.md fixture is really copied. Assert the file exists and
        # carries the body BEFORE the token assertion -- this test fails if the
        # Claude copy was never written (no fabricated green).
        claude_path = context.claude_dir / "skills" / "nw-foo" / "SKILL.md"
        assert claude_path.is_file(), (
            "Claude copy must be genuinely written by SkillsPlugin"
        )
        claude_copy = claude_path.read_text()
        assert "# nw-foo" in claude_copy, "Claude copy must carry the skill body"

        codex_copy = (codex_target / "nw-foo" / "SKILL.md").read_text()
        opencode_copy = (opencode_target / "nw-foo" / "SKILL.md").read_text()

        # Claude -- canonical token survives (no-op host).
        assert "~/.claude/skills/" in claude_copy, (
            "Claude copy must keep canonical ~/.claude/skills/"
        )

        # Codex -- its own base, no others.
        assert "~/.agents/skills/" in codex_copy
        assert "~/.claude/skills/" not in codex_copy
        assert "~/.config/opencode/skills/" not in codex_copy

        # OpenCode -- its own base, no others.
        assert "~/.config/opencode/skills/" in opencode_copy
        assert "~/.claude/skills/" not in opencode_copy
        assert "~/.agents/skills/" not in opencode_copy
