"""Tests for skill audit script.

Validates that audit_skills.py correctly catalogs skill files,
detects naming collisions across agent groups, maps cross-agent
references, and produces a structured JSON report.

Acceptance criteria (US-01):
1. Script catalogs all skill files under nWave/skills/ with agent ownership
2. Script detects and reports name collisions across agent groups
3. Script maps cross-agent skill references from agent frontmatter
4. Output includes collision groups with content-hash comparison
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "nWave" / "skills"
AGENTS_DIR = PROJECT_ROOT / "nWave" / "agents"


# ---------------------------------------------------------------------------
# Acceptance: audit against real nWave source tree
# ---------------------------------------------------------------------------


class TestAuditSkillsAcceptance:
    """Acceptance: audit confirms no collisions remain after restructuring."""

    def test_no_collisions_after_restructuring(self):
        """After restructuring, all collisions are resolved via nw-{abbrev}- prefix."""
        from scripts.validation.audit_skills import audit_skills

        report = audit_skills(SKILLS_DIR, AGENTS_DIR)
        collisions = report["collisions"]

        assert len(collisions) == 0, (
            f"Expected zero collisions after restructuring, got {len(collisions)}: "
            f"{list(collisions.keys())}"
        )

    def test_collision_entries_include_content_hash(self, tmp_path):
        """Each collision entry must include a content_hash for comparison."""
        from scripts.validation.audit_skills import audit_skills

        # Use controlled fixture with a known collision (real tree has none)
        skills = tmp_path / "skills"
        for agent in ("agent-a", "agent-b"):
            d = skills / agent
            d.mkdir(parents=True)
            (d / "shared-skill.md").write_text(f"# Content for {agent}")

        agents = tmp_path / "agents"
        agents.mkdir()

        report = audit_skills(skills, agents)
        assert "shared-skill" in report["collisions"]
        for entry in report["collisions"]["shared-skill"]:
            assert "content_hash" in entry, (
                f"Collision entry missing content_hash: {entry}"
            )


# ---------------------------------------------------------------------------
# Unit tests: audit functions through public API (driving port)
# ---------------------------------------------------------------------------


def _make_skill_file(
    skills_dir: Path, group: str, name: str, content: str = ""
) -> Path:
    """Helper: create a skill .md file under skills_dir/group/name.md."""
    group_dir = skills_dir / group
    group_dir.mkdir(parents=True, exist_ok=True)
    filepath = group_dir / f"{name}.md"
    if not content:
        content = f"---\nname: {name}\n---\n\n# {name}\n\nSkill content for {group}.\n"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _make_agent_file(agents_dir: Path, agent_name: str, skills: list[str]) -> Path:
    """Helper: create an agent .md file with skills frontmatter."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_yaml = "\n".join(f"  - {s}" for s in skills)
    content = (
        f"---\nname: {agent_name}\ndescription: Test agent\n"
        f"model: inherit\nskills:\n{skills_yaml}\n---\n\n# {agent_name}\n"
    )
    filepath = agents_dir / f"{agent_name}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


class TestCatalogSkills:
    """Unit: catalog_skills returns all skill files with agent ownership."""

    def test_catalogs_skills_with_agent_group(self, tmp_path):
        """Each cataloged skill must include skill_name and agent_group."""
        from scripts.validation.audit_skills import catalog_skills

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "software-crafter", "tdd-methodology")
        _make_skill_file(skills_dir, "product-owner", "user-stories")

        result = catalog_skills(skills_dir)

        assert len(result) == 2
        names = {s["skill_name"] for s in result}
        assert names == {"tdd-methodology", "user-stories"}
        groups = {s["agent_group"] for s in result}
        assert groups == {"software-crafter", "product-owner"}

    def test_catalogs_skill_file_path(self, tmp_path):
        """Each cataloged skill must include the file_path."""
        from scripts.validation.audit_skills import catalog_skills

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "researcher", "deep-search")

        result = catalog_skills(skills_dir)

        assert len(result) == 1
        assert "file_path" in result[0]
        assert result[0]["file_path"].endswith("deep-search.md")

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """An empty skills directory should return an empty catalog."""
        from scripts.validation.audit_skills import catalog_skills

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        result = catalog_skills(skills_dir)
        assert result == []


