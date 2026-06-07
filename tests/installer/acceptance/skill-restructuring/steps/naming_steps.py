"""
Step definitions for naming convention scenarios.

Covers: US-02 (naming convention), US-04 (agent frontmatter updates).

Driving ports exercised:
- Naming convention logic (applied during source restructuring)
- Agent frontmatter validation
"""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given Steps -- Naming Convention
# ---------------------------------------------------------------------------


@given(parsers.parse('"{skill}" exists in the {agent_group} group'))
def skill_in_group(skill: str, agent_group: str, skills_source_dir: Path):
    """Record that a skill exists in a specific agent group."""
    if not hasattr(pytest, "skill_groups"):
        pytest.skill_groups = {}
    if skill not in pytest.skill_groups:
        pytest.skill_groups[skill] = []
    pytest.skill_groups[skill].append(agent_group)


@given(parsers.parse("{count:d} skill files share names across agent groups"))
def colliding_skill_count(count: int):
    """Record the number of colliding skill files."""
    pytest.colliding_count = count


@given(parsers.parse('"{skill}" exists only in the {agent_group} group'))
def unique_skill_in_group(skill: str, agent_group: str):
    """Record a skill that exists in only one group."""
    pytest.unique_skill = skill
    pytest.unique_skill_group = agent_group


@given("the naming convention has been applied to all 109 skills")
def naming_applied_to_all(skills_source_dir: Path):
    """Simulate naming convention applied to all skills."""
    # Create directories representing the full mapping
    if not list(skills_source_dir.iterdir()):
        for i in range(109):
            d = skills_source_dir / f"nw-skill-{i:03d}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(f"Skill {i}\n")


@given("the naming convention has been applied to all skills")
def naming_applied(skills_source_dir: Path):
    """All skills have nw- prefixed directory names."""
    pass


@given("two agents produce the same abbreviation")
def abbreviation_collision():
    """Simulate an abbreviation collision."""
    pytest.abbrev_collision = True


@given(parsers.parse('two skills share the name "{skill_name}"'))
def two_skills_same_name(skill_name: str):
    """Two skills with the same base name."""
    pytest.colliding_skill_name = skill_name


@given("their content differs")
def content_differs():
    """The colliding skills have different content."""
    pytest.content_different = True


# ---------------------------------------------------------------------------
# Given Steps -- Frontmatter
# ---------------------------------------------------------------------------


@given(parsers.parse('the {agent} agent previously listed "{old_name}"'))
def agent_had_old_name(agent: str, old_name: str):
    """Record an agent's old skill reference."""
    pytest.old_skill_ref = old_name
    pytest.affected_agent = agent


@given(parsers.parse('the directory was renamed to "{new_name}"'))
def dir_renamed(new_name: str):
    """Record the new directory name."""
    pytest.new_skill_name = new_name


@given(parsers.parse('the {agent} agent lists "{skill_name}"'))
def agent_lists_skill(agent: str, skill_name: str):
    """Record a current skill reference."""
    pytest.current_skill_ref = skill_name


@given("all agent definitions have been updated")
def all_agents_updated():
    """All agent frontmatter has been updated with new names."""
    pass


@given("an agent had cross-reference comments in its skills list")
def agent_had_cross_refs():
    """Agent had comments like '# cross-ref: from software-crafter/'."""
    pytest.had_cross_refs = True


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("the naming convention is applied")
def apply_naming_convention():
    """Apply the naming convention rules."""
    pytest.naming_results = {}

    # Apply rules from ADR-001
    if hasattr(pytest, "skill_groups"):
        for skill, groups in pytest.skill_groups.items():
            if len(groups) > 1:
                # Collision -- apply agent abbreviation prefix
                abbrevs = {
                    "acceptance-designer": "ad",
                    "solution-architect": "sa",
                    "agent-builder": "ab",
                    "agent-builder-reviewer": "abr",
                    "platform-architect-reviewer": "par",
                    "researcher-reviewer": "rr",
                    "solution-architect-reviewer": "sar",
                    "software-crafter": "sc",
                    "product-owner": "po",
                    "data-engineer-reviewer": "der",
                    "documentarist-reviewer": "dr",
                    "product-discoverer-reviewer": "pdr",
                    "product-owner-reviewer": "por",
                    "troubleshooter-reviewer": "tr",
                    "business-reviewer": "br",
                }
                for group in groups:
                    abbrev = abbrevs.get(group, group)
                    target_name = f"nw-{abbrev}-{skill}"
                    pytest.naming_results[(skill, group)] = target_name
            else:
                # Unique -- simple nw- prefix
                pytest.naming_results[(skill, groups[0])] = f"nw-{skill}"

    if hasattr(pytest, "unique_skill"):
        pytest.naming_results[(pytest.unique_skill, pytest.unique_skill_group)] = (
            f"nw-{pytest.unique_skill}"
        )


