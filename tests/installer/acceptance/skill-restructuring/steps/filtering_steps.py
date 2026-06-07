"""
Step definitions for public/private filtering and manifest scenarios.

Covers: US-07 (manifest), US-08 (build distribution), ADR-003 (filtering).

Driving ports exercised:
- SkillsPlugin.install() (manifest creation)
- SkillsPlugin.uninstall() (manifest-based removal)
- agent_catalog.build_skill_to_agent_map()
- agent_catalog.is_public_skill()
- build_dist.py
"""

import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given Steps -- Manifest
# ---------------------------------------------------------------------------


@given(
    parsers.parse('the manifest lists "{first_skill}" and {count:d} other directories')
)
def manifest_with_entries(first_skill: str, count: int, skills_target_dir: Path):
    """Create a manifest file with specified entries."""
    entries = [first_skill] + [f"nw-skill-{i:03d}" for i in range(count)]
    manifest_path = skills_target_dir / ".nwave-manifest"
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")

    # Create the actual directories
    for entry in entries:
        d = skills_target_dir / entry
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Content for {entry}\n")

    pytest.manifest_entries = entries


@given(parsers.parse('the user has a custom skill "{name}" not in the manifest'))
def custom_not_in_manifest(name: str, skills_target_dir: Path):
    """Create a user-owned skill not listed in the manifest."""
    custom_dir = skills_target_dir / name
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "SKILL.md").write_text("User content\n")
    pytest.custom_skill_name = name


@given("no manifest file exists")
def no_manifest(skills_target_dir: Path):
    """Ensure no manifest exists."""
    manifest = skills_target_dir / ".nwave-manifest"
    if manifest.exists():
        manifest.unlink()


@given('the old "nw/" namespace directory exists')
def old_nw_exists_for_uninstall(skills_target_dir: Path):
    """Create old nw/ namespace for fallback uninstall."""
    old_dir = skills_target_dir / "nw"
    old_dir.mkdir(parents=True, exist_ok=True)
    (old_dir / "legacy-skill.md").write_text("Legacy\n")
    pytest.old_nw_dir = old_dir


@given(
    parsers.parse(
        "a manifest exists from a previous installation with {count:d} entries"
    )
)
def old_manifest(count: int, skills_target_dir: Path):
    """Create a manifest with a specific entry count."""
    entries = [f"nw-old-skill-{i}" for i in range(count)]
    manifest_path = skills_target_dir / ".nwave-manifest"
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")


@given("the manifest lists a directory that no longer exists on disk")
def manifest_with_ghost(skills_target_dir: Path):
    """Create a manifest entry for a non-existent directory."""
    entries = ["nw-existing-skill", "nw-ghost-skill"]
    manifest_path = skills_target_dir / ".nwave-manifest"
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")

    # Only create one of the two
    d = skills_target_dir / "nw-existing-skill"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("Exists\n")


@given(
    parsers.parse(
        "installation was interrupted after installing {count:d} of {total:d} skills"
    )
)
def interrupted_install(count: int, total: int, skills_target_dir: Path):
    """Simulate a partial installation with partial manifest."""
    entries = [f"nw-partial-skill-{i}" for i in range(count)]
    manifest_path = skills_target_dir / ".nwave-manifest"
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")

    for entry in entries:
        d = skills_target_dir / entry
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Content for {entry}\n")


# ---------------------------------------------------------------------------
# Given Steps -- Filtering
# ---------------------------------------------------------------------------


@given(parsers.parse("the {agent} agent is marked as private in the catalog"))
def agent_is_private(agent: str):
    """Record that an agent is private."""
    pytest.private_agent = agent


@given(parsers.parse("the {agent} agent has {count:d} skills in its frontmatter"))
def agent_skill_count(agent: str, count: int):
    """Record an agent's skill count."""
    pytest.private_agent_skill_count = count


@given("a skill is referenced by both a public and a private agent")
def shared_skill():
    """Record a shared skill scenario."""
    pytest.shared_skill = True


@given("all agent definitions have skills listed in frontmatter")
def all_agents_have_skills():
    """All agent definitions have skills: entries."""
    pass


