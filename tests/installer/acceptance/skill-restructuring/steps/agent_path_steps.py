"""
Step definitions for agent Skill Loading path verification.

Covers: US-05 (Skill Loading path update).

Driving port: filesystem scan of agent definition files.
Asserts: all skill Read paths use nw-prefixed SKILL.md format,
no old agent-grouped paths remain.
"""

import re
from pathlib import Path

import pytest
from pytest_bdd import given, then, when


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Old pattern: ~/.claude/skills/nw/{agent-name}/{skill}.md
# Matches paths like ~/.claude/skills/nw/software-crafter/tdd-methodology.md
# or ~/.claude/skills/nw/troubleshooter/ (trailing slash)
OLD_PATH_PATTERN = re.compile(r"~/.claude/skills/nw/(?!nw-)[a-z][a-z0-9-]*/")

# New pattern: ~/.claude/skills/nw-{skill}/SKILL.md
# or ~/.claude/skills/nw-{skill}/ (directory reference)
# Also matches template placeholders like nw-{skill-name}/SKILL.md
NEW_PATH_PATTERN = re.compile(
    r"~/.claude/skills/nw-(?:[a-z][a-z0-9-]*|\{[a-z-]+\})/(?:SKILL\.md)?"
)


# ---------------------------------------------------------------------------
# Given Steps
# ---------------------------------------------------------------------------


@given("the agent definitions have Skill Loading sections")
def agent_defs_have_skill_loading(project_root: Path):
    """Verify agent definitions exist and contain Skill Loading sections."""
    agents_dir = project_root / "nWave" / "agents"
    assert agents_dir.exists(), f"Agents directory not found: {agents_dir}"

    agents_with_skill_loading = []
    for agent_file in sorted(agents_dir.glob("nw-*.md")):
        content = agent_file.read_text(encoding="utf-8")
        if "Skill Loading" in content:
            agents_with_skill_loading.append(agent_file)

    assert len(agents_with_skill_loading) > 0, "No agents have Skill Loading sections"
    pytest.agents_with_skill_loading = agents_with_skill_loading


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("an agent file is read")
def read_agent_files():
    """Read all agent files that have Skill Loading sections."""
    pytest.agent_path_results = {}
    for agent_file in pytest.agents_with_skill_loading:
        content = agent_file.read_text(encoding="utf-8")
        old_matches = OLD_PATH_PATTERN.findall(content)
        new_matches = NEW_PATH_PATTERN.findall(content)
        pytest.agent_path_results[agent_file.name] = {
            "old_paths": old_matches,
            "new_paths": new_matches,
            "content": content,
        }


# ---------------------------------------------------------------------------
# Then Steps
# ---------------------------------------------------------------------------


@then('all Read paths use "~/.claude/skills/nw-{skill}/SKILL.md" format')
def all_paths_use_new_format():
    """Verify all skill path references use the new nw-prefixed format.

    Checks that every ~/.claude/skills/ path in agent files uses
    the nw-{skill-name}/SKILL.md pattern.
    """
    agents_without_new_paths = []
    for agent_name, result in pytest.agent_path_results.items():
        # Every agent with Skill Loading should have at least one new-format path
        # (unless it's a template like agent-builder's {agent-name} placeholder)
        content = result["content"]
        # Check for any skill path reference
        all_skill_paths = re.findall(r"~/.claude/skills/nw[-/][^\s`|)\"']+", content)
        if all_skill_paths:
            new_format_paths = [
                p for p in all_skill_paths if NEW_PATH_PATTERN.search(p)
            ]
            if not new_format_paths:
                agents_without_new_paths.append(
                    f"{agent_name}: has skill paths but none in new format"
                )

    assert not agents_without_new_paths, (
        "Agents without new-format paths:\n"
        + "\n".join(f"  - {a}" for a in agents_without_new_paths)
    )


@then('no paths use old "~/.claude/skills/nw/{agent}/{skill}.md" format')
def no_old_format_paths():
    """Verify no agent file contains old-format skill paths.

    Old format: ~/.claude/skills/nw/{agent-name}/{skill-name}.md
    Examples that should NOT exist:
    - ~/.claude/skills/nw/software-crafter/tdd-methodology.md
    - ~/.claude/skills/nw/troubleshooter/
    """
    agents_with_old_paths = []
    for agent_name, result in pytest.agent_path_results.items():
        if result["old_paths"]:
            agents_with_old_paths.append(f"{agent_name}: {result['old_paths']}")

    assert not agents_with_old_paths, (
        "Agents still using old path format:\n"
        + "\n".join(f"  - {a}" for a in agents_with_old_paths)
    )
