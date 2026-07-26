"""Regression -- the shared `[REF] Slice Plan` parser reads the table's cells
by FIXED POSITIONAL OFFSET from the `slice-NN` cell, ignoring what the header
row actually names; and when the resulting mis-read trips the mandatory-
justification guard, the rejection blames the CONTENT instead of naming the
MISSING COLUMN, sending the author to rewrite correct prose forever.

Found in `src/des/cli/carpaccio_format.py`:

* `_build_slice_rows` (~line 465) reads every field by offset::

      value_statement=_cell_at(cells, slice_index + 1),
      status=_cell_at(cells, slice_index + 2),
      annotation=_cell_at(cells, slice_index + 3),
      justification=_cell_at(cells, slice_index + 4),

  -- BUG: the header row (`table_rows[0]`, already collected by
  `parse_slice_plan_rows` and thrown away) is never consulted. On a 4-column
  `| Slice | Value statement | Annotation | Justification |` table the
  `@coupled` tag lands in `status`, the JUSTIFICATION prose lands in
  `annotation`, and `justification` reads past the end of the row and stays
  `''`. `slice_plan_header_deviation` (~line 484) proves the header row IS
  readable at this locus -- it is simply not used by the row builder.

* `_check_value_annotation` (~line 1268) then rejects with::

      f"slice {row.slice_id} carries annotation {row.annotation!r} "
      "but records no justification"

  -- BUG (the defect the operator actually experiences): on a table that
  genuinely LACKS a `Justification` column, this message names a CONTENT
  problem ("records no justification") when the real cause is a MISSING
  COLUMN. No rewrite of the prose can ever clear it, because there is no
  column to write the prose into. The message is the defect: it routes the
  author to the wrong repair, indefinitely.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero `src/` edits): resolve each canonical column by its HEADER CELL NAME
(`SLICE_PLAN_CANONICAL_COLUMNS`, line 135 -- the existing SSOT), reading an
absent canonical column as `''` and ignoring non-canonical extra columns; and
make the mandatory-justification rejection distinguish "the Justification
column is absent from the header" (name the missing column, show the header
as FOUND and the canonical header as EXPECTED) from "the Justification cell
is present but empty" (keep directing the author to write the prose).

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
the SAME two public production functions `carpaccio_slice_gate.main` composes
at lines 917-930 -- `parse_slice_plan(text)` then `check_carpaccio(plan, ...)`
-- never a private helper. That composition is also the only path by which a
header fact can reach the gate's message, so the ATs constrain the observable
contract, not an implementation shape. Same driving-port precedent as the
sibling `tests/bugs/des/test_carpaccio_gherkin_coupled_row_escape.py`.

RED-for-right-reason: scenarios (1)-(3) assert on parsed cell VALUES and on
rendered MESSAGE content against calls that execute fully today and return /
raise the wrong thing -- genuine semantic `AssertionError`s, never an
import/collection error. Scenario (4) is a negative guard, GREEN today and
after the fix: it locks that the missing-column diagnosis is never emitted for
a table whose Justification column is present but empty.
"""

from __future__ import annotations

import pytest

from des.cli.carpaccio_format import (
    SLICE_PLAN_CANONICAL_COLUMNS,
    GateError,
    Scenario,
    check_carpaccio,
    parse_slice_plan,
)


_ENTERING_SLICE = "slice-01"
_SLICE_MAX = 7
_OVER_CEILING_COUNT = 8  # > _SLICE_MAX -- engages the size-ceiling branch

#: A distinctive Justification-cell sentence -- distinctive so an assertion
#: failure shows unambiguously WHICH cell the parser put it in.
_JUSTIFICATION_PROSE = (
    "the three scenarios prove one indivisible end-to-end vertical and "
    "splitting them would leave neither half demoable"
)

_VALUE_STATEMENT = "ships the thin vertical an operator can demo"


def _canonical_header() -> str:
    """The canonical header line, derived from the parser's OWN SSOT
    (`SLICE_PLAN_CANONICAL_COLUMNS`) -- never a second hardcoded copy."""
    return "| " + " | ".join(SLICE_PLAN_CANONICAL_COLUMNS) + " |"


