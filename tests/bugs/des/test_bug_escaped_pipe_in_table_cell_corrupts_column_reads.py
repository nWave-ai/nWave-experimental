"""Regression -- `_parse_table_cells` (`src/des/cli/validate_feature_delta.py`
:538-548) splits a GFM table row on EVERY `|` character, ignoring a GFM-escaped
pipe (`\\|`). A cell that carries an escaped pipe as literal text is split at
that point, so every column AFTER the escape shifts by one for the rest of
that row.

Diagnosed by direct comparison against the CORRECT sibling parser,
`_split_table_cells` (`src/des/cli/carpaccio_format.py:407-423`), which honors
`\\|` via `_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\\\)\\|")` and un-escapes the
survivor back to `|`. On the real offending row (feature-delta.md:182 of
`docs/feature/mikado-slices-as-tree-nodes/feature-delta.md`) the buggy parser
returns 6 cells / a garbled Decision value; the correct parser returns 5 cells
/ the real Decision (`EXTEND`).

`_parse_table_cells` is not a leaf -- it is the shared cell reader for the
Slice Plan section, consumed by (at minimum) three distinct production
surfaces, each damaged a DIFFERENT way by the same defect:

1. `read_slice_plan_dependencies` (:919-958) -- positional cell reads
   (`cells[3]` for Annotation) silently return the WRONG cell once a prior
   column's escape has shifted the row, so a genuinely declared
   `depends-on {slice-id}` is read back as "no dependency" -- a declared
   dependency is LOST.
2. `_classify_slice_dependency_justification` (:694-736), reached from
   `validate_slice_plan_content` -- the same shifted `cells[3]` means the
   mandatory-justification VETO never fires for a row that truly declares an
   unjustified dependency: the escape becomes an accidental bypass for a
   value that must be rejected.
3. `feature_delta_schema._slice_plan_row` (:552-568), the P4 role projection
   feeding `project_for_role` (crafter/examiner/atd, :655-733) --
   `dict(zip(header, _parse_table_cells(row), strict=False))` pairs the FIXED
   5-column header against the shifted (6+-cell) row: every field after the
   escape is silently WRONG, and because `zip` is non-strict, the row's real
   trailing Justification cell is dropped entirely with no error -- the
   projected Justification a crafter/examiner reads is a different column's
   content, and the operator has no signal anything went missing.

Charter (oracle SSOT): `docs/product/expectations/fix-feature-delta-table-
parser/operator-escapes-a-pipe-in-a-table-cell-and-dispatch-accepts-the-
document.md`. The charter's most important negative oracle -- "an escaped
pipe in ONE cell must not act as a general escape hatch for the rest of the
row" -- is exactly class 2 above (test 2 below): the escape sits in the
`Value statement` cell, the bad value it must not shield sits in
`Annotation`/`Justification`, two columns later in the SAME row.

Driving surface: direct import of the PUBLIC production functions
(`read_slice_plan_dependencies`, `validate_slice_plan_content`,
`project_for_role`) plus the one PRIVATE function the RCA names explicitly as
a distinct damaged consumer (`_slice_plan_row`) -- same precedent as the
sibling `tests/bugs/des/test_slice_plan_columns_read_by_header_not_position.py`
(imports private helpers of the diagnosed module directly; this is a
pytest-regression bugfix file, not a DISTILL Gherkin AT, so Mandate 16
driving-port-only does not apply here -- the mechanical seal route applies
instead per `nw-distill` Deliverable-Type Verification Routing).

RED-for-right-reason: tests 1-3 assert on VALUES/VERDICTS returned by calls
that execute fully today and return the wrong thing -- genuine semantic
`AssertionError`s, never an import/collection error. Tests 4-5 are negative
guards (GREEN today AND after the fix): they pin that an unrelated rejection
still names the true cause, and that a genuinely malformed document (no
escaped pipes anywhere) stays rejected, unchanged by whatever fix lands.

@contract-shape:bounded-change (tests 1-3): a row carrying a GFM-escaped pipe
moves from "silently misread" (today) to "read identically to the
unescaped-equivalent row" (the fix).

@contract-shape:unbounded-preservation (tests 4-5): unrelated rejections and
already-malformed documents must not regress under the fix -- the fix must
not become more permissive to buy its green.
"""

