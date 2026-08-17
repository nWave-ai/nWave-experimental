"""Structural regressions for the completed skill-namespace migration.

Skill contents are deliberately not pinned byte-for-byte.  Generated projections
are owned by ``docgen --check`` and the public-skill validators; freezing Markdown
hashes would make prompt refactoring indistinguishable from migration breakage.
"""

from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parents[3] / "nWave" / "skills"

# Migration baseline: 146 bulk skills plus the three troubleshooter skills.
EXPECTED_NW_SKILL_FLOOR = 149

# Agent-grouped directories emptied by the nw-* namespace migration.
FULLY_EMPTIED_AGENT_DIRS = (
    "business-discoverer",
    "business-osint",
    "common",
    "data-engineer",
    "deal-closer",
    "documentarist",
    "functional-software-crafter",
    "outreach-writer",
    "platform-architect",
    "product-discoverer",
    "researcher",
    "software-crafter-reviewer",
    "tutorialist",
    "ux-designer",
    "workshopper",
)


def test_migrated_skills_use_the_flat_nw_namespace() -> None:
    """The migration keeps its namespace shape without freezing skill prose."""
    migrated = [
        path for path in SKILLS_DIR.glob("nw-*/SKILL.md") if path.parent.is_dir()
    ]

    assert len(migrated) >= EXPECTED_NW_SKILL_FLOOR
    assert all(path.parent.name.startswith("nw-") for path in migrated)


def test_emptied_agent_dirs_stay_absent() -> None:
    """The migration must not recreate the retired agent-grouped layout."""
    leftovers = [
        name for name in FULLY_EMPTIED_AGENT_DIRS if (SKILLS_DIR / name).exists()
    ]

    assert leftovers == []
