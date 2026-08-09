"""Regression: A09 (example-count rule) was deleted; A13 must still fire."""

from __future__ import annotations

from pathlib import Path

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_agent,
)


_VALID_AGENT_BODY = (
    "# nw-test-fixture\n"
    "You are Fixture, a minimal test-double agent used only for validator regression coverage.\n"
    "Your principles diverge from defaults only in scope, not in rigor.\n"
    "In subagent mode, respond with CLARIFICATION_NEEDED if the task is ambiguous.\n## Core Principles\n- Keep it minimal.\n"
    "## Skill Loading\n"
    "Your FIRST action before any other work is to load required skill files from\n"
    "~/.claude/skills/nw-fixture-skill/SKILL.md.\n"
    "| Phase | Load | Trigger |\n|-------|------|---------|\n| Start | nw-fixture-skill | Always |\n"
    "## Workflow\n1. Do the fixture thing.\n"
)


def _write_fixture_agent(tmp_path: Path, body: str) -> Path:
    agent_file = tmp_path / "nw-test-fixture.md"
    agent_file.write_text(
        "---\nname: nw-test-fixture\n"
        "description: Test fixture agent for A09 removal regression coverage.\n"
        "model: haiku\ntools: Read, Grep\n---\n\n" + body
    )
    return agent_file


def test_valid_agent_with_zero_example_headings_produces_no_a09_warning(tmp_path):
    agent_file = _write_fixture_agent(tmp_path, _VALID_AGENT_BODY)

    result = ValidationResult()
    validate_agent(agent_file, result)

    assert result.findings == [], (
        f"expected zero findings for a valid agent with no examples, got: {result.findings}"
    )


def test_unrelated_a13_warning_still_fires_without_examples(tmp_path):
    body = _VALID_AGENT_BODY.replace(
        "Your principles diverge from defaults only in scope, not in rigor.\n",
        "",
    )
    agent_file = _write_fixture_agent(tmp_path, body)

    result = ValidationResult()
    validate_agent(agent_file, result)

    rule_ids = [f.rule_id for f in result.findings]
    assert rule_ids == ["A13"], f"expected only A13 to fire, got: {result.findings}"
    assert "A09" not in rule_ids
