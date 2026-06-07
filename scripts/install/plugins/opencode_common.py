"""Shared utilities for OpenCode installer plugins.

Provides pure functions for parsing/rendering YAML frontmatter and
manifest-based uninstall/verify lifecycle helpers, used by both
opencode_agents_plugin and opencode_commands_plugin.

These functions handle malformed input gracefully by returning empty
dicts rather than raising exceptions -- the caller's install() method
wraps everything in try/except for higher-level error reporting.

The lifecycle helpers (read_manifest, uninstall_with_manifest,
verify_with_manifest) abstract the noun-vs-noun differences between
"commands" and "agents" plugins via callable + label parameters,
preserving exact behavior of both pre-refactor implementations.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import yaml


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from scripts.install.plugins.base import InstallContext, PluginResult


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body content.

    Expects content in the form:
        ---
        key: value
        ---

        Body content here.

    Handles gracefully:
    - Missing opening delimiter: returns ({}, content)
    - Missing closing delimiter: returns ({}, content)
    - Malformed YAML: returns ({}, content)

    Args:
        content: Full file content with YAML frontmatter

    Returns:
        Tuple of (parsed frontmatter dict, body string including leading newline)
    """
    if not content.startswith("---"):
        return {}, content

    end_index = content.find("---", 3)
    if end_index == -1:
        return {}, content

    frontmatter_text = content[3:end_index].strip()
    body = content[end_index + 3 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return {}, content

    return frontmatter, body


def render_frontmatter(frontmatter: dict) -> str:
    """Serialize a frontmatter dict back to YAML frontmatter string.

    Uses block style for nested mappings (not flow style) because
    OpenCode's Zod parser expects a record format.

    Args:
        frontmatter: Transformed frontmatter dict

    Returns:
        String in "---\\nkey: value\\n---" format
    """
    yaml_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_text}---"


def read_manifest(target_dir: Path, manifest_filename: str) -> dict | None:
    """Read the install manifest from target_dir, or None if absent.

    Args:
        target_dir: Directory containing the manifest
        manifest_filename: Manifest file name (e.g. ".nwave-commands-manifest.json")

    Returns:
        Parsed manifest dict, or None if file does not exist.
    """
    manifest_path = target_dir / manifest_filename
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def uninstall_with_manifest(
    context: InstallContext,
    plugin_name: str,
    target_dir: Path,
    manifest_filename: str,
    noun: str,
    installed_key: str,
) -> PluginResult:
    """Manifest-driven uninstall shared between OpenCode commands + agents plugins.

    Reads the manifest from target_dir, removes each item listed under
    ``installed_key`` (file = ``<name>.md`` in target_dir), then deletes the
    manifest itself. Items not in the manifest are preserved (user-created).

    Args:
        context: Install context (used for logging).
        plugin_name: Plugin identifier for the returned PluginResult.
        target_dir: OpenCode subdirectory containing items + manifest.
        manifest_filename: Manifest file name.
        noun: Human label for log + message ("commands" or "agents").
        installed_key: Manifest key listing installed item names
            (e.g. "installed_commands" or "installed_agents").

    Returns:
        PluginResult with success/failure outcome.
    """
    from scripts.install.plugins.base import PluginResult

    try:
        context.logger.info(f"  \U0001f5d1️ Uninstalling OpenCode {noun}...")
        manifest = read_manifest(target_dir, manifest_filename)

        if manifest is None:
            context.logger.info(f"  ⏭️ No OpenCode {noun} manifest found, skipping")
            return PluginResult(
                success=True,
                plugin_name=plugin_name,
                message=f"No OpenCode {noun} to uninstall (no manifest found)",
            )

        installed = manifest.get(installed_key, [])
        removed_count = 0
        for item_name in installed:
            item_file = target_dir / f"{item_name}.md"
            if item_file.exists():
                item_file.unlink()
                removed_count += 1

        manifest_path = target_dir / manifest_filename
        if manifest_path.exists():
            manifest_path.unlink()

        context.logger.info(f"  \U0001f5d1️ Removed {removed_count} OpenCode {noun}")
        return PluginResult(
            success=True,
            plugin_name=plugin_name,
            message=f"OpenCode {noun} uninstalled ({removed_count} removed)",
        )
    except Exception as e:
        context.logger.error(f"  ❌ Failed to uninstall OpenCode {noun}: {e}")
        return PluginResult(
            success=False,
            plugin_name=plugin_name,
            message=f"OpenCode {noun} uninstallation failed: {e!s}",
            errors=[str(e)],
        )


def verify_with_manifest(
    context: InstallContext,
    plugin_name: str,
    target_dir: Path,
    manifest_filename: str,
    noun: str,
    installed_key: str,
    source_finder: Callable[[InstallContext], Path | None],
) -> PluginResult:
    """Manifest-driven verify shared between OpenCode commands + agents plugins.

    Reads the manifest and asserts each listed file exists. If the manifest is
    absent AND the source path resolves (via source_finder), the absence is a
    failure (manifest expected but missing). If both manifest and source are
    absent, verification is skipped (nothing was configured).

    Args:
        context: Install context (used for logging).
        plugin_name: Plugin identifier for the returned PluginResult.
        target_dir: OpenCode subdirectory.
        manifest_filename: Manifest file name.
        noun: Human label ("commands" or "agents").
        installed_key: Manifest key listing installed names.
        source_finder: Callable returning the source directory if present,
            or None if the plugin had nothing to install.

    Returns:
        PluginResult with verification outcome.
    """
    from scripts.install.plugins.base import PluginResult

    try:
        context.logger.info(f"  \U0001f50e Verifying OpenCode {noun}...")
        manifest = read_manifest(target_dir, manifest_filename)

        if manifest is None:
            source = source_finder(context)
            if source is None:
                context.logger.info(
                    f"  ⏭️ No OpenCode {noun} to verify (none configured)"
                )
                return PluginResult(
                    success=True,
                    plugin_name=plugin_name,
                    message=f"No OpenCode {noun} configured, verification skipped",
                )
            return PluginResult(
                success=False,
                plugin_name=plugin_name,
                message=f"OpenCode {noun} verification failed: manifest not found",
                errors=[f"Manifest file {manifest_filename} not found"],
            )

        installed = manifest.get(installed_key, [])
        missing: list[str] = []
        verified_count = 0
        for item_name in installed:
            item_file = target_dir / f"{item_name}.md"
            if not item_file.exists():
                missing.append(f"{item_name}.md not found")
            else:
                verified_count += 1

        if missing:
            context.logger.error(
                f"  ❌ OpenCode {noun} verification failed: {len(missing)} missing"
            )
            return PluginResult(
                success=False,
                plugin_name=plugin_name,
                message=(
                    f"OpenCode {noun} verification failed: "
                    f"{len(missing)} {noun} missing"
                ),
                errors=missing,
            )

        context.logger.info(f"  ✅ Verified {verified_count} OpenCode {noun}")
        return PluginResult(
            success=True,
            plugin_name=plugin_name,
            message=f"OpenCode {noun} verification passed ({verified_count} {noun})",
        )
    except Exception as e:
        context.logger.error(f"  ❌ Failed to verify OpenCode {noun}: {e}")
        return PluginResult(
            success=False,
            plugin_name=plugin_name,
            message=f"OpenCode {noun} verification failed: {e!s}",
            errors=[str(e)],
        )
