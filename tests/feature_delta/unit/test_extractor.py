"""Unit tests for GherkinExtractor application service (driving port: extract()).

Test Budget: 3 distinct behaviors * 2 = 6 unit tests max.
  B1: extraction emits Feature: header + all block contents
  B2: no gherkin blocks → ExtractionError with file path and message
  B3: multiple blocks preserved in document order

Mandate M2: tests drive through GherkinExtractor.extract() — the application
service driving port. Domain parser is exercised indirectly.
"""

from __future__ import annotations

import pytest
from nwave_ai.feature_delta.application.extractor import (
    ExtractionError,
    GherkinExtractor,
)


# ---------------------------------------------------------------------------
# B1 — extraction emits Feature: header + block contents
# ---------------------------------------------------------------------------


def test_extract_emits_feature_header_from_h1():
    """Feature: <id> derived from first # heading."""
    markdown = (
        "# my-feature\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: one\n"
        "  Given a thing\n"
        "  When it runs\n"
        "  Then it works\n"
        "```\n"
    )
    result = GherkinExtractor().extract(markdown, path="feature-delta.md")
    assert result.startswith("Feature: my-feature")


def test_extract_includes_block_contents_after_feature_header():
    """Block content follows Feature: header."""
    markdown = (
        "# my-feature\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: happy path\n"
        "  Given a clean repo\n"
        "  When scaffolds\n"
        "  Then delta exists\n"
        "```\n"
    )
    result = GherkinExtractor().extract(markdown, path="feature-delta.md")
    assert "Scenario: happy path" in result
    assert "Given a clean repo" in result


# ---------------------------------------------------------------------------
# B2 — no blocks → ExtractionError with file:line info
# ---------------------------------------------------------------------------


def test_extract_raises_when_no_gherkin_blocks():
    """Empty gherkin → ExtractionError naming the file."""
    markdown = "# no-blocks\n\n## Wave: DISCUSS\n\nplain prose only\n"
    with pytest.raises(ExtractionError) as exc_info:
        GherkinExtractor().extract(
            markdown, path="docs/feature/no-blocks/feature-delta.md"
        )
    assert "feature-delta.md" in str(exc_info.value)
    assert "no gherkin blocks found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# B3 — multiple blocks preserved in document order
# ---------------------------------------------------------------------------


def test_extract_concatenates_multiple_blocks_in_order():
    """Three blocks appear in document order, DISCUSS → DESIGN → DISTILL."""
    markdown = (
        "# multi-block\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: alpha\n"
        "  Given alpha\n"
        "```\n\n"
        "## Wave: DESIGN\n\n"
        "```gherkin\n"
        "Scenario: beta\n"
        "  Given beta\n"
        "```\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        "Scenario: gamma\n"
        "  Given gamma\n"
        "```\n"
    )
    result = GherkinExtractor().extract(markdown, path="feature-delta.md")
    alpha_pos = result.index("Scenario: alpha")
    beta_pos = result.index("Scenario: beta")
    gamma_pos = result.index("Scenario: gamma")
    assert alpha_pos < beta_pos < gamma_pos
