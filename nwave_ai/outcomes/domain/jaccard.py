"""JaccardScorer — pure functions for keyword similarity.

Tier-2 collision detection compares keyword sets via Jaccard similarity.
Two outcomes whose keyword sets overlap ``>= 0.4`` are considered
semantically similar by the DESIGN spec verdict matrix.

Tokenization rules:
  1. Lowercase.
  2. Split on ``-``, ``_``, whitespace.
  3. Drop tokens of length ``<= 2`` (filter noise like "a", "of").

Score: ``|A & B| / |A | B|``; both empty -> ``0.0`` (no signal).
"""

from __future__ import annotations

import re


_SPLITTER = re.compile(r"[-_\s]+")
_MIN_TOKEN_LEN = 3


def tokenize(text: str) -> frozenset[str]:
    """Return the canonical token set for a keyword string."""
    if not text:
        return frozenset()
    parts = _SPLITTER.split(text.lower())
    return frozenset(p for p in parts if len(p) >= _MIN_TOKEN_LEN)


def score(a: frozenset[str], b: frozenset[str]) -> float:
    """Return Jaccard similarity ``|A & B| / |A | B|``; 0.0 if both empty."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)