from __future__ import annotations

import pytest

from des.cli.feature_delta_schema import _slice_plan_row, project_for_role
from des.cli.validate_feature_delta import (
    VERDICT_ACCEPTED,
    VERDICT_DUPLICATE_SLICE_ID,
    VERDICT_MALFORMED_SLICE_PLAN,
    VERDICT_UNJUSTIFIED_SLICE_DEPENDENCY,
    read_slice_plan_dependencies,
    validate_slice_plan_content,
)


_SLICE_PLAN_HEADING = "## Wave: DISCUSS / [REF] Slice Plan"
_SLICE_PLAN_HEADER_ROW = (
    "| Slice | Value statement | Status | Annotation | Justification |"
)
_SLICE_PLAN_SEPARATOR_ROW = "|---|---|---|---|---|"

#: The literal cell text an author writes to mean a single vertical bar as
#: part of the prose (GFM escape) -- e.g. "read/\|write access".
_ESCAPED_VALUE_STATEMENT = r"Refactor a\|b handling"
#: The value a human (and the CORRECT parser) reads out of that cell: the
#: literal pipe survives, the backslash does not.
_REAL_VALUE_STATEMENT = "Refactor a|b handling"


def _row(
    slice_id: str,
    value_statement: str,
    status: str,
    annotation: str,
    justification: str,
) -> str:
    """One Slice Plan data row in the D2 fixed five-column order."""
    return f"| {slice_id} | {value_statement} | {status} | {annotation} | {justification} |"


def _feature_delta_with_slice_plan(data_rows: list[str]) -> str:
    """A minimal feature-delta carrying one `[REF] Slice Plan` table with the
    given data rows, followed by an unrelated section (mirrors the sibling
    fixture idiom in `test_slice_plan_columns_read_by_header_not_position.py`)."""
    rows_text = "\n".join(data_rows)
    return (
        f"{_SLICE_PLAN_HEADING}\n"
        "\n"
        f"{_SLICE_PLAN_HEADER_ROW}\n"
        f"{_SLICE_PLAN_SEPARATOR_ROW}\n"
        f"{rows_text}\n"
        "\n"
        "## Wave: DISTILL / [REF] Scenario list\n"
        "\n"
        "prose after the table\n"
    )


# ===========================================================================
# 1 -- class 1: a declared dependency is LOST (positional post-split read)
# ===========================================================================


def test_escaped_pipe_shifts_and_hides_a_declared_dependency() -> None:
    """`read_slice_plan_dependencies` must recover `depends-on slice-00` for
    BOTH rows -- the escaped-pipe row and its no-escape sibling -- since both
    genuinely declare the identical dependency, only differing in whether the
    Value statement happens to contain a literal pipe.

    RED TODAY for `slice-01` (escaped): the escape in `Value statement`
    shifts the row so `cells[3]` (consulted for Annotation) holds "IN_PROGRESS"
    (the real Status value) instead of "depends-on slice-00" -- the dependency
    is read back as declared-NONE.

    GREEN control for `slice-02` (no escape): proves the harness and the
    dependency-reading path work end to end; the escape is the only variable.
    """
    text = _feature_delta_with_slice_plan(
        [
            _row(
                "slice-01",
                _ESCAPED_VALUE_STATEMENT,
                "IN_PROGRESS",
                "depends-on slice-00",
                "prior slice lands first",
            ),
            _row(
                "slice-02",
                "Refactor ab handling, no escape here",
                "IN_PROGRESS",
                "depends-on slice-00",
                "prior slice lands first",
            ),
        ]
    )

    graph = dict(read_slice_plan_dependencies(text) or ())

    assert graph.get("slice-02") == ("slice-00",), (
        "control sanity: the no-escape sibling row must read its declared "
        f"dependency correctly -- got {graph.get('slice-02')!r}. If this "
        "fails the harness itself is broken, not the escaped-pipe bug."
    )
    assert graph.get("slice-01") == ("slice-00",), (
        "slice-01 declares 'depends-on slice-00' in its Annotation cell -- "
        "an escaped pipe earlier in the SAME row (Value statement) must "
        "never cause that declaration to be lost. Got "
        f"{graph.get('slice-01')!r} -- a positional read landed on the "
        "wrong cell once the escape shifted the row."
    )


