"""Acceptance tests for strip_private_agents.py rewrite.

Scenarios covered (step 02-01):
  P0b-01: Stripping removes private agents using allow-list
  P0b-02: Uncatalogued agent is stripped (fail-closed)
  P0b-03: Skills owned by private agents are removed
  P0b-04: Multi-owner skill kept when any owner is public
  P0b-05: Post-strip verification passes when only public agents remain
  P0b-06: Post-strip verification fails when unexpected agent remains
  P0b-07: Skill with name different from agent is stripped by ownership
  P0b-08: Reviewer agent files are stripped alongside base agent
  P0b-09: Missing catalog in target directory halts stripping
  P0b-10: Multi-owner skill with all owners private is stripped
  P0b-11: Corrupted agent frontmatter halts skill stripping

Test Budget: 11 distinct behaviors x 2 = 22 max. Using 11 tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.shared.agent_catalog import CatalogNotFoundError


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATALOG_PUBLIC_PRIVATE = """\
agents:
  alpha:
    wave: DELIVER
    public: true
    description: "Alpha agent"
  beta:
    wave: DESIGN
    public: true
    description: "Beta agent"
  internal-tool:
    wave: DELIVER
    public: false
    description: "Internal only"
  secret-builder:
    wave: DELIVER
    public: false
    description: "Secret builder"
"""

CATALOG_ALPHA_ONLY = """\
agents:
  alpha:
    wave: DELIVER
    public: true
    description: "Alpha agent"