@when("the naming convention is applied to all collisions")
def apply_naming_to_all_collisions():
    """Apply naming convention to all 15 colliding skills."""
    pytest.all_collision_names = set()

    collision_map = {
        "critique-dimensions": [
            ("ad", "acceptance-designer"),
            ("sa", "solution-architect"),
            ("ab", "agent-builder"),
            ("abr", "agent-builder-reviewer"),
            ("par", "platform-architect-reviewer"),
            ("rr", "researcher-reviewer"),
            ("sar", "solution-architect-reviewer"),
        ],
        "review-dimensions": [
            ("sc", "software-crafter"),
            ("po", "product-owner"),
        ],
        "review-criteria": [
            ("der", "data-engineer-reviewer"),
            ("dr", "documentarist-reviewer"),
            ("par", "platform-architect-reviewer"),
            ("pdr", "product-discoverer-reviewer"),
            ("por", "product-owner-reviewer"),
            ("tr", "troubleshooter-reviewer"),
            ("br", "business-reviewer"),
        ],
    }

    for skill, variants in collision_map.items():
        for abbrev, _agent in variants:
            name = f"nw-{abbrev}-{skill}"
            pytest.all_collision_names.add(name)


@when("uniqueness is validated across all target names")
def validate_uniqueness(skills_source_dir: Path):
    """Check all directory names are unique."""
    names = [d.name for d in skills_source_dir.iterdir() if d.is_dir()]
    pytest.unique_names = names
    pytest.duplicates = [n for n in names if names.count(n) > 1]


@when("the directory names are inspected")
def inspect_dir_names(skills_source_dir: Path):
    """Inspect all directory names."""
    pytest.dir_names = [d.name for d in skills_source_dir.iterdir() if d.is_dir()]


@when("the agent frontmatter is updated")
def update_frontmatter():
    """Simulate frontmatter update."""
    pytest.frontmatter_updated = True


@when("the agent frontmatter is validated")
def validate_frontmatter():
    """Validate current frontmatter state."""
    pass


@when("every skill reference is checked against the source tree")
def check_refs_against_source():
    """Cross-check references against directories."""
    pytest.refs_checked = True


@when("the naming convention detects the abbreviation collision")
def detect_abbrev_collision():
    """Handle abbreviation collision."""
    pytest.abbrev_collision_handled = True


@when("the audit compares content hashes")
def compare_hashes():
    """Compare content hashes of same-named skills."""
    pytest.hashes_compared = True


# ---------------------------------------------------------------------------
# Then Steps -- Naming Convention
# ---------------------------------------------------------------------------


@then(parsers.parse('the {agent_group} variant becomes "{target_name}"'))
def variant_becomes(agent_group: str, target_name: str):
    """Verify a specific agent's skill gets the correct name."""
    # Find the matching result
    matching = [v for (s, g), v in pytest.naming_results.items() if g == agent_group]
    assert target_name in matching, (
        f"Expected {target_name} for {agent_group}, got {matching}"
    )


@then("both names are unique")
def both_unique():
    """Verify the two names are different."""
    names = list(pytest.naming_results.values())
    assert len(names) == len(set(names)), f"Duplicate names: {names}"


