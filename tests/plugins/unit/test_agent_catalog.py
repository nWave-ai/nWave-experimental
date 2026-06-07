"""Unit tests for the shared agent_catalog module.

Tests the public/private agent filtering logic that prevents
private agents and skills from leaking into public installations.
"""

from pathlib import Path

import pytest

from scripts.shared.agent_catalog import (
    build_ownership_map,
    is_public_agent,
    is_public_skill,
    load_public_agents,
)


# ---------------------------------------------------------------------------
# Real catalog path for integration-style unit tests
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"


class TestLoadPublicAgents:
    """Tests for load_public_agents using the real framework-catalog.yaml."""

    def test_returns_nonempty_set_from_real_catalog(self):
        result = load_public_agents(NWAVE_DIR)
        assert len(result) > 0, "Should load at least one public agent"

    def test_excludes_known_private_agents(self):
        result = load_public_agents(NWAVE_DIR)
        private_agents = {
            "workshopper",
            "workshopper-reviewer",
            "tutorialist",
            "tutorialist-reviewer",
            "business-discoverer",
            "business-reviewer",
            "deal-closer",
            "outreach-writer",
            "ux-designer",
        }
        leaked = private_agents & result
        assert leaked == set(), f"Private agents leaked into public set: {leaked}"

    def test_includes_known_public_agents(self):
        result = load_public_agents(NWAVE_DIR)
        expected_public = {
            "software-crafter",
            "product-owner",
            "solution-architect",
            "researcher",
            "platform-architect",
        }
        missing = expected_public - result
        assert missing == set(), f"Expected public agents missing: {missing}"

    def test_returns_empty_set_when_catalog_missing(self, tmp_path):
        result = load_public_agents(tmp_path, strict=False)
        assert result == set()

    def test_returns_empty_set_when_yaml_invalid(self, tmp_path):
        catalog = tmp_path / "framework-catalog.yaml"
        catalog.write_text("{{invalid yaml: [")
        result = load_public_agents(tmp_path, strict=False)
        assert result == set()


class TestIsPublicAgent:
    """Tests for is_public_agent file-name matching."""

    @pytest.mark.parametrize(
        "filename",
        [
            "nw-software-crafter.md",
            "nw-product-owner.md",
            "nw-researcher.md",
        ],
    )
    def test_public_agent_returns_true(self, filename):
        public_agents = {"software-crafter", "product-owner", "researcher"}
        assert is_public_agent(filename, public_agents) is True

    @pytest.mark.parametrize(
        "filename",
        [
            "nw-workshopper.md",
            "nw-business-discoverer.md",
            "nw-deal-closer.md",
            "nw-ux-designer.md",
        ],
    )
    def test_private_agent_returns_false(self, filename):
        public_agents = {"software-crafter", "product-owner"}
        assert is_public_agent(filename, public_agents) is False

    def test_reviewer_explicitly_in_catalog_returns_true(self):
        public_agents = {"software-crafter", "software-crafter-reviewer"}
        assert is_public_agent("nw-software-crafter-reviewer.md", public_agents) is True

    def test_reviewer_not_in_catalog_returns_false(self):
        """Reviewer must be explicitly listed — no inheritance from base agent."""
        public_agents = {"software-crafter"}
        assert (
            is_public_agent("nw-software-crafter-reviewer.md", public_agents) is False
        )

    def test_reviewer_of_private_agent_returns_false(self):
        public_agents = {"software-crafter"}
        assert is_public_agent("nw-workshopper-reviewer.md", public_agents) is False

    def test_empty_public_agents_returns_true_for_all(self):
        assert is_public_agent("nw-workshopper.md", set()) is True
        assert is_public_agent("nw-software-crafter.md", set()) is True