"""

AGENT_FRONTMATTER_TEMPLATE = """\
---
name: nw-{name}
skills:
{skills_yaml}
---
# Agent {name}
"""

CORRUPTED_FRONTMATTER = """\
---
name: nw-alpha
skills: [{{{{broken yaml
---
# Corrupted
"""


def _create_agent_file(
    agents_dir: Path, name: str, skills: list[str] | None = None
) -> None:
    """Create an agent file with optional skill frontmatter."""
    if skills:
        skills_yaml = "\n".join(f"  - {s}" for s in skills)
        content = AGENT_FRONTMATTER_TEMPLATE.format(name=name, skills_yaml=skills_yaml)
    else:
        content = f"---\nname: nw-{name}\n---\n# Agent {name}\n"
    (agents_dir / f"nw-{name}.md").write_text(content)


def _create_skill_dir(skills_dir: Path, name: str) -> None:
    """Create a skill directory with a SKILL.md marker."""
    skill_dir = skills_dir / f"nw-{name}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n")


def _create_target(
    tmp_path: Path,
    catalog_content: str,
    agents: dict[str, list[str] | None] | None = None,
    skills: list[str] | None = None,
) -> Path:
    """Create a full target directory with catalog, agents, and skills."""
    target = tmp_path / "target"
    nwave = target / "nWave"
    agents_dir = nwave / "agents"
    skills_dir = nwave / "skills"
    nwave.mkdir(parents=True)
    agents_dir.mkdir()
    skills_dir.mkdir()
    (nwave / "framework-catalog.yaml").write_text(catalog_content)

    if agents:
        for name, agent_skills in agents.items():
            _create_agent_file(agents_dir, name, agent_skills)

    if skills:
        for skill_name in skills:
            _create_skill_dir(skills_dir, skill_name)

    return target


# ---------------------------------------------------------------------------
# P0b-01: Stripping removes private agents using allow-list
# ---------------------------------------------------------------------------


class TestStripRemovesPrivateAgents:
    """P0b-01: Stripping removes private agents using allow-list."""

    def test_strip_removes_private_agents_using_allow_list(
        self, tmp_path: Path
    ) -> None:
        """Given public and private agents, strip removes only private ones."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": None,
                "beta": None,
                "internal-tool": None,
                "secret-builder": None,
            },
        )

        strip(target)

        agents_dir = target / "nWave" / "agents"
        remaining = {f.name for f in agents_dir.glob("nw-*.md")}
        assert "nw-alpha.md" in remaining
        assert "nw-beta.md" in remaining
        assert "nw-internal-tool.md" not in remaining
        assert "nw-secret-builder.md" not in remaining


# ---------------------------------------------------------------------------
# P0b-02: Uncatalogued agent is stripped (fail-closed)
# ---------------------------------------------------------------------------


class TestUncataloguedAgentStripped:
    """P0b-02: Uncatalogued agent is stripped as fail-closed behavior."""

    def test_uncatalogued_agent_stripped_fail_closed(self, tmp_path: Path) -> None:
        """Given uncatalogued 'nw-rogue.md', it is stripped (not in allow-list)."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_ALPHA_ONLY,
            agents={"alpha": None},
        )
        # Add rogue agent not in catalog
        agents_dir = target / "nWave" / "agents"
        (agents_dir / "nw-rogue.md").write_text("---\nname: rogue\n---\n")

        strip(target)

        remaining = {f.name for f in agents_dir.glob("nw-*.md")}
        assert "nw-alpha.md" in remaining
        assert "nw-rogue.md" not in remaining


# ---------------------------------------------------------------------------
# P0b-03: Skills owned by private agents are removed
# ---------------------------------------------------------------------------


class TestPrivateSkillsRemoved:
    """P0b-03: Skills owned by private agents are removed."""

    def test_skills_owned_by_private_agents_removed(self, tmp_path: Path) -> None:
        """Given private agent owns a skill, that skill dir is removed."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": ["nw-alpha-skill"],
                "secret-builder": ["nw-secret-builder"],
            },
            skills=["alpha-skill", "secret-builder"],
        )

        strip(target)

        skills_dir = target / "nWave" / "skills"
        assert (skills_dir / "nw-alpha-skill").exists()
        assert not (skills_dir / "nw-secret-builder").exists()


# ---------------------------------------------------------------------------
# P0b-04: Multi-owner skill kept when any owner is public
# ---------------------------------------------------------------------------


class TestMultiOwnerSkillKept:
    """P0b-04: Multi-owner skill kept when any owner is public."""

    def test_multi_owner_skill_kept_when_any_owner_public(self, tmp_path: Path) -> None:
        """Given skill owned by both public and private agent, it is kept."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": ["nw-tdd-methodology"],
                "internal-tool": ["nw-tdd-methodology"],
            },
            skills=["tdd-methodology"],
        )

        strip(target)

        skills_dir = target / "nWave" / "skills"
        assert (skills_dir / "nw-tdd-methodology").exists()


# ---------------------------------------------------------------------------
# P0b-05: Post-strip verification passes when only public agents remain
# ---------------------------------------------------------------------------


class TestVerifyStripPasses:
    """P0b-05: Post-strip verification passes when only public agents remain."""

    def test_post_strip_verification_passes(self, tmp_path: Path) -> None:
        """Given only public agents remain after strip, verification passes."""
        from scripts.release.strip_private_agents import strip, verify_strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": None,
                "beta": None,
                "internal-tool": None,
                "secret-builder": None,
            },
        )

        strip(target)
        errors = verify_strip(target)
        assert errors == []


# ---------------------------------------------------------------------------
# P0b-06: Post-strip verification fails when unexpected agent remains
# ---------------------------------------------------------------------------


class TestVerifyStripFails:
    """P0b-06: Post-strip verification fails when unexpected agent remains."""

    def test_verify_strip_fails_when_unexpected_agent_remains(
        self, tmp_path: Path
    ) -> None:
        """Given unexpected agent remains after strip, verification fails."""
        from scripts.release.strip_private_agents import verify_strip

        target = _create_target(
            tmp_path,
            CATALOG_ALPHA_ONLY,
            agents={"alpha": None},
        )
        # Simulate unexpected agent still on disk
        agents_dir = target / "nWave" / "agents"
        (agents_dir / "nw-rogue.md").write_text("---\nname: rogue\n---\n")

        errors = verify_strip(target)
        assert len(errors) > 0
        assert any("nw-rogue.md" in e for e in errors)


# ---------------------------------------------------------------------------
# P0b-07: Skill with name different from agent is stripped by ownership
# ---------------------------------------------------------------------------


class TestSkillDifferentNameStrippedByOwnership:
    """P0b-07: Skill with name different from agent stripped by ownership."""

    def test_skill_different_name_stripped_by_ownership(self, tmp_path: Path) -> None:
        """Given private agent owns skill with different name, it is stripped."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": ["nw-alpha-skill"],
                "secret-builder": ["nw-quality-framework"],
            },
            skills=["alpha-skill", "quality-framework"],
        )

        strip(target)

        skills_dir = target / "nWave" / "skills"
        assert (skills_dir / "nw-alpha-skill").exists()
        assert not (skills_dir / "nw-quality-framework").exists()


