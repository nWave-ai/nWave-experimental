"""Unit tests: JaccardScorer pure functions (tokenize + score).

Driving port: the module-level functions ``tokenize`` and ``score`` are
their own driving ports — calling them directly IS port-to-port testing
because the function signature IS the public interface (per nw-tdd-methodology
skill, "pure domain functions ARE their own driving ports").

Tokenization rules (per DESIGN spec):
  - lowercase
  - split on ``-``, ``_``, whitespace
  - drop tokens of length <= 2

Score rule: ``|A & B| / |A | B|``; both empty -> 0.0.
"""

from __future__ import annotations

import pytest
from nwave_ai.outcomes.domain.jaccard import score, tokenize


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Lowercase + hyphen split.
        ("Cherry-Pick", frozenset({"cherry", "pick"})),
        # Underscore split.
        ("row_count", frozenset({"row", "count"})),
        # Whitespace split + length filter (<=2 dropped).
        ("a bb ccc dddd", frozenset({"ccc", "dddd"})),
        # Mixed delimiters.
        (
            "format-suggestion_render text",
            frozenset({"format", "suggestion", "render", "text"}),
        ),
        # Empty.
        ("", frozenset()),
        # All short tokens dropped.
        ("a b c", frozenset()),
    ],
)
def test_tokenize_normalizes_and_filters(raw: str, expected: frozenset[str]) -> None:
    assert tokenize(raw) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Identical sets -> 1.0
        (frozenset({"cherry", "pick"}), frozenset({"cherry", "pick"}), 1.0),
        # Disjoint sets -> 0.0
        (frozenset({"cherry"}), frozenset({"pick"}), 0.0),
        # Both empty -> 0.0 (avoid div-by-zero)
        (frozenset(), frozenset(), 0.0),
        # One empty -> 0.0
        (frozenset({"x", "y"}), frozenset(), 0.0),
        # Partial overlap: |A & B| = 1, |A | B| = 3 -> 1/3
        (frozenset({"a", "b"}), frozenset({"a", "c"}), 1.0 / 3.0),
    ],
)
def test_score_returns_jaccard_similarity(
    a: frozenset[str], b: frozenset[str], expected: float
) -> None:
    assert score(a, b) == pytest.approx(expected)
