"""AC-1 acceptance test -- Codex agents per-host skill-path rewrite.

Feature: installer-per-host-skill-path-portability.

Codex agent bodies are deployed as TOML developer_instructions. They must
reference the Codex skill base (~/.agents/skills/), NOT the canonical Claude
Code base (~/.claude/skills/). The body must remain valid TOML and the source
.md file on disk must be byte-unchanged.

ACTIVE-RED (atdd_pure): the codex_agents plugin does NOT yet rewrite paths
(per design.md Existing System Analysis: "Path rewrite today: NONE (bug)"),
so the rewrite assertions fail with AssertionError.
"""

from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
from scripts.install.plugins.opencode_common import parse_frontmatter


_AGENT_WITH_SKILL_PATHS = (
    "---\n"
    "name: nw-foo\n"
    "description: Some agent\n"
    "model: inherit\n"
    "tools: Read, Write, Edit, Bash\n"
    "maxTurns: 50\n"
    "---\n"
    "\n"
    "# nw-foo\n"
    "\n"
    "## Skill Loading -- MANDATORY\n"
    "\n"
    "Read these files NOW:\n"
    "- `~/.claude/skills/nw-foo/SKILL.md`\n"
    "- `~/.claude/skills/nw-tdd-methodology/SKILL.md`\n"
)


def _make_context(tmp_path):
    """Create an InstallContext with a minimal Codex agent source layout."""
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    agents_source = project_root / "nWave" / "agents"
    agents_source.mkdir(parents=True)

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

    codex_agents_target = tmp_path / "home" / ".codex" / "agents"
    return context, agents_source, codex_agents_target


def _force_codex_present(monkeypatch, target):
    """Point the plugin at tmp dirs and make Codex appear installed."""
    monkeypatch.setattr(
        "scripts.install.plugins.codex_agents_plugin._codex_agents_dir",
        lambda: target,
    )
    monkeypatch.setattr(
        "scripts.install.plugins.codex_agents_plugin._codex_config_dir",
        lambda: target.parent,
    )
    target.parent.mkdir(parents=True, exist_ok=True)


class TestCodexAgentBodyHasCodexSkillPaths:
    """Agent installed for Codex must reference ~/.agents/skills/."""

    def test_codex_agent_body_has_codex_skill_paths(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agent whose body references ~/.claude/skills/
        WHEN: The Codex agents plugin installs it
        THEN: The deployed .toml developer_instructions contains
              ~/.agents/skills/ AND contains NO ~/.claude/skills/ AND the
              body is valid TOML (parses back) AND source .md is byte-unchanged.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, agents_source, target = _make_context(tmp_path)
        _force_codex_present(monkeypatch, target)

        source_file = agents_source / "nw-foo.md"
        source_file.write_text(_AGENT_WITH_SKILL_PATHS)
        source_bytes_before = source_file.read_bytes()

        result = CodexAgentsPlugin().install(context)
        assert result.success is True

        installed_content = (target / "nw-foo.toml").read_text()

        # Body is valid TOML (parses).
        import tomllib

        parsed = tomllib.loads(installed_content)
        body = parsed["developer_instructions"]

        assert "~/.agents/skills/" in body, (
            "Installed Codex agent body must use Codex skill paths"
        )
        assert "~/.claude/skills/" not in body, (
            "Installed Codex agent body must NOT contain Claude Code skill paths"
        )

        # Source .md byte-unchanged.
        assert source_file.read_bytes() == source_bytes_before, (
            "Source agent file must NOT be mutated by install"
        )

    def test_codex_agent_toml_still_valid_with_escaping_intact(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: A source agent body with skill paths
        WHEN: The Codex agents plugin installs it (rewrite-before-TOML-escape)
        THEN: developer_instructions round-trips through TOML AND the
              frontmatter scalar fields (name) survive.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        context, agents_source, target = _make_context(tmp_path)
        _force_codex_present(monkeypatch, target)

        (agents_source / "nw-foo.md").write_text(_AGENT_WITH_SKILL_PATHS)

        CodexAgentsPlugin().install(context)

        import tomllib

        parsed = tomllib.loads((target / "nw-foo.toml").read_text())
        assert parsed["name"] == "nw-foo"
        # The source frontmatter parses (sanity on the fixture shape).
        frontmatter, _body = parse_frontmatter(_AGENT_WITH_SKILL_PATHS)
        assert frontmatter["name"] == "nw-foo"
        # Same right-reason RED anchor: rewrite must have happened.
        assert "~/.claude/skills/" not in parsed["developer_instructions"]