def _feature_delta(header_cells: tuple[str, ...], row_cells: tuple[str, ...]) -> str:
    """A minimal feature-delta carrying one `[REF] Slice Plan` table with the
    given header and a single data row."""
    header = "| " + " | ".join(header_cells) + " |"
    separator = "|" + "---|" * len(header_cells)
    row = "| " + " | ".join(row_cells) + " |"
    return (
        "## Wave: DISCUSS / [REF] Slice Plan\n"
        "\n"
        f"{header}\n"
        f"{separator}\n"
        f"{row}\n"
        "\n"
        "## Wave: DISTILL / [REF] Scenario list\n"
        "\n"
        "prose after the table\n"
    )


def _rendered_message(error: GateError) -> str:
    """The message an operator actually reads -- the gate emits `error` and
    `instruction` together as one single-line JSON verdict."""
    return (
        f"{error.payload.get('error', '')} {error.payload.get('instruction', '')}"
    ).strip()


def _scenarios(count: int) -> list[Scenario]:
    """`count` parsed `.feature` scenarios, each tagged for the entering slice
    and none carrying a per-scenario `@coupled` tag -- the shape of a real
    slice whose author annotated the PLAN ROW, which is the only coupling
    signal these ATs vary."""
    return [
        Scenario(
            slice_tags=(_ENTERING_SLICE,),
            has_coupled_tag=False,
            normalized_body=f"given step {i}\nwhen step {i}\nthen step {i}",
        )
        for i in range(count)
    ]


def _drive_gate(text: str, scenarios: list[Scenario]) -> dict[str, object] | GateError:
    """Compose exactly as `carpaccio_slice_gate.main` does (lines 917-930):
    parse the plan out of the feature-delta text, then run the carpaccio
    assertions over it. `GateError` is captured as a return value.

    Every caller passes at least one scenario tagged for the entering slice,
    so the no-scenarios-for-slice branch is never reached and the ONLY
    reachable rejections are the ones under observation (assertion 4, the
    mandatory-justification guard; assertion 1, the size ceiling).
    """
    plan = parse_slice_plan(text)
    try:
        return check_carpaccio(plan, scenarios, _ENTERING_SLICE, _SLICE_MAX)
    except GateError as exc:
        return exc


# ===========================================================================
# 1 -- RED-today core: every canonical column is resolved by its HEADER NAME
# ===========================================================================

#: Four header shapes that live in this repo today (39 distinct shapes were
#: censused). Each case: (header cells, row cells, expected parsed row).
#: `status=""` is the correct read of an ABSENT canonical column; a
#: non-canonical extra column ("Class", "ADD + REMOVE") is ignored.
_HEADER_SHAPES = {
    "canonical-5-col": (
        ("Slice", "Value statement", "Status", "Annotation", "Justification"),
        (
            _ENTERING_SLICE,
            _VALUE_STATEMENT,
            "pending",
            "@coupled",
            _JUSTIFICATION_PROSE,
        ),
        {
            "value_statement": _VALUE_STATEMENT,
            "status": "pending",
            "annotation": "@coupled",
            "justification": _JUSTIFICATION_PROSE,
        },
    ),
    "4-col-without-status": (
        ("Slice", "Value statement", "Annotation", "Justification"),
        (_ENTERING_SLICE, _VALUE_STATEMENT, "@coupled", _JUSTIFICATION_PROSE),
        {
            "value_statement": _VALUE_STATEMENT,
            "status": "",
            "annotation": "@coupled",
            "justification": _JUSTIFICATION_PROSE,
        },
    ),
    "6-col-with-leading-class": (
        (
            "Slice",
            "Class",
            "Value statement",
            "Status",
            "Annotation",
            "Justification",
        ),
        (
            _ENTERING_SLICE,
            "bugfix",
            _VALUE_STATEMENT,
            "pending",
            "@coupled",
            _JUSTIFICATION_PROSE,
        ),
        {
            "value_statement": _VALUE_STATEMENT,
            "status": "pending",
            "annotation": "@coupled",
            "justification": _JUSTIFICATION_PROSE,
        },
    ),
    "annotation-at-index-2-with-extra-column": (
        ("Slice", "Value statement", "Annotation", "ADD + REMOVE", "Justification"),
        (
            _ENTERING_SLICE,
            _VALUE_STATEMENT,
            "@coupled",
            "+src/des/cli/carpaccio_format.py",
            _JUSTIFICATION_PROSE,
        ),
        {
            "value_statement": _VALUE_STATEMENT,
            "status": "",
            "annotation": "@coupled",
            "justification": _JUSTIFICATION_PROSE,
        },
    ),
}


