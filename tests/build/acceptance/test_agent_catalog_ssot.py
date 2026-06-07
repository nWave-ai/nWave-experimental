"""Acceptance tests for agent_catalog.py SSOT enhancements.

Scenarios covered (step 01-01):
  WS-2:   Missing catalog blocks the build (strict=True raises CatalogNotFoundError)
  P0a-01: Catalog lookup returns only public agents
  P0a-02: Catalog lookup raises when catalog file is missing (strict=True)
  P0a-03: Catalog lookup returns empty set in lenient mode (strict=False)
  P0a-04: Private agents are the complement of public agents
  P0a-09: Catalog lookup raises on corrupted catalog (CatalogParseError)
  P0a-04/09: Full catalog returns all registered agents

Scenarios covered (step 01-02):
  P0a-05: Agent name normalized from filename with prefix and suffix
  P0a-06: Reviewer suffix stripped to find base agent
  P0a-07: Normalize bare name is idempotent
  P0a-08: Base non-reviewer name is no-op
  P0a-11: End-to-end normalize then base for reviewer filename

Test Budget: 8 distinct behaviors x 2 = 16 max. Using 10 tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.shared.agent_catalog import (
    CatalogNotFoundError,
    CatalogParseError,
    base_agent_name,
    load_all_agents,
    load_private_agents,
    load_public_agents,
    normalize_agent_name,
)


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CATALOG = """\
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

CORRUPTED_CATALOG = """\
agents:
  alpha:
    public: true
  - this is invalid yaml: [
    broken: {unclosed
"""


@pytest.fixture()
def catalog_dir(tmp_path: Path) -> Path:
    """Create a temp nWave dir with a valid framework-catalog.yaml."""
    nwave_dir = tmp_path / "nWave"
    nwave_dir.mkdir()
    (nwave_dir / "framework-catalog.yaml").write_text(SAMPLE_CATALOG)
    return nwave_dir


@pytest.fixture()
def empty_dir(tmp_path: Path) -> Path:
    """Create a temp nWave dir with NO catalog file."""
    nwave_dir = tmp_path / "nWave"
    nwave_dir.mkdir()
    return nwave_dir


@pytest.fixture()
def corrupted_dir(tmp_path: Path) -> Path:
    """Create a temp nWave dir with a corrupted catalog file."""
    nwave_dir = tmp_path / "nWave"
    nwave_dir.mkdir()
    (nwave_dir / "framework-catalog.yaml").write_text(CORRUPTED_CATALOG)
    return nwave_dir


# ---------------------------------------------------------------------------
# WS-2 + P0a-02: Missing catalog raises CatalogNotFoundError (strict=True)
# ---------------------------------------------------------------------------


class TestMissingCatalogStrictMode:
    """WS-2 + P0a-02: Missing catalog blocks the build."""

    def test_missing_catalog_raises_catalog_not_found_error(
        self, empty_dir: Path
    ) -> None:
        """Given no framework-catalog.yaml, strict=True raises CatalogNotFoundError."""
        with pytest.raises(CatalogNotFoundError) as exc_info:
            load_public_agents(empty_dir, strict=True)

        # Error must identify the expected catalog path
        expected_path = str(empty_dir / "framework-catalog.yaml")
        assert expected_path in str(exc_info.value)


# ---------------------------------------------------------------------------
# P0a-03: Lenient mode returns empty set
# ---------------------------------------------------------------------------


class TestMissingCatalogLenientMode:
    """P0a-03: Lenient mode returns empty set on missing catalog."""

    def test_missing_catalog_returns_empty_set_in_lenient_mode(
        self, empty_dir: Path
    ) -> None:
        """Given no framework-catalog.yaml, strict=False returns empty set."""
        result = load_public_agents(empty_dir, strict=False)
        assert result == set()


# ---------------------------------------------------------------------------
# P0a-01: load_public_agents returns only agents with public != False
# ---------------------------------------------------------------------------


class TestLoadPublicAgents:
    """P0a-01: Catalog lookup returns only public agents."""

    def test_returns_only_public_agents(self, catalog_dir: Path) -> None:
        """Given catalog with public and private agents, returns only public."""
        result = load_public_agents(catalog_dir)
        assert result == {"alpha", "beta"}
        assert "internal-tool" not in result
        assert "secret-builder" not in result


