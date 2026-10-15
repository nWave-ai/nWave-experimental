"""Every reviewer told to use Jev can run the Jev client.

Jev is reached only by running the skill's ``scripts/jev_decide.py``. A reviewer
that preloads ``nw-typesafe-system-one`` but declares no Bash cannot make that
call, so its Jev obligation is unexecutable. Reviewers stay read-only for
mutation: Write and Edit remain absent.
"""

from pathlib import Path

import pytest
import yaml

from des.domain.agent_capability import split_declared_tools


AGENTS_DIR = Path(__file__).resolve().parents[2] / "nWave" / "agents"


def _frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    return yaml.safe_load(content[4 : content.index("\n---\n", 4)])


def _declared_tools(frontmatter: dict) -> set[str]:
    raw = frontmatter.get("tools") or []
    if isinstance(raw, str):
        return set(split_declared_tools(raw))
    return {str(tool).strip() for tool in raw}


JEV_REVIEWERS = sorted(
    path
    for path in AGENTS_DIR.glob("nw-*-reviewer.md")
    if "nw-typesafe-system-one" in (_frontmatter(path).get("skills") or [])
)


def test_reviewers_preloading_jev_exist() -> None:
    assert JEV_REVIEWERS, f"no reviewer in {AGENTS_DIR} preloads nw-typesafe-system-one"


@pytest.mark.parametrize("agent", JEV_REVIEWERS, ids=lambda path: path.stem)
def test_jev_reviewer_can_run_the_client_without_mutation_tools(agent: Path) -> None:
    tools = _declared_tools(_frontmatter(agent))
    assert "Bash" in tools, (
        f"{agent.stem} tools={sorted(tools)} cannot run jev_decide.py"
    )
    assert not tools & {"Write", "Edit"}, f"{agent.stem} tools={sorted(tools)}"
