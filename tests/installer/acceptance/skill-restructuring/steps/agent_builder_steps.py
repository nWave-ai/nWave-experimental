"""
Step definitions for agent builder output path verification.

Covers: Agent builder produces skills in nw-prefixed SKILL.md format.

Driving port: filesystem scan of agent-builder definition + its skills.
Asserts: the agent-builder's instructions direct new agents to use
nw-prefixed SKILL.md output paths, not old agent-grouped paths.
"""

import re
from pathlib import Path

import pytest
from pytest_bdd import given, then, when


# ---------------------------------------------------------------------------
# Patterns for detecting old vs new format in agent-builder instructions
# ---------------------------------------------------------------------------

# Old source path: nWave/skills/{agent-name}/{skill-name}.md
OLD_SOURCE_PATH = re.compile(
    r"nWave/skills/\{agent-name\}/(?:\{skill-name\}\.md|\{[^}]+\}\.md)"
)

# Old installed path: ~/.claude/skills/nw/{agent-name}/
OLD_INSTALLED_PATH = re.compile(r"~/.claude/skills/nw/\{agent-name\}/")

# New source path: nWave/skills/nw-{skill-name}/SKILL.md (or nw-{name}/)
NEW_SOURCE_PATH = re.compile(r"nWave/skills/nw-\{[^}]+\}/(?:SKILL\.md)?")

# New installed path: ~/.claude/skills/nw-{skill}/SKILL.md
NEW_INSTALLED_PATH = re.compile(r"~/.claude/skills/nw-\{[^}]+\}/(?:SKILL\.md)?")


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("the agent builder creates a new agent with skills")
def read_agent_builder_files(project_root: Path):
    """Read the agent-builder agent definition and its creation workflow skill."""
    agent_file = project_root / "nWave" / "agents" / "nw-agent-builder.md"
    skill_file = (
        project_root / "nWave" / "skills" / "nw-agent-creation-workflow" / "SKILL.md"
    )

    assert agent_file.exists(), f"Agent builder not found: {agent_file}"
    assert skill_file.exists(), f"Creation workflow skill not found: {skill_file}"

    pytest.agent_builder_content = agent_file.read_text(encoding="utf-8")
    pytest.agent_builder_skill_content = skill_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the builder outputs the skill files and agent definition")
def inspect_builder_output_instructions():
    """Inspect the agent-builder content for path patterns."""
    agent_content = pytest.agent_builder_content
    skill_content = pytest.agent_builder_skill_content

    pytest.builder_analysis = {
        "agent_old_source": OLD_SOURCE_PATH.findall(agent_content),
        "agent_old_installed": OLD_INSTALLED_PATH.findall(agent_content),
        "agent_new_source": NEW_SOURCE_PATH.findall(agent_content),
        "agent_new_installed": NEW_INSTALLED_PATH.findall(agent_content),
        "skill_old_source": OLD_SOURCE_PATH.findall(skill_content),
        "skill_old_installed": OLD_INSTALLED_PATH.findall(skill_content),
        "skill_new_source": NEW_SOURCE_PATH.findall(skill_content),
        "skill_new_installed": NEW_INSTALLED_PATH.findall(skill_content),
    }


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then('skills are created at "nWave/skills/nw-{name}/SKILL.md" paths')
def verify_source_output_paths():
    """Verify skill creation instructions use nw-prefixed SKILL.md paths."""
    analysis = pytest.builder_analysis

    # Must NOT have old source paths
    old_paths = analysis["skill_old_source"]
    assert not old_paths, (
        f"Creation workflow skill still has old-format source paths: {old_paths}"
    )

    # Must have new source paths
    new_paths = analysis["skill_new_source"]
    assert new_paths, (
        "Creation workflow skill has no nw-prefixed source path instructions"
    )


@then('the agent frontmatter lists skills with "nw-" prefixed names')
def verify_frontmatter_skill_names():
    """Verify the agent template's frontmatter uses nw- prefixed skill names."""
    skill_content = pytest.agent_builder_skill_content
    agent_content = pytest.agent_builder_content

    # The template in either file should show skills with nw- prefix
    # Look for the frontmatter template pattern: skills:\n  - nw-{...}
    combined = agent_content + "\n" + skill_content
    template_skill_pattern = re.compile(r"skills:\s*\n\s*-\s*nw-\{[^}]+\}")
    has_nw_prefixed_template = template_skill_pattern.search(combined)

    # Also check that old format (skills without nw- prefix in template) is absent
    old_template_pattern = re.compile(
        r"skills:\s*\n\s*-\s*\{(?!.*nw-)[^}]*skill[^}]*\}"
    )
    has_old_template = old_template_pattern.search(combined)

    assert has_nw_prefixed_template, (
        "Agent builder template does not show nw- prefixed skill names in frontmatter"
    )
    assert not has_old_template, (
        "Agent builder template still shows non-nw-prefixed skill names in frontmatter"
    )


@then(
    'the Skill Loading section uses "~/.claude/skills/nw-{skill}/SKILL.md" Read paths'
)
def verify_skill_loading_paths():
    """Verify Skill Loading section in template uses nw-prefixed paths."""
    analysis = pytest.builder_analysis

    # Must NOT have old installed paths in either file
    all_old = analysis["agent_old_installed"] + analysis["skill_old_installed"]
    assert not all_old, (
        f"Agent builder files still have old-format installed paths: {all_old}"
    )

    # Must have new installed paths in at least one file
    all_new = analysis["agent_new_installed"] + analysis["skill_new_installed"]
    assert all_new, (
        "Agent builder files have no nw-prefixed installed path instructions"
    )
