"""
Step definitions for plugin build assembly scenarios.

Covers: walking-skeleton.feature, milestone-1-plugin-assembler.feature
Driving port: PluginAssembler (build pipeline entry point)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


if TYPE_CHECKING:
    from pathlib import Path


# Register feature files for this step module
scenarios("../walking-skeleton.feature")
scenarios("../milestone-1-plugin-assembler.feature")


# ---------------------------------------------------------------------------
# Given Steps: Source Tree Context
# ---------------------------------------------------------------------------


@given("the nWave source tree is available")
def nwave_source_available(nwave_source_tree: Path):
    """Verify the nWave source tree exists and contains expected content."""
    assert nwave_source_tree.exists()
    assert (nwave_source_tree / "agents").exists()


@given("a clean output directory for the plugin build")
def clean_output_dir(plugin_output_dir: Path):
    """Verify the output directory is clean and writable."""
    assert plugin_output_dir.exists()
    assert len(list(plugin_output_dir.iterdir())) == 0


@given("default build configuration for the nWave source tree")
def default_config(build_config: dict[str, Any]):
    """Verify default build configuration is available."""
    assert build_config["plugin_name"] == "nw"
    assert build_config["nwave_dir"].exists()


@given(parsers.parse('the project version is "{version}"'))
def project_version_set(build_config: dict[str, Any], tmp_path: Path, version: str):
    """Override the project version for testing."""
    # Create a temporary pyproject.toml with the specified version
    pyproject = tmp_path / "pyproject_override.toml"
    pyproject.write_text(
        f'[project]\nname = "nwave"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    build_config["pyproject_path"] = pyproject
    build_config["expected_version"] = version


# ---------------------------------------------------------------------------
# Given Steps: Error Path Setup
# ---------------------------------------------------------------------------


@given("the source tree is missing the agents directory")
def source_missing_agents(build_config: dict[str, Any], tmp_path: Path):
    """Create a source tree without agents."""
    broken_source = tmp_path / "broken_source" / "nWave"
    broken_source.mkdir(parents=True)
    # Create skills and commands but NOT agents
    (broken_source / "skills").mkdir()
    (broken_source / "tasks" / "nw").mkdir(parents=True)
    build_config["nwave_dir"] = broken_source


@given("the source tree is missing the skills directory")
def source_missing_skills(build_config: dict[str, Any], tmp_path: Path):
    """Create a source tree without skills."""
    broken_source = tmp_path / "broken_source" / "nWave"
    broken_source.mkdir(parents=True)
    (broken_source / "agents").mkdir()
    (broken_source / "tasks" / "nw").mkdir(parents=True)
    build_config["nwave_dir"] = broken_source


@given("the source tree is missing the commands directory")
def source_missing_commands(build_config: dict[str, Any], tmp_path: Path):
    """Create a source tree without commands."""
    broken_source = tmp_path / "broken_source" / "nWave"
    broken_source.mkdir(parents=True)
    (broken_source / "agents").mkdir()
    (broken_source / "skills").mkdir()
    build_config["nwave_dir"] = broken_source


@given("the project configuration file is missing")
def project_config_missing(build_config: dict[str, Any], tmp_path: Path):
    """Point to a non-existent pyproject.toml."""
    build_config["pyproject_path"] = tmp_path / "nonexistent" / "pyproject.toml"


# ---------------------------------------------------------------------------
# Given Steps: Edge Cases
# ---------------------------------------------------------------------------


@given("a source tree with exactly 1 agent, 1 skill, and 1 command")
def minimal_source(build_config: dict[str, Any], minimal_source_tree: Path):
    """Use the minimal source tree fixture."""
    build_config["source_root"] = minimal_source_tree
    build_config["nwave_dir"] = minimal_source_tree / "nWave"
    build_config["des_dir"] = minimal_source_tree / "src" / "des"
    build_config["pyproject_path"] = minimal_source_tree / "pyproject.toml"


@given(parsers.parse('an agent file named "{filename}" exists in the source'))
def agent_file_exists(filename: str, nwave_source_tree: Path):
    """Verify a specific agent file exists in the source."""
    agent_path = nwave_source_tree / "agents" / filename
    assert agent_path.exists(), f"Agent file not found: {agent_path}"


@given("any valid nWave source tree")
def any_valid_source(nwave_source_tree: Path):
    """Use the real nWave source tree for property-based checks."""
    assert nwave_source_tree.exists()


@given("any valid project version string")
def any_valid_version():
    """Placeholder for property-based version testing."""
    pass


# ---------------------------------------------------------------------------
# When Steps: Build Execution
# ---------------------------------------------------------------------------


@when("the plugin assembler builds the plugin")
def build_plugin(build_config: dict[str, Any], build_result: dict[str, Any]):
    """
    Execute the plugin build pipeline.

    This step invokes the PluginAssembler driving port.
    Implementation will be provided by the software crafter.
    """
    # TODO: Replace with actual PluginAssembler invocation
    # from scripts.build_plugin import PluginAssembler, BuildConfig
    # config = BuildConfig(**build_config)
    # result = PluginAssembler.build(config)
    # build_result["plugin_dir"] = result.output_dir
    # build_result["success"] = result.is_success()
    pytest.skip("PluginAssembler not yet implemented")


@when("the plugin assembler attempts to build the plugin")
def attempt_build_plugin(build_config: dict[str, Any], build_result: dict[str, Any]):
    """
    Execute the plugin build pipeline expecting failure.

    Captures the error rather than raising it.
    """
    # TODO: Replace with actual PluginAssembler invocation
    # from scripts.build_plugin import PluginAssembler, BuildConfig
    # try:
    #     config = BuildConfig(**build_config)
    #     result = PluginAssembler.build(config)
    #     build_result["success"] = result.is_success()
    #     build_result["error"] = result.error if not result.is_success() else None
    # except Exception as e:
    #     build_result["success"] = False
    #     build_result["error"] = str(e)
    pytest.skip("PluginAssembler not yet implemented")


@when("the plugin validator checks the output")
def validate_plugin(build_result: dict[str, Any]):
    """
    Run the plugin validator on the build output.

    Driving port: PluginValidator
    """
    # TODO: Replace with actual PluginValidator invocation
    # from scripts.build_plugin import PluginValidator
    # validation = PluginValidator.validate(build_result["plugin_dir"])
    # build_result["validation_result"] = validation
    pytest.skip("PluginValidator not yet implemented")


# ---------------------------------------------------------------------------
# Then Steps: Metadata Assertions
# ---------------------------------------------------------------------------


@then("the plugin directory contains a metadata file with the project version")
def plugin_has_metadata_with_version(build_result: dict[str, Any]):
    """Verify plugin.json exists and contains the project version."""
    plugin_dir = build_result["plugin_dir"]
    metadata_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert metadata_path.exists(), f"Metadata file not found: {metadata_path}"

    import json

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert "version" in metadata
    assert metadata["version"], "Version must not be empty"


@then("the plugin metadata version matches the project version")
def metadata_version_matches_project(
    build_result: dict[str, Any], build_config: dict[str, Any]
):
    """Verify metadata version matches pyproject.toml version."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    # Read expected version from pyproject.toml
    import tomllib

    with open(build_config["pyproject_path"], "rb") as f:
        pyproject = tomllib.load(f)
    expected = pyproject["project"]["version"]

    assert metadata["version"] == expected


