"""Test A05 rule: Skill Loading section imperative recognition.

A05 accepts legacy forms ('You MUST load', 'Your FIRST action'), compact 'Read'
imperative, native capability-backed 'Invoke Skill(nw-...)' (requires the
'Skill' tool token in frontmatter), EagerPreloaded (nonempty frontmatter
'skills:'), and the explicit NoRuntimeSkill sentence ('No runtime Skill
loading.' with no frontmatter skills and no 'Skill' tool).
A05 rejects bare paths, outside-section reads, lowercase prose, missing
sections, native invocation without the Skill tool, malformed native names,
and NoRuntimeSkill misuse (the sentence alongside frontmatter skills or the
Skill tool).
"""

from __future__ import annotations

import pytest

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_agent,
)


_SKILLS_PRESENT = "\n  - nw-test-skill"
_SKILLS_EMPTY = ""

_AGENT_FM_TEMPLATE = (
    "---\nname: nw-test-agent\ndescription: Test.\n"
    "model: haiku\ntools: {tools}\nskills:{skills}\n---\n\n"
)

_AGENT_BASE = (
    "# nw-test-agent\n"
    "You are Tester.\n"
    "Your principles diverge from defaults.\n"
    "In subagent mode, CLARIFICATION_NEEDED.\n"
    "## Core Principles\n- P1\n"
)

_A05_CASES = [
    (
        _AGENT_BASE
        + "## Skill Loading\nRead `~/.claude/skills/nw-test-skill/SKILL.md`.\n",
        "Read, Write",
        True,
        "compact_concrete",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nRead `~/.claude/skills/nw-{skill-name}/SKILL.md`.\n",
        "Read, Write",
        True,
        "compact_template",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nYou MUST load your skill files.\n",
        "Read, Write",
        True,
        "legacy_must",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nYour FIRST action before any other work.\n",
        "Read, Write",
        True,
        "legacy_first",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nText.\n## Workflow\nRead `~/.claude/skills/nw-test-skill/SKILL.md`.\n",
        "Read, Write",
        False,
        "read_outside_section",
    ),
    (
        _AGENT_BASE + "## Skill Loading\n`~/.claude/skills/nw-test-skill/SKILL.md`\n",
        "Read, Write",
        False,
        "bare_path_no_read",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nYou should read at ~/.claude/skills/nw-test-skill/SKILL.md.\n",
        "Read, Write",
        False,
        "lowercase_read_prose",
    ),
    (
        _AGENT_BASE + "## Workflow\nSome workflow.\n",
        "Read, Write",
        False,
        "no_skill_loading_section",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-test-skill)\n",
        "Read, Write, Skill",
        True,
        "native_concrete_with_skill_tool",
    ),
    (
        _AGENT_BASE + "## Skill Loading\n- Invoke ONE Skill(nw-test-skill)\n",
        "Read, Write, Skill",
        True,
        "native_one_with_skill_tool",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-{skill-name})\n",
        "Read, Write, Skill",
        True,
        "native_template_with_skill_tool",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-test-skill)\n",
        "Read, Write",
        False,
        "native_without_skill_tool",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nText.\n## Workflow\nInvoke Skill(nw-test-skill)\n",
        "Read, Write, Skill",
        False,
        "native_outside_section",
    ),
    (
        _AGENT_BASE + "## Skill Loading\ninvoke skill(nw-test-skill)\n",
        "Read, Write, Skill",
        False,
        "native_lowercase_prose",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(test-skill)\n",
        "Read, Write, Skill",
        False,
        "native_malformed_name",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nInvoke Skill(nw-test-skill) ON-TRIGGER — contested law\n",
        "Read, Write, Skill",
        True,
        "native_concrete_with_suffix",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\n- Invoke ONE Skill(nw-test-skill) ON-TRIGGER — language property\n",
        "Read, Write, Skill",
        True,
        "native_one_with_suffix",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-test-skill) ON-TRIGGER — \n",
        "Read, Write, Skill",
        False,
        "native_empty_trigger_suffix",
    ),
]


