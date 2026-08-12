"""Test A05 rule: Skill Loading section imperative recognition.

A05 accepts legacy forms ('You MUST load', 'Your FIRST action'), compact 'Read'
imperative, and native capability-backed 'Invoke Skill(nw-...)' (requires the
'Skill' tool token in frontmatter).
A05 rejects bare paths, outside-section reads, lowercase prose, missing
sections, native invocation without the Skill tool, and malformed native names.
"""

from __future__ import annotations

import pytest

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_agent,
)


_AGENT_FM_TEMPLATE = (
    "---\nname: nw-test-agent\ndescription: Test.\n"
    "model: haiku\ntools: {tools}\nskills:\n  - nw-test-skill\n---\n\n"
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
    agent_file.write_text(_AGENT_FM_TEMPLATE.format(tools=tools) + body)
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
    agent_file.write_text(_AGENT_FM_TEMPLATE.format(tools=tools) + body)
    result = ValidationResult()
    validate_agent(agent_file, result)
    a06_errors = [f for f in result.findings if f.rule_id == "A06"]
    if should_pass:
        assert len(a06_errors) == 0, (
            f"{case_id}: A06 should pass; {[e.message for e in a06_errors]}"
        )
    else:
        assert len(a06_errors) > 0, f"{case_id}: A06 should reject"
