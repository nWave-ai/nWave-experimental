"""Test A05 rule: Skill Loading section imperative recognition.

A05 accepts legacy forms ('You MUST load', 'Your FIRST action') and compact 'Read' imperative.
A05 rejects bare paths, outside-section reads, lowercase prose, and missing sections.
"""

from __future__ import annotations

import pytest

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_agent,
)


_AGENT_FM = (
    "---\nname: nw-test-agent\ndescription: Test.\n"
    "model: haiku\ntools: Read, Write\nskills:\n  - nw-test-skill\n---\n\n"
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
        True,
        "compact_concrete",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nRead `~/.claude/skills/nw-{skill-name}/SKILL.md`.\n",
        True,
        "compact_template",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nYou MUST load your skill files.\n",
        True,
        "legacy_must",
    ),
    (
        _AGENT_BASE + "## Skill Loading\nYour FIRST action before any other work.\n",
        True,
        "legacy_first",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nText.\n## Workflow\nRead `~/.claude/skills/nw-test-skill/SKILL.md`.\n",
        False,
        "read_outside_section",
    ),
    (
        _AGENT_BASE + "## Skill Loading\n`~/.claude/skills/nw-test-skill/SKILL.md`\n",
        False,
        "bare_path_no_read",
    ),
    (
        _AGENT_BASE
        + "## Skill Loading\nYou should read at ~/.claude/skills/nw-test-skill/SKILL.md.\n",
        False,
        "lowercase_read_prose",
    ),
    (
        _AGENT_BASE + "## Workflow\nSome workflow.\n",
        False,
        "no_skill_loading_section",
    ),
]


@pytest.mark.parametrize("body,should_pass,case_id", _A05_CASES)
def test_a05_skill_loading_imperative(tmp_path, body, should_pass, case_id):
    """Parametrized A05 acceptance and rejection cases."""
    agent_file = tmp_path / "nw-test-agent.md"
    agent_file.write_text(_AGENT_FM + body)
    result = ValidationResult()
    validate_agent(agent_file, result)
    a05_errors = [f for f in result.findings if f.rule_id == "A05"]
    if should_pass:
        assert len(a05_errors) == 0, (
            f"{case_id}: A05 should pass; {[e.message for e in a05_errors]}"
        )
    else:
        assert len(a05_errors) > 0, f"{case_id}: A05 should reject"
