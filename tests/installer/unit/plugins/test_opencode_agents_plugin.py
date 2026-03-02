"""Unit tests for OpenCode agents installer plugin.

Tests validate that:
- _parse_tools() normalizes CSV strings and YAML arrays to lowercase lists
- _transform_frontmatter() removes name/model/skills, renames maxTurns, adds mode
- _transform_agent() produces a complete OpenCode-format agent file
- install() creates transformed agent files in the target directory
- install() preserves body content unchanged
- verify() checks that installed agent files exist
- uninstall() only removes manifest-tracked agents, not user-created ones
- install() creates a .nwave-agents-manifest.json tracking installed agents

CRITICAL: Tests follow hexagonal architecture - mocks only at port boundaries.
"""

import json
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.opencode_agents_plugin import (
    OpenCodeAgentsPlugin,
    _parse_tools,
    _transform_agent,
    _transform_frontmatter,
)
from scripts.install.plugins.opencode_common import parse_frontmatter


def _make_context(tmp_path):
    """Create an InstallContext with a minimal agent source layout.

    Returns:
        Tuple of (context, agents_source, opencode_agents_target)
    """
    project_root = tmp_path / "project"
    framework_source = tmp_path / "framework"

    agents_source = project_root / "nWave" / "agents"
    agents_source.mkdir(parents=True)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    logger = MagicMock()

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logger,
        project_root=project_root,
        framework_source=framework_source,
    )

    opencode_agents_target = tmp_path / "home" / ".config" / "opencode" / "agents"

    return context, agents_source, opencode_agents_target


def _create_agent(agents_source, agent_name, content):
    """Create an agent .md file in the source layout.

    Args:
        agents_source: Path to nWave/agents/ directory
        agent_name: Agent filename without extension (e.g. 'nw-software-crafter')
        content: Full file content with frontmatter + body
    """
    (agents_source / f"{agent_name}.md").write_text(content)


_CSV_TOOLS_AGENT = (
    "---\n"
    "name: nw-software-crafter\n"
    "description: DELIVER wave - Outside-In TDD\n"
    "model: inherit\n"
    "tools: Read, Write, Edit, Bash, Glob, Grep, Task\n"
    "maxTurns: 50\n"
    "skills:\n"
    "  - tdd-methodology\n"
    "  - progressive-refactoring\n"
    "---\n"
    "\n"
    "# nw-software-crafter\n"
    "\n"
    "Body content here.\n"
)

_ARRAY_TOOLS_AGENT = (
    "---\n"
    "name: nw-documentarist-reviewer\n"
    "description: Documentation quality reviewer\n"
    "model: haiku\n"
    "tools: [Read, Glob, Grep]\n"
    "maxTurns: 25\n"
    "skills:\n"
    "  - review-criteria\n"
    "---\n"
    "\n"
    "# nw-documentarist-reviewer\n"
    "\n"
    "Reviewer body content.\n"
)


class TestParseToolsCsvToObject:
    """Test that _parse_tools normalizes CSV string to lowercase list."""

    def test_transform_tools_csv_to_object(self):
        """
        GIVEN: A tools value as CSV string "Read, Write, Edit"
        WHEN: _parse_tools() is called
        THEN: Returns {"read": True, "write": True, "edit": True}
        """
        result = _parse_tools("Read, Write, Edit")

        assert result == {"read": True, "write": True, "edit": True}


class TestParseToolsArrayToObject:
    """Test that _parse_tools normalizes YAML array to lowercase list."""

    def test_transform_tools_array_to_object(self):
        """
        GIVEN: A tools value as list ["Read", "Glob", "Grep"]
        WHEN: _parse_tools() is called
        THEN: Returns {"read": True, "glob": True, "grep": True}
        """
        result = _parse_tools(["Read", "Glob", "Grep"])

        assert result == {"read": True, "glob": True, "grep": True}