# ---------------------------------------------------------------------------
# P0a-04: load_private_agents returns agents with public: false
# ---------------------------------------------------------------------------


class TestLoadPrivateAgents:
    """P0a-04: Private agents are the complement of public agents."""

    def test_returns_private_agents(self, catalog_dir: Path) -> None:
        """Given catalog with public and private agents, returns only private."""
        result = load_private_agents(catalog_dir)
        assert result == {"internal-tool", "secret-builder"}
        assert "alpha" not in result
        assert "beta" not in result


# ---------------------------------------------------------------------------
# P0a-09: load_all_agents returns full catalog dict
# ---------------------------------------------------------------------------


class TestLoadAllAgents:
    """P0a-09: Full catalog returns all registered agents."""

    def test_returns_all_agents_with_metadata(self, catalog_dir: Path) -> None:
        """Given catalog with 4 agents, returns dict with all of them."""
        result = load_all_agents(catalog_dir)
        assert set(result.keys()) == {
            "alpha",
            "beta",
            "internal-tool",
            "secret-builder",
        }
        # Each entry includes its metadata from the catalog
        assert result["alpha"]["public"] is True
        assert result["internal-tool"]["public"] is False
        assert result["alpha"]["description"] == "Alpha agent"


# ---------------------------------------------------------------------------
# P0a-09: Corrupted catalog raises CatalogParseError
# ---------------------------------------------------------------------------


class TestCorruptedCatalog:
    """P0a-09: Corrupted catalog raises CatalogParseError in strict mode."""

    def test_corrupted_catalog_raises_catalog_parse_error(
        self, corrupted_dir: Path
    ) -> None:
        """Given corrupted YAML, strict=True raises CatalogParseError."""
        with pytest.raises(CatalogParseError) as exc_info:
            load_public_agents(corrupted_dir, strict=True)

        # Error must describe the parsing failure
        assert (
            "parse" in str(exc_info.value).lower()
            or "yaml" in str(exc_info.value).lower()
        )


# ---------------------------------------------------------------------------
# P0a-05 / P0a-07: normalize_agent_name strips prefix and suffix
# ---------------------------------------------------------------------------


class TestNormalizeAgentName:
    """P0a-05: Agent name normalized from filename with prefix and suffix."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("nw-solution-architect.md", "solution-architect"),  # P0a-05
            ("solution-architect", "solution-architect"),  # P0a-07: idempotent
            ("nw-solution-architect-reviewer.md", "solution-architect-reviewer"),
        ],
    )
    def test_normalize_agent_name_strips_prefix_and_suffix(
        self, raw: str, expected: str
    ) -> None:
        """Given various agent filenames/names, normalization produces bare name."""
        assert normalize_agent_name(raw) == expected


# ---------------------------------------------------------------------------
# P0a-06 / P0a-08: base_agent_name strips reviewer suffix
# ---------------------------------------------------------------------------


class TestBaseAgentName:
    """P0a-06: Reviewer suffix stripped to find base agent."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("solution-architect-reviewer", "solution-architect"),  # P0a-06
            ("software-crafter", "software-crafter"),  # P0a-08: no-op
        ],
    )
    def test_base_agent_name_strips_reviewer_suffix(
        self, name: str, expected: str
    ) -> None:
        """Given agent names, base extraction strips -reviewer when present."""
        assert base_agent_name(name) == expected


# ---------------------------------------------------------------------------
# P0a-11: End-to-end normalize then base for reviewer filename
# ---------------------------------------------------------------------------


class TestNormalizeAndBase:
    """P0a-11: Reviewer agent filename normalized and base extracted."""

    def test_end_to_end_normalize_then_base(self) -> None:
        """Given 'nw-solution-architect-reviewer.md', normalize then base -> 'solution-architect'."""
        normalized = normalize_agent_name("nw-solution-architect-reviewer.md")
        assert normalized == "solution-architect-reviewer"
        base = base_agent_name(normalized)
        assert base == "solution-architect"
