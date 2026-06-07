"""Tests for shared skill_distribution module.

Drives the public API of scripts.shared.skill_distribution through
its function interfaces (pure utility module -- no ports/adapters).

Test Budget: 8 behaviors x 2 = 16 max unit tests (clean_existing is distinct behavior)
"""

from pathlib import Path

import pytest

from scripts.shared.skill_distribution import (
    SourceLayout,
    cleanup_legacy_namespace,
    copy_skills_to_target,
    detect_layout,
    enumerate_skills,
    filter_public_skills,
    read_manifest,
    write_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_source(tmp_path: Path) -> Path:
    """Source directory with NEW_FLAT layout: nw-*/SKILL.md."""
    source = tmp_path / "skills"
    source.mkdir()
    for name in ("nw-tdd-methodology", "nw-hexagonal-testing", "nw-quality-framework"):
        d = source / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {name}\nContent.\n", encoding="utf-8")
    return source


@pytest.fixture
def hierarchical_source(tmp_path: Path) -> Path:
    """Source directory with OLD_HIERARCHICAL layout: {agent}/*.md."""
    source = tmp_path / "skills"
    source.mkdir()
    crafter = source / "software-crafter"
    crafter.mkdir()
    (crafter / "tdd-methodology.md").write_text("# TDD\n", encoding="utf-8")
    (crafter / "hexagonal-testing.md").write_text("# Hex\n", encoding="utf-8")
    architect = source / "solution-architect"
    architect.mkdir()
    (architect / "architecture-patterns.md").write_text("# Arch\n", encoding="utf-8")
    return source


# ---------------------------------------------------------------------------
# Acceptance: Full pipeline enumerate -> filter -> copy
# ---------------------------------------------------------------------------


class TestSkillDistributionPipeline:
    """Full pipeline: enumerate, filter, copy produces correct skills at target."""

    def test_full_pipeline_enumerates_filters_and_copies_flat_skills(
        self, flat_source: Path, tmp_path: Path
    ) -> None:
        """Given flat source with 3 skills, 1 private, pipeline copies only 2 public."""
        # Add a private skill
        private = flat_source / "nw-private-skill"
        private.mkdir()
        (private / "SKILL.md").write_text("# Private\n", encoding="utf-8")

        # public_agents and ownership_map: nw-private-skill owned by "private-agent"
        public_agents = {"software-crafter", "solution-architect"}
        ownership_map = {
            "nw-tdd-methodology": {"software-crafter"},
            "nw-hexagonal-testing": {"software-crafter"},
            "nw-quality-framework": {"software-crafter"},
            "nw-private-skill": {"private-agent"},
        }

        entries = enumerate_skills(flat_source)
        filtered = filter_public_skills(entries, public_agents, ownership_map)
        target = tmp_path / "target"
        target.mkdir()
        count = copy_skills_to_target(filtered, target)

        assert count == 3
        assert (target / "nw-tdd-methodology" / "SKILL.md").exists()
        assert (target / "nw-hexagonal-testing" / "SKILL.md").exists()
        assert (target / "nw-quality-framework" / "SKILL.md").exists()
        assert not (target / "nw-private-skill").exists()


# ---------------------------------------------------------------------------
# detect_layout
# ---------------------------------------------------------------------------


class TestDetectLayout:
    """detect_layout identifies source directory structure."""

    def test_detects_new_flat_layout(self, flat_source: Path) -> None:
        assert detect_layout(flat_source) == SourceLayout.NEW_FLAT

    def test_detects_old_hierarchical_layout(self, hierarchical_source: Path) -> None:
        assert detect_layout(hierarchical_source) == SourceLayout.OLD_HIERARCHICAL


# ---------------------------------------------------------------------------
# enumerate_skills
# ---------------------------------------------------------------------------


class TestEnumerateSkills:
    """enumerate_skills discovers skill entries from source directory."""

    def test_enumerates_flat_layout_returns_skill_entries(
        self, flat_source: Path
    ) -> None:
        entries = enumerate_skills(flat_source)

        assert len(entries) == 3
        names = {e.name for e in entries}
        assert names == {
            "nw-tdd-methodology",
            "nw-hexagonal-testing",
            "nw-quality-framework",
        }
        # Each entry's path should be the nw-* directory
        for entry in entries:
            assert entry.source_path.is_dir()
            assert (entry.source_path / "SKILL.md").exists()

    def test_enumerates_hierarchical_layout_returns_skill_entries(
        self, hierarchical_source: Path
    ) -> None:
        entries = enumerate_skills(hierarchical_source)

        assert len(entries) == 3
        names = {e.name for e in entries}
        assert names == {
            "tdd-methodology",
            "hexagonal-testing",
            "architecture-patterns",
        }

    def test_returns_sorted_entries(self, flat_source: Path) -> None:
        entries = enumerate_skills(flat_source)
        names = [e.name for e in entries]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# filter_public_skills
# ---------------------------------------------------------------------------


class TestFilterPublicSkills:
    """filter_public_skills removes private skills via ownership_map."""

    def test_filters_private_skills_using_ownership_map(
        self, flat_source: Path
    ) -> None:
        # Add a skill owned by a private agent
        private = flat_source / "nw-secret-internal"
        private.mkdir()
        (private / "SKILL.md").write_text("# Secret\n", encoding="utf-8")

        entries = enumerate_skills(flat_source)
        public_agents = {"software-crafter"}
        ownership_map = {
            "nw-tdd-methodology": {"software-crafter"},
            "nw-hexagonal-testing": {"software-crafter"},
            "nw-quality-framework": {"software-crafter"},
            "nw-secret-internal": {"private-agent"},
        }

        filtered = filter_public_skills(entries, public_agents, ownership_map)

        filtered_names = {e.name for e in filtered}
        assert "nw-secret-internal" not in filtered_names
        assert len(filtered) == 3

    def test_empty_public_agents_returns_all(self, flat_source: Path) -> None:
        """Backward compatibility: empty public_agents = include everything."""
        entries = enumerate_skills(flat_source)
        filtered = filter_public_skills(entries, set(), {})
        assert len(filtered) == len(entries)


# ---------------------------------------------------------------------------
# copy_skills_to_target
# ---------------------------------------------------------------------------


class TestCopySkillsToTarget:
    """copy_skills_to_target copies SkillEntry directories to target."""

    def test_copies_skill_directories_to_target(
        self, flat_source: Path, tmp_path: Path
    ) -> None:
        entries = enumerate_skills(flat_source)
        target = tmp_path / "target"
        target.mkdir()

        count = copy_skills_to_target(entries, target)

        assert count == 3
        for entry in entries:
            target_skill = target / entry.name
            assert target_skill.is_dir()
            assert (target_skill / "SKILL.md").exists()

    def test_returns_zero_for_empty_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        count = copy_skills_to_target([], target)
        assert count == 0

    def test_clean_existing_removes_stale_nw_dirs_before_copy(
        self, flat_source: Path, tmp_path: Path
    ) -> None:
        """clean_existing=True removes stale nw-* dirs, preserves non-nw dirs."""
        target = tmp_path / "target"
        target.mkdir()

        # Pre-populate target with a stale nw-* dir and a user dir
        stale = target / "nw-old-removed-skill"
        stale.mkdir()
        (stale / "SKILL.md").write_text("stale", encoding="utf-8")
        user_dir = target / "my-custom-skill"
        user_dir.mkdir()
        (user_dir / "notes.md").write_text("keep me", encoding="utf-8")

        entries = enumerate_skills(flat_source)
        count = copy_skills_to_target(entries, target, clean_existing=True)

        assert count == 3
        # Stale nw-* dir should be gone
        assert not stale.exists()
        # User dir preserved
        assert user_dir.exists()
        assert (user_dir / "notes.md").exists()
        # New skills copied
        assert (target / "nw-tdd-methodology" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# cleanup_legacy_namespace
# ---------------------------------------------------------------------------


class TestCleanupLegacyNamespace:
    """cleanup_legacy_namespace removes old skills/nw/ directory."""

    def test_removes_nw_subdirectory(self, tmp_path: Path) -> None:
        nw_dir = tmp_path / "nw"
        nw_dir.mkdir()
        (nw_dir / "old-skill.md").write_text("old", encoding="utf-8")

        result = cleanup_legacy_namespace(tmp_path)

        assert result is True
        assert not nw_dir.exists()

    def test_returns_false_when_no_nw_directory(self, tmp_path: Path) -> None:
        result = cleanup_legacy_namespace(tmp_path)
        assert result is False


# ---------------------------------------------------------------------------
# Manifest roundtrip
# ---------------------------------------------------------------------------


class TestManifest:
    """write_manifest and read_manifest handle .nwave-manifest.json."""

    def test_manifest_roundtrip(self, tmp_path: Path) -> None:
        skill_names = ["nw-tdd-methodology", "nw-hexagonal-testing"]

        write_manifest(tmp_path, skill_names)
        manifest = read_manifest(tmp_path)

        assert manifest is not None
        assert manifest["installed_skills"] == sorted(skill_names)
        assert manifest["version"] == "1.0"

    def test_read_manifest_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert read_manifest(tmp_path) is None
