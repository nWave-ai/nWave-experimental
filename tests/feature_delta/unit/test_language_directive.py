"""Unit tests for # language: <code> directive preservation in extractor (US-13 AC-5).

Test Budget: 1 distinct behavior x 2 = 2 unit tests max.
Using 1 (complete behavioral assertion covers directive passthrough).

Behavior:
  B5 — gherkin block containing "# language: it" directive is preserved
       verbatim in extracted output; Italian keyword "Funzionalità:" is
       also preserved.

Port: GherkinExtractor.extract() — driving port (application service).
"""

from __future__ import annotations

from nwave_ai.feature_delta.application.extractor import GherkinExtractor


def test_italian_language_directive_preserved_in_extraction() -> None:
    """# language: it directive and Funzionalità: keyword survive extraction (US-13 AC-5)."""
    markdown = (
        "# my-feature\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        "# language: it\n"
        "Funzionalità: accesso utente\n"
        "  Scenario: accesso con credenziali valide\n"
        "    Dato un utente registrato\n"
        "    Quando inserisce le credenziali\n"
        "    Allora accede al sistema\n"
        "```\n"
    )
    result = GherkinExtractor().extract(markdown, path="feature-delta.md")
    assert "# language: it" in result, (
        f"language directive must be preserved in output; got:\n{result}"
    )
    assert "Funzionalità:" in result, (
        f"Italian keyword Funzionalità: must be preserved; got:\n{result}"
    )
