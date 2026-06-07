"""ShapeNormalizer — pure function canonicalising type-shape strings.

Tier-1 collision detection compares normalized strings for exact equality.
Two shapes that mean the same thing must produce the same canonical form.

Rules (this step — keep minimal, expand in 02-01):
  1. Strip all whitespace.
  2. Strip parameter names from tuple-form `(name: T, name: T)` → `(T,T)`.
  3. Idempotent: f(f(x)) == f(x).
"""

from __future__ import annotations

import re


_PARAM_TUPLE = re.compile(r"\([^)]*\)")
_WHITESPACE = re.compile(r"\s+")


def normalize_shape(raw: str) -> str:
    """Return the canonical form of a type-shape string."""
    no_ws = _WHITESPACE.sub("", raw)
    return _PARAM_TUPLE.sub(_strip_param_names, no_ws)


def _strip_param_names(match: re.Match[str]) -> str:
    """Replace parenthesised parameter list `(name:T, name:T)` with `(T,T)`."""
    inner = match.group()[1:-1]
    if not inner:
        return "()"
    types = tuple(_take_type(part) for part in inner.split(","))
    return "(" + ",".join(types) + ")"


def _take_type(part: str) -> str:
    """For `name:T` return `T`; otherwise return the part unchanged."""
    if ":" in part:
        return part.split(":", 1)[1]
    return part
