"""Unit tests for the OMP agents installer plugin.

Projection law assertions: model omitted (GLM inheritance), tools mapped to
canonical lowercase names only, StructuredOutput carried as an output schema
never as a tool, skills delivered once via autoloadSkills (never inlined),
and ownership refusals that preserve foreign/private bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.omp_agents_plugin import OmpAgentsPlugin
from scripts.install.plugins.omp_common import (
    map_declared_tools,
    project_agent_content,
    project_agent_frontmatter,
    translate_skill_invocations,
)


SAMPLE_ROLE = """---
name: nw-sample
description: Sample role for OMP projection tests.
model: sonnet
maxTurns: 45
tools: Read, Glob, Grep, Task, Skill, StructuredOutput
skills:
  - nw-sample-skill
  - nw-private-knowledge
---

# nw-sample

Read ~/.claude/skills/nw-sample-skill/references for details.

Invoke Skill(nw-other-skill) ON-TRIGGER — when the condition holds.
"""

#: A VALID closed public role for install-fixture use: every mandatory
#: preload name is supplied as an installed public skill, so the role is
#: installable as-is (a role declaring knowledge the public tree does not
#: ship is not a valid public-install fixture — the installer excludes the
#: missing preload and reports it, which the negative test pins separately).
SAMPLE_ROLE_VALID = """---
name: nw-sample
description: Sample role for OMP install tests.
model: sonnet
maxTurns: 45
tools: Read, Glob, Grep, Task, Skill, StructuredOutput
skills:
  - nw-sample-skill
---

# nw-sample

Read ~/.claude/skills/nw-sample-skill/references for details.

Invoke Skill(nw-other-skill) ON-TRIGGER — when the condition holds.
"""

_SAMPLE_PUBLIC_SKILLS = frozenset({"nw-sample-skill", "nw-other-skill"})


@pytest.fixture(autouse=True)
def _isolated_omp_home(monkeypatch, tmp_path):
    """Pin every omp path resolver to an isolated fake home."""
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path))
    monkeypatch.delenv("PI_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OMP_PROFILE", raising=False)
    monkeypatch.delenv("PI_PROFILE", raising=False)
    return tmp_path


class _Logger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        self.lines.append(str(message))

    def error(self, message: str) -> None:
        self.lines.append(str(message))

    def warn(self, message: str) -> None:
        self.lines.append(str(message))


def _parse_projected(content: str) -> tuple[dict, str]:
    from scripts.install.plugins.opencode_common import parse_frontmatter

    return parse_frontmatter(content)


class TestMapDeclaredTools:
    """Tool-name projection onto OMP's canonical lowercase builtin set."""

    def test_maps_claude_names_to_lowercase_omp_names(self):
        mapped, scoped, unmapped, structured = map_declared_tools(
            "Read, Write, Edit, Bash, Glob, Grep, Task"
        )
        assert mapped == [
            "read",
            "write",
            "edit",
            "bash",
            "glob",
            "grep",
            "task",
        ]
        assert scoped == [] and unmapped == [] and structured is False

    def test_web_tools_map_to_native_names(self):
        mapped, _scoped, _unmapped, _s = map_declared_tools("WebSearch, WebFetch")
        assert mapped == ["web_search", "read"]

    def test_structured_output_is_reply_channel_not_tool(self):
        mapped, scoped, unmapped, structured = map_declared_tools(
            "Read, StructuredOutput"
        )
        assert mapped == ["read"]
        assert structured is True
        assert scoped == [] and unmapped == []

    def test_scoped_grant_is_omitted_not_widened(self):
        mapped, scoped, unmapped, _s = map_declared_tools("Bash(des code-fact:*)")
        assert mapped == []
        assert scoped == ["Bash(des code-fact:*)"]
        assert unmapped == []

    def test_unmapped_name_is_dropped_and_reported(self):
        mapped, _scoped, unmapped, _s = map_declared_tools("Read, MyStudioTool")
        assert mapped == ["read"]
        assert unmapped == ["MyStudioTool"]

    def test_none_declares_no_tools(self):
        assert map_declared_tools(None) == ([], [], [], False)

    def test_reply_channel_only_role_maps_to_empty_tools(self):
        """A StructuredOutput-only role gets tools: [] (yield only via OMP)."""
        mapped, _scoped, _unmapped, structured = map_declared_tools("StructuredOutput")
        assert mapped == [] and structured is True


