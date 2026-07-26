"""Plugin for installing nWave agents into Codex CLI's TOML agent format.

Codex CLI expects agents at: ~/.codex/agents/{agent-name}.toml
Each agent file is TOML with:
  name = "agent-name"
  description = "..."
  developer_instructions = '''
  ...full agent body...
  '''
  model = "..."   (optional)

This is distinct from OpenCode (~/.config/opencode/agents/*.md), which uses
YAML-frontmatter Markdown. The transform pipeline:

  Claude Code source (.md, YAML frontmatter + Markdown body)
    -> parse frontmatter + body
    -> extract scalar fields (name, description, model)
    -> drop tools block (Codex has no tool-permission equivalent; WARN logged)
    -> render TOML with body as developer_instructions

A manifest (.nwave-agents-manifest.json) tracks which agents nWave installed,
enabling safe uninstallation without touching user-created agents.
"""

import importlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.install.plugins.codex_des_plugin import _legacy_direct_des_command
from scripts.install.plugins.opencode_common import parse_frontmatter
from scripts.shared.agent_catalog import is_public_agent, load_public_agents
from scripts.shared.platform_contracts import CODEX_AGENT_FORBIDDEN_FIELDS
from scripts.shared.skill_path_rewrite import rewrite_host_paths


_MANIFEST_FILENAME = ".nwave-agents-manifest.json"
_LEGACY_AGENT_SOURCES = {
    "nw-architect": "nw-solution-architect",
    "nw-crafter": "nw-software-crafter",
}
_logger = logging.getLogger(__name__)
_toml_reader = importlib.import_module(
    "tomllib" if sys.version_info >= (3, 11) else "tomli"
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _codex_agents_dir() -> Path:
    """Return the Codex CLI agents target directory.

    Codex agents live at ~/.codex/agents/. CODEX_HOME overrides ~/.codex/.

    Returns:
        Path to ~/.codex/agents/ (or $CODEX_HOME/agents/)
    """
    override = os.environ.get("CODEX_HOME")
    base = Path(override) if override else Path.home() / ".codex"
    return base / "agents"


def _codex_config_dir() -> Path:
    """Return the Codex CLI configuration directory.

    Returns:
        Path to ~/.codex/ (or $CODEX_HOME if set)
    """
    override = os.environ.get("CODEX_HOME")
    return Path(override) if override else Path.home() / ".codex"


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


# ---------------------------------------------------------------------------
# Transform pipeline (pure functions)
# ---------------------------------------------------------------------------


def _extract_scalar_fields(frontmatter: dict) -> dict[str, str]:
    """Extract string-valued TOML fields from the agent frontmatter.

    Keeps only scalar (string) fields that have TOML equivalents.
    Drops all fields in CODEX_AGENT_FORBIDDEN_FIELDS and any non-string
    complex values (lists, dicts).

    Args:
        frontmatter: Parsed YAML frontmatter dict from a Claude Code agent

    Returns:
        Dict of TOML-compatible scalar fields
    """
    return {
        key: str(value)
        for key, value in frontmatter.items()
        if key not in CODEX_AGENT_FORBIDDEN_FIELDS and isinstance(value, str)
    }


def _omit_unsupported_model(scalar_fields: dict[str, str]) -> None:
    """Drop Claude-only model selectors that have no declared Codex mapping."""
    model = scalar_fields.get("model", "")
    normalized = model.casefold()
    if normalized in {"inherit", "haiku", "sonnet", "opus"} or normalized.startswith(
        "claude-"
    ):
        scalar_fields.pop("model", None)


def _warn_if_tools_dropped(agent_name: str, frontmatter: dict) -> None:
    """Log a warning when a tools block is dropped during transform.

    Codex CLI has no per-agent tool-permission block equivalent; permissions
    are controlled via sandbox_mode and approval_policy at config level.

    Args:
        agent_name: Agent identifier (for log context)
        frontmatter: Parsed frontmatter dict, potentially containing tools
    """
    if "tools" in frontmatter:
        _logger.warning(
            "codex_agents_plugin: dropping 'tools' block for agent '%s' "
            "(Codex has no per-agent tool-permission equivalent; "
            "use sandbox_mode/approval_policy in config.toml instead)",
            agent_name,
        )


def _render_toml_agent(scalar_fields: dict[str, str], body: str) -> str:
    """Render a Codex agent TOML file from scalar fields and the agent body.

    The Codex agent TOML schema requires:
      name = "..."            (required)
      description = "..."     (required)
      developer_instructions = "..."  (multi-line string, equivalent to body)

    Optional fields (model, etc.) are included when present in scalar_fields.
    The body is assigned to developer_instructions using a TOML basic
    multi-line string (triple-quoted).

    Args:
        scalar_fields: TOML-compatible scalar fields (name, description, model…)
        body: Agent body text (Markdown section after the YAML frontmatter)

    Returns:
        Complete TOML file content as a string
    """
    lines: list[str] = []

    # Emit canonical fields first in a stable order
    for key in ("name", "description", "model"):
        if key in scalar_fields:
            lines.append(f"{key} = {_toml_string(scalar_fields[key])}")

    # Emit remaining scalar fields (alphabetical for stability)
    for key in sorted(scalar_fields):
        if key not in ("name", "description", "model"):
            lines.append(f"{key} = {_toml_string(scalar_fields[key])}")

    # JSON string escaping is compatible with TOML basic strings and safely
    # handles quotes, backslashes, and control characters in arbitrary bodies.
    lines.append(f"developer_instructions = {_toml_multiline_string(body)}")

    return "\n".join(lines) + "\n"


def _toml_string(value: str) -> str:
    """Render a TOML basic string using JSON's compatible string grammar.

    Args:
        value: Raw Python string value

    Returns:
        TOML-quoted string (e.g. '"hello \\"world\\""')
    """
    # Keep non-ASCII scalar values literal: JSON's UTF-16 surrogate-pair escapes
    # for astral characters are not valid TOML Unicode escapes. JSON already
    # escapes C0 controls; TOML additionally forbids a literal DEL character.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")


def _toml_multiline_string(value: str) -> str:
    """Render arbitrary text as a TOML-compatible multi-line basic string.

    The body is escaped first with the stdlib JSON serializer, whose string
    escape grammar is compatible with TOML basic strings. Only the JSON
    delimiters are replaced by TOML's multi-line delimiters.

    Args:
        value: Multi-line string content (agent body)

    Returns:
        TOML multi-line basic string literal
    """
    escaped_body = _toml_string(value)[1:-1]
    return f'"""\n{escaped_body}"""'


def _transform_agent(source_content: str, agent_name: str) -> str:
    """Full transform pipeline: Claude Code agent MD -> Codex TOML.

    Pipeline:
      1. Parse YAML frontmatter + Markdown body
      2. Warn if tools block is present (will be dropped)
      3. Extract scalar TOML fields (drop forbidden + non-scalar)
      4. Render TOML with body as developer_instructions

    Args:
        source_content: Full source agent file content (Claude Code format)
        agent_name: Agent stem name (used for log context only)

    Returns:
        Transformed agent TOML content
    """
    frontmatter, body = parse_frontmatter(source_content)
    _warn_if_tools_dropped(agent_name, frontmatter)
    scalar_fields = _extract_scalar_fields(frontmatter)
    _omit_unsupported_model(scalar_fields)
    body = rewrite_host_paths(body, "codex")
    return _render_toml_agent(scalar_fields, body)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _write_manifest(target_dir: Path, installed_agent_names: list[str]) -> None:
    """Write the manifest tracking nWave-installed Codex agents.

    Args:
        target_dir: Codex agents directory
        installed_agent_names: List of installed agent stems (without .toml)
    """
    manifest = {
        "installed_agents": sorted(installed_agent_names),
        "version": "1.0",
    }
    manifest_path = target_dir / _MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _read_manifest(target_dir: Path) -> dict | None:
    """Read the manifest file if it exists.

    Args:
        target_dir: Codex agents directory

    Returns:
        Parsed manifest dict, or None if not found
    """
    manifest_path = target_dir / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _legacy_agent_names(codex_dir: Path, target_dir: Path) -> set[str]:
    """Return legacy aliases only when the DES ownership witness is exact."""
    if (target_dir / _MANIFEST_FILENAME).exists():
        return set()
    hooks_path = codex_dir / "hooks.json"
    manifest_path = codex_dir / ".nwave-des-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hooks_document = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    if _legacy_direct_des_command(manifest, hooks_path, hooks_document) is None:
        return set()
    return {
        name
        for name in _LEGACY_AGENT_SOURCES
        if (target_dir / f"{name}.toml").is_file()
    }


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------


class CodexAgentsPlugin(InstallationPlugin):
    """Plugin for installing nWave agents into Codex CLI TOML format."""

    def __init__(self) -> None:
        """Initialize Codex agents plugin with name and priority."""
        super().__init__(name="codex-agents", priority=45)
        self.dependencies = ["codex-skills"]

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Check whether Codex CLI is present; skip gracefully if not.

        Detection: ~/.codex/ directory exists OR `codex` binary in PATH.

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
                message="Codex CLI not detected, skipping agents installation",
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Codex agents prerequisites validated",
        )

    def install(self, context: InstallContext) -> PluginResult:
        """Install agents from nWave/agents/ as Codex TOML files.

        Transform pipeline per agent:
          1. Parse YAML frontmatter + Markdown body
          2. Drop tools block (WARN logged; Codex has no equivalent)
          3. Emit scalar fields (name, description, model) as TOML
          4. Emit Markdown body as developer_instructions multi-line string
          5. Write to ~/.codex/agents/{agent-name}.toml

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            prereq = self.validate_prerequisites(context)
            if "skip" in prereq.message.lower():
                return prereq

            context.logger.info("  Installing Codex agents...")

            agents_source = _find_agents_source(context)
            if agents_source is None:
                context.logger.info("  No agents directory found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No agents to install (source directory not found)",
                )

            target_dir = _codex_agents_dir()
            target_dir.mkdir(parents=True, exist_ok=True)

            public_agents = (
                set()
                if context.dev_mode
                else load_public_agents(context.project_root / "nWave")
            )

            agent_files = sorted(agents_source.glob("nw-*.md"))
            if not agent_files:
                context.logger.info("  No agent files found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No agent files found in source directory",
                )

            installed_names: list[str] = []
            installed_files: list[Path] = []

            for source_file in agent_files:
                if not is_public_agent(source_file.name, public_agents):
                    continue

                agent_name = source_file.stem
                content = source_file.read_text(encoding="utf-8")
                transformed = _transform_agent(content, agent_name)

                target_file = target_dir / f"{agent_name}.toml"
                target_file.write_text(transformed, encoding="utf-8")

                installed_names.append(agent_name)
                installed_files.append(target_file)

            # The old bootstrap used two role aliases before the native Codex
            # agent manifest existed.  The exact DES witness authorizes only
            # these known aliases; arbitrary ``nw-*.toml`` files remain the
            # preflight's fail-closed concern.
            codex_dir = _codex_config_dir()
            for legacy_name in sorted(_legacy_agent_names(codex_dir, target_dir)):
                source_name = _LEGACY_AGENT_SOURCES[legacy_name]
                source_file = agents_source / f"{source_name}.md"
                if not source_file.is_file():
                    continue
                content = source_file.read_text(encoding="utf-8")
                transformed = _transform_agent(content, legacy_name)
                target_file = target_dir / f"{legacy_name}.toml"
                target_file.write_text(transformed, encoding="utf-8")
                installed_names.append(legacy_name)
                installed_files.append(target_file)

            _write_manifest(target_dir, installed_names)

            context.logger.info(
                f"  Codex agents installed ({len(installed_names)} agents)"
            )

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=(
                    f"Codex agents installed successfully ({len(installed_names)} agents)"
                ),
                installed_files=installed_files,
            )

        except Exception as e:
            context.logger.error(f"  Failed to install Codex agents: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex agents installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Uninstall only nWave-installed Codex agents using manifest.

        Reads the manifest to determine which agents were installed by nWave,
        removes only those (.toml files), and leaves user-created agents
        untouched. The manifest is also removed.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            context.logger.info("  Uninstalling Codex agents...")

            target_dir = _codex_agents_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                context.logger.info("  No Codex agents manifest found, skipping")
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="No Codex agents to uninstall (no manifest found)",
                )

            installed_agents = manifest.get("installed_agents", [])
            removed_count = 0

            for agent_name in installed_agents:
                agent_file = target_dir / f"{agent_name}.toml"
                if agent_file.exists():
                    agent_file.unlink()
                    removed_count += 1

            manifest_path = target_dir / _MANIFEST_FILENAME
            if manifest_path.exists():
                manifest_path.unlink()

            context.logger.info(f"  Removed {removed_count} Codex agents")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Codex agents uninstalled ({removed_count} removed)",
            )

        except Exception as e:
            context.logger.error(f"  Failed to uninstall Codex agents: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex agents uninstallation failed: {e!s}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify Codex agents were installed correctly.

        Checks that each agent listed in the manifest has a valid .toml file.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            context.logger.info("  Verifying Codex agents...")

            target_dir = _codex_agents_dir()
            manifest = _read_manifest(target_dir)

            if manifest is None:
                agents_source = _find_agents_source(context)
                if agents_source is None:
                    context.logger.info("  No Codex agents to verify (none configured)")
                    return PluginResult(
                        success=True,
                        plugin_name=self.name,
                        message="No Codex agents configured, verification skipped",
                    )

                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Codex agents verification failed: manifest not found",
                    errors=["Manifest file .nwave-agents-manifest.json not found"],
                )

            installed_agents = manifest.get("installed_agents", [])
            if not isinstance(installed_agents, list) or not installed_agents:
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Codex agents verification failed: empty population",
                    errors=["Manifest contains no installed Codex agents"],
                )

            agents_source = _find_agents_source(context)
            if agents_source is None:
                expected_agents: set[str] = set()
            else:
                public_agents = (
                    set()
                    if context.dev_mode
                    else load_public_agents(context.project_root / "nWave")
                )
                expected_agents = {
                    source_file.stem
                    for source_file in agents_source.glob("nw-*.md")
                    if is_public_agent(source_file.name, public_agents)
                }
            installed_set = set(installed_agents)
            permitted_agents = expected_agents | set(_LEGACY_AGENT_SOURCES)
            if not expected_agents.issubset(
                installed_set
            ) or not installed_set.issubset(permitted_agents):
                missing = sorted(expected_agents - installed_set)
                unexpected = sorted(installed_set - permitted_agents)
                errors = []
                if missing:
                    errors.append(
                        f"Manifest missing expected agents: {', '.join(missing)}"
                    )
                if unexpected:
                    errors.append(
                        f"Manifest contains unexpected agents: {', '.join(unexpected)}"
                    )
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Codex agents verification failed: population mismatch",
                    errors=errors,
                )

            missing_agents: list[str] = []
            verified_count = 0

            for agent_name in installed_agents:
                agent_toml = target_dir / f"{agent_name}.toml"
                if not agent_toml.exists():
                    missing_agents.append(f"{agent_name}.toml not found")
                else:
                    try:
                        document = _toml_reader.loads(
                            agent_toml.read_text(encoding="utf-8")
                        )
                    except (OSError, _toml_reader.TOMLDecodeError) as error:
                        missing_agents.append(
                            f"{agent_name}.toml is not loadable TOML: {error}"
                        )
                        continue
                    required = ("name", "description", "developer_instructions")
                    absent = [
                        field
                        for field in required
                        if not isinstance(document.get(field), str)
                        or not document[field].strip()
                    ]
                    if absent:
                        missing_agents.append(
                            f"{agent_name}.toml missing required fields: "
                            f"{', '.join(absent)}"
                        )
                        continue
                    verified_count += 1

            if missing_agents:
                context.logger.error(
                    f"  Codex agents verification failed: {len(missing_agents)} missing"
                )
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message=(
                        f"Codex agents verification failed: "
                        f"{len(missing_agents)} agents missing .toml"
                    ),
                    errors=missing_agents,
                )

            context.logger.info(f"  Verified {verified_count} Codex agents")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message=f"Codex agents verification passed ({verified_count} agents)",
            )

        except Exception as e:
            context.logger.error(f"  Failed to verify Codex agents: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex agents verification failed: {e!s}",
                errors=[str(e)],
            )