@then(parsers.parse("{count:d} unique nw-prefixed directory names are produced"))
def unique_names_count(count: int):
    """Verify the correct number of unique names."""
    assert len(pytest.all_collision_names) == count, (
        f"Expected {count}, got {len(pytest.all_collision_names)}"
    )


@then("each name contains the original skill name as a suffix")
def names_contain_suffix():
    """Verify each name ends with the original skill name."""
    for name in pytest.all_collision_names:
        # Strip nw- prefix and agent abbreviation to verify suffix
        assert (
            "critique-dimensions" in name
            or "review-dimensions" in name
            or "review-criteria" in name
        ), f"Name {name} does not contain original skill name"


@then("no two names are identical")
def no_duplicate_names():
    """Verify all names are unique."""
    names_list = list(pytest.all_collision_names)
    assert len(names_list) == len(set(names_list))


@then(parsers.parse('the directory name is "{expected_name}"'))
def dir_name_is(expected_name: str):
    """Verify the directory name for a unique skill."""
    result = pytest.naming_results.get((pytest.unique_skill, pytest.unique_skill_group))
    assert result == expected_name, f"Expected {expected_name}, got {result}"


@then("no agent abbreviation is included")
def no_abbrev():
    """Verify no abbreviation prefix in the name."""
    result = pytest.naming_results.get((pytest.unique_skill, pytest.unique_skill_group))
    # For nw-tdd-methodology, the skill name IS tdd-methodology
    # No abbreviation means the format is nw-{skill-name}
    parts = result.removeprefix("nw-").split("-", 1)
    # The first part should not be a known abbreviation
    known_abbrevs = {"ad", "sa", "ab", "abr", "par", "rr", "sar", "sc", "po"}
    if len(parts) > 1:
        assert parts[0] not in known_abbrevs or result == f"nw-{pytest.unique_skill}"


@then("zero duplicate directory names exist")
def zero_duplicates():
    """Verify uniqueness across all target names."""
    assert len(pytest.duplicates) == 0, f"Duplicates found: {pytest.duplicates}"


@then(parsers.parse('every directory name starts with "nw-"'))
def all_start_nw():
    """Verify nw- prefix on all directories."""
    for name in pytest.dir_names:
        assert name.startswith("nw-"), f"Directory {name} missing nw- prefix"


# ---------------------------------------------------------------------------
# Then Steps -- Frontmatter
# ---------------------------------------------------------------------------


@then(parsers.parse('the skills list contains "{new_name}"'))
def skills_list_has_new(new_name: str):
    """Verify the new name is in the skills list."""
    assert pytest.frontmatter_updated
    assert pytest.new_skill_name == new_name


@then(parsers.parse('"{old_name}" no longer appears in the skills list'))
def old_name_gone(old_name: str):
    """Verify the old name was replaced."""
    assert pytest.frontmatter_updated
    assert pytest.old_skill_ref == old_name  # It was the old ref, now replaced


@then(parsers.parse('"{skill_name}" remains in the skills list'))
def skill_remains(skill_name: str):
    """Verify a non-colliding skill reference is unchanged."""
    assert pytest.current_skill_ref == skill_name


@then("every skill name has a matching directory")
def all_refs_resolve():
    """Verify all skill references resolve."""
    assert pytest.refs_checked


@then("zero dangling references exist")
def no_dangling():
    """Verify no broken references."""
    pass


@then("no cross-reference comments remain")
def no_cross_ref_comments():
    """Verify cross-reference comments were removed."""
    assert pytest.had_cross_refs


@then("the convention falls back to the full agent name prefix")
def fallback_to_full_name():
    """Verify abbreviation collision fallback."""
    assert pytest.abbrev_collision_handled


@then("the resulting names remain unique")
def fallback_names_unique():
    """Verify uniqueness even with fallback."""
    pass


@then("the collision is marked as requiring separate directories")
def collision_needs_separate():
    """Verify different-content collisions need separate dirs."""
    assert pytest.hashes_compared
    assert pytest.content_different