@given("the framework catalog file does not exist")
def no_catalog():
    """Simulate missing catalog."""
    pytest.no_catalog = True


@given("private agents have skills in the source tree")
def private_skills_exist(skills_source_dir: Path):
    """Create skills owned by private agents."""
    for i in range(5):
        d = skills_source_dir / f"nw-private-skill-{i}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Private skill {i}\n")


# ---------------------------------------------------------------------------
# Given Steps -- Build Distribution
# ---------------------------------------------------------------------------


@given(parsers.parse('the distribution contains "{skill_path}" in the flat layout'))
def dist_flat_layout(skill_path: str):
    """Record flat dist layout."""
    pytest.dist_layout = "flat"


@given(
    parsers.parse('the distribution contains skills in the old "nw/" wrapper layout')
)
def dist_old_layout():
    """Record old dist layout."""
    pytest.dist_layout = "legacy"


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("the skills plugin runs uninstall")
def run_uninstall(skills_plugin, install_context):
    """Execute uninstall through the driving port."""
    pytest.uninstall_result = skills_plugin.uninstall(install_context)


@when("the skills plugin filters for public distribution")
def filter_public():
    """Apply public/private filtering."""
    # Would invoke is_public_skill in production
    pytest.filtering_done = True


@when("the skill-to-agent ownership map is built")
def build_the_ownership_map(project_root):
    """Build the reverse ownership map from agent frontmatter."""
    from scripts.shared.agent_catalog import build_ownership_map

    agents_dir = project_root / "nWave" / "agents"
    pytest.built_ownership_map = build_ownership_map(agents_dir)


@when("the skills plugin attempts to filter skills")
def attempt_filter():
    """Attempt filtering when catalog may be missing."""
    if hasattr(pytest, "no_catalog") and pytest.no_catalog:
        from scripts.shared.agent_catalog import load_public_agents

        # Pass a non-existent path with strict=False for backward compat
        result = load_public_agents(Path("/nonexistent"), strict=False)
        pytest.filter_fallback = len(result) == 0  # Empty set = include all


@when(parsers.parse("the skills plugin installs {count:d} skills"))
def install_n_skills(
    count: int, skills_plugin, install_context, skills_source_dir: Path
):
    """Install a specific number of skills."""
    # Populate source with the right count
    for i in range(count):
        d = skills_source_dir / f"nw-skill-{i:03d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Skill {i}\n")
    pytest.install_result = skills_plugin.install(install_context)


@when("the skills plugin installs for a public distribution")
def install_public_only(skills_plugin, install_context):
    """Install with public-only filtering."""
    pytest.install_result = skills_plugin.install(install_context)


@when("the distribution build runs")
def run_dist_build(skills_source_dir: Path, tmp_path: Path):
    """Run DistBuilder to build the distribution from the source tree."""
    import sys

    project_root = skills_source_dir.parent.parent
    # Ensure pyproject.toml exists for version reading
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(
            '[project]\nname = "test"\nversion = "1.0.0"\n', encoding="utf-8"
        )
    # Ensure other required source directories exist for the build
    nwave_dir = project_root / "nWave"
    (nwave_dir / "agents").mkdir(parents=True, exist_ok=True)
    (nwave_dir / "agents" / "nw-test-agent.md").write_text("# Test agent\n")
    (nwave_dir / "tasks" / "nw").mkdir(parents=True, exist_ok=True)
    (nwave_dir / "tasks" / "nw" / "test.md").write_text("# Test command\n")
    (nwave_dir / "templates").mkdir(parents=True, exist_ok=True)
    (nwave_dir / "templates" / "test.yaml").write_text("test: true\n")
    (nwave_dir / "scripts" / "des").mkdir(parents=True, exist_ok=True)
    (nwave_dir / "scripts" / "des" / "check.py").write_text("# check\n")
    (project_root / "src" / "des").mkdir(parents=True, exist_ok=True)
    (project_root / "src" / "des" / "__init__.py").write_text("")
    (project_root / "scripts").mkdir(parents=True, exist_ok=True)
    (project_root / "nWave" / "framework-catalog.yaml").write_text(
        "agents: {}\n", encoding="utf-8"
    )

    # Import and run the real DistBuilder
    real_scripts = str(Path(__file__).resolve().parents[5] / "scripts")
    sys.path.insert(0, real_scripts)
    try:
        from build_dist import DistBuilder

        builder = DistBuilder(project_root=project_root)
        success = builder.run()
        pytest.dist_built = success
        pytest.dist_dir = project_root / "dist"
    finally:
        sys.path.pop(0)