class TestIsPublicSkill:
    """Tests for is_public_skill directory-name matching."""

    @pytest.mark.parametrize(
        "dirname",
        [
            "software-crafter",
            "product-owner",
            "researcher",
        ],
    )
    def test_public_skill_returns_true(self, dirname):
        public_agents = {"software-crafter", "product-owner", "researcher"}
        assert is_public_skill(dirname, public_agents) is True

    @pytest.mark.parametrize(
        "dirname",
        [
            "workshopper",
            "business-discoverer",
            "deal-closer",
        ],
    )
    def test_private_skill_returns_false(self, dirname):
        public_agents = {"software-crafter", "product-owner"}
        assert is_public_skill(dirname, public_agents) is False

    def test_common_always_public(self):
        public_agents = {"software-crafter"}
        assert is_public_skill("common", public_agents) is True

    def test_common_public_even_with_nonempty_set(self):
        # "common" should be public regardless of what's in the set
        public_agents = {"only-one-agent"}
        assert is_public_skill("common", public_agents) is True

    def test_nw_canary_always_public(self):
        # nw-canary is infrastructure (ADR-006) — always public
        public_agents = {"only-one-agent"}
        assert is_public_skill("nw-canary", public_agents) is True

    def test_reviewer_skill_explicitly_in_catalog(self):
        public_agents = {"software-crafter", "software-crafter-reviewer"}
        assert is_public_skill("software-crafter-reviewer", public_agents) is True

    def test_reviewer_skill_not_in_catalog_returns_false(self):
        """Reviewer skill must be explicitly listed — no inheritance from base agent."""
        public_agents = {"software-crafter"}
        assert is_public_skill("software-crafter-reviewer", public_agents) is False

    def test_reviewer_of_private_skill_returns_false(self):
        public_agents = {"software-crafter"}
        assert is_public_skill("workshopper-reviewer", public_agents) is False

    def test_empty_public_agents_returns_true_for_all(self):
        assert is_public_skill("workshopper", set()) is True
        assert is_public_skill("software-crafter", set()) is True


