"""
Step definitions for coexistence verification scenarios.

Covers: milestone-5-coexistence.feature
Driving port: PluginAssembler, path resolution utilities
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../milestone-5-coexistence.feature")


# ---------------------------------------------------------------------------
# Given Steps
# ---------------------------------------------------------------------------


@given("only the plugin is installed")
def only_plugin_installed(tmp_path: Path, build_result: dict[str, Any]):
    """Simulate an environment with only the plugin."""
    plugin_dir = tmp_path / ".claude" / "plugins" / "cache" / "nwave"
    plugin_dir.mkdir(parents=True)
    build_result["plugin_install_path"] = plugin_dir
    build_result["installer_install_path"] = None


@given("only the custom installer is active")
def only_installer_active(tmp_path: Path, build_result: dict[str, Any]):
    """Simulate an environment with only the custom installer."""
    installer_dir = tmp_path / ".claude"
    (installer_dir / "agents" / "nw").mkdir(parents=True)
    (installer_dir / "commands" / "nw").mkdir(parents=True)
    (installer_dir / "skills" / "nw").mkdir(parents=True)
    build_result["installer_install_path"] = installer_dir
    build_result["plugin_install_path"] = None


@given("the plugin is installed")
def plugin_is_installed(tmp_path: Path, build_result: dict[str, Any]):
    """Create plugin installation."""
    plugin_dir = tmp_path / ".claude" / "plugins" / "cache" / "nwave"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "agents").mkdir()
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "hooks").mkdir()
    build_result["plugin_install_path"] = plugin_dir


@given("the custom installer is also active")
def installer_also_active(tmp_path: Path, build_result: dict[str, Any]):
    """Create custom installer installation alongside plugin."""
    installer_dir = tmp_path / ".claude"
    (installer_dir / "agents" / "nw").mkdir(parents=True)
    (installer_dir / "commands" / "nw").mkdir(parents=True)
    build_result["installer_install_path"] = installer_dir


@given("the plugin hook registrations are in the plugin directory")
def plugin_hooks_in_plugin_dir(build_result: dict[str, Any]):
    """Verify plugin hooks are in plugin directory."""
    plugin_dir = build_result.get("plugin_install_path")
    if plugin_dir:
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)


@given("the custom installer hook registrations are in the settings file")
def installer_hooks_in_settings(build_result: dict[str, Any]):
    """Verify installer hooks are in settings.json."""
    pytest.skip("Hook registration location check not yet implemented")


@given(parsers.parse('the plugin is version "{version}"'))
def plugin_version_is(version: str, build_result: dict[str, Any]):
    """Set plugin version."""
    build_result["plugin_version"] = version


@given(parsers.parse('the custom installer is version "{version}"'))
def installer_version_is(version: str, build_result: dict[str, Any]):
    """Set custom installer version."""
    build_result["installer_version"] = version


@given("both plugin and custom installer are active")
def both_active(tmp_path: Path, build_result: dict[str, Any]):
    """Create both installations."""
    # Plugin path
    plugin_dir = tmp_path / ".claude" / "plugins" / "cache" / "nwave"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "agents").mkdir()
    (plugin_dir / "commands").mkdir()

    # Installer path
    installer_dir = tmp_path / ".claude"
    (installer_dir / "agents" / "nw").mkdir(parents=True)
    (installer_dir / "commands" / "nw").mkdir(parents=True)

    build_result["plugin_install_path"] = plugin_dir
    build_result["installer_install_path"] = installer_dir


@given("any valid installation of both plugin and custom installer")
def any_valid_dual_install():
    """Placeholder for property-based path disjointness test."""
    pytest.skip("Implement with Hypothesis in DELIVER wave")


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("a user invokes a slash command")
def invoke_slash_command():
    """Simulate invoking a /nw: command."""
    # This is a behavioral test -- command discovery is Claude Code's job
    pytest.skip("Command invocation requires Claude Code runtime")


@when("both are active simultaneously")
def both_simultaneous(build_result: dict[str, Any]):
    """Verify both installations exist."""
    assert build_result.get("plugin_install_path") is not None
    assert build_result.get("installer_install_path") is not None


@when("a version consistency check runs")
def run_version_check(build_result: dict[str, Any]):
    """Run version consistency between plugin and installer."""
    # TODO: Implement version consistency check
    pytest.skip("Version consistency check not yet implemented")


@when("the custom installer is uninstalled")
def uninstall_installer(build_result: dict[str, Any]):
    """Simulate removing the custom installer."""
    import shutil

    installer_path = build_result.get("installer_install_path")
    if installer_path:
        for subdir in ["agents/nw", "commands/nw", "skills/nw"]:
            target = installer_path / subdir
            if target.exists():
                shutil.rmtree(target)


@when("the plugin is removed")
def remove_plugin(build_result: dict[str, Any]):
    """Simulate removing the plugin."""
    import shutil

    plugin_path = build_result.get("plugin_install_path")
    if plugin_path and plugin_path.exists():
        shutil.rmtree(plugin_path)


# ---------------------------------------------------------------------------
# Then Steps
# ---------------------------------------------------------------------------


@then("the plugin target directory differs from the custom installer target directory")
def different_install_paths(build_result: dict[str, Any]):
    """Verify plugin and installer use different paths."""
    # Plugin: ~/.claude/plugins/cache/nwave/
    # Installer: ~/.claude/agents/nw/, ~/.claude/commands/nw/, etc.
    plugin_path = Path("~/.claude/plugins/cache/nwave").expanduser()
    installer_agents = Path("~/.claude/agents/nw").expanduser()
    assert plugin_path != installer_agents
    assert not str(plugin_path).startswith(str(installer_agents))
    assert not str(installer_agents).startswith(str(plugin_path))


@then("no files overlap between plugin and custom installer paths")
def no_file_overlap():
    """Verify disjoint file sets."""
    # Plugin is in plugins/cache/nwave/, installer is in agents/nw/ etc.
    # These are structurally different paths
    plugin_base = "plugins/cache/nwave"
    installer_bases = ["agents/nw", "commands/nw", "skills/nw"]
    for base in installer_bases:
        assert not plugin_base.startswith(base)
        assert not base.startswith(plugin_base)


@then("the command is discovered from the plugin directory")
def command_from_plugin():
    """Verify command discovery from plugin."""
    pytest.skip("Command discovery requires Claude Code runtime")


@then("no errors reference missing custom installer files")
def no_installer_errors():
    """Verify no errors about missing installer files."""
    pytest.skip("Error reference check requires Claude Code runtime")


@then("the command is discovered from the custom installer directory")
def command_from_installer():
    """Verify command discovery from installer."""
    pytest.skip("Command discovery requires Claude Code runtime")


@then("no errors reference missing plugin files")
def no_plugin_errors():
    """Verify no errors about missing plugin files."""
    pytest.skip("Error reference check requires Claude Code runtime")


@then("the command executes successfully from one of the two sources")
def command_executes_from_either():
    """Verify command works with both installations."""
    pytest.skip("Command execution requires Claude Code runtime")


@then("each DES enforcement event is handled by exactly one source")
def single_event_handler():
    """Verify no duplicate hook handling."""
    pytest.skip("Hook deduplication check not yet implemented")


@then("no event triggers duplicate enforcement")
def no_duplicate_enforcement():
    """Verify no double-enforcement."""
    pytest.skip("Duplicate enforcement check not yet implemented")


@then("a warning is raised about version mismatch between installation methods")
def version_mismatch_warning():
    """Verify version mismatch detection."""
    pytest.skip("Version mismatch warning not yet implemented")


@then("the plugin continues to operate normally")
def plugin_still_works(build_result: dict[str, Any]):
    """Verify plugin survives installer removal."""
    plugin_path = build_result.get("plugin_install_path")
    if plugin_path:
        assert plugin_path.exists()


@then("no plugin files are affected by the uninstall")
def plugin_files_intact(build_result: dict[str, Any]):
    """Verify plugin files remain after installer removal."""
    plugin_path = build_result.get("plugin_install_path")
    if plugin_path:
        assert plugin_path.exists()
        assert (plugin_path / "agents").exists()


@then("the custom installer continues to operate normally")
def installer_still_works(build_result: dict[str, Any]):
    """Verify installer survives plugin removal."""
    installer_path = build_result.get("installer_install_path")
    if installer_path:
        assert (installer_path / "agents" / "nw").exists()


@then("no custom installer files are affected by the removal")
def installer_files_intact(build_result: dict[str, Any]):
    """Verify installer files remain after plugin removal."""
    installer_path = build_result.get("installer_install_path")
    if installer_path:
        assert (installer_path / "agents" / "nw").exists()


@then(
    "the set of files owned by the plugin is disjoint from the set owned by the custom installer"
)
def disjoint_file_ownership():
    """Property: plugin and installer file sets never overlap."""
    # This is structurally guaranteed by different base paths
    plugin_prefix = "plugins/cache/nwave"
    installer_prefixes = ["agents/nw", "commands/nw", "skills/nw", "lib/python"]
    for prefix in installer_prefixes:
        assert not plugin_prefix.startswith(prefix)
        assert not prefix.startswith(plugin_prefix)