# ===========================================================================
# 2 -- class 2: the escape becomes an accidental VETO BYPASS (the charter's
# most important negative oracle -- a pass in one cell must not shield a bad
# value elsewhere in the same row)
# ===========================================================================


@pytest.mark.parametrize(
    ("value_statement", "justification", "expected_verdict", "case_id"),
    [
        pytest.param(
            _ESCAPED_VALUE_STATEMENT,
            "",
            VERDICT_UNJUSTIFIED_SLICE_DEPENDENCY,
            "escaped-pipe-hides-the-veto",
        ),
        pytest.param(
            "Refactor ab handling, no escape here",
            "",
            VERDICT_UNJUSTIFIED_SLICE_DEPENDENCY,
            "no-escape-control-still-rejects",
        ),
        pytest.param(
            "Refactor ab handling, no escape here",
            "prior slice lands first",
            VERDICT_ACCEPTED,
            "no-escape-well-formed-baseline",
        ),
    ],
)
def test_escaped_pipe_does_not_bypass_the_unjustified_dependency_veto(
    value_statement: str, justification: str, expected_verdict: str, case_id: str
) -> None:
    """A row declaring `depends-on slice-00` with an EMPTY Justification cell
    must be REJECTED (`unjustified-slice-dependency`) whether or not its
    Value statement happens to carry an escaped pipe -- an escaped pipe in
    one cell (Value statement) must never act as a pass for a genuinely bad
    value in a DIFFERENT cell of the same row (Annotation/Justification).

    RED TODAY for `escaped-pipe-hides-the-veto`: the escape shifts the row so
    the dependency-justification classifier reads the wrong cells and never
    detects the `depends-on` claim at all -- the row is wrongly `accepted`,
    the exact bypass the charter's oracle forbids.

    GREEN controls for the other two ids: they exercise the identical
    production code path with no escape involved, pinning that (a) the veto
    itself works and (b) a genuinely well-formed, justified row is accepted
    -- both must stay byte-identical after whatever fix lands.
    """
    text = _feature_delta_with_slice_plan(
        [
            _row(
                "slice-01",
                value_statement,
                "IN_PROGRESS",
                "depends-on slice-00",
                justification,
            )
        ]
    )

    result = validate_slice_plan_content(text)

    assert result.verdict == expected_verdict, (
        f"[{case_id}] expected verdict {expected_verdict!r}; got "
        f"{result.verdict!r} (detail={result.detail!r}). An escaped pipe "
        "elsewhere in the row must never change whether a genuine "
        "unjustified 'depends-on' claim is caught, nor make a genuinely "
        "well-formed row less accepted."
    )


# ===========================================================================
# 3 -- class 3: the P4 role projection is silently corrupted, and the row's
# REAL Justification disappears without any error (non-strict zip)
# ===========================================================================