@pytest.mark.parametrize(
    ("header_cells", "row_cells", "expected"),
    [pytest.param(*case, id=shape) for shape, case in _HEADER_SHAPES.items()],
)
def test_slice_plan_columns_read_by_header_not_position(
    header_cells: tuple[str, ...],
    row_cells: tuple[str, ...],
    expected: dict[str, str],
) -> None:
    """Whatever the column layout, each canonical field must come from the
    cell the HEADER names -- an absent canonical column reads `''` and a
    non-canonical extra column is ignored.

    RED TODAY for every shape except `canonical-5-col`: `_build_slice_rows`
    reads by fixed offset from the `slice-NN` cell, so on
    `4-col-without-status` the `@coupled` tag lands in `status`, the
    Justification prose lands in `annotation`, and `justification` reads past
    the end of the row and stays `''`. `canonical-5-col` is GREEN today and
    after -- the pin that a header-driven read does not regress the layout
    that already works.
    """
    plan = parse_slice_plan(_feature_delta(header_cells, row_cells))
    row = plan.row_for(_ENTERING_SLICE)

    assert row is not None, (
        f"the {_ENTERING_SLICE!r} row must parse out of header={header_cells} "
        f"row={row_cells}; got plan={plan!r}"
    )
    observed = {
        "value_statement": row.value_statement,
        "status": row.status,
        "annotation": row.annotation,
        "justification": row.justification,
    }
    assert observed == expected, (
        "every canonical Slice Plan column must be resolved by its HEADER "
        f"CELL NAME, not by offset from the slice-id cell. header="
        f"{header_cells} -- expected {expected}, observed {observed}. A "
        "mismatch where 'annotation' holds the justification prose (and "
        "'justification' is empty) is the positional read: the header row is "
        "collected by parse_slice_plan_rows and then discarded."
    )


# ===========================================================================
# 2 -- RED-today: the operator DID annotate and DID justify, in the columns
# the header names -- the gate must honor the escape it promises
# ===========================================================================


def test_row_escape_is_honored_when_the_header_omits_the_status_column() -> None:
    """An over-ceiling slice whose table has no `Status` column but DOES carry
    `@coupled` under `Annotation` and prose under `Justification` must clear
    via `CoupledSliceAccepted` -- the author did exactly what the gate's own
    rejection message instructs.

    RED TODAY: the positional read puts `@coupled` in `status` and the prose in
    `annotation`, so `_COUPLED_TAG_RE.search(row.annotation)` is False and
    `row.justification` is `''` -- the escape silently does not apply and
    `CARPACCIO_SLICE_TOO_LARGE` fires on a fully compliant row. This is the
    operator-visible half of the defect: the artifact is correct, the gate says
    otherwise, and no edit to the PROSE can ever change the verdict.
    """
    text = _feature_delta(
        ("Slice", "Value statement", "Annotation", "Justification"),
        (_ENTERING_SLICE, _VALUE_STATEMENT, "@coupled", _JUSTIFICATION_PROSE),
    )

    result = _drive_gate(text, _scenarios(_OVER_CEILING_COUNT))

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "a slice whose Annotation column (named by the header) carries "
        "@coupled and whose Justification column carries prose must clear via "
        f"CoupledSliceAccepted -- observed "
        f"{getattr(result, 'payload', result)!r}. A rejection means the parser "
        "read those two cells positionally instead of by header name, so the "
        "escape the gate advertises is unreachable for this table layout."
    )


# ===========================================================================
# 3 -- RED-today: the message is the defect. A genuinely MISSING column must
# be named as such, never blamed on the prose
# ===========================================================================

