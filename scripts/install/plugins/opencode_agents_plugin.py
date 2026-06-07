"""
Plugin for installing nWave agents into OpenCode's agent format.

OpenCode expects agents at: ~/.config/opencode/agents/{agent-name}.md
Each agent has YAML frontmatter with mode, steps, tools (as mapping), and
description -- but no name, model, or skills fields.

A manifest file (.nwave-agents-manifest.json) tracks which agents nWave
installed, so uninstall() can remove only nWave agents without touching
user-created ones.
"""

import json
import os
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.install.plugins.opencode_common import (
    parse_frontmatter,
    render_frontmatter,
    uninstall_with_manifest,
    verify_with_manifest,
)
from scripts.shared.agent_catalog import is_public_agent, load_public_agents


_MANIFEST_FILENAME = ".nwave-agents-manifest.json"

_FIELDS_TO_REMOVE = {"name", "model", "skills"}


def _opencode_agents_dir() -> Path:
    """Return the OpenCode agents target directory.

    Returns:
        Path to ~/.config/opencode/agents/
    """
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    base = Path(override) if override else Path.home() / ".config" / "opencode"
    return base / "agents"


def _find_agents_source(context: InstallContext) -> Path | None:
    """Locate the agents source directory from dist or project layout.

    Args:
        context: InstallContext with framework_source and project_root

    Returns:
        Path to the agents source directory, or None if not found
    """
    dist_agents = context.framework_source / "agents"
    if dist_agents.exists():
        return dist_agents

    project_agents = context.project_root / "nWave" / "agents"
    if project_agents.exists():
        return project_agents

    return None


def _parse_tools(tools_value: str | list) -> dict[str, str]:
    """Normalize tools from CSV string or YAML array to OpenCode permission mapping.

    Handles both formats:
        CSV:   "Read, Write, Edit, Bash"
        Array: ["Read", "Glob", "Grep"]

    OpenCode markdown agents require permission values as strings ("allow",
    "deny", "ask"), not booleans. The legacy boolean format is ignored in
    markdown frontmatter.

    Args:
        tools_value: Tools specification as CSV string or list

    Returns:
        Dict mapping lowercase tool names to "allow"
    """
    if isinstance(tools_value, list):
        tool_names = [str(tool).strip() for tool in tools_value]
    else:
        tool_names = [tool.strip() for tool in str(tools_value).split(",")]

    return {name.lower(): "allow" for name in tool_names if name}


def _transform_frontmatter(frontmatter: dict) -> dict:
    """Apply all transformation rules to convert Claude Code frontmatter to OpenCode.

    Transformations:
        1. Remove name, model, skills fields
        2. Rename maxTurns to steps
        3. Add mode: subagent
        4. Transform tools from CSV/array to mapping

    Args:
        frontmatter: Parsed YAML frontmatter dict from Claude Code agent

    Returns:
        New dict with OpenCode-compatible frontmatter
    """
    result = {
        key: value
        for key, value in frontmatter.items()
        if key not in _FIELDS_TO_REMOVE and key != "maxTurns"
    }

    if "maxTurns" in frontmatter:
        result["steps"] = frontmatter["maxTurns"]

    result["mode"] = "subagent"

    if "tools" in result:
        result["permission"] = _parse_tools(result.pop("tools"))

    return result


def _rewrite_skill_paths(body: str) -> str:
    """Rewrite Claude Code skill paths to OpenCode paths in agent body.

    Agent markdown bodies contain hardcoded ~/.claude/skills/ paths that must
    be rewritten to ~/.config/opencode/skills/ for OpenCode compatibility.

    Args:
        body: Agent body text (everything after the frontmatter)

    Returns:
        Body with all skill path references rewritten for OpenCode
    """
    return body.replace("~/.claude/skills/", "~/.config/opencode/skills/")


def _transform_agent(content: str) -> str:
    """Full transformation pipeline: parse, transform, render with body.

    Args:
        content: Full source agent file content (Claude Code format)

    Returns:
        Transformed agent file content (OpenCode format)
    """
    frontmatter, body = parse_frontmatter(content)
    transformed = _transform_frontmatter(frontmatter)
    rendered = render_frontmatter(transformed)
    body = _rewrite_skill_paths(body)
    return rendered + body


def _write_manifest(
    target_dir: Path,
    installed_agent_names: list[str],
) -> None:
    """Write the manifest file tracking nWave-installed agents.

    Args:
        target_dir: OpenCode agents directory
        installed_agent_names: List of installed agent filenames (without .md)
    """
    manifest = {
        "installed_agents": sorted(installed_agent_names),
        "version": "1.0",
    }
    manifest_path = target_dir / _MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# _read_manifest moved to opencode_common.read_manifest (parameterized).


class OpenCodeAgentsPlugin(InstallationPlugin):
    """Plugin for installing nWave agents into OpenCode format."""

    def __init__(self):
        """Initialize OpenCode agents plugin with name and priority."""
        super().__init__(name="opencode-agents", priority=37)

    def install(self, context: InstallContext) -> PluginResult:
        """Install agents from nWave/agents/ as OpenCode agent files.

        Transforms each source agent file by:
        - Removing name, model, skills fields
        - Renaming maxTurns to steps
        - Adding mode: subagent
        - Converting tools to permission mapping with "allow" string values

        A manifest tracks installed agents for safe uninstallation.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  \U0001f4e6 Installing OpenCode agents...")

            agents_source = _find_agents_source(context)
            if agents_source is None:
                context.logger.info(
                    "  \u23ed\ufe0f No agents directory found, skipping"
                )
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No agents to install (source directory not found)",
                )

            target_dir = _opencode_agents_dir()
            target_dir.mkdir(parents=True, exist_ok=True)

            public_agents = (
                set()
                if context.dev_mode
                else load_public_agents(context.project_root / "nWave")
            )

            agent_files = sorted(agents_source.glob("nw-*.md"))
            if not agent_files:
                context.logger.info("  \u23ed\ufe0f No agent files found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No agent files found in source directory",
                )

            installed_names = []
            installed_files = []

            for source_file in agent_files:
                if not is_public_agent(source_file.name, public_agents):
                    continue
                agent_name = source_file.stem
                content = source_file.read_text(encoding="utf-8")

                transformed = _transform_agent(content)

                target_file = target_dir / f"{agent_name}.md"
                target_file.write_text(transformed, encoding="utf-8")

                installed_names.append(agent_name)
                installed_files.append(target_file)

            _write_manifest(target_dir, installed_names)

            context.logger.info(
                f"  \u2705 OpenCode agents installed ({len(installed_names)} agents)"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=(
                    f"OpenCode agents installed successfully "
                    f"({len(installed_names)} agents)"
                ),
                installed_files=installed_files,
            )
        except Exception as e:
            context.logger.error(f"  \u274c Failed to install OpenCode agents: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"OpenCode agents installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall only nWave-installed OpenCode agents using manifest."""
        return uninstall_with_manifest(
            context=context,
            plugin_name=self.name,
            target_dir=_opencode_agents_dir(),
            manifest_filename=_MANIFEST_FILENAME,
            noun="agents",
            installed_key="installed_agents",
        )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify OpenCode agents were installed correctly."""
        return verify_with_manifest(
            context=context,
            plugin_name=self.name,
            target_dir=_opencode_agents_dir(),
            manifest_filename=_MANIFEST_FILENAME,
            noun="agents",
            installed_key="installed_agents",
            source_finder=_find_agents_source,
        )