@pytest.mark.parametrize("body,tools,should_pass,case_id", _A05_CASES)
def test_a05_skill_loading_imperative(tmp_path, body, tools, should_pass, case_id):
    """Parametrized A05 acceptance and rejection cases."""
    agent_file = tmp_path / "nw-test-agent.md"
    agent_file.write_text(
        _AGENT_FM_TEMPLATE.format(tools=tools, skills=_SKILLS_EMPTY) + body
    )
    result = ValidationResult()
    validate_agent(agent_file, result)
    a05_errors = [f for f in result.findings if f.rule_id == "A05"]
    if should_pass:
        assert len(a05_errors) == 0, (
            f"{case_id}: A05 should pass; {[e.message for e in a05_errors]}"
        )
    else:
        assert len(a05_errors) > 0, f"{case_id}: A05 should reject"


_A06_NATIVE_CASES = [
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-test-skill)\n",
        "Read, Write, Skill",
        True,
        "native_pass_covers_a06",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nInvoke Skill(nw-test-skill)\n",
        "Read, Write",
        False,
        "native_without_skill_tool_fails_a06",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nInvoke Skill(nw-test-skill) ON-TRIGGER — contested law\n",
        "Read, Write, Skill",
        True,
        "native_suffixed_pass_covers_a06",
    ),
]


@pytest.mark.parametrize("body,tools,should_pass,case_id", _A06_NATIVE_CASES)
def test_a06_native_skill_route_boundary(tmp_path, body, tools, should_pass, case_id):
    """A06 accepts the same capability-backed native Skill route as A05."""
    agent_file = tmp_path / "nw-test-agent.md"
    agent_file.write_text(
        _AGENT_FM_TEMPLATE.format(tools=tools, skills=_SKILLS_EMPTY) + body
    )
    result = ValidationResult()
    validate_agent(agent_file, result)
    a06_errors = [f for f in result.findings if f.rule_id == "A06"]
    if should_pass:
        assert len(a06_errors) == 0, (
            f"{case_id}: A06 should pass; {[e.message for e in a06_errors]}"
        )
    else:
        assert len(a06_errors) > 0, f"{case_id}: A06 should reject"


_A05_A06_NORUNTIMESKILL_CASES = [
    (
        _AGENT_BASE
        + "## Skill Loading\nRead `~/.claude/skills/nw-test-skill/SKILL.md`.\n",
        "Read, Write",
        _SKILLS_PRESENT,
        True,
        "read_command_with_skills",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nNo runtime Skill loading.\n",
        "Read, Write",
        _SKILLS_EMPTY,
        True,
        "no_runtime_exact_empty",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nNo runtime Skill loading.\n",
        "Read, Write",
        _SKILLS_PRESENT,
        False,
        "no_runtime_with_skills",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nNo runtime Skill loading.\n",
        "Read, Write, Skill",
        _SKILLS_EMPTY,
        False,
        "no_runtime_with_skill_tool",
    ),
]


@pytest.mark.parametrize(
    "body,tools,skills,should_pass,case_id", _A05_A06_NORUNTIMESKILL_CASES
)
def test_a05_a06_noruntimeskill_boundary(
    tmp_path, body, tools, skills, should_pass, case_id
):
    """A05/A06 coordination on No runtime Skill loading directive."""
    agent_file = tmp_path / "nw-test-agent.md"
    agent_file.write_text(_AGENT_FM_TEMPLATE.format(tools=tools, skills=skills) + body)
    result = ValidationResult()
    validate_agent(agent_file, result)
    a05_errors = [f for f in result.findings if f.rule_id == "A05"]
    a06_errors = [f for f in result.findings if f.rule_id == "A06"]
    if should_pass:
        assert len(a05_errors) == 0, (
            f"{case_id}: A05 should pass; {[e.message for e in a05_errors]}"
        )
        assert len(a06_errors) == 0, (
            f"{case_id}: A06 should pass; {[e.message for e in a06_errors]}"
        )
    else:
        assert len(a05_errors) > 0, f"{case_id}: A05 should reject"
        assert len(a06_errors) > 0, f"{case_id}: A06 should reject"


# TEST_CASES_READY
