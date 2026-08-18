"""Every route agent's `maxTurns` must cover its own mandated Workflow floor.

A real installed K4 run (transcripts `agent-a16cc0ee61d5e0b95`,
`agent-a35e631616b938936`) killed `nw-acceptance-designer` at 17 and 18 tool
calls, mid-exploration, with no terminal result -- `maxTurns: 12`
(`nWave/agents/nw-acceptance-designer.md`, set at the direct-delivery-kernel
cutover `2fe4a3cba`, never sized against the role's own mandated route). The
root then re-dispatched the same role blindly: a killed subagent looked
indistinguishable from one still working (ADR-SSOT-002 §1a items 1/12,
GDP-6).

This is the cheap, generic, mechanical HALF of the fix -- a build-time floor
derived straight from an agent's own numbered `## Workflow` steps plus any
`SKILL.md` loads that section mandates. It exists to catch `maxTurns`
configured BELOW what the agent's own spec already commits to; it is
DELIBERATELY not a realistic budget. `nw-acceptance-designer`'s real fix
(`fix(distill): size the acceptance designer budget on its mandated route`)
came from the two real transcripts above, not from this floor alone --
`maxTurns: 12` already sat above this floor (6) and still starved in
practice, because the role's own "cross-layer quality compilation" mandate
touches more files than its literal "at most two" example-read cap accounts
for. This test cannot see that; it only refuses the cheaper, purely
mechanical failure mode: a number that contradicts the agent's own numbered
steps before a single real run ever happens.

One generic parametrized test, not a constant per agent: adding a numbered
step to any of these five agents' Workflow, or dropping maxTurns below the
existing floor, fails this test without a matching per-agent edit here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_AGENTS_DIR = Path("nWave/agents")

#: The wave-pipeline route agents (architect -> ATD -> crafter -> examiner)
#: plus PO, all of which own a `## Workflow` section of literal numbered
#: steps. Reviewer variants are read-only critique passes over an existing
#: artifact, not a route with its own mandated write sequence -- excluded
#: deliberately, not an oversight.
_ROUTE_AGENTS = (
    "nw-acceptance-designer",
    "nw-product-owner",
    "nw-software-crafter",
    "nw-functional-software-crafter",
    "nw-user-examiner",
    "nw-solution-architect",
)

_MAX_TURNS_RE = re.compile(r"^maxTurns:\s*(\d+)\s*$", re.MULTILINE)
_NUMBERED_STEP_RE = re.compile(r"^(\d+)\.\s", re.MULTILINE)


def frontmatter_max_turns(text: str) -> int:
    """The `maxTurns:` value from the `---`-delimited YAML frontmatter."""
    end = text.index("\n---", 3)
    frontmatter = text[:end]
    match = _MAX_TURNS_RE.search(frontmatter)
    if match is None:
        raise AssertionError("agent frontmatter carries no maxTurns")
    return int(match.group(1))


def _workflow_section(text: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## Workflow":
            start = i + 1
            break
    if start is None:
        raise AssertionError("agent carries no '## Workflow' section")
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def mandated_tool_call_floor(text: str) -> int:
    """The cheapest, generic, mechanical lower bound this agent's OWN spec
    commits to: the highest-numbered step in the LARGEST single numbered
    list inside `## Workflow`. Alternative routes (e.g. ATD's RED_TO_GREEN
    vs GREEN_TO_GREEN) each restart their own list at 1 -- they are
    ALTERNATIVES, so the floor is the max across them, never their sum.
    One tool call is added per distinct `SKILL.md` load mentioned in that
    same section: a Skill invocation is itself a turn.
    """
    workflow = _workflow_section(text)
    step_numbers = [int(n) for n in _NUMBERED_STEP_RE.findall(workflow)]
    groups: list[list[int]] = []
    for n in step_numbers:
        if n == 1 or not groups:
            groups.append([n])
        else:
            groups[-1].append(n)
    max_steps = max((max(group) for group in groups), default=0)
    skill_loads = workflow.count("SKILL.md")
    return max_steps + skill_loads


@pytest.mark.parametrize("agent_name", _ROUTE_AGENTS)
def test_max_turns_covers_the_agents_own_mandated_workflow_floor(agent_name):
    path = _AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text(encoding="utf-8")

    max_turns = frontmatter_max_turns(text)
    floor = mandated_tool_call_floor(text)

    assert max_turns >= floor, (
        f"{agent_name}: maxTurns={max_turns} is BELOW its own mandated "
        f"Workflow floor={floor} -- a subagent killed before finishing its "
        f"own numbered steps returns no terminal result, which a caller "
        f"cannot distinguish from success (GDP-6)."
    )


def test_the_floor_computation_discriminates_a_planted_insufficient_maxturns():
    """A fixture that cannot discriminate yields a vacuous pass: prove the
    check genuinely refuses a maxTurns below the computed floor, not only
    that it happens to hold for the five real agents today."""
    planted = (
        "---\n"
        "name: nw-fake-route-agent\n"
        "maxTurns: 3\n"
        "---\n\n"
        "## Workflow\n\n"
        "1. First step.\n"
        "2. Second step.\n"
        "3. Third step.\n"
        "4. Fourth step, loads `~/.claude/skills/nw-fake/SKILL.md`.\n"
    )

    max_turns = frontmatter_max_turns(planted)
    floor = mandated_tool_call_floor(planted)

    assert floor == 5, f"expected floor 4 steps + 1 skill load, got {floor}"
    assert max_turns < floor, (
        "the planted fixture must be genuinely insufficient, or this test "
        "proves nothing about the real assertion's discriminating power"
    )