# ---------------------------------------------------------------------------
# P0b-08: Reviewer agent files are stripped alongside base agent
# ---------------------------------------------------------------------------


class TestReviewerStrippedWithBase:
    """P0b-08: Reviewer agent files are stripped alongside base agent."""

    def test_reviewer_stripped_alongside_base_agent(self, tmp_path: Path) -> None:
        """Given private agent has reviewer file, both are removed."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={"alpha": None, "internal-tool": None},
        )
        # Add reviewer file for private agent
        agents_dir = target / "nWave" / "agents"
        (agents_dir / "nw-internal-tool-reviewer.md").write_text(
            "---\nname: internal-tool-reviewer\n---\n"
        )

        strip(target)

        remaining = {f.name for f in agents_dir.glob("nw-*.md")}
        assert "nw-alpha.md" in remaining
        assert "nw-internal-tool.md" not in remaining
        assert "nw-internal-tool-reviewer.md" not in remaining


# ---------------------------------------------------------------------------
# P0b-09: Missing catalog in target directory halts stripping
# ---------------------------------------------------------------------------


class TestMissingCatalogHaltsStrip:
    """P0b-09: Missing catalog in target directory halts stripping."""

    def test_missing_catalog_halts_stripping(self, tmp_path: Path) -> None:
        """Given no framework-catalog.yaml, strip raises CatalogNotFoundError."""
        from scripts.release.strip_private_agents import strip

        target = tmp_path / "target"
        nwave = target / "nWave"
        nwave.mkdir(parents=True)
        (nwave / "agents").mkdir()

        with pytest.raises(CatalogNotFoundError):
            strip(target)


# ---------------------------------------------------------------------------
# P0b-10: Multi-owner skill with all owners private is stripped
# ---------------------------------------------------------------------------


class TestMultiOwnerAllPrivateStripped:
    """P0b-10: Multi-owner skill with all owners private is stripped."""

    def test_multi_owner_all_private_stripped(self, tmp_path: Path) -> None:
        """Given skill owned by two private agents, it is stripped."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_PUBLIC_PRIVATE,
            agents={
                "alpha": ["nw-alpha-skill"],
                "internal-tool": ["nw-internal-framework"],
                "secret-builder": ["nw-internal-framework"],
            },
            skills=["alpha-skill", "internal-framework"],
        )

        strip(target)

        skills_dir = target / "nWave" / "skills"
        assert (skills_dir / "nw-alpha-skill").exists()
        assert not (skills_dir / "nw-internal-framework").exists()


# ---------------------------------------------------------------------------
# P0b-11: Corrupted agent frontmatter halts skill stripping
# ---------------------------------------------------------------------------


class TestCorruptedFrontmatterHalts:
    """P0b-11: Corrupted agent frontmatter halts skill stripping."""

    def test_corrupted_frontmatter_halts_skill_stripping(self, tmp_path: Path) -> None:
        """Given corrupted YAML frontmatter, strip raises an error."""
        from scripts.release.strip_private_agents import strip

        target = _create_target(
            tmp_path,
            CATALOG_ALPHA_ONLY,
            agents={},
        )
        # Create agent file with corrupted frontmatter
        agents_dir = target / "nWave" / "agents"
        (agents_dir / "nw-alpha.md").write_text(CORRUPTED_FRONTMATTER)

        with pytest.raises((ValueError, TypeError, KeyError)):
            strip(target)
