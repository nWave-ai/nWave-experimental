"""Regression test: DISTILL/DELIVER skill authorities pin dependency-manifest completeness.

K4 defect: ATs introduced an undeclared test-only import (Hypothesis); ambient
availability masked the gap until a clean-install run failed collection with
ModuleNotFoundError. Pins the manifest-vs-ambient property on both owning
authorities plus the existing BROKEN classification, without hardcoding line
numbers (content drifts; the property must not).
"""

from pathlib import Path

import pytest

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    load_public_agents,
)
from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

# Cross-language manifest markers: the property must not read Python-only.
MANIFEST_MARKERS = (
    "requirements",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
)

REQUIRED_PHRASE = {
    "nw-ad-distill-dod": "dependency manifest",
    "nw-crafter-discipline-atdd-pure": "dependency closure",
}


@pytest.fixture(scope="module")
def public_skill_names() -> set[str]:
    public_agents = load_public_agents(NWAVE_DIR)
    ownership_map = build_ownership_map(AGENTS_DIR)
    command_skills = detect_command_skills(SKILLS_DIR)
    entries = enumerate_skills(SKILLS_DIR)
    kept = filter_public_skills(entries, public_agents, ownership_map, command_skills)
    return {entry.name for entry in kept}


def _skill_text(skill_name: str) -> str:
    return (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill_name,required_phrase", sorted(REQUIRED_PHRASE.items()))
def test_skill_pins_manifest_vs_ambient_property(
    skill_name, required_phrase, public_skill_names
):
    assert skill_name in public_skill_names, (
        f"{skill_name}: missing from public distribution"
    )
    content = _skill_text(skill_name)
    assert required_phrase in content, (
        f"{skill_name}: lost '{required_phrase}' requirement"
    )
    assert "ambient" in content.lower(), (
        f"{skill_name}: lost ambient-interpreter rejection"
    )
    for marker in MANIFEST_MARKERS:
        assert marker in content, (
            f"{skill_name}: manifest marker `{marker}` missing -- not Python-only"
        )


def test_red_scaffolding_still_classifies_missing_module_as_broken():
    content = _skill_text("nw-distill-red-scaffolding")
    assert "ModuleNotFoundError" in content and "BROKEN" in content, (
        "nw-distill-red-scaffolding: ModuleNotFoundError -> BROKEN classification "
        "missing -- undeclared test dependencies would no longer block handoff"
    )
