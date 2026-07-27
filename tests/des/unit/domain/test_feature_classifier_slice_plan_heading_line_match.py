"""Regression test for techdebt.md
`feature-classifier-slice-plan-heading-substring-match-false-positive`.

``has_slice_plan()`` (via ``_has_slice_plan_heading``) used a bare substring
check (``SLICE_PLAN_HEADING in markdown.read_text(...)``) against the WHOLE
file text -- so any prose that merely *mentions* the heading string (e.g. an
author's note explaining the grammar to the next author) made the probe
return ``True`` even though no actual Slice Plan heading line was ever
written. The live reproduction: a feature dir whose only markdown file is a
notes.md that quotes the heading inside a sentence to describe it, without
promoting it -- must NOT be classified as carrying a Slice Plan.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.feature_classifier import has_slice_plan


def test_heading_mentioned_in_prose_is_not_a_promoted_slice_plan(
    tmp_path: Path,
) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    (feature_dir / "notes.md").write_text(
        "A promoted feature must carry the "
        "`## Wave: DISCUSS / [REF] Slice Plan` heading and a populated "
        "table. We have NOT written that section yet.",
        encoding="utf-8",
    )

    assert has_slice_plan(feature_dir) is False


def test_heading_as_a_real_heading_line_still_yields_true(tmp_path: Path) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    (feature_dir / "plan.md").write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n| Slice | ... |\n",
        encoding="utf-8",
    )

    assert has_slice_plan(feature_dir) is True


def test_heading_line_with_surrounding_whitespace_still_yields_true(
    tmp_path: Path,
) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    (feature_dir / "plan.md").write_text(
        "intro\n\n  ## Wave: DISCUSS / [REF] Slice Plan  \n\ncontent\n",
        encoding="utf-8",
    )

    assert has_slice_plan(feature_dir) is True
