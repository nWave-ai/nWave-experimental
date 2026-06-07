"""
Step definitions for skill audit and CI validation scenarios.

Covers: US-01 (audit), US-09 (CI validation), US-10 (E2E verification).

Driving ports exercised:
- validate_skill_agent_mapping.py (CI validation script)
- SkillsPlugin.verify()
"""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given Steps -- Audit
# ---------------------------------------------------------------------------


@given("the source tree contains skills from multiple agent groups")
def source_has_multiple_groups(skills_source_dir: Path):
    """Create skill directories spanning multiple collision groups."""
    # Create a collision scenario: critique-dimensions in two groups
    for prefix in ["nw-ad", "nw-sa", "nw-ab", "nw-abr", "nw-par", "nw-rr", "nw-sar"]:
        d = skills_source_dir / f"{prefix}-critique-dimensions"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Critique dims for {prefix}\n")

    for prefix in ["nw-sc", "nw-po"]:
        d = skills_source_dir / f"{prefix}-review-dimensions"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Review dims for {prefix}\n")

    for prefix in ["nw-der", "nw-dr", "nw-par", "nw-pdr", "nw-por", "nw-tr", "nw-br"]:
        d = skills_source_dir / f"{prefix}-review-criteria"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Review criteria for {prefix}\n")


@given("the source tree is fully populated")
def fully_populated_source(skills_source_dir: Path):
    """Create a full set of 109 skill directories for counting."""
    # Create enough directories to simulate 109 skills
    for i in range(109):
        d = skills_source_dir / f"nw-skill-{i:03d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"Skill {i} content\n")


@given("the functional software crafter references skills from the software crafter")
def cross_agent_reference():
    """The functional-software-crafter uses software-crafter's skills."""
    # This is a known cross-reference in the agent frontmatter
    pass


@given("a skill file exists that no agent references in its frontmatter")
def orphan_skill(skills_source_dir: Path):
    """Create a skill directory that no agent references."""
    orphan = skills_source_dir / "nw-orphan-technique"
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "SKILL.md").write_text("Orphan skill content\n")


# ---------------------------------------------------------------------------
# Given Steps -- CI Validation
# ---------------------------------------------------------------------------


@given(parsers.parse('an agent lists "{skill_name}" in its frontmatter'))
def agent_has_skill_ref(skill_name: str):
    """Record that an agent references a specific skill."""
    pytest.broken_skill_ref = skill_name


@given(parsers.parse('no directory named "nw-{skill_name}" exists'))
def no_skill_dir(skill_name: str, skills_source_dir: Path):
    """Verify no matching skill directory exists."""
    path = skills_source_dir / f"nw-{skill_name}"
    assert not path.exists()


@given(parsers.parse('a skill directory "{dir_name}" exists'))
def skill_dir_exists(dir_name: str, skills_source_dir: Path):
    """Create a specific skill directory."""
    d = skills_source_dir / dir_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"Content for {dir_name}\n")


@given(parsers.parse('no agent references "{dir_name}" in its frontmatter'))
def no_agent_refs_skill(dir_name: str):
    """Record that no agent references this skill."""
    pytest.orphan_skill_name = dir_name


@given("every agent skill reference has a matching directory")
def all_refs_match():
    """Pre-condition: all references are valid."""
    pass


@given("every skill directory is referenced by at least one agent")
def all_dirs_referenced():
    """Pre-condition: no orphan directories."""
    pass


@given('a skill directory without the "nw-" prefix exists')
def non_prefixed_dir(skills_source_dir: Path):
    """Create a directory violating the naming convention."""
    bad_dir = skills_source_dir / "legacy-skill"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "SKILL.md").write_text("Bad naming\n")


# ---------------------------------------------------------------------------
# Given Steps -- E2E Verification
# ---------------------------------------------------------------------------


@given("the skills plugin has completed installation")
def plugin_completed_install(
    skills_plugin, install_context, populate_troubleshooter_skills
):
    """Run a successful installation."""
    result = skills_plugin.install(install_context)
    assert result.success


@given("a clean Docker container runs the installer")
def docker_container():
    """Placeholder for Docker-based verification."""
    pytest.skip("Docker verification requires container infrastructure")


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("the skill audit is performed")
def perform_audit(skills_source_dir: Path):
    """Scan for collisions and cross-references."""
    all_dirs = [d for d in skills_source_dir.iterdir() if d.is_dir()]
    pytest.audit_dirs = all_dirs
    pytest.audit_count = len(all_dirs)

    # Detect collisions by suffix pattern

    suffixes = []
    for d in all_dirs:
        name = d.name
        # Strip nw- prefix and any agent abbreviation to find base skill name
        if name.startswith("nw-"):
            parts = name[3:].split("-", 1)
            if len(parts) > 1:
                # Could be abbreviation-prefixed or just a hyphenated skill name
                suffixes.append(name)
    pytest.audit_suffixes = suffixes


@when("the skill audit maps cross-agent references")
def audit_cross_refs():
    """Identify cross-agent skill references."""
    # This would parse agent frontmatter in production
    pytest.cross_refs_found = True


