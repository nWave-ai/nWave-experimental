"""The shared TypeSafe policy ships to every public host catalogue."""

from pathlib import Path

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    load_public_agents,
)
from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills


ROOT = Path(__file__).resolve().parents[3]
SKILL = "nw-typesafe-system-one"


def test_typesafe_skill_is_publicly_distributed() -> None:
    """The shared catalogue makes the policy available to main and subagents.

    Applicable roles preload the policy; source-blind EXAMINE retains its
    explicit capability boundary. Distribution is required independently.
    """
    content = (ROOT / "nWave" / "skills" / SKILL / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "typesafe: unavailable" in content

    public = load_public_agents(ROOT / "nWave")
    ownership = build_ownership_map(ROOT / "nWave" / "agents")
    commands = detect_command_skills(ROOT / "nWave" / "skills")
    distributed = {
        entry.name
        for entry in filter_public_skills(
            enumerate_skills(ROOT / "nWave" / "skills"), public, ownership, commands
        )
    }
    assert SKILL in distributed