class TestTransformRemovesNameAndModel:
    """Test that _transform_frontmatter removes name and model fields."""

    def test_transform_removes_name_and_model(self):
        """
        GIVEN: A frontmatter dict with name, model, and other fields
        WHEN: _transform_frontmatter() is called
        THEN: name and model are not in the result
        """
        frontmatter = {
            "name": "nw-software-crafter",
            "description": "DELIVER wave",
            "model": "inherit",
            "tools": "Read, Write",
            "maxTurns": 50,
        }

        result = _transform_frontmatter(frontmatter)

        assert "name" not in result
        assert "model" not in result


class TestTransformRemovesSkills:
    """Test that _transform_frontmatter removes skills field."""

    def test_transform_removes_skills(self):
        """
        GIVEN: A frontmatter dict with a skills list
        WHEN: _transform_frontmatter() is called
        THEN: skills is not in the result
        """
        frontmatter = {
            "name": "nw-software-crafter",
            "description": "DELIVER wave",
            "model": "inherit",
            "tools": "Read, Write",
            "maxTurns": 50,
            "skills": ["tdd-methodology", "progressive-refactoring"],
        }

        result = _transform_frontmatter(frontmatter)

        assert "skills" not in result


class TestTransformRenamesMaxTurnsToSteps:
    """Test that _transform_frontmatter renames maxTurns to steps."""

    def test_transform_renames_maxturns_to_steps(self):
        """
        GIVEN: A frontmatter dict with maxTurns: 50
        WHEN: _transform_frontmatter() is called
        THEN: Result has steps: 50 and no maxTurns
        """
        frontmatter = {
            "name": "nw-software-crafter",
            "description": "DELIVER wave",
            "model": "inherit",
            "tools": "Read, Write",
            "maxTurns": 50,
        }

        result = _transform_frontmatter(frontmatter)

        assert result["steps"] == 50
        assert "maxTurns" not in result


class TestTransformAddsSubagentMode:
    """Test that _transform_frontmatter adds mode: subagent."""

    def test_transform_adds_mode_subagent(self):
        """
        GIVEN: A frontmatter dict without mode
        WHEN: _transform_frontmatter() is called
        THEN: Result has mode: "subagent"
        """
        frontmatter = {
            "name": "nw-software-crafter",
            "description": "DELIVER wave",
            "model": "inherit",
            "tools": "Read, Write",
            "maxTurns": 50,
        }

        result = _transform_frontmatter(frontmatter)

        assert result["mode"] == "subagent"


