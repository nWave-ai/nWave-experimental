"""
Step definitions for plugin validation scenarios.

Covers: milestone-3-plugin-validation.feature
Driving port: PluginValidator
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_bdd import given, parsers, scenarios, then


if TYPE_CHECKING:
    from pathlib import Path


scenarios("../milestone-3-plugin-validation.feature")


# ---------------------------------------------------------------------------
# Given Steps: Broken Plugin Directories
# ---------------------------------------------------------------------------


@given("a plugin directory without a metadata file")
def plugin_without_metadata(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a plugin directory missing .claude-plugin/plugin.json."""
    # Create some content but no metadata
    agents = plugin_output_dir / "agents"
    agents.mkdir(parents=True)
    (agents / "test-agent.md").write_text("# Agent", encoding="utf-8")
    (plugin_output_dir / "hooks").mkdir()
    build_result["plugin_dir"] = plugin_output_dir


@given("a plugin directory with an empty agents section")
def plugin_empty_agents(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a plugin directory with empty agents/."""
    (plugin_output_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_output_dir / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "nw", "version": "1.0.0"}', encoding="utf-8"
    )
    (plugin_output_dir / "agents").mkdir()  # Empty
    (plugin_output_dir / "hooks").mkdir()
    build_result["plugin_dir"] = plugin_output_dir


@given("a plugin directory without hook registrations")
def plugin_without_hooks(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a plugin directory missing hooks/hooks.json."""
    (plugin_output_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_output_dir / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "nw", "version": "1.0.0"}', encoding="utf-8"
    )
    agents = plugin_output_dir / "agents"
    agents.mkdir()
    (agents / "test-agent.md").write_text("# Agent", encoding="utf-8")
    build_result["plugin_dir"] = plugin_output_dir