def test_escaped_pipe_corrupts_the_role_projection_and_drops_the_real_justification() -> (
    None
):
    """`_slice_plan_row` (feeding `project_for_role`) must return the SAME
    field values a human reading the table would -- the literal-pipe Value
    statement un-escaped, and the row's REAL Justification text, not a
    neighboring column's leaked content.

    RED TODAY on both assertions: the escape in Value statement shifts the
    row to 6 cells against a 5-cell header; `dict(zip(header, cells,
    strict=False))` truncates to the header's length, so `row['Value
    statement']` is a truncated fragment, and `row['Justification']` is
    actually the row's Annotation content ('depends-on slice-00') -- the
    row's REAL trailing Justification cell ('prior slice lands first') is
    silently dropped: `zip(strict=False)` raises nothing, so nothing signals
    the loss.
    """
    real_justification = "prior slice lands first"
    text = _feature_delta_with_slice_plan(
        [
            _row(
                "slice-01",
                _ESCAPED_VALUE_STATEMENT,
                "IN_PROGRESS",
                "depends-on slice-00",
                real_justification,
            )
        ]
    )

    row = _slice_plan_row(text, "slice-01")

    assert row is not None, f"slice-01 must be found in the Slice Plan; got {row!r}"
    assert row.get("Value statement") == _REAL_VALUE_STATEMENT, (
        "the projected Value statement must un-escape the literal pipe and "
        f"carry the FULL cell text -- expected {_REAL_VALUE_STATEMENT!r}, "
        f"got {row.get('Value statement')!r} (a truncated/garbled fragment "
        "means the row was split at the escaped pipe)."
    )
    assert row.get("Justification") == real_justification, (
        "the projected Justification must be the row's REAL trailing cell "
        f"-- expected {real_justification!r}, got "
        f"{row.get('Justification')!r}. If this shows the Annotation value "
        "instead, the real Justification cell was silently dropped by "
        "non-strict zip against a header shorter than the shifted row."
    )

    projection = project_for_role(
        text, "examiner", "slice-01", "fixture-feature-delta.md"
    )
    assert _REAL_VALUE_STATEMENT in projection.markdown, (
        "the examiner-role projection (what a crafter/examiner actually "
        f"reads) must carry the real, un-escaped Value statement -- expected "
        f"{_REAL_VALUE_STATEMENT!r} inside the rendered markdown; got:\n"
        f"{projection.markdown}"
    )


# ===========================================================================
# 4 -- negative guard (GREEN today and after): an UNRELATED rejection must
# keep naming the true cause, never blame the pipe-bearing column
# ===========================================================================


@pytest.mark.negative_at
def test_escaped_pipe_never_masks_an_unrelated_duplicate_slice_id_rejection() -> None:
    """Two rows sharing the SAME slice id are rejected as
    `duplicate-slice-id` regardless of an escaped pipe sitting in one of
    their Value statement cells -- the escape must never distract the
    duplicate-id check (which reads only `cells[0]`, unaffected by any
    downstream shift) into naming the wrong cause, or into missing the
    duplicate entirely.
    """
    text = _feature_delta_with_slice_plan(
        [
            _row("slice-01", _ESCAPED_VALUE_STATEMENT, "IN_PROGRESS", "", ""),
            _row(
                "slice-01",
                "A second, competing claim about the same slice",
                "IN_PROGRESS",
                "",
                "",
            ),
        ]
    )

    result = validate_slice_plan_content(text)

    assert result.verdict == VERDICT_DUPLICATE_SLICE_ID, (
        f"two rows both id'd 'slice-01' must be rejected as "
        f"{VERDICT_DUPLICATE_SLICE_ID!r} regardless of an escaped pipe in "
        f"one row's Value statement; got {result.verdict!r} "
        f"(detail={result.detail!r})"
    )
    assert "slice-01" in result.detail and "duplicate" in result.detail.lower(), (
        "the rejection must name the TRUE cause (a duplicated slice id) -- "
        f"never blame the pipe-bearing column; got detail={result.detail!r}"
    )


# ===========================================================================
# 5 -- negative guard (GREEN today and after): a genuinely malformed document
# with NO escaped pipes anywhere stays rejected, same verdict class
# ===========================================================================


@pytest.mark.negative_at
def test_genuinely_malformed_document_without_any_escape_stays_rejected() -> None:
    """A row missing its Justification cell entirely (four cells, no escaped
    pipes anywhere in the document) must stay `malformed-slice-plan` -- the
    fix for the escaped-pipe defect must not buy its green by loosening this
    unrelated, already-correct rejection.
    """
    text = _feature_delta_with_slice_plan(
        ["| slice-01 | Ship the thing | IN_PROGRESS | depends-on slice-00 |"]
    )

    result = validate_slice_plan_content(text)

    assert result.verdict == VERDICT_MALFORMED_SLICE_PLAN, (
        "a Slice Plan row genuinely missing its Justification cell (no "
        f"escaped pipes involved at all) must stay {VERDICT_MALFORMED_SLICE_PLAN!r}; "
        f"got {result.verdict!r} (detail={result.detail!r})"
    )