class TestDetectCollisions:
    """Unit: detect_collisions identifies skill names shared across groups."""

    def test_detects_collision_across_two_groups(self, tmp_path):
        """Same skill name in two groups must be detected as collision."""
        from scripts.validation.audit_skills import catalog_skills, detect_collisions

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "group-a", "shared-skill", "Content A")
        _make_skill_file(skills_dir, "group-b", "shared-skill", "Content B")

        catalog = catalog_skills(skills_dir)
        collisions = detect_collisions(catalog)

        assert "shared-skill" in collisions
        assert len(collisions["shared-skill"]) == 2

    def test_no_collision_for_unique_names(self, tmp_path):
        """Skills with unique names across groups produce no collisions."""
        from scripts.validation.audit_skills import catalog_skills, detect_collisions

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "group-a", "unique-a")
        _make_skill_file(skills_dir, "group-b", "unique-b")

        catalog = catalog_skills(skills_dir)
        collisions = detect_collisions(catalog)

        assert len(collisions) == 0

    def test_collision_entries_contain_agent_group_and_hash(self, tmp_path):
        """Each collision entry must have agent_group and content_hash."""
        from scripts.validation.audit_skills import catalog_skills, detect_collisions

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "alpha", "review", "Alpha content")
        _make_skill_file(skills_dir, "beta", "review", "Beta content")

        catalog = catalog_skills(skills_dir)
        collisions = detect_collisions(catalog)

        for entry in collisions["review"]:
            assert "agent_group" in entry
            assert "content_hash" in entry

    def test_different_content_produces_different_hashes(self, tmp_path):
        """Colliding skills with different content must have different hashes."""
        from scripts.validation.audit_skills import catalog_skills, detect_collisions

        skills_dir = tmp_path / "skills"
        _make_skill_file(skills_dir, "alpha", "review", "Content version A")
        _make_skill_file(skills_dir, "beta", "review", "Content version B")

        catalog = catalog_skills(skills_dir)
        collisions = detect_collisions(catalog)

        hashes = {e["content_hash"] for e in collisions["review"]}
        assert len(hashes) == 2, "Different content should produce different hashes"


class TestMapCrossReferences:
    """Unit: map_cross_references identifies skills referenced from other groups."""

    def test_detects_cross_agent_reference(self, tmp_path):
        """Agent referencing a skill from another group's directory is a cross-ref."""
        from scripts.validation.audit_skills import catalog_skills, map_cross_references

        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"

        # software-crafter owns tdd-methodology
        _make_skill_file(skills_dir, "software-crafter", "tdd-methodology")
        # functional-software-crafter references it but has no such skill in own dir
        _make_skill_file(skills_dir, "functional-software-crafter", "fp-principles")
        _make_agent_file(
            agents_dir,
            "nw-functional-software-crafter",
            ["tdd-methodology", "fp-principles"],
        )
        _make_agent_file(agents_dir, "nw-software-crafter", ["tdd-methodology"])

        catalog = catalog_skills(skills_dir)
        cross_refs = map_cross_references(catalog, agents_dir)

        # functional-software-crafter references tdd-methodology from software-crafter
        matching = [
            r
            for r in cross_refs
            if r["agent"] == "nw-functional-software-crafter"
            and r["skill"] == "tdd-methodology"
        ]
        assert len(matching) == 1
        assert matching[0]["owner_group"] == "software-crafter"

    def test_no_cross_reference_for_own_skills(self, tmp_path):
        """Agent referencing skills from its own group is not a cross-reference."""
        from scripts.validation.audit_skills import catalog_skills, map_cross_references

        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"

        _make_skill_file(skills_dir, "software-crafter", "tdd-methodology")
        _make_agent_file(agents_dir, "nw-software-crafter", ["tdd-methodology"])

        catalog = catalog_skills(skills_dir)
        cross_refs = map_cross_references(catalog, agents_dir)

        assert len(cross_refs) == 0


class TestDetectOrphans:
    """Unit: detect_orphans identifies skills not referenced by any agent."""

    def test_unreferenced_skill_is_orphan(self, tmp_path):
        """Skill not listed in any agent's frontmatter is an orphan."""
        from scripts.validation.audit_skills import catalog_skills, detect_orphans

        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"

        _make_skill_file(skills_dir, "group-a", "used-skill")
        _make_skill_file(skills_dir, "group-a", "orphan-skill")
        _make_agent_file(agents_dir, "nw-group-a", ["used-skill"])

        catalog = catalog_skills(skills_dir)
        orphans = detect_orphans(catalog, agents_dir)

        orphan_names = [o["skill_name"] for o in orphans]
        assert "orphan-skill" in orphan_names

    def test_referenced_skill_is_not_orphan(self, tmp_path):
        """Skill listed in an agent's frontmatter is not an orphan."""
        from scripts.validation.audit_skills import catalog_skills, detect_orphans

        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"

        _make_skill_file(skills_dir, "group-a", "my-skill")
        _make_agent_file(agents_dir, "nw-group-a", ["my-skill"])

        catalog = catalog_skills(skills_dir)
        orphans = detect_orphans(catalog, agents_dir)

        orphan_names = [o["skill_name"] for o in orphans]
        assert "my-skill" not in orphan_names
