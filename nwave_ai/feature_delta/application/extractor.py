"""GherkinExtractor — application service for Gherkin block extraction.

ADR-04: pure-function design — no side effects beyond returning the string.
DD-A4: zero side effects (G4).
"""

from __future__ import annotations

from nwave_ai.feature_delta.domain.parser import MarkdownSectionParser


class ExtractionError(Exception):
    """Raised when no gherkin blocks are found in the feature-delta document."""


class GherkinExtractor:
    """Extract all fenced gherkin blocks from a feature-delta markdown document.

    Emits:
      Feature: <feature-id>   — derived from the first # heading
      <block1 contents>
      <block2 contents>
      ...

    Blocks are concatenated in document order (wave section order, then block
    order within each section).

    Raises ExtractionError when no gherkin blocks are found.
    """

    def __init__(self, parser: MarkdownSectionParser | None = None) -> None:
        self._parser = parser or MarkdownSectionParser()

    def extract(self, markdown: str, *, path: str = "<unknown>") -> str:
        """Extract gherkin blocks from markdown text.

        Args:
            markdown: raw text of a feature-delta.md document.
            path: file path for error messages (not read from disk).

        Returns:
            A string beginning with "Feature: <feature-id>" followed by all
            gherkin block contents in document order.

        Raises:
            ExtractionError: if no gherkin fenced blocks are found.
        """
        model = self._parser.parse(markdown)

        blocks: list[str] = []
        for section in model.sections:
            blocks.extend(section.gherkin_blocks)

        if not blocks:
            raise ExtractionError(
                f"{path}: no gherkin blocks found — "
                "add ```gherkin ... ``` fenced blocks to the feature-delta"
            )

        parts = [f"Feature: {model.feature_id}"]
        parts.extend(blocks)
        return "\n\n".join(parts) + "\n"