class TestProjectAgentFrontmatter:
    """Frontmatter projection: omit what OMP must not receive."""

    def test_model_omitted_for_glm_inheritance(self):
        projected, _reports = project_agent_frontmatter(
            {"name": "nw-sample", "description": "d", "model": "sonnet"},
            installed_public_skills=frozenset(),
        )
        assert "model" not in projected

    def test_claude_model_alias_not_projected_as_selector(self):
        for alias in ("sonnet", "haiku", "opus", "inherit", "claude-opus-5"):
            projected, _reports = project_agent_frontmatter(
                {"name": "nw-sample", "description": "d", "model": alias},
                installed_public_skills=frozenset(),
            )
            assert "model" not in projected

    def test_max_turns_omitted_and_reported(self):
        projected, reports = project_agent_frontmatter(
            {"name": "nw-sample", "description": "d", "maxTurns": 45},
            installed_public_skills=frozenset(),
        )
        assert "maxTurns" not in projected
        assert any("maxTurns" in r for r in reports)

    def test_tools_always_explicit(self):
        """OMP grants the FULL default toolset when tools is absent."""
        projected, _reports = project_agent_frontmatter(
            {"name": "nw-sample", "description": "d"},
            installed_public_skills=frozenset(),
        )
        assert projected["tools"] == []

    def test_autoload_skills_names_only_installed_public_skills(self):
        projected, reports = project_agent_frontmatter(
            {
                "name": "nw-sample",
                "description": "d",
                "skills": ["nw-sample-skill", "nw-private-knowledge"],
            },
            installed_public_skills=frozenset({"nw-sample-skill"}),
        )
        assert projected["autoloadSkills"] == ["nw-sample-skill"]
        assert any("nw-private-knowledge" in r for r in reports)

    def test_structured_output_projects_envelope_schema(self):
        projected, _reports = project_agent_frontmatter(
            {"name": "nw-sample", "description": "d", "tools": "StructuredOutput"},
            installed_public_skills=frozenset(),
        )
        assert "output" in projected
        assert "outcome" in projected["output"].get("properties", {})

    def test_uncovered_role_reports_capability_ceiling(self):
        """A role outside the canonical envelope gets the universal outcome
        floor plus an explicit ceiling report -- never an invented payload."""
        projected, reports = project_agent_frontmatter(
            {
                "name": "nw-uncovered-role",
                "description": "d",
                "tools": "StructuredOutput",
            },
            installed_public_skills=frozenset(),
        )
        assert "output" in projected
        assert any("capability ceiling" in r for r in reports)


class TestProjectAgentContent:
    """Full pipeline: body transformations and deliver-once skills."""

    def test_body_not_inlined_and_invocations_translated(self):
        content, reports = project_agent_content(
            SAMPLE_ROLE, installed_public_skills=_SAMPLE_PUBLIC_SKILLS
        )
        frontmatter, body = _parse_projected(content)
        assert "KNOWLEDGE of nw-sample-skill" not in body  # never inlined
        assert "Read `skill://nw-other-skill/SKILL.md` ON-TRIGGER" in body
        assert "Invoke Skill(" not in body
        assert frontmatter["autoloadSkills"] == ["nw-sample-skill"]
        assert frontmatter["name"] == "nw-sample"
        assert any("nw-private-knowledge" in r for r in reports)

    def test_host_paths_rewritten_by_caller_in_plugin(self):
        from scripts.shared.skill_path_rewrite import rewrite_host_paths

        content, _reports = project_agent_content(
            SAMPLE_ROLE, installed_public_skills=_SAMPLE_PUBLIC_SKILLS
        )
        _fm, body = _parse_projected(content)
        rewritten = rewrite_host_paths(body, "omp")
        assert "~/.omp/agent/skills/nw-sample-skill/references" in rewritten

    def test_role_without_required_frontmatter_is_refused(self):
        with pytest.raises(ValueError, match="name and description"):
            project_agent_content(
                "no frontmatter at all", installed_public_skills=frozenset()
            )

    def test_translate_preserves_non_invocation_text(self):
        body = "Back\\slash stays; Invoke Skill(nw-x) ON-TRIGGER; rest unchanged."
        assert "Back\\slash stays" in translate_skill_invocations(body)


