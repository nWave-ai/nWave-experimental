"""Regression test for techdebt.md
`incomplete-exception-handler-feature-classifier-py-205-210`.

``has_slice_plan()`` promises a crash-free probe (docstring: "an unreadable
markdown file yields False rather than raising"), but its guard only caught
``OSError``. A markdown file containing invalid UTF-8 bytes raises
``UnicodeDecodeError`` (a ``ValueError`` subclass, NOT an ``OSError``
subclass) from ``Path.read_text(encoding="utf-8")``, which used to propagate
uncaught and crash the classifier instead of yielding ``False``.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.feature_classifier import has_slice_plan


def test_non_utf8_markdown_file_yields_false_instead_of_crashing(
    tmp_path: Path,
) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    bad_markdown = feature_dir / "notes.md"
    # 0xFF is not valid UTF-8 in any position -- guarantees UnicodeDecodeError.
    bad_markdown.write_bytes(b"some notes \xff\xfe more text")

    assert has_slice_plan(feature_dir) is False


def test_valid_markdown_without_heading_still_yields_false(tmp_path: Path) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    (feature_dir / "notes.md").write_text("just some notes", encoding="utf-8")

    assert has_slice_plan(feature_dir) is False


def test_valid_markdown_with_heading_yields_true(tmp_path: Path) -> None:
    feature_dir = tmp_path / "f-example"
    feature_dir.mkdir()
    (feature_dir / "plan.md").write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\ncontent", encoding="utf-8"
    )

    assert has_slice_plan(feature_dir) is True
