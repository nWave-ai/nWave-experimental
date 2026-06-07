"""
Step definitions for CI validation scenarios.

Covers: US-09 (CI validation of skill-agent mapping)

Driving port exercised:
- validate_skill_agent_mapping.validate() -- the core validation function
"""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given Steps -- CI Validation
# ---------------------------------------------------------------------------


@given(parsers.parse('an agent lists "{skill_name}" in its frontmatter'))
def agent_lists_skill_in_frontmatter(tmp_path: Path, skill_name: str):
    """Create an agent file that references a skill."""
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agents_dir / "nw-test-agent.md"
    agent_file.write_text(
        f"---\nname: nw-test-agent\n"
        f"description: Test agent\n"
        f"model: inherit\n"
        f"skills:\n"
        f"  - {skill_name}\n"
        f"---\n\n# Test Agent\n",
        encoding="utf-8",
    )


@given(parsers.parse('no directory named "nw-{skill_name}" exists'))
def no_skill_directory(tmp_path: Path, skill_name: str):
    """Ensure no matching skill directory exists."""
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / f"nw-{skill_name}"
    assert not target.exists(), f"Directory {target} should not exist"


@given(parsers.parse('a skill directory "{dir_name}" exists'))
def skill_directory_exists(tmp_path: Path, dir_name: str):
    """Create a skill directory."""
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = skills_dir / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {dir_name}\ndescription: Test\n---\n\n# Skill\n",
        encoding="utf-8",
    )


@given(parsers.parse('no agent references "{dir_name}" in its frontmatter'))
def no_agent_references(tmp_path: Path, dir_name: str):
    """Ensure no agent frontmatter references the given directory name."""
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    # Ensure agents dir exists but no agent references this skill.
    # Do NOT create agents with broken references to other skills.


@given("every agent skill reference has a matching directory")
def all_refs_have_dirs(tmp_path: Path):
    """Create agents and matching skill directories."""
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    agent_file = agents_dir / "nw-test-agent.md"
    agent_file.write_text(
        "---\nname: nw-test-agent\n"
        "description: Test agent\n"
        "model: inherit\n"
        "skills:\n"
        "  - nw-tdd-methodology\n"
        "  - nw-quality-framework\n"
        "---\n\n# Test Agent\n",
        encoding="utf-8",
    )

    for skill_name in ["nw-tdd-methodology", "nw-quality-framework"]:
        skill_dir = skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_name}\n---\n\n# Skill\n",
            encoding="utf-8",
        )


@given("every skill directory is referenced by at least one agent")
def all_dirs_referenced():
    """All skill directories are already referenced (set up in prior step)."""
    pass


@given('a skill directory without the "nw-" prefix exists')
def non_prefixed_directory(tmp_path: Path):
    """Create a skill directory without the nw- prefix."""
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    bad_dir = skills_dir / "bad-skill-name"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "SKILL.md").write_text(
        "---\nname: bad-skill-name\n---\n\n# Skill\n",
        encoding="utf-8",
    )
    # Also ensure agents dir exists
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("CI validation runs the skill-agent consistency check")
def run_consistency_check(tmp_path: Path):
    """Run the validation script against the test fixture."""
    from scripts.validation.validate_skill_agent_mapping import validate

    project_root = tmp_path
    pytest.ci_validation_result = validate(project_root)


@when("CI validation runs the naming convention check")
def run_naming_check(tmp_path: Path):
    """Run the validation script against the test fixture."""
    from scripts.validation.validate_skill_agent_mapping import validate

    project_root = tmp_path
    pytest.ci_validation_result = validate(project_root)


# ---------------------------------------------------------------------------
# Then Steps
# ---------------------------------------------------------------------------


@then("the check fails")
def check_fails():
    """Verify the validation returned failure (exit code 1)."""
    result = pytest.ci_validation_result
    assert result.exit_code != 0, (
        f"Expected failure but got exit_code={result.exit_code}"
    )


@then("the error names the agent and the missing skill")
def error_names_agent_and_skill():
    """Verify the error message identifies both agent and skill."""
    result = pytest.ci_validation_result
    assert len(result.errors) > 0, "Expected at least one error"
    # At least one error should mention agent and skill
    error_text = " ".join(result.errors)
    assert "nw-test-agent" in error_text, (
        f"Error should name the agent: {result.errors}"
    )
    assert "nonexistent-skill" in error_text, (
        f"Error should name the missing skill: {result.errors}"
    )


@then("a warning is emitted for the orphan skill")
def orphan_warning():
    """Verify a warning was emitted for the orphan directory."""
    result = pytest.ci_validation_result
    assert len(result.warnings) > 0, "Expected at least one warning"
    warning_text = " ".join(result.warnings)
    assert "nw-experimental-technique" in warning_text, (
        f"Warning should name the orphan: {result.warnings}"
    )


@then("the check does not fail")
def check_does_not_fail():
    """Verify the check passed (orphans are warnings, not errors)."""
    result = pytest.ci_validation_result
    assert result.exit_code == 0, (
        f"Expected success but got exit_code={result.exit_code}, errors={result.errors}"
    )


@then("the check passes with no errors or warnings")
def check_passes_clean():
    """Verify clean pass with no errors or warnings."""
    result = pytest.ci_validation_result
    assert result.exit_code == 0, f"Expected success: errors={result.errors}"
    assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"
    assert len(result.warnings) == 0, f"Unexpected warnings: {result.warnings}"


@then("the error identifies the non-compliant directory name")
def error_identifies_bad_name():
    """Verify the error message names the bad directory."""
    result = pytest.ci_validation_result
    assert len(result.errors) > 0, "Expected at least one error"
    error_text = " ".join(result.errors)
    assert "bad-skill-name" in error_text, (
        f"Error should name the non-compliant dir: {result.errors}"
    )