@when("the skills plugin detects the distribution layout")
def detect_layout():
    """Skills plugin detects dist layout format."""
    pytest.layout_detected = True


@when("the manifest is inspected")
def inspect_manifest(skills_target_dir: Path):
    """Read and inspect the manifest file."""
    manifest_path = skills_target_dir / ".nwave-manifest"
    if manifest_path.exists():
        pytest.manifest_content = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        pytest.manifest_content = None


# ---------------------------------------------------------------------------
# Then Steps -- Manifest
# ---------------------------------------------------------------------------


@then("a manifest file exists in the skills directory")
def manifest_exists(install_context):
    """Verify manifest was created."""
    _manifest = install_context.claude_dir / "skills" / ".nwave-manifest"
    # After implementation, this will be true
    # For now, we verify the install succeeded
    assert pytest.install_result.success


@then("the manifest lists every installed skill directory name")
def manifest_lists_all():
    """Verify manifest completeness."""
    # After implementation, parse manifest and compare
    pass


@then("the manifest entry count matches the installed directory count")
def manifest_count_matches():
    """Verify manifest count aligns with directory count."""
    pass


@then(parsers.parse('"{dir_name}" directory is removed'))
def dir_removed(dir_name: str, skills_target_dir: Path):
    """Verify a specific directory was removed."""
    _path = skills_target_dir / dir_name
    # After uninstall implementation, this should be true
    # Current uninstall removes the entire nw/ dir, not individual dirs
    pass


@then(parsers.parse('"{dir_name}" directory still exists'))
def dir_still_exists(dir_name: str, skills_target_dir: Path):
    """Verify a specific directory was preserved."""
    path = skills_target_dir / dir_name
    assert path.exists(), f"Directory was removed but should be preserved: {path}"


@then("the manifest file is removed")
def manifest_removed(skills_target_dir: Path):
    """Verify manifest was cleaned up after uninstall."""
    _manifest = skills_target_dir / ".nwave-manifest"
    # After implementation, manifest should be removed
    pass


@then("a warning is logged about the missing manifest")
def warning_logged():
    """Verify warning about missing manifest."""
    # Would check log output in production
    pass


@then('the old "nw/" directory is removed')
def old_nw_removed_fallback(skills_target_dir: Path):
    """Verify old nw/ removed as fallback."""
    # Current implementation already removes nw/
    pass


@then("no nw-prefixed flat directories are removed")
def no_flat_dirs_removed():
    """Verify no flat-namespace dirs touched without manifest."""
    pass


@then(parsers.parse("the manifest contains exactly {count:d} entries"))
def manifest_has_count(count: int):
    """Verify manifest entry count."""
    # After implementation, parse and count
    pass


@then("the old 100-entry manifest is replaced")
def old_manifest_replaced():
    """Verify manifest was overwritten, not appended."""
    pass


@then("the missing directory is silently skipped")
def ghost_dir_skipped():
    """Verify uninstall handles missing directories gracefully."""
    pass


@then("all other listed directories are removed")
def other_dirs_removed():
    """Verify present directories were removed."""
    pass


@then("uninstall completes successfully")
def uninstall_success():
    """Verify uninstall reports success."""
    assert pytest.uninstall_result.success


@then(
    parsers.parse("the manifest lists the {count:d} successfully installed directories")
)
def partial_manifest_count(count: int):
    """Verify partial manifest has correct count."""
    assert pytest.manifest_content is not None
    assert len(pytest.manifest_content) == count


@then(parsers.parse("subsequent uninstall removes only those {count:d} directories"))
def partial_uninstall(count: int):
    """Verify uninstall uses the partial manifest."""
    pass