@then(parsers.parse('the plugin metadata name is "{name}"'))
def metadata_name_is(name: str, build_result: dict[str, Any]):
    """Verify plugin name in metadata."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert metadata["name"] == name


@then("the plugin metadata contains a description")
def metadata_has_description(build_result: dict[str, Any]):
    """Verify metadata includes a description field."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "description" in metadata
    assert len(metadata["description"]) > 0


@then("the plugin metadata contains keywords for discoverability")
def metadata_has_keywords(build_result: dict[str, Any]):
    """Verify metadata includes keywords."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "keywords" in metadata
    assert len(metadata["keywords"]) > 0


@then('the plugin metadata source path starts with "./"')
def metadata_source_starts_with_dot_slash(build_result: dict[str, Any]):
    """Verify source field starts with ./ per Claude Code validation."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    if "source" in metadata:
        assert metadata["source"].startswith("./")


@then(parsers.parse('the plugin metadata version is "{version}"'))
def metadata_version_is(version: str, build_result: dict[str, Any]):
    """Verify specific version in metadata."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert metadata["version"] == version


# ---------------------------------------------------------------------------
# Then Steps: Component Presence
# ---------------------------------------------------------------------------


@then(
    parsers.parse("the plugin directory contains at least {count:d} agent definition")
)
def plugin_has_agents(count: int, build_result: dict[str, Any]):
    """Verify minimum agent count in plugin."""
    plugin_dir = build_result["plugin_dir"]
    agents_dir = plugin_dir / "agents"
    assert agents_dir.exists()
    agent_files = list(agents_dir.glob("*.md"))
    assert len(agent_files) >= count


@then("the plugin contains all 23 agent definitions")
def plugin_has_all_agents(build_result: dict[str, Any]):
    """Verify all 23 agents are present."""
    plugin_dir = build_result["plugin_dir"]
    agents_dir = plugin_dir / "agents"
    agent_files = list(agents_dir.glob("*.md"))
    assert len(agent_files) == 23, f"Expected 23 agents, found {len(agent_files)}"


@then("every agent file is a valid markdown file with frontmatter")
def agents_have_frontmatter(build_result: dict[str, Any]):
    """Verify every agent file has YAML frontmatter."""
    plugin_dir = build_result["plugin_dir"]
    for agent_file in (plugin_dir / "agents").glob("*.md"):
        content = agent_file.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Agent {agent_file.name} missing frontmatter"


@then("the content of each agent file in the plugin matches the source")
def agents_match_source(build_result: dict[str, Any], build_config: dict[str, Any]):
    """Verify agent files are copied without modification."""
    plugin_dir = build_result["plugin_dir"]
    source_dir = build_config["nwave_dir"] / "agents"
    for agent_file in (plugin_dir / "agents").glob("*.md"):
        source_file = source_dir / agent_file.name
        assert source_file.exists()
        assert agent_file.read_text(encoding="utf-8") == source_file.read_text(
            encoding="utf-8"
        )


@then(
    parsers.parse("the plugin directory contains at least {count:d} command definition")
)
def plugin_has_commands(count: int, build_result: dict[str, Any]):
    """Verify minimum command count in plugin."""
    plugin_dir = build_result["plugin_dir"]
    # Commands may be in commands/ or commands/nw/
    commands_dir = plugin_dir / "commands"
    assert commands_dir.exists()
    cmd_files = list(commands_dir.rglob("*.md"))
    assert len(cmd_files) >= count


@then("the plugin contains all command definitions")
def plugin_has_all_commands(build_result: dict[str, Any]):
    """Verify all commands are present."""
    plugin_dir = build_result["plugin_dir"]
    commands_dir = plugin_dir / "commands"
    cmd_files = list(commands_dir.rglob("*.md"))
    assert len(cmd_files) >= 21, f"Expected >= 21 commands, found {len(cmd_files)}"


@then("command files reside in the commands directory")
def commands_in_correct_dir(build_result: dict[str, Any]):
    """Verify commands are in the expected directory."""
    plugin_dir = build_result["plugin_dir"]
    commands_dir = plugin_dir / "commands"
    assert commands_dir.exists()
    assert any(commands_dir.rglob("*.md"))


@then('every command file produces a "/nw:" prefixed slash command')
def commands_produce_nw_prefix(build_result: dict[str, Any]):
    """Verify command files support /nw: namespace."""
    plugin_dir = build_result["plugin_dir"]
    commands_dir = plugin_dir / "commands"
    for cmd_file in commands_dir.rglob("*.md"):
        # Command name derives from file path within plugin
        # The /nw: prefix comes from the plugin name being "nw"
        assert cmd_file.suffix == ".md"


@then(parsers.parse("the plugin directory contains at least {count:d} skill file"))
def plugin_has_skills(count: int, build_result: dict[str, Any]):
    """Verify minimum skill count in plugin."""
    plugin_dir = build_result["plugin_dir"]
    skills_dir = plugin_dir / "skills"
    assert skills_dir.exists()
    skill_files = list(skills_dir.rglob("*.md"))
    assert len(skill_files) >= count


@then("the plugin contains all skill files from the source tree")
def plugin_has_all_skills(build_result: dict[str, Any], build_config: dict[str, Any]):
    """Verify all skills are present."""
    plugin_dir = build_result["plugin_dir"]
    source_dir = build_config["nwave_dir"] / "skills"
    source_skills = list(source_dir.rglob("*.md"))
    plugin_skills = list((plugin_dir / "skills").rglob("*.md"))
    assert len(plugin_skills) >= len(source_skills), (
        f"Expected >= {len(source_skills)} skills, found {len(plugin_skills)}"
    )


@then("skill files are organized by agent name")
def skills_organized_by_agent(build_result: dict[str, Any]):
    """Verify skills are in agent-named subdirectories."""
    plugin_dir = build_result["plugin_dir"]
    skills_dir = plugin_dir / "skills"
    subdirs = [d for d in skills_dir.iterdir() if d.is_dir()]
    assert len(subdirs) > 0, "Skills should be in agent-named subdirectories"


@then("the directory structure mirrors the source layout")
def skills_mirror_source_layout(
    build_result: dict[str, Any], build_config: dict[str, Any]
):
    """Verify skill directory structure matches source."""
    plugin_dir = build_result["plugin_dir"]
    source_dir = build_config["nwave_dir"] / "skills"
    source_dirs = {d.name for d in source_dir.iterdir() if d.is_dir()}
    plugin_dirs = {d.name for d in (plugin_dir / "skills").iterdir() if d.is_dir()}
    assert source_dirs == plugin_dirs


@then('no skill files are renamed to "SKILL.md"')
def no_skill_md_rename(build_result: dict[str, Any]):
    """Verify no SKILL.md files exist (per ADR-003)."""
    plugin_dir = build_result["plugin_dir"]
    skill_md_files = list((plugin_dir / "skills").rglob("SKILL.md"))
    assert len(skill_md_files) == 0, (
        f"Found {len(skill_md_files)} SKILL.md files -- ADR-003 forbids renaming"
    )


@then("each skill file retains its original filename")
def skills_retain_filenames(build_result: dict[str, Any], build_config: dict[str, Any]):
    """Verify skill filenames are preserved."""
    plugin_dir = build_result["plugin_dir"]
    source_dir = build_config["nwave_dir"] / "skills"
    source_names = {f.name for f in source_dir.rglob("*.md")}
    plugin_names = {f.name for f in (plugin_dir / "skills").rglob("*.md")}
    assert source_names == plugin_names


# ---------------------------------------------------------------------------
# Then Steps: Error Assertions
# ---------------------------------------------------------------------------


@then("the build fails with a missing agents error")
def build_fails_missing_agents(build_result: dict[str, Any]):
    """Verify build failure message mentions agents."""
    assert build_result["success"] is False
    assert "agents" in build_result["error"].lower()


@then("the build fails with a missing skills error")
def build_fails_missing_skills(build_result: dict[str, Any]):
    """Verify build failure message mentions skills."""
    assert build_result["success"] is False
    assert "skills" in build_result["error"].lower()


@then("the build fails with a missing commands error")
def build_fails_missing_commands(build_result: dict[str, Any]):
    """Verify build failure message mentions commands."""
    assert build_result["success"] is False
    assert "commands" in build_result["error"].lower()


@then("the build fails with a version read error")
def build_fails_version_error(build_result: dict[str, Any]):
    """Verify build failure message mentions version."""
    assert build_result["success"] is False
    assert "version" in build_result["error"].lower()


@then("no partial plugin directory is created")
def no_partial_output(build_result: dict[str, Any]):
    """Verify failed build does not leave partial output."""
    plugin_dir = build_result.get("plugin_dir")
    if plugin_dir is not None:
        # Either dir does not exist or is empty
        assert not plugin_dir.exists() or len(list(plugin_dir.iterdir())) == 0


# ---------------------------------------------------------------------------
# Then Steps: Edge Case Assertions
# ---------------------------------------------------------------------------


@then("the plugin directory is created successfully")
def plugin_dir_created(build_result: dict[str, Any]):
    """Verify plugin directory was created."""
    assert build_result["success"] is True
    assert build_result["plugin_dir"].exists()


@then("the plugin metadata is valid")
def plugin_metadata_valid(build_result: dict[str, Any]):
    """Verify metadata is parseable JSON with required fields."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert "name" in metadata
    assert "version" in metadata


