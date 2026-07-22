"""Regression (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED): unit tests for the
PURE markdown-surgery helpers `carpaccio_format.mark_slice_status_shipped`
and `carpaccio_format.mark_feature_end_sealed`.

ROOT CAUSE (backlog.md, F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED): `des
commit-slice` and `des feature-end run` both APPEND to the AT-completion
ledger on success, but NEITHER writes back to the feature-delta.md `[REF]
Slice Plan` markdown table's `Status` column -- so a genuinely-shipped slice
can sit on disk with a stale `pending` row indefinitely.

These are the PURE core (no filesystem I/O -- `carpaccio_format.py`'s own
module contract is "reads nothing, mutates nothing" at the FILESYSTEM
level; both functions take a string and return a string-or-None). The
CLI-level wiring (`commit_slice._sync_slice_plan_status`,
`feature_end._sync_feature_delta_on_feature_end`) is regression-tested
separately in `tests/bugs/des/test_slice_plan_status_column_sync.py`.
"""

from __future__ import annotations

from des.cli.carpaccio_format import (
    FEATURE_END_SEALED_MARKER,
    mark_feature_end_sealed,
    mark_slice_status_shipped,
)


_SLICE_PLAN_TEXT = """## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|----------------|
| slice-01 | First slice value | pending | @walking_skeleton | reason one |
| slice-02 | Second slice value | shipped | depends-on slice-01 | reason two |
| slice-03 | Third slice value | blocked | depends-on slice-01 | reason three |

## Wave: DESIGN / [REF] Something Else

not a table row
"""


def test_flips_pending_to_shipped_for_the_matching_row() -> None:
    rewritten = mark_slice_status_shipped(_SLICE_PLAN_TEXT, "slice-01")

    assert rewritten is not None
    lines = rewritten.splitlines()
    slice_01_line = next(line for line in lines if line.startswith("| slice-01"))
    assert "| shipped |" in slice_01_line
    assert "pending" not in slice_01_line
    # Every OTHER row's text is untouched, byte-for-byte.
    slice_02_line = next(line for line in lines if line.startswith("| slice-02"))
    slice_03_line = next(line for line in lines if line.startswith("| slice-03"))
    assert (
        slice_02_line
        == "| slice-02 | Second slice value | shipped | depends-on slice-01 | reason two |"
    )
    assert (
        slice_03_line
        == "| slice-03 | Third slice value | blocked | depends-on slice-01 | reason three |"
    )


def test_already_shipped_row_is_a_no_op() -> None:
    assert mark_slice_status_shipped(_SLICE_PLAN_TEXT, "slice-02") is None


def test_a_non_pending_non_shipped_status_is_never_clobbered() -> None:
    """A hand-authored `blocked`/`in-progress` value must never be silently
    overwritten by the mechanical sync -- GDP-6, never invent a diagnosis
    for an unexpected value, just decline to touch it."""
    assert mark_slice_status_shipped(_SLICE_PLAN_TEXT, "slice-03") is None


def test_unknown_slice_id_is_a_no_op() -> None:
    assert mark_slice_status_shipped(_SLICE_PLAN_TEXT, "slice-99") is None


def test_missing_slice_plan_section_is_a_no_op_never_raises() -> None:
    assert (
        mark_slice_status_shipped("# Just a heading\n\nSome prose.", "slice-01") is None
    )


def test_malformed_table_is_a_no_op_never_raises() -> None:
    malformed = (
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|----------------|\n"
        "| not-a-slice-id | value | pending | | |\n"
    )
    assert mark_slice_status_shipped(malformed, "slice-01") is None


def test_result_is_idempotent_across_two_calls() -> None:
    once = mark_slice_status_shipped(_SLICE_PLAN_TEXT, "slice-01")
    assert once is not None
    twice = mark_slice_status_shipped(once, "slice-01")
    assert twice is None


def test_preserves_trailing_newline_convention() -> None:
    no_trailing_newline = _SLICE_PLAN_TEXT.rstrip("\n")
    rewritten = mark_slice_status_shipped(no_trailing_newline, "slice-01")
    assert rewritten is not None
    assert not rewritten.endswith("\n")

    with_trailing_newline = _SLICE_PLAN_TEXT
    rewritten2 = mark_slice_status_shipped(with_trailing_newline, "slice-01")
    assert rewritten2 is not None
    assert rewritten2.endswith("\n")


def test_appends_feature_end_marker_once() -> None:
    sealed = mark_feature_end_sealed(_SLICE_PLAN_TEXT)
    assert sealed is not None
    assert sealed.count(FEATURE_END_SEALED_MARKER) == 1
    assert sealed.startswith(_SLICE_PLAN_TEXT.rstrip("\n"))


def test_feature_end_marker_append_is_idempotent() -> None:
    sealed = mark_feature_end_sealed(_SLICE_PLAN_TEXT)
    assert sealed is not None
    assert mark_feature_end_sealed(sealed) is None


def test_feature_end_marker_works_with_no_slice_plan_section() -> None:
    """A feature-delta with no Slice Plan section still gets sealed."""
    sealed = mark_feature_end_sealed("# Just a heading\n\nSome prose.\n")
    assert sealed is not None
    assert FEATURE_END_SEALED_MARKER in sealed
