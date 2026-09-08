"""AT for the class ``roles-are-instructed-to-invoke-skills-the-flag-makes-uninvocable``.

Defect (defects.md, reported by a user on 2026-09-06 with a session log): a
shipped role spec instructed ``Invoke Skill(x)`` where ``x`` carries
``disable-model-invocation: true``. The Skill tool refuses, the role has no
fallback, and the delivery wave stops at that trigger. Three separate instances
were patched one at a time before the class itself was closed.

The producer-side repair lives in ``scripts/docgen.py``, which now derives the
directive verb from the target's own frontmatter. This gate is the last-resort
falsifier (GDP-0) for the remaining route into the state: a hand-edited spec, or
a GENERATED region that was never re-rendered after a skill gained the flag.

Driving port: ``validate_invocability(project_root, result)`` -- the same
function ``main()`` calls, exercised against a synthetic asset tree so the
verdict is a property of the RULE, not of today's shipped tree.

RED before the fix: ``validate_invocability`` does not exist, and the shipped
tree (with one instance restored) validates clean.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_invocability,
)


def _skill(root: Path, name: str, *, invocable: bool) -> None:
    skill_dir = root / "nWave" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    flag = "" if invocable else "disable-model-invocation: true\n"
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Fixture skill.\nuser-invocable: false\n"
        f"{flag}---\n\n# {name}\n"
    )


def _agent(root: Path, name: str, body: str) -> None:
    agents = root / "nWave" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: Fixture agent.\n---\n\n{body}\n"
    )


def _tree(tmp_path: Path) -> Path:
    """A minimal asset tree with both kinds of skill and the empty dirs the
    validator walks."""
    root = tmp_path / "repo"
    _skill(root, "nw-fixture-knowledge", invocable=False)
    _skill(root, "nw-fixture-procedure", invocable=True)
    (root / "nWave" / "tasks" / "nw").mkdir(parents=True, exist_ok=True)
    (root / "nWave" / "agents").mkdir(parents=True, exist_ok=True)
    return root


def _x03(root: Path) -> list[str]:
    result = ValidationResult()
    validate_invocability(root, result)
    return [f.message for f in result.findings if f.rule_id == "X03"]


def test_invoking_a_flagged_skill_is_rejected(tmp_path):
    """The exact shape that blocked the user: an ON-TRIGGER invocation of a
    skill the Skill tool cannot reach."""
    root = _tree(tmp_path)
    _agent(
        root,
        "nw-fixture-reviewer",
        "- Invoke Skill(nw-fixture-knowledge) ON-TRIGGER — review start",
    )

    findings = _x03(root)

    assert len(findings) == 1, f"expected one X03 finding, got: {findings}"
    assert "nw-fixture-knowledge" in findings[0]


def test_rejection_states_what_why_and_how(tmp_path):
    """A rejection the reader cannot act on is worse than none: the message
    must name the target, why the tool cannot reach it, and both repairs."""
    root = _tree(tmp_path)
    _agent(
        root,
        "nw-fixture-reviewer",
        "- Invoke Skill(nw-fixture-knowledge) ON-TRIGGER — review start",
    )

    message = _x03(root)[0]

    assert "disable-model-invocation" in message
    assert "~/.claude/skills/nw-fixture-knowledge/SKILL.md" in message
    assert "scripts/docgen.py" in message


@pytest.mark.negative_at
def test_invoking_an_invocable_skill_is_accepted(tmp_path):
    """The rule must not degrade into "never invoke a skill" -- a procedure the
    role genuinely executes keeps its invocation directive."""
    root = _tree(tmp_path)
    _agent(
        root,
        "nw-fixture-agent",
        "- Invoke Skill(nw-fixture-procedure) ON-TRIGGER — obligation selected",
    )

    assert _x03(root) == []


@pytest.mark.negative_at
def test_reading_a_flagged_skill_is_accepted(tmp_path):
    """Reading the file is the repair, so it must never trip the gate."""
    root = _tree(tmp_path)
    _agent(
        root,
        "nw-fixture-reviewer",
        "- Read `~/.claude/skills/nw-fixture-knowledge/SKILL.md` ON-TRIGGER — start",
    )

    assert _x03(root) == []


def test_a_command_and_a_skill_body_are_scanned_too(tmp_path):
    """Agents are not the only shipped specs an LLM executes: a wave command
    and a composing skill can carry the same directive."""
    root = _tree(tmp_path)
    directive = "- Invoke Skill(nw-fixture-knowledge) ON-TRIGGER — start"
    (root / "nWave" / "tasks" / "nw" / "fixture.md").write_text(
        f"---\nname: fixture\ndescription: Fixture command.\n---\n\n{directive}\n"
    )
    (root / "nWave" / "skills" / "nw-fixture-procedure" / "SKILL.md").write_text(
        f"---\nname: nw-fixture-procedure\ndescription: Fixture.\n---\n\n{directive}\n"
    )

    findings = _x03(root)

    assert len(findings) == 2, f"expected both specs flagged, got: {findings}"


def test_the_shipped_tree_is_clean():
    """The repo's own assets carry no such directive. This is the row that
    turns red if a skill gains the flag without its callers being re-rendered."""
    root = Path(__file__).resolve().parents[3]

    assert _x03(root) == []
