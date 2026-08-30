"""Unit tests for scripts/shared/ghost_verb_census.py -- the backtick-span
`des <verb>` extractor and live/ghost classifier feeding both the baseline
generator and the documentation-staleness ratchet gate
(F-INSTALL-REMOVAL-TRANSPARENCY follow-up).
"""

from __future__ import annotations

from pathlib import Path

from scripts.shared.ghost_verb_census import (
    census_ghost_citations,
    extract_des_verb_citations,
    ghost_verbs,
)


def test_extracts_a_simple_backtick_citation() -> None:
    text = "Run `des commit-slice` to seal the step."

    assert extract_des_verb_citations(text) == frozenset({"commit-slice"})


def test_extracts_a_verb_not_at_the_start_of_the_span() -> None:
    """`pipenv run des commit-slice --repo .` -- the verb is mid-span, not
    the first token; this is the case a strict "backtick immediately
    followed by des" pattern missed (see module docstring)."""
    text = "! pipenv run des commit-slice --repo . --message x"
    wrapped = f"`{text}`"

    assert extract_des_verb_citations(wrapped) == frozenset({"commit-slice"})


def test_ignores_prose_mentioning_des_outside_backticks() -> None:
    """The exact false-positive class defects.md's own entry names:
    Italian prose "... risolve des al SUO source" must not be read as a
    citation of a verb called "al"."""
    text = "`uv run` in un worktree crea il PROPRIO .venv e risolve des al SUO source."

    assert extract_des_verb_citations(text) == frozenset()


def test_deduplicates_repeated_citations_in_the_same_text() -> None:
    text = "`des commit-slice` ... later again `des commit-slice --at-kind x`"

    assert extract_des_verb_citations(text) == frozenset({"commit-slice"})


def test_multiple_distinct_verbs_in_one_text() -> None:
    text = "`des commit-slice` then `des feature-end`"

    assert extract_des_verb_citations(text) == frozenset(
        {"commit-slice", "feature-end"}
    )


def test_no_citation_returns_empty_set() -> None:
    assert extract_des_verb_citations("nothing here") == frozenset()


def test_ghost_verbs_excludes_live_names() -> None:
    cited = frozenset({"commit-slice", "health-check"})
    live = frozenset({"health-check"})

    assert ghost_verbs(cited, live=live) == frozenset({"commit-slice"})


def test_ghost_verbs_counts_a_retired_but_declared_name_as_still_ghost() -> None:
    """Deliberate: `_RETIRED` fixes the CLI's runtime symptom, not a
    doc telling a reader to run the retired verb -- see module docstring."""
    cited = frozenset({"commit-slice"})
    live = frozenset()  # commit-slice is NOT live, only _RETIRED-declared

    assert ghost_verbs(cited, live=live) == frozenset({"commit-slice"})


def test_census_ghost_citations_keys_by_given_path_and_skips_clean_files(
    tmp_path: Path,
) -> None:
    live = frozenset({"alpha"})
    offending = tmp_path / "offending.md"
    offending.write_text("Run `des ghost-verb` now.\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("Run `des alpha` now.\n", encoding="utf-8")

    result = census_ghost_citations([offending, clean], live=live)

    assert result == {str(offending): frozenset({"ghost-verb"})}