@given("a plugin directory without the DES enforcement module")
def plugin_without_des(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a plugin directory missing scripts/des/."""
    (plugin_output_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_output_dir / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "nw", "version": "1.0.0"}', encoding="utf-8"
    )
    agents = plugin_output_dir / "agents"
    agents.mkdir()
    (agents / "test-agent.md").write_text("# Agent", encoding="utf-8")
    hooks = plugin_output_dir / "hooks"
    hooks.mkdir()
    (hooks / "hooks.json").write_text('{"hooks": []}', encoding="utf-8")
    build_result["plugin_dir"] = plugin_output_dir


@given("a plugin directory missing metadata, agents, and hooks")
def plugin_missing_multiple(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a plugin directory missing multiple required sections."""
    # Just an empty directory
    build_result["plugin_dir"] = plugin_output_dir


@given("a plugin directory with exactly 1 agent, 1 skill, 1 command, and valid hooks")
def minimal_valid_plugin(plugin_output_dir: Path, build_result: dict[str, Any]):
    """Create a minimal but valid plugin directory."""
    import json

    # Metadata
    meta_dir = plugin_output_dir / ".claude-plugin"
    meta_dir.mkdir(parents=True)
    (meta_dir / "plugin.json").write_text(
        json.dumps({"name": "nw", "version": "0.0.1"}),
        encoding="utf-8",
    )

    # 1 agent
    agents = plugin_output_dir / "agents"
    agents.mkdir()
    (agents / "nw-test.md").write_text(
        "---\nname: nw-test\n---\n# Test\n", encoding="utf-8"
    )

    # 1 skill
    skills = plugin_output_dir / "skills" / "test"
    skills.mkdir(parents=True)
    (skills / "test-skill.md").write_text(
        "---\nname: test\n---\n# Skill\n", encoding="utf-8"
    )

    # 1 command
    commands = plugin_output_dir / "commands"
    commands.mkdir()
    (commands / "test-cmd.md").write_text(
        "---\nname: test-cmd\n---\n# Cmd\n", encoding="utf-8"
    )

    # Hooks
    hooks = plugin_output_dir / "hooks"
    hooks.mkdir()
    (hooks / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "event": "PreToolUse",
                        "command": "echo test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    # DES module
    des = plugin_output_dir / "scripts" / "des"
    des.mkdir(parents=True)
    (des / "__init__.py").write_text("", encoding="utf-8")

    build_result["plugin_dir"] = plugin_output_dir


@given("any plugin directory state")
def any_plugin_state():
    """Placeholder for property-based validation purity test."""
    pass


# ---------------------------------------------------------------------------
# Then Steps: Validation Results
# ---------------------------------------------------------------------------


@then("the validation result is success")
def validation_is_success(build_result: dict[str, Any]):
    """Verify validation passed."""
    validation = build_result["validation_result"]
    assert validation is not None
    assert validation["success"] is True


@then("no validation errors are reported")
def no_validation_errors(build_result: dict[str, Any]):
    """Verify no errors in validation output."""
    validation = build_result["validation_result"]
    errors = validation.get("errors", [])
    assert len(errors) == 0, f"Unexpected errors: {errors}"


@then("the validation result is failure")
def validation_is_failure(build_result: dict[str, Any]):
    """Verify validation failed."""
    validation = build_result["validation_result"]
    assert validation is not None
    assert validation["success"] is False


@then("the validation report confirms agents section is present")
def validation_agents_present(build_result: dict[str, Any]):
    """Verify agents section checked."""
    validation = build_result["validation_result"]
    assert validation["sections"]["agents"] is True


@then("the validation report confirms skills section is present")
def validation_skills_present(build_result: dict[str, Any]):
    """Verify skills section checked."""
    validation = build_result["validation_result"]
    assert validation["sections"]["skills"] is True


@then("the validation report confirms commands section is present")
def validation_commands_present(build_result: dict[str, Any]):
    """Verify commands section checked."""
    validation = build_result["validation_result"]
    assert validation["sections"]["commands"] is True


@then("the validation report confirms hooks section is present")
def validation_hooks_present(build_result: dict[str, Any]):
    """Verify hooks section checked."""
    validation = build_result["validation_result"]
    assert validation["sections"]["hooks"] is True


@then("the validation report confirms metadata section is present")
def validation_metadata_present(build_result: dict[str, Any]):
    """Verify metadata section checked."""
    validation = build_result["validation_result"]
    assert validation["sections"]["metadata"] is True


@then("the hook configuration is valid according to the expected schema")
def hooks_valid_schema(build_result: dict[str, Any]):
    """Verify hooks.json validates against schema."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    assert "hooks" in hooks
    assert isinstance(hooks["hooks"], list)


@then("every hook entry has a command and event type")
def hooks_have_required_fields(build_result: dict[str, Any]):
    """Verify each hook has command and event."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    for hook in hooks["hooks"]:
        assert "event" in hook, f"Hook missing event: {hook}"
        assert "command" in hook, f"Hook missing command: {hook}"


# ---------------------------------------------------------------------------
# Then Steps: Completeness Report
# ---------------------------------------------------------------------------


@then(parsers.parse("the validation report shows {count:d} agents"))
def validation_agent_count(count: int, build_result: dict[str, Any]):
    """Verify agent count in validation report."""
    validation = build_result["validation_result"]
    assert validation["counts"]["agents"] == count


@then(parsers.parse("the validation report shows at least {count:d} skill files"))
def validation_skill_count(count: int, build_result: dict[str, Any]):
    """Verify minimum skill count in validation report."""
    validation = build_result["validation_result"]
    assert validation["counts"]["skills"] >= count


@then(parsers.parse("the validation report shows at least {count:d} command files"))
def validation_command_count(count: int, build_result: dict[str, Any]):
    """Verify minimum command count in validation report."""
    validation = build_result["validation_result"]
    assert validation["counts"]["commands"] >= count


# ---------------------------------------------------------------------------
# Then Steps: Error Details
# ---------------------------------------------------------------------------


@then("the validation error mentions missing metadata")
def error_mentions_metadata(build_result: dict[str, Any]):
    """Verify error message references metadata."""
    validation = build_result["validation_result"]
    errors = " ".join(validation.get("errors", []))
    assert "metadata" in errors.lower() or "plugin.json" in errors.lower()


@then("the validation error mentions missing agents")
def error_mentions_agents(build_result: dict[str, Any]):
    """Verify error message references agents."""
    validation = build_result["validation_result"]
    errors = " ".join(validation.get("errors", []))
    assert "agent" in errors.lower()


@then("the validation error mentions missing hooks")
def error_mentions_hooks(build_result: dict[str, Any]):
    """Verify error message references hooks."""
    validation = build_result["validation_result"]
    errors = " ".join(validation.get("errors", []))
    assert "hook" in errors.lower()


@then("the validation error mentions missing DES module")
def error_mentions_des(build_result: dict[str, Any]):
    """Verify error message references DES."""
    validation = build_result["validation_result"]
    errors = " ".join(validation.get("errors", []))
    assert "des" in errors.lower()


@then(
    parsers.parse(
        "the validation error list contains at least {count:d} distinct errors"
    )
)
def multiple_validation_errors(count: int, build_result: dict[str, Any]):
    """Verify multiple errors reported at once."""
    validation = build_result["validation_result"]
    errors = validation.get("errors", [])
    assert len(errors) >= count, (
        f"Expected >= {count} errors, got {len(errors)}: {errors}"
    )


# ---------------------------------------------------------------------------
# Then Steps: Property-Based
# ---------------------------------------------------------------------------


@then("both validation results are identical")
def validation_deterministic():
    """Property: validation is deterministic (placeholder)."""
    pass


@then("the plugin directory is unchanged after validation")
def validation_no_side_effects():
    """Property: validation has no side effects (placeholder)."""
    pass
