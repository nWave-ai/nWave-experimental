"""Roles that create new files declare the Write tool, not only Edit.

The acceptance designer writes new oracle and support files and both crafters
write CREATE_NEW targets. Edit cannot create a file, so without Write a role
must fall back to shell redirection. DES observes the bytes each turn changed,
so Write does not widen what a role may change.
"""

from pathlib import Path

import pytest
import yaml

from des.domain.agent_capability import split_declared_tools


AGENTS_DIR = Path(__file__).resolve().parents[2] / "nWave" / "agents"


def _declared_tools(agent: str) -> list[str]:
    content = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content[4 : content.index("\n---\n", 4)])
    return sorted(split_declared_tools(frontmatter["tools"]))


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        (
            "nw-acceptance-designer",
            ["Bash", "Edit", "Read", "StructuredOutput", "Write"],
        ),
        (
            "nw-software-crafter",
            ["Bash", "Edit", "Glob", "Read", "StructuredOutput", "Write"],
        ),
        (
            "nw-functional-software-crafter",
            ["Bash", "Edit", "Read", "StructuredOutput", "Write"],
        ),
    ],
)
def test_file_authoring_roles_can_create_files(agent: str, expected: list[str]) -> None:
    assert _declared_tools(agent) == expected