class _Fixture:
    """Shared install fixture: project layout with one public role."""

    def __init__(self, tmp_path: Path, dev_mode: bool = False) -> None:
        self.project = tmp_path / "project"
        self.agents_source = self.project / "nWave" / "agents"
        self.skills_source = self.project / "nWave" / "skills"
        self.agents_source.mkdir(parents=True, exist_ok=True)
        self.skills_source.mkdir(parents=True, exist_ok=True)
        (self.project / "nWave" / "framework-catalog.yaml").write_text(
            "version: 1\nagents:\n  sample:\n    public: true\n",
            encoding="utf-8",
        )
        skill_dir = self.skills_source / "nw-sample-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: nw-sample-skill\ndescription: Sample.\n---\n\nBody.\n",
            encoding="utf-8",
        )
        (self.agents_source / "nw-sample.md").write_text(
            SAMPLE_ROLE_VALID, encoding="utf-8"
        )
        self.context = InstallContext(
            claude_dir=tmp_path / "claude",
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=_Logger(),
            project_root=self.project,
            framework_source=tmp_path / "dist",
            dev_mode=dev_mode,
            target_platforms={"omp"},
        )
        from scripts.shared.install_paths import omp_agents_dir

        self.target_dir = omp_agents_dir()


class TestInstall:
    """install() writes projected agents with manifest-driven ownership."""

    def test_install_writes_projected_agent(self, tmp_path):
        fixture = _Fixture(tmp_path)

        result = OmpAgentsPlugin().install(fixture.context)

        assert result.success, result.message
        target_file = fixture.target_dir / "nw-sample.md"
        assert target_file.is_file()
        content = target_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_projected(content)
        assert "model" not in frontmatter
        assert frontmatter["tools"] == ["read", "glob", "grep", "task"]
        # Valid closed role: the mandatory preload is fully installed, so
        # autoloadSkills carries it and NO exclusion report fires.
        assert frontmatter["autoloadSkills"] == ["nw-sample-skill"]
        assert "output" in frontmatter
        assert "skill://nw-other-skill/SKILL.md" in body
        assert "~/.omp/agent/skills/nw-sample-skill/references" in body
        assert not any(
            "excluded from autoloadSkills" in line
            for line in fixture.context.logger.lines
        )

    def test_install_refuses_role_with_missing_mandatory_preload(self, tmp_path):
        """Contract negative: frontmatter skills are MANDATORY knowledge.

        A public role declaring preload knowledge the public install does
        not carry is REFUSED for the whole run BEFORE any write -- never
        installed as a warning-carrying partial. Field effects: nothing is
        created in the target, and the refusal names every deficient role.
        """
        fixture = _Fixture(tmp_path)
        (fixture.agents_source / "nw-sample.md").write_text(
            SAMPLE_ROLE, encoding="utf-8"
        )

        result = OmpAgentsPlugin().install(fixture.context)

        assert not result.success
        assert "mandatory frontmatter skills are required knowledge" in result.message
        assert "nw-private-knowledge" in result.message
        assert not fixture.target_dir.exists()  # zero-write refusal

    def test_refusal_preserves_previous_install_intact(self, tmp_path):
        """A later run whose roles lost knowledge closure writes NOTHING and
        keeps the previous install byte-for-byte (no partial roster)."""
        fixture = _Fixture(tmp_path)
        plugin = OmpAgentsPlugin()
        assert plugin.install(fixture.context).success
        before = (fixture.target_dir / "nw-sample.md").read_text(encoding="utf-8")
        manifest_before = (
            fixture.target_dir / ".nwave-agents-manifest.json"
        ).read_text(encoding="utf-8")

        (fixture.agents_source / "nw-sample.md").write_text(
            SAMPLE_ROLE, encoding="utf-8"
        )
        result = plugin.install(fixture.context)

        assert not result.success
        assert (fixture.target_dir / "nw-sample.md").read_text(
            encoding="utf-8"
        ) == before
        assert (fixture.target_dir / ".nwave-agents-manifest.json").read_text(
            encoding="utf-8"
        ) == manifest_before

    def test_install_writes_manifest_and_is_idempotent(self, tmp_path):
        fixture = _Fixture(tmp_path)
        plugin = OmpAgentsPlugin()

        first = plugin.install(fixture.context)
        second = plugin.install(fixture.context)

        assert first.success and second.success
        manifest = json.loads(
            (fixture.target_dir / ".nwave-agents-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest == {"installed_agents": ["nw-sample"], "version": "1.0"}

    def test_install_prunes_stale_owned_agent(self, tmp_path):
        fixture = _Fixture(tmp_path)
        plugin = OmpAgentsPlugin()
        assert plugin.install(fixture.context).success

        (fixture.agents_source / "nw-sample.md").unlink()
        result = plugin.install(fixture.context)

        assert result.success, result.message
        assert not (fixture.target_dir / "nw-sample.md").exists()
        manifest = json.loads(
            (fixture.target_dir / ".nwave-agents-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["installed_agents"] == []

    def test_install_refuses_foreign_agent_file(self, tmp_path):
        fixture = _Fixture(tmp_path)
        fixture.target_dir.mkdir(parents=True, exist_ok=True)
        foreign = fixture.target_dir / "nw-foreign.md"
        foreign.write_text("user bytes\n", encoding="utf-8")

        result = OmpAgentsPlugin().install(fixture.context)

        assert not result.success
        assert "foreign or untracked OMP agent collision" in result.message
        assert foreign.read_text(encoding="utf-8") == "user bytes\n"

    def test_install_refuses_untrusted_manifest(self, tmp_path):
        """An agents manifest failing the strict trust bar refuses the install.

        Same bar as the skills plugin: exact key set, version 1.0, safe
        unique basenames -- ownership is claimed only by a trusted manifest.
        """
        fixture = _Fixture(tmp_path)
        fixture.target_dir.mkdir(parents=True, exist_ok=True)
        (fixture.target_dir / ".nwave-agents-manifest.json").write_text(
            json.dumps({"installed_agents": ["nw-sample"]}),  # no version key
            encoding="utf-8",
        )

        result = OmpAgentsPlugin().install(fixture.context)

        assert not result.success
        assert "untrusted OMP agents manifest" in result.message
        # Nothing was written: the foreign preflight never saw the roster.
        assert not (fixture.target_dir / "nw-sample.md").exists()

    def test_install_refuses_symlinked_owned_agent(self, tmp_path):
        """A symlink at an owned path is never replaced through the link."""
        fixture = _Fixture(tmp_path)
        fixture.context.dev_mode = True  # skip public filter
        real_agent = tmp_path / "outside.md"
        real_agent.write_text("outside\n", encoding="utf-8")
        fixture.target_dir.mkdir(parents=True, exist_ok=True)
        (fixture.target_dir / ".nwave-agents-manifest.json").write_text(
            json.dumps({"installed_agents": ["nw-sample"], "version": "1.0"}),
            encoding="utf-8",
        )
        link = fixture.target_dir / "nw-sample.md"
        link.symlink_to(real_agent)

        result = OmpAgentsPlugin().install(fixture.context)

        assert not result.success
        assert "symlink" in result.message.lower()
        assert link.is_symlink()
        assert real_agent.read_text(encoding="utf-8") == "outside\n"

    def test_install_private_fixture_untouched(self, tmp_path):
        """Private symlinks in the agents dir survive an install."""
        fixture = _Fixture(tmp_path)
        fixture.target_dir.mkdir(parents=True, exist_ok=True)
        private_target = tmp_path / "private-role.md"
        private_target.write_text("private\n", encoding="utf-8")
        symlink = fixture.target_dir / "personal-agent.md"
        symlink.symlink_to(private_target)

        result = OmpAgentsPlugin().install(fixture.context)

        assert result.success, result.message
        assert symlink.is_symlink()
        assert private_target.read_text(encoding="utf-8") == "private\n"


class TestUninstallAndVerify:
    """Manifest-driven uninstall removes only owned agents."""

    def test_uninstall_removes_owned_keeps_private(self, tmp_path):
        fixture = _Fixture(tmp_path)
        plugin = OmpAgentsPlugin()
        assert plugin.install(fixture.context).success
        private_target = tmp_path / "private-role.md"
        private_target.write_text("private\n", encoding="utf-8")
        symlink = fixture.target_dir / "external-user-skill.md"
        symlink.symlink_to(private_target)

        result = plugin.uninstall(fixture.context)

        assert result.success, result.message
        assert not (fixture.target_dir / "nw-sample.md").exists()
        assert symlink.is_symlink()
        assert not (fixture.target_dir / ".nwave-agents-manifest.json").exists()

    def test_uninstall_without_manifest_is_noop(self, tmp_path):
        fixture = _Fixture(tmp_path)
        fixture.target_dir.mkdir(parents=True, exist_ok=True)

        result = OmpAgentsPlugin().uninstall(fixture.context)

        assert result.success

    def test_verify_passes_after_install(self, tmp_path):
        fixture = _Fixture(tmp_path)

        assert OmpAgentsPlugin().install(fixture.context).success
        result = OmpAgentsPlugin().verify(fixture.context)

        assert result.success, result.message

    def test_verify_fails_when_agent_missing(self, tmp_path):
        fixture = _Fixture(tmp_path)

        assert OmpAgentsPlugin().install(fixture.context).success
        (fixture.target_dir / "nw-sample.md").unlink()

        result = OmpAgentsPlugin().verify(fixture.context)

        assert not result.success