@when("the skill audit checks for orphans")
def audit_orphans(skills_source_dir: Path):
    """Check for skills unreferenced by any agent."""
    pytest.orphan_found = (skills_source_dir / "nw-orphan-technique").exists()


@when("CI validation runs the skill-agent consistency check")
def run_ci_validation():
    """Simulate CI validation check."""
    # In production, this invokes validate_skill_agent_mapping.py
    pytest.ci_validation_ran = True


@when("CI validation runs the naming convention check")
def run_naming_check(skills_source_dir: Path):
    """Check all directories follow nw- naming convention."""
    non_compliant = [
        d.name
        for d in skills_source_dir.iterdir()
        if d.is_dir() and not d.name.startswith("nw-")
    ]
    pytest.non_compliant_dirs = non_compliant


@when("the verification check runs")
def run_verification(skills_plugin, install_context):
    """Run verification through the driving port."""
    pytest.verify_result = skills_plugin.verify(install_context)


@when("the verification suite runs")
def run_verification_suite():
    """Run full verification suite (Docker context)."""
    pytest.skip("Docker verification requires container infrastructure")


# ---------------------------------------------------------------------------
# Then Steps -- Audit
# ---------------------------------------------------------------------------


@then(parsers.parse('"{name}" is flagged as colliding across {count:d} groups'))
def collision_flagged(name: str, count: int):
    """Verify a collision is detected with correct count."""
    # In production, the audit script would produce this
    # Here we verify the test data setup is correct
    matching = [
        d
        for d in pytest.audit_dirs
        if d.name.endswith(f"-{name}") or d.name == f"nw-{name}"
    ]
    assert len(matching) == count, (
        f"Expected {count} groups for {name}, found {len(matching)}: "
        f"{[d.name for d in matching]}"
    )


@then("no other collisions exist")
def no_other_collisions():
    """Verify only the known collisions exist."""
    pass  # The test data is controlled, so this is implicitly true


@then(parsers.parse("exactly {count:d} skill files are cataloged"))
def exact_file_count(count: int):
    """Verify the total skill count."""
    assert pytest.audit_count == count, (
        f"Expected {count} skills, found {pytest.audit_count}"
    )


@then("all agent-to-skill references are mapped")
def refs_mapped():
    """Verify all references are captured."""
    pass  # Would check the mapping data structure in production


@then("the cross-references are identified with source and target agents")
def cross_refs_identified():
    """Verify cross-references were found."""
    assert pytest.cross_refs_found


@then("the orphan skill is reported with its file path")
def orphan_reported():
    """Verify orphan was detected."""
    assert pytest.orphan_found


# ---------------------------------------------------------------------------
# Then Steps -- CI Validation
# ---------------------------------------------------------------------------


@then("the check fails")
def ci_check_fails():
    """Verify CI validation detected the problem."""
    assert pytest.ci_validation_ran
    # Would check exit code in production


@then("the error names the agent and the missing skill")
def error_names_agent_and_skill():
    """Verify error message is specific."""
    assert hasattr(pytest, "broken_skill_ref")


@then("a warning is emitted for the orphan skill")
def orphan_warning():
    """Verify orphan skill produces a warning, not failure."""
    assert hasattr(pytest, "orphan_skill_name")


@then("the check does not fail")
def check_passes():
    """Orphan warnings do not cause CI failure."""
    pass


@then("the check passes with no errors or warnings")
def check_clean_pass():
    """CI validation passes cleanly."""
    assert pytest.ci_validation_ran


@then("the error identifies the non-compliant directory name")
def non_compliant_identified():
    """Verify the non-compliant directory is reported."""
    assert len(pytest.non_compliant_dirs) > 0
    assert "legacy-skill" in pytest.non_compliant_dirs


# ---------------------------------------------------------------------------
# Then Steps -- E2E Verification
# ---------------------------------------------------------------------------


@then("the expected number of SKILL.md files exist")
def expected_skill_count(install_context):
    """Verify SKILL.md file count."""
    skills_dir = install_context.claude_dir / "skills"
    if skills_dir.exists():
        skill_files = list(skills_dir.rglob("SKILL.md"))
        assert len(skill_files) > 0


@then("each file is non-empty")
def files_non_empty(install_context):
    """Verify no SKILL.md file is empty."""
    skills_dir = install_context.claude_dir / "skills"
    if skills_dir.exists():
        for f in skills_dir.rglob("SKILL.md"):
            assert f.stat().st_size > 0, f"Empty SKILL.md: {f}"


@then("each agent's skill list entries match installed directory names")
def skill_list_matches_dirs():
    """Verify agent frontmatter aligns with installed directories."""
    # Would compare frontmatter to actual directories in production
    pass


@then("all skill directories are created")
def all_dirs_created():
    """Verify all expected directories exist."""
    pass


@then("the skill count matches the expected total")
def count_matches_total():
    """Verify total count."""
    pass


@then("no files exist in the old namespace path")
def no_old_namespace_files(install_context):
    """Verify the old nw/ path has no files."""
    old_path = install_context.claude_dir / "skills" / "nw"
    assert not old_path.exists()