#: The misdirecting phrasing: it tells the author their CONTENT is missing
#: when the COLUMN is. Every rewrite of the prose leaves the gate refusing.
_MISDIRECTING_PHRASE = "but records no justification"

#: A header that genuinely lacks a `Justification` column altogether.
_HEADER_WITHOUT_JUSTIFICATION = ("Slice", "Value statement", "Status", "Annotation")


def test_missing_justification_column_rejection_names_the_column_not_the_prose() -> (
    None
):
    """When the Slice Plan header carries NO `Justification` column at all,
    the rejection must (1) name the missing column, (2) show the header as
    FOUND verbatim alongside the EXPECTED canonical header, and (3) never use
    the content-blaming phrasing that sends the author to rewrite prose that
    has nowhere to live.

    RED TODAY on all three: `_check_value_annotation` emits
    `slice slice-01 carries annotation '@coupled' but records no
    justification` -- which names neither the missing column nor either
    header, and IS the misdirecting phrasing.
    """
    text = _feature_delta(
        _HEADER_WITHOUT_JUSTIFICATION,
        (_ENTERING_SLICE, _VALUE_STATEMENT, "pending", "@coupled"),
    )

    result = _drive_gate(text, _scenarios(1))

    assert isinstance(result, GateError), (
        "an annotated escape row on a table with no Justification column "
        f"must still be rejected -- observed {result!r}"
    )
    message = _rendered_message(result)
    found_header = "| " + " | ".join(_HEADER_WITHOUT_JUSTIFICATION) + " |"

    assert "Justification" in message, (
        "the rejection must NAME the missing column ('Justification', as "
        "spelled in SLICE_PLAN_CANONICAL_COLUMNS) so the author knows a "
        f"COLUMN is absent, not that prose is missing -- observed {message!r}"
    )
    assert found_header in message, (
        "the rejection must show the header row it FOUND, verbatim, so the "
        f"author can see which table is malformed -- expected {found_header!r} "
        f"in the message; observed {message!r}"
    )
    assert _canonical_header() in message, (
        "the rejection must show the EXPECTED canonical header so the fix is "
        f"copy-pasteable -- expected {_canonical_header()!r} in the message; "
        f"observed {message!r}"
    )
    assert _MISDIRECTING_PHRASE not in message.lower(), (
        f"the rejection must NOT carry {_MISDIRECTING_PHRASE!r}: it names a "
        "CONTENT problem when the cause is a MISSING COLUMN, so the author "
        "rewrites correct prose forever and no rewrite can ever clear the "
        f"gate -- observed {message!r}"
    )


# ===========================================================================
# 4 -- negative guard (GREEN today and after): a PRESENT-but-empty
# Justification cell must never be diagnosed as a missing column
# ===========================================================================


@pytest.mark.negative_at
def test_empty_justification_cell_is_not_diagnosed_as_a_missing_column() -> None:
    """GUARD: when the `Justification` column IS present in the header but the
    cell is empty, the author's repair is to WRITE the prose -- so the
    rejection must stay content-directed and must NOT emit the missing-column
    diagnosis (whose signature is the canonical header shown as EXPECTED).

    Proves the fix DISTINGUISHES the two failure modes instead of replacing
    one blanket message with another: conflating them re-creates the defect in
    mirror image, routing an author with a real empty cell to add a column
    that is already there.
    """
    text = _feature_delta(
        ("Slice", "Value statement", "Status", "Annotation", "Justification"),
        (_ENTERING_SLICE, _VALUE_STATEMENT, "pending", "@coupled", ""),
    )

    result = _drive_gate(text, _scenarios(1))

    assert isinstance(result, GateError), (
        "an annotated escape row with an empty Justification cell must still "
        f"be rejected -- observed {result!r}"
    )
    message = _rendered_message(result)
    assert _canonical_header() not in message, (
        "a PRESENT-but-empty Justification cell is a content problem, not a "
        "malformed header -- the rejection must not carry the missing-column "
        f"diagnosis ({_canonical_header()!r} shown as the expected header); "
        f"observed {message!r}"
    )
    assert _ENTERING_SLICE in message and "justification" in message.lower(), (
        "the rejection must still name the offending slice and direct the "
        f"author to record a justification -- observed {message!r}"
    )