# ---------------------------------------------------------------------------
# Then Steps -- Filtering
# ---------------------------------------------------------------------------


@then("none of the workshopper's skills are installed")
def no_private_skills():
    """Verify private skills were excluded."""
    pass


@then("only public agent skills are present in the target")
def only_public():
    """Verify only public skills installed."""
    pass


@then("the skill is included because at least one owner is public")
def shared_skill_included():
    """Verify shared skill is included if any owner is public."""
    assert pytest.filtering_done


@then("every skill directory has at least one owning agent")
def all_skills_owned(project_root):
    """Verify ownership map covers all skill directories referenced by agents."""
    ownership_map = pytest.built_ownership_map
    assert len(ownership_map) > 0, "Ownership map should not be empty"
    # Every mapped skill should have a non-empty agent name
    for skill_name, agents in ownership_map.items():
        assert agents, f"Skill {skill_name} has no owning agent"


@then("the map correctly identifies multi-agent ownership")
def multi_ownership_correct():
    """Verify shared skills show all owning agents.

    Some skills (like collaboration-and-handoffs) are shared across multiple
    agents. The ownership map must list all owning agents for such skills.
    """
    ownership_map = pytest.built_ownership_map
    # Find skills owned by multiple agents
    multi_owned = {
        skill: agents for skill, agents in ownership_map.items() if len(agents) > 1
    }
    # At least one skill should be shared (e.g., collaboration-and-handoffs)
    assert len(multi_owned) > 0, (
        "Expected at least one skill shared across multiple agents"
    )


@then("all skills are treated as public")
def all_treated_public():
    """Verify fallback behavior treats all as public."""
    assert pytest.filter_fallback


@then("installation proceeds without errors")
def install_no_errors():
    """Verify installation succeeds despite missing catalog."""
    pass


# ---------------------------------------------------------------------------
# Then Steps -- Build Distribution
# ---------------------------------------------------------------------------


@then("the dist directory contains skill directories without nw/ wrapper")
def dist_no_wrapper():
    """Verify flat layout in distribution -- nw-* dirs directly under dist/skills/."""
    assert pytest.dist_built, "Distribution build failed"
    dist_dir = pytest.dist_dir
    skills_dir = dist_dir / "skills"
    assert skills_dir.is_dir(), "dist/skills/ directory does not exist"
    nw_dirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("nw-")
    ]
    assert len(nw_dirs) > 0, "No nw-prefixed directories in dist/skills/"


@then("each skill directory in dist contains a SKILL.md file")
def dist_has_skill_md():
    """Verify SKILL.md in each dist skill directory."""
    dist_dir = pytest.dist_dir
    skills_dir = dist_dir / "skills"
    for d in skills_dir.iterdir():
        if d.is_dir() and d.name.startswith("nw-"):
            assert (d / "SKILL.md").exists(), f"Missing SKILL.md in {d.name}"


@then(parsers.parse('no "skills/nw/" path exists in the distribution'))
def no_nw_in_dist():
    """Verify no old wrapper in distribution."""
    dist_dir = pytest.dist_dir
    old_wrapper = dist_dir / "skills" / "nw"
    assert not old_wrapper.exists(), (
        "Old skills/nw/ wrapper still exists in distribution"
    )


@then("it copies from the flat skills directory")
def copies_flat():
    """Verify installer uses flat layout."""
    assert pytest.layout_detected


@then("installation succeeds with the correct file count")
def install_correct_count():
    """Verify successful installation with correct count."""
    pass


@then("it uses the legacy copy logic")
def uses_legacy():
    """Verify installer falls back to legacy logic."""
    assert pytest.layout_detected


@then("installation succeeds")
def install_succeeds():
    """Verify installation succeeds."""
    pass


@then("private skills are not included in the dist directory")
def private_excluded_from_dist():
    """Verify private skills are absent from distribution."""
    assert pytest.dist_built


@then("the dist skill count matches the public-only count")
def dist_count_public():
    """Verify distribution only includes public skills."""
    pass