class TestInstallCreatesAgentFiles:
    """Test that install() creates transformed agent files in the target directory."""

    def test_install_creates_agent_files(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agent at nWave/agents/nw-software-crafter.md
        WHEN: install() is called
        THEN: nw-software-crafter.md is created in the OpenCode agents directory
              with transformed frontmatter
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        _create_agent(agents_source, "nw-software-crafter", _CSV_TOOLS_AGENT)

        plugin = OpenCodeAgentsPlugin()
        result = plugin.install(context)

        assert result.success is True

        agent_file = target / "nw-software-crafter.md"
        assert agent_file.exists(), f"Expected {agent_file} to exist"

        content = agent_file.read_text()
        # Verify transformed frontmatter
        assert "mode: subagent" in content
        assert "steps: 50" in content
        assert "name:" not in content
        assert "model:" not in content
        assert "skills:" not in content
        assert "maxTurns:" not in content


class TestInstallPreservesBody:
    """Test that install() preserves body content unchanged after transformation."""

    def test_install_preserves_body(self, tmp_path, monkeypatch):
        """
        GIVEN: An agent file with specific body content
        WHEN: install() transforms it
        THEN: The body content after the frontmatter is unchanged
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        _create_agent(agents_source, "nw-software-crafter", _CSV_TOOLS_AGENT)

        plugin = OpenCodeAgentsPlugin()
        plugin.install(context)

        agent_file = target / "nw-software-crafter.md"
        content = agent_file.read_text()

        # Parse source to get original body
        _, source_body = parse_frontmatter(_CSV_TOOLS_AGENT)

        # Parse output to get transformed body
        _, output_body = parse_frontmatter(content)

        assert output_body == source_body


class TestUninstallRemovesOnlyManifestAgents:
    """Test that uninstall() removes only manifest-tracked agents."""

    def test_uninstall_removes_only_manifest_agents(self, tmp_path, monkeypatch):
        """
        GIVEN: An OpenCode agents directory with both nWave-installed and
               user-created agent files
        WHEN: uninstall() is called
        THEN: Only nWave-installed agents (listed in manifest) are removed;
              user-created agents remain untouched
        """
        context, _agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        target.mkdir(parents=True, exist_ok=True)

        # Create nWave-installed agent
        nwave_agent = target / "nw-software-crafter.md"
        nwave_agent.write_text("---\nmode: subagent\n---\n\n# Agent\n")

        # Create user-owned agent (NOT in manifest)
        user_agent = target / "my-custom-agent.md"
        user_agent.write_text("---\nmode: subagent\n---\n\n# My agent\n")

        # Manifest only tracks nWave agents
        manifest = {
            "installed_agents": ["nw-software-crafter"],
            "version": "1.0",
        }
        (target / ".nwave-agents-manifest.json").write_text(json.dumps(manifest))

        plugin = OpenCodeAgentsPlugin()
        result = plugin.uninstall(context)

        assert result.success is True

        # nWave agent should be removed
        assert not nwave_agent.exists(), "nWave agent should be removed"

        # User agent should remain
        assert user_agent.exists(), "User-created agent must remain untouched"


class TestInstallCreatesManifest:
    """Test that install() creates a manifest tracking installed agent names."""

    def test_install_creates_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: Multiple source agent files
        WHEN: install() is called
        THEN: A .nwave-agents-manifest.json is created listing all installed agents
        """
        context, agents_source, target = _make_context(tmp_path)
        monkeypatch.setattr(
            "scripts.install.plugins.opencode_agents_plugin._opencode_agents_dir",
            lambda: target,
        )

        _create_agent(agents_source, "nw-software-crafter", _CSV_TOOLS_AGENT)
        _create_agent(agents_source, "nw-documentarist-reviewer", _ARRAY_TOOLS_AGENT)

        plugin = OpenCodeAgentsPlugin()
        plugin.install(context)

        manifest_path = target / ".nwave-agents-manifest.json"
        assert manifest_path.exists(), "Manifest should be created"

        manifest = json.loads(manifest_path.read_text())
        assert "installed_agents" in manifest
        assert sorted(manifest["installed_agents"]) == sorted(
            ["nw-software-crafter", "nw-documentarist-reviewer"]
        )


class TestTransformAgentFullPipeline:
    """Test the full _transform_agent pipeline from source to OpenCode format."""

    def test_transform_agent_csv_tools(self):
        """
        GIVEN: A full agent file with CSV tools format
        WHEN: _transform_agent() is called
        THEN: Produces valid OpenCode format with all transformations applied
        """
        result = _transform_agent(_CSV_TOOLS_AGENT)

        frontmatter, body = parse_frontmatter(result)

        assert frontmatter["mode"] == "subagent"
        assert frontmatter["steps"] == 50
        assert frontmatter["description"] == "DELIVER wave - Outside-In TDD"
        assert frontmatter["tools"] == {
            "read": True,
            "write": True,
            "edit": True,
            "bash": True,
            "glob": True,
            "grep": True,
            "task": True,
        }
        assert "name" not in frontmatter
        assert "model" not in frontmatter
        assert "skills" not in frontmatter
        assert "maxTurns" not in frontmatter

        assert "# nw-software-crafter" in body
        assert "Body content here." in body

    def test_transform_agent_array_tools(self):
        """
        GIVEN: A full agent file with array-style tools format
        WHEN: _transform_agent() is called
        THEN: Produces valid OpenCode format with tools as mapping
        """
        result = _transform_agent(_ARRAY_TOOLS_AGENT)

        frontmatter, body = parse_frontmatter(result)

        assert frontmatter["tools"] == {
            "read": True,
            "glob": True,
            "grep": True,
        }
        assert frontmatter["steps"] == 25
        assert "# nw-documentarist-reviewer" in body
