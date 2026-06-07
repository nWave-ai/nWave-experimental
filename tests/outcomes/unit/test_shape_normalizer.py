"""Unit test: ShapeNormalizer — canonicalization rules.

Driving port: pure function `normalize_shape(raw: str) -> str`. The
function signature IS the public contract.
"""

from __future__ import annotations

import pytest
from nwave_ai.outcomes.domain.shape import normalize_shape


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Whitespace-only variations collapse to the same canonical form.
        ("FeatureDeltaModel", "FeatureDeltaModel"),
        ("  FeatureDeltaModel  ", "FeatureDeltaModel"),
        ("Feature Delta Model", "FeatureDeltaModel"),
        # Parameter names stripped from tuples — only types remain.
        ("(text: str, file_path: str)", "(str,str)"),
        ("(text:str,file_path:str)", "(str,str)"),
        ("(name: T, value: U)", "(T,U)"),
        # Output shapes preserved verbatim modulo whitespace.
        ("tuple[Violation, ...]", "tuple[Violation,...]"),
        # Idempotence: normalizing a normalized form yields the same string.
        ("(str,str)", "(str,str)"),
    ],
)
def test_normalize_shape_canonicalises_inputs(raw: str, expected: str) -> None:
    assert normalize_shape(raw) == expected


def test_normalize_shape_is_idempotent() -> None:
    """f(f(x)) == f(x) for any reasonable input."""
    samples = [
        "(text: str, file_path: str)",
        "tuple[Violation, ...]",
        "  FeatureDeltaModel  ",
        "(FeatureDeltaModel, verbs: tuple)",
    ]
    for raw in samples:
        once = normalize_shape(raw)
        twice = normalize_shape(once)
        assert once == twice, f"not idempotent for {raw!r}: {once!r} -> {twice!r}"