class TestBuildOwnershipMapUnit:
    """Unit tests for build_ownership_map with controlled fixtures."""

    def _create_agent_file(self, agents_dir: Path, name: str, skills: list[str]):
        """Helper: create a minimal agent .md file with YAML frontmatter."""
        skills_yaml = "\n".join(f"  - {s}" for s in skills)
        content = (
            f"---\nname: {name}\nskills:\n{skills_yaml}\n---\n\n"
            f"# {name}\n\nAgent content.\n"
        )
        (agents_dir / f"{name}.md").write_text(content, encoding="utf-8")

    def test_parses_skills_from_single_agent(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        self._create_agent_file(
            agents_dir,
            "nw-software-crafter",
            ["nw-tdd-methodology", "nw-quality-framework"],
        )
        result = build_ownership_map(agents_dir)
        assert "nw-tdd-methodology" in result
        assert "nw-quality-framework" in result
        assert "software-crafter" in result["nw-tdd-methodology"]

    def test_shared_skill_maps_to_multiple_agents(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        self._create_agent_file(
            agents_dir, "nw-software-crafter", ["nw-collaboration-and-handoffs"]
        )
        self._create_agent_file(
            agents_dir, "nw-product-owner", ["nw-collaboration-and-handoffs"]
        )
        result = build_ownership_map(agents_dir)
        assert result["nw-collaboration-and-handoffs"] == {
            "software-crafter",
            "product-owner",
        }

    def test_returns_empty_dict_for_missing_directory(self, tmp_path):
        result = build_ownership_map(tmp_path / "nonexistent")
        assert result == {}

    def test_skips_agent_without_skills_key(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Agent without skills frontmatter
        (agents_dir / "nw-broken.md").write_text(
            "---\nname: nw-broken\n---\n\n# Broken\n",
            encoding="utf-8",
        )
        self._create_agent_file(agents_dir, "nw-good", ["nw-skill-a"])
        result = build_ownership_map(agents_dir)
        assert "nw-skill-a" in result
        assert len(result) == 1

    def test_derives_agent_name_from_filename(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        self._create_agent_file(agents_dir, "nw-my-agent", ["nw-my-skill"])
        result = build_ownership_map(agents_dir)
        assert result["nw-my-skill"] == {"my-agent"}


class TestIsPublicSkillWithOwnershipMap:
    """Unit tests for is_public_skill with the ownership_map parameter."""

    @pytest.mark.parametrize(
        "skill_name,expected",
        [
            ("nw-tdd-methodology", True),  # owned by public agent
            ("nw-private-skill", False),  # owned by private agent
        ],
    )
    def test_filters_by_owning_agent_publicity(self, skill_name, expected):
        public_agents = {"software-crafter"}
        ownership_map = {
            "nw-tdd-methodology": {"software-crafter"},
            "nw-private-skill": {"workshopper"},
        }
        assert is_public_skill(skill_name, public_agents, ownership_map) is expected

    def test_shared_skill_public_if_any_owner_public(self):
        public_agents = {"software-crafter"}
        ownership_map = {
            "nw-shared-skill": {"software-crafter", "workshopper"},
        }
        assert is_public_skill("nw-shared-skill", public_agents, ownership_map) is True

    def test_falls_back_to_old_heuristic_when_no_map(self):
        public_agents = {"software-crafter"}
        # Without ownership_map, old behavior should work
        assert is_public_skill("software-crafter", public_agents) is True
        assert is_public_skill("workshopper", public_agents) is False

    def test_skill_not_in_map_falls_back_to_heuristic(self):
        public_agents = {"software-crafter"}
        ownership_map = {"nw-known-skill": {"software-crafter"}}
        # Skill not in map -- falls back to old heuristic
        assert is_public_skill("software-crafter", public_agents, ownership_map) is True


class TestBuildOwnershipMap:
    """Acceptance tests for build_ownership_map using real agent files.

    Scenario: Ownership map built correctly from agent frontmatter
    Given all agent definitions have skills listed in frontmatter
    When the skill-to-agent ownership map is built
    Then every skill has at least one owning agent
    And the map correctly identifies multi-agent ownership
    """

    AGENTS_DIR = NWAVE_DIR / "agents"

    def test_builds_nonempty_map_from_real_agents(self):
        result = build_ownership_map(self.AGENTS_DIR)
        assert len(result) > 0, "Ownership map should not be empty"

    def test_every_mapped_skill_has_owning_agents(self):
        result = build_ownership_map(self.AGENTS_DIR)
        for skill_name, agents in result.items():
            assert len(agents) > 0, f"Skill {skill_name} has no owning agents"

    def test_known_public_skill_maps_to_correct_agent(self):
        result = build_ownership_map(self.AGENTS_DIR)
        # nw-tdd-methodology is owned by software-crafter
        assert "nw-tdd-methodology" in result
        assert "software-crafter" in result["nw-tdd-methodology"]

    def test_detects_multi_agent_ownership(self):
        result = build_ownership_map(self.AGENTS_DIR)
        multi_owned = {
            skill: agents for skill, agents in result.items() if len(agents) > 1
        }
        assert len(multi_owned) > 0, (
            "Expected at least one skill shared across multiple agents"
        )

    def test_is_public_skill_uses_ownership_map(self):
        """End-to-end: build map, load public agents, filter skill."""
        ownership_map = build_ownership_map(self.AGENTS_DIR)
        public_agents = load_public_agents(NWAVE_DIR)
        # nw-tdd-methodology is owned by software-crafter (public)
        assert (
            is_public_skill("nw-tdd-methodology", public_agents, ownership_map) is True
        )

    def test_private_skill_excluded_via_ownership_map(self):
        """End-to-end: private agent skill filtered out."""
        ownership_map = build_ownership_map(self.AGENTS_DIR)
        public_agents = load_public_agents(NWAVE_DIR)
        # Find a skill owned only by a private agent
        private_agents = {
            "workshopper",
            "workshopper-reviewer",
            "tutorialist",
            "tutorialist-reviewer",
            "business-discoverer",
            "business-reviewer",
            "deal-closer",
            "outreach-writer",
            "ux-designer",
        }
        private_only_skills = [
            skill
            for skill, agents in ownership_map.items()
            if all(a in private_agents for a in agents)
        ]
        assert len(private_only_skills) > 0, "Should have private-only skills"
        for skill in private_only_skills:
            assert is_public_skill(skill, public_agents, ownership_map) is False, (
                f"Private-only skill {skill} should be excluded"
            )
