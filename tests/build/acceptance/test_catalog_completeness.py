"""Acceptance tests for catalog completeness validation.

Scenarios covered (step 01-03):
  P0c-01: Uncatalogued agent fails validation
  P0c-02: All agents catalogued passes validation
  P0c-03: Reviewer agent with catalogued base passes validation
  P0c-04: Reviewer agent without catalogued base fails validation
  P0c-05: Catalog entry missing explicit public field fails validation
  P0c-06: Multiple uncatalogued agents listed in error message

Test Budget: 6 distinct behaviors x 2 = 12 max. Using 6 tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.shared.agent_catalog import is_agent_on_disk_catalogued
from scripts.validation.validate_catalog_completeness import main


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATALOG_WITH_ALL = """\
agents:
  alpha:
    wave: DELIVER
    public: true
  beta:
    wave: DESIGN
    public: true
"""

CATALOG_ALPHA_ONLY = """\
agents:
  alpha:
    wave: DELIVER
    public: true
"""

CATALOG_FOO = """\
agents:
  foo:
    wave: DELIVER
    public: true
"""

CATALOG_MISSING_PUBLIC = """\
agents:
  baz:
    wave: DELIVER
    description: "Missing public field"
"""


@pytest.fixture()
def nwave_dir(tmp_path: Path) -> Path:
    """Create a temp nWave dir structure."""
    nwave = tmp_path / "nWave"
    nwave.mkdir()
    (nwave / "agents").mkdir()
    return nwave


# ---------------------------------------------------------------------------
# P0c-01: Uncatalogued agent fails validation
# ---------------------------------------------------------------------------


class TestUncataloguedAgentFails:
    """P0c-01: Uncatalogued agent fails validation."""

    def test_uncatalogued_agent_fails_validation(self, nwave_dir: Path) -> None:
        """Given agent 'nw-uncatalogued.md' not in catalog, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-uncatalogued.md").write_text("---\nname: uncatalogued\n---\n")

        result = main(nwave_dir)
        assert result == 1

        # Also verify via is_agent_on_disk_catalogued
        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-uncatalogued.md" in uncatalogued


# ---------------------------------------------------------------------------
# P0c-02: All agents catalogued passes validation
# ---------------------------------------------------------------------------


class TestAllCataloguedPasses:
    """P0c-02: All agents catalogued passes validation."""

    def test_all_agents_catalogued_passes_validation(self, nwave_dir: Path) -> None:
        """Given every agent file has a catalog entry with public field, validation passes."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_WITH_ALL)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-beta.md").write_text("---\nname: beta\n---\n")

        result = main(nwave_dir)
        assert result == 0


# ---------------------------------------------------------------------------
# P0c-03: Reviewer agent with catalogued base passes validation
# ---------------------------------------------------------------------------


class TestReviewerWithBasePasses:
    """P0c-03: Reviewer agent with catalogued base passes validation."""

    def test_reviewer_with_catalogued_base_passes(self, nwave_dir: Path) -> None:
        """Given 'nw-foo-reviewer.md' and 'foo' in catalog, validation passes."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_FOO)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-foo.md").write_text("---\nname: foo\n---\n")
        (agents_dir / "nw-foo-reviewer.md").write_text("---\nname: foo-reviewer\n---\n")

        result = main(nwave_dir)
        assert result == 0

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert not any("foo-reviewer" in u for u in uncatalogued)


# ---------------------------------------------------------------------------
# P0c-04: Reviewer agent without catalogued base fails validation
# ---------------------------------------------------------------------------


class TestReviewerWithoutBaseFails:
    """P0c-04: Reviewer agent without catalogued base fails validation."""

    def test_reviewer_without_catalogued_base_fails(self, nwave_dir: Path) -> None:
        """Given 'nw-bar-reviewer.md' and 'bar' NOT in catalog, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-bar-reviewer.md").write_text("---\nname: bar-reviewer\n---\n")

        result = main(nwave_dir)
        assert result == 1

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-bar-reviewer.md" in uncatalogued


# ---------------------------------------------------------------------------
# P0c-05: Catalog entry missing explicit public field fails validation
# ---------------------------------------------------------------------------


class TestMissingPublicFieldFails:
    """P0c-05: Catalog entry missing explicit public field fails validation."""

    def test_missing_public_field_fails_validation(self, nwave_dir: Path) -> None:
        """Given agent 'baz' registered without explicit public field, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_MISSING_PUBLIC)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-baz.md").write_text("---\nname: baz\n---\n")

        result = main(nwave_dir)
        assert result == 1

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert any("missing public field" in u for u in uncatalogued)


# ---------------------------------------------------------------------------
# P0c-06: Multiple uncatalogued agents listed in error message
# ---------------------------------------------------------------------------


class TestMultipleUncataloguedListed:
    """P0c-06: Multiple uncatalogued agents listed in error message."""

    def test_multiple_uncatalogued_agents_listed(self, nwave_dir: Path) -> None:
        """Given two uncatalogued agents, both are listed in error output."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-rogue-one.md").write_text("---\nname: rogue-one\n---\n")
        (agents_dir / "nw-rogue-two.md").write_text("---\nname: rogue-two\n---\n")

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-rogue-one.md" in uncatalogued
        assert "nw-rogue-two.md" in uncatalogued

        result = main(nwave_dir)
        assert result == 1
