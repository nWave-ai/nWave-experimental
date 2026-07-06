"""heading-SSOT unification — `_section_body` accepts bare AND wave-tagged forms.

velocity-fix (2026-07-05): the authoring convention (lean-wave-documentation D2)
emits `## Wave: <W> / [REF] <core>` headings while several gate literals in
`feature_delta_schema` are bare `## <core>` — two independent definitions of the
same heading that drifted, so a correctly-authored section was rejected on
grammar alone (the DELIVER-entry friction-wall, FR-11). `_heading_matches` now
accepts the two forms interchangeably (ADD-not-mutate) so the two sides can never
disagree on heading grammar. These tests lock that behavior.
"""

from __future__ import annotations

import pytest

from des.cli.feature_delta_schema import _section_body


_LITERAL = "## Test Reuse & Consolidation Analysis"


@pytest.mark.parametrize(
    ("heading_line", "expected"),
    [
        pytest.param(_LITERAL, "body", id="bare-form-still-matches"),
        pytest.param(
            "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis",
            "body",
            id="wave-tagged-form-now-matches",
        ),
        pytest.param(
            "## Wave: DESIGN / [REF] Test Reuse & Consolidation Analysis",
            "body",
            id="wave-tagged-any-wave-name-matches",
        ),
    ],
)
def test_section_body_accepts_bare_and_wave_tagged_headings(
    heading_line: str, expected: str
) -> None:
    content = f"{heading_line}\n\nbody\n\n## Next Section\n\nother\n"
    assert _section_body(content, _LITERAL) == expected


def test_section_body_does_not_match_an_unrelated_heading() -> None:
    """Core-name equality guards against a false match — a different section
    (`## Out of scope`) must NOT be read as the Reuse-Analysis section."""
    content = "## Out of scope\n\nnope\n\n## Next\n\nx\n"
    assert _section_body(content, _LITERAL) is None