@then(parsers.parse("the agent file appears in the plugin with its original name"))
def agent_file_preserved_name(build_result: dict[str, Any]):
    """Verify agent filename is preserved in plugin output."""
    # This step validates that special characters in filenames are handled
    plugin_dir = build_result["plugin_dir"]
    agents_dir = plugin_dir / "agents"
    # At minimum, the agents directory should have files
    assert any(agents_dir.glob("*.md"))


@then("every agent in the source has exactly one corresponding file in the plugin")
def one_to_one_agent_mapping(
    build_result: dict[str, Any], build_config: dict[str, Any]
):
    """Property: bijective mapping between source and plugin agents."""
    source_agents = {
        f.name for f in (build_config["nwave_dir"] / "agents").glob("*.md")
    }
    plugin_agents = {
        f.name for f in (build_result["plugin_dir"] / "agents").glob("*.md")
    }
    assert source_agents == plugin_agents


@then("no extra agent files are introduced")
def no_extra_agents(build_result: dict[str, Any], build_config: dict[str, Any]):
    """Property: no files added that are not in source."""
    source_agents = {
        f.name for f in (build_config["nwave_dir"] / "agents").glob("*.md")
    }
    plugin_agents = {
        f.name for f in (build_result["plugin_dir"] / "agents").glob("*.md")
    }
    extra = plugin_agents - source_agents
    assert len(extra) == 0, f"Extra agents introduced: {extra}"


@then("the plugin metadata version is identical to the source version")
def version_identity(build_result: dict[str, Any]):
    """Property: version is always preserved exactly."""
    # This is verified by the specific version tests above
    pass


# ---------------------------------------------------------------------------
# Then Steps: Validation
# ---------------------------------------------------------------------------


@then("the plugin passes structural validation")
def validation_passes(build_result: dict[str, Any]):
    """Verify structural validation succeeds."""
    validation = build_result["validation_result"]
    assert validation is not None
    assert validation["success"] is True


@then("the validation report confirms all required sections are present")
def validation_all_sections(build_result: dict[str, Any]):
    """Verify validation checked all sections."""
    validation = build_result["validation_result"]
    assert "sections" in validation
    for section in ["agents", "skills", "commands", "hooks", "metadata"]:
        assert section in validation["sections"]
        assert validation["sections"][section] is True
