"""Regression AT for reconcile-a12-reviewer-bash (bugfix lane).

Defect (docs/feature/reconcile-a12-reviewer-bash/feature-delta.md): the A12 rule in
``scripts/validation/validate_framework_templates.py`` forbids ``("Write", "Edit",
"Bash")`` for reviewer agents. WS-12 (Ale-greenlit, shipped ee48faa62) deliberately
grants read-only ``Bash`` to the 8 code-fact ``nw-*-reviewer`` agents so the
``nw-code-analysis-port`` grep tier is reachable from reviewers. Every reviewer
carrying WS-12's Bash therefore fails A12 today -- framework validation is red and
a plain ``git commit`` (no ``--no-verify``) is blocked.

Fix (crafter-owned, NOT authored here): A12's reviewer-forbidden-tool set narrows
from ``("Write", "Edit", "Bash")`` to ``("Write", "Edit")``. Bash becomes an
allowed, read-only investigative tool for reviewers (WS-12); the read-only scoping
is enforced by permission rules, not by denying the tool outright. The reviewer
read-only-for-*mutation* invariant is preserved -- Write/Edit remain forbidden.

Driving port: ``validate_agent(filepath, result)`` -- the same function
``main()`` calls per discovered agent file (Layer 2, in-process; mirrors the
precedent in ``tests/build/unit/test_validate_skill_agent_mapping.py``). Findings
are filtered to ``rule_id == "A12"`` so unrelated frontmatter/body rules (A01-A16)
never mask the A12 verdict under test.

RED now: ``test_reviewer_with_bash_tool_produces_no_a12_error`` fails because A12
currently flags Bash as forbidden for reviewers.
GREEN both before and after: ``test_reviewer_with_write_or_edit_tool_still_fails_a12``
(negative AT) -- guards against the fix over-broadening past Write/Edit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validation.validate_framework_templates import (
    ValidationResult,
    validate_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The exact shipped WS-12 tools string (nw-software-crafter-reviewer.md,
# commit ee48faa62) -- read-only Bash alongside the code-fact MCP tools.
_WS12_REVIEWER_TOOLS = (
    "Read, Glob, Grep, Task, Bash, mcp__tsunami__callers_of, "
    "mcp__tsunami__reads_of, mcp__tsunami__never_wired, "
    "mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section"
)


def _write_agent(tmp_path: Path, name: str, tools: str) -> Path:
    """Write a realistic agent frontmatter+body file and return its path.

    ``is_reviewer`` in ``validate_agent`` is derived from the filename stem
    (``name.endswith("-reviewer")``), not the frontmatter -- so the caller's
    ``name`` controls reviewer-classification, mirroring production agents.
    """
    agent_file = tmp_path / f"{name}.md"
    agent_file.write_text(
        f"---\n"
        f"name: {name}\n"
        f"description: Test fixture agent for A12 regression coverage.\n"
        f"model: haiku\n"
        f"tools: {tools}\n"
        f"---\n\n"
        f"# {name}\n\n"
        f"You are a test fixture reviewer.\n"
    )
    return agent_file


def _a12_findings(filepath: Path) -> list[str]:
    """Run validate_agent and return only the A12 finding messages."""
    result = ValidationResult()
    validate_agent(filepath, result)
    return [f.message for f in result.findings if f.rule_id == "A12"]


# ---------------------------------------------------------------------------
# Positive: reviewer + Bash -> no A12 error (RED now, GREEN after the fix)
# ---------------------------------------------------------------------------


def test_reviewer_with_bash_tool_produces_no_a12_error(tmp_path):
    """A12 must permit Bash for a reviewer (WS-12's read-only-Bash grant).

    Mirrors the shipped ``nw-software-crafter-reviewer`` frontmatter. Today
    A12's forbidden set is ``("Write", "Edit", "Bash")`` -- Bash trips the
    rule and this assertion fails with a real A12 finding (AssertionError,
    not a collection/import error).
    """
    agent_file = _write_agent(
        tmp_path, "nw-software-crafter-reviewer", _WS12_REVIEWER_TOOLS
    )

    findings = _a12_findings(agent_file)

    assert findings == [], (
        f"expected zero A12 findings for a reviewer carrying read-only Bash "
        f"(WS-12), got: {findings}"
    )


# ---------------------------------------------------------------------------
# Negative: reviewer + Write/Edit -> A12 error STILL fires (never weakened)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("mutating_tool", ["Write", "Edit"])
def test_reviewer_with_write_or_edit_tool_still_fails_a12(tmp_path, mutating_tool):
    """A12 must keep rejecting a reviewer that carries a true mutation tool.

    Guards against the WS-12 reconciliation over-broadening the forbidden
    set to nothing: Write/Edit are the actual mutation tools the
    read-only-for-mutation invariant protects, and they must trip A12
    both BEFORE and AFTER the fix that removes Bash from the forbidden set.
    """
    tools = f"Read, Glob, Grep, Task, {mutating_tool}"
    agent_file = _write_agent(tmp_path, "nw-fixture-reviewer", tools)

    findings = _a12_findings(agent_file)

    assert len(findings) == 1, (
        f"expected exactly one A12 finding for a reviewer carrying "
        f"'{mutating_tool}', got: {findings}"
    )
    assert mutating_tool in findings[0]


# ---------------------------------------------------------------------------
# Control: a non-reviewer agent is unaffected by A12 regardless of tools
# ---------------------------------------------------------------------------


def test_non_reviewer_agent_never_produces_a12_finding(tmp_path):
    """A12 only applies to reviewer agents (filename ends with '-reviewer').

    A specialist agent carrying Bash, Write, and Edit together produces zero
    A12 findings -- the rule's reviewer-only scope is untouched by the
    WS-12/A12 reconciliation. Stays green before and after the fix.
    """
    agent_file = _write_agent(
        tmp_path, "nw-software-crafter", "Read, Write, Edit, Bash, Glob, Grep"
    )

    findings = _a12_findings(agent_file)

    assert findings == []


# ---------------------------------------------------------------------------
# Regression for techdebt row
# agent-tools-frontmatter-substring-membership-check-not-exact: A12 used a
# raw substring search (``forbidden in tools``) over the bare comma-scalar
# frontmatter string instead of a tokenized membership check. A tool name
# that merely CONTAINS "Write"/"Edit" as a substring (not the literal
# granted token) must not trip A12.
# ---------------------------------------------------------------------------


def test_reviewer_with_tool_name_containing_edit_substring_produces_no_a12_error(
    tmp_path,
):
    """A12 must not false-positive on a tool whose NAME merely contains 'Edit'.

    ``mcp__wiki__SuggestEdit`` is a distinct granted token, not the literal
    ``Edit`` mutation tool -- ``"Edit" in tools_string`` (substring) matches
    it wrongly; ``"Edit" in tools_tokens`` (tokenized membership) does not.
    """
    agent_file = _write_agent(
        tmp_path, "nw-fixture-reviewer", "Read, Glob, Grep, mcp__wiki__SuggestEdit"
    )

    findings = _a12_findings(agent_file)

    assert findings == [], (
        f"expected zero A12 findings for a tool merely containing the "
        f"substring 'Edit', got: {findings}"
    )


def test_reviewer_with_bracketed_tool_list_and_edit_substring_produces_no_a12_error(
    tmp_path,
):
    """Same false-positive check, for the one agent using YAML flow-list
    brackets (parsed as an actual list by yaml.safe_load) instead of a bare
    comma-scalar string -- both frontmatter styles must behave identically.
    """
    agent_file = _write_agent(
        tmp_path, "nw-fixture-reviewer", "[Read, Glob, mcp__wiki__SuggestEdit]"
    )

    findings = _a12_findings(agent_file)

    assert findings == []
