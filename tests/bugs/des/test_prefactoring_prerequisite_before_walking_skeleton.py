"""Regression -- `_check_walking_skeleton_first` (`carpaccio_format.py`,
~line 1505) unconditionally demands the `@walking-skeleton`-tagged Slice Plan
row sit at index 0, with no exception for a legitimate behavior-preserving
`@prefactoring` prerequisite placed immediately in front of it. A Slice Plan
whose FIRST row is a single `@prefactoring` step (e.g. an extract-interface
refactor that must land before the walking skeleton can be written) is
rejected today with the generic::

    GateError(44, {"event": "CARPACCIO_SLICE_TOO_LARGE",
                   "error": "the @walking-skeleton slice is not ordered "
                            "first (found at row 2)",
                   "instruction": "order the @walking-skeleton slice first "
                                  "in the plan"})

-- even though nothing in that ordering endangers walking-skeleton-first
discipline: any number of `@prefactoring` rows before the walking skeleton is
a recognized, behavior-preserving prerequisite, not an ad-hoc reordering.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero `src/` edits): `_check_walking_skeleton_first` must allow `ws_index > 0`
IFF every row in the prefix `[0, ws_index)` carries `@prefactoring`
(`_PREFACTORING_TAG_RE`). The valid shape is `prefactoring* -> first
behavioral walking skeleton -> later behavioral slices` -- N>=0 valid
`@prefactoring` rows may precede it; COUNT is NEVER a reason to refuse. Only
the CONTENT of the prefix matters: a prefix containing so much as one row
that is NOT `@prefactoring` must still raise `CARPACCIO_SLICE_TOO_LARGE`,
with a message NAMING the specific offending row's `slice_id` and the reason
it disqualifies (neither the walking skeleton nor a recognized
`@prefactoring` prerequisite) -- not the old generic "not ordered first"
text. `ws_index is None` and `ws_index == 0` are UNCHANGED (assertion 1/2's
job, and `des walking-skeleton-gate`'s job at feature-end, respectively --
NOT this assertion's job to invent a new rejection for "no walking skeleton
at all").

EXPLICITLY OUT OF SCOPE for this fix: a `@prefactoring` row placed AFTER the
walking skeleton must keep clearing exactly as it does today -- this is the
SHIPPED shape of `docs/feature/f-prefactoring-dispatch-clears-honestly/
feature-delta.md` (`@walking-skeleton` at slice-01, `@prefactoring` at
slice-03); rejecting that arrangement would be a false positive on shipped
work. `test_prefactoring_row_after_walking_skeleton_still_clears` below pins
this (P2 in the fix's task list).

Driving surface (Mandate 16, no-direct-domain-testing): `_check_walking_
skeleton_first` and `check_carpaccio` are the SAME functions the carpaccio
gate's `main()` calls at assertion 3 -- direct-function-import is the
established precedent for a pure-function format assertion in this module
(see `_no_scenarios_rejection` imported directly in
`test_carpaccio_no_scenarios_message_lists_pytest_path.py`).

RED-for-right-reason: the regression scenario
(`test_prefactoring_row_immediately_before_walking_skeleton_clears`, P1) MUST
fail with today's real `GateError` ("the @walking-skeleton slice is not
ordered first") -- a genuine assertion on the defect, never an import or
collection error. The named-rejection guards (N1, N3) will also fail today
(they assert the NEW specific-naming message, which does not exist yet) --
expected and correct. `test_multiple_prefactoring_rows_before_walking_
skeleton_clear` pins that COUNT is never a refusal axis (N>=0 valid
`@prefactoring` rows must clear). The end-to-end guard (N4) proves the
ordering fix does not bypass the EXISTING `_check_value_annotation`
mandatory-justification check -- it too fails today because assertion 3
raises its old generic message before assertion 4 ever runs. P2/P3/P4 pin
UNCHANGED behavior and must already PASS before and after the fix.
"""

from __future__ import annotations

import pytest

from des.cli.carpaccio_format import (
    GateError,
    Scenario,
    SlicePlan,
    SlicePlanRow,
    _check_walking_skeleton_first,
    check_carpaccio,
)


_SLICE_MAX = 7

_PREFACTORING_JUSTIFICATION = (
    "extract the shared port interface before the walking skeleton can "
    "drive it -- behavior-preserving, no observable change"
)


# --- shared fixture builders -------------------------------------------


def _row(
    slice_id: str,
    *,
    annotation: str = "",
    justification: str = "",
) -> SlicePlanRow:
    return SlicePlanRow(
        slice_id=slice_id,
        value_statement=f"value statement for {slice_id}",
        status="pending",
        annotation=annotation,
        justification=justification,
    )


def _plan(*rows: SlicePlanRow) -> SlicePlan:
    return SlicePlan(rows=tuple(rows))


def _invoke_ws_check(plan: SlicePlan) -> GateError | None:
    """Best-effort `_check_walking_skeleton_first` call, `GateError`
    captured as a return value (mirrors the sibling driving-port helpers in
    this test package, e.g. `test_carpaccio_gherkin_coupled_row_escape.py`).
    """
    try:
        _check_walking_skeleton_first(plan)
    except GateError as exc:
        return exc
    return None


# ===========================================================================
# Positive -- these arrangements must NOT raise
# ===========================================================================


def test_prefactoring_row_immediately_before_walking_skeleton_clears() -> None:
    """P1 -- THE REGRESSION. Exactly one `@prefactoring` row (with a
    non-empty Justification) at index 0, `@walking-skeleton` at index 1,
    further behavior rows after -- must NOT raise.

    RED TODAY: `_check_walking_skeleton_first` raises unconditionally
    whenever `ws_index != 0`, regardless of the prefix's content -- this
    exact arrangement is refused with "the @walking-skeleton slice is not
    ordered first (found at row 2)" even though the prefix is a legitimate,
    behavior-preserving prerequisite.
    """
    plan = _plan(
        _row(
            "slice-01",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
        _row("slice-02", annotation="@walking-skeleton"),
        _row("slice-03"),
    )

    result = _invoke_ws_check(plan)

    assert result is None, (
        "a single @prefactoring row immediately before the @walking-skeleton "
        "row must clear _check_walking_skeleton_first -- observed a raised "
        f"GateError instead: {result!r}"
    )


def test_prefactoring_row_after_walking_skeleton_still_clears() -> None:
    """P2 -- real-shape guard, pinning the SHIPPED plan shape (explicitly
    OUT OF SCOPE for this fix): `@walking-skeleton` at index 0,
    `@prefactoring` later (index 2, mirroring
    `docs/feature/f-prefactoring-dispatch-clears-honestly/feature-delta.md`)
    -- must NOT raise, exactly as it does not raise today. A fix that
    rejects a `@prefactoring` row occurring AFTER the walking skeleton would
    be a false positive on shipped work.
    """
    plan = _plan(
        _row("slice-01", annotation="@walking-skeleton"),
        _row("slice-02"),
        _row(
            "slice-03",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
    )

    result = _invoke_ws_check(plan)

    assert result is None, (
        "a @prefactoring row occurring AFTER the @walking-skeleton row "
        "(the shipped real-world shape) must clear -- observed a raised "
        f"GateError: {result!r}"
    )


def test_no_walking_skeleton_row_at_all_clears() -> None:
    """P3 -- `ws_index is None` (no `@walking-skeleton` row anywhere) --
    UNCHANGED from today. "No walking skeleton at all" is NOT this
    assertion's job; `des walking-skeleton-gate` owns that check at
    feature-end. Must NOT raise here.
    """
    plan = _plan(
        _row("slice-01"),
        _row("slice-02", annotation="@prefactoring", justification="x"),
        _row("slice-03"),
    )

    result = _invoke_ws_check(plan)

    assert result is None, (
        "a plan with no @walking-skeleton row at all must clear "
        f"_check_walking_skeleton_first -- observed {result!r}"
    )


def test_walking_skeleton_first_with_nothing_before_it_clears() -> None:
    """P4 -- `ws_index == 0` with nothing before it -- UNCHANGED from today.
    Must NOT raise.
    """
    plan = _plan(
        _row("slice-01", annotation="@walking-skeleton"),
        _row("slice-02"),
    )

    result = _invoke_ws_check(plan)

    assert result is None, (
        f"a @walking-skeleton row already first must clear -- observed {result!r}"
    )


# ===========================================================================
# Negative -- these arrangements must raise CARPACCIO_SLICE_TOO_LARGE,
# naming the specific offending row
# ===========================================================================


@pytest.mark.negative_at
def test_plain_behavior_row_before_walking_skeleton_rejects_naming_that_row() -> None:
    """N1 -- a plain behavior row (no annotation) at index 0,
    `@walking-skeleton` at index 1 -- must be refused, and the rejection
    message must NAME the offending row's `slice_id` ("slice-01") and
    explain it is neither the walking skeleton nor a recognized
    `@prefactoring` prerequisite -- NOT the old generic "not ordered first"
    text.
    """
    plan = _plan(
        _row("slice-01"),
        _row("slice-02", annotation="@walking-skeleton"),
    )

    result = _invoke_ws_check(plan)

    assert isinstance(result, GateError), (
        "an unannotated row before the @walking-skeleton row must be "
        f"refused -- observed {result!r}"
    )
    assert result.exit_code == 44, result.payload
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload
    message = str(result.payload.get("error", ""))
    assert "slice-01" in message, (
        "the rejection must NAME the offending row's slice_id ('slice-01') "
        f"-- observed message={message!r}"
    )
    assert "prefactoring" in message.lower(), (
        "the rejection must explain the row is not a recognized "
        f"@prefactoring prerequisite -- observed message={message!r}"
    )


def test_multiple_prefactoring_rows_before_walking_skeleton_clear() -> None:
    """Cardinality is NOT a refusal axis: THREE valid `@prefactoring` rows
    (each with a non-empty Justification) at indexes 0, 1, 2,
    `@walking-skeleton` at index 3, a later behavioral row after it -- must
    NOT raise. The valid shape is `prefactoring* -> first behavioral walking
    skeleton -> later behavioral slices`: N>=0 valid `@prefactoring` rows may
    precede the walking skeleton, with no cap. Three rows (not merely two)
    pins "no cap", not just "two is allowed" -- an arrangement is refused for
    what a row IS (a non-`@prefactoring`, non-walking-skeleton row), never
    for how many `@prefactoring` rows there are.
    """
    plan = _plan(
        _row(
            "slice-01",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
        _row(
            "slice-02",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
        _row(
            "slice-03",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
        _row("slice-04", annotation="@walking-skeleton"),
        _row("slice-05"),
    )

    result = _invoke_ws_check(plan)

    assert result is None, (
        "three valid @prefactoring rows immediately before the "
        "@walking-skeleton row must clear -- count is never a refusal axis "
        f"-- observed a raised GateError instead: {result!r}"
    )


@pytest.mark.negative_at
def test_non_prefactoring_row_in_mixed_prefix_rejects_naming_that_row() -> None:
    """N3 -- mixed prefix: `@prefactoring` at index 0 (compliant), a plain
    behavior row at index 1 (NOT `@prefactoring`), `@walking-skeleton` at
    index 2 -- must be refused, naming the plain row (index 1, "slice-02")
    as the disqualifying one.
    """
    plan = _plan(
        _row(
            "slice-01",
            annotation="@prefactoring",
            justification=_PREFACTORING_JUSTIFICATION,
        ),
        _row("slice-02"),
        _row("slice-03", annotation="@walking-skeleton"),
    )

    result = _invoke_ws_check(plan)

    assert isinstance(result, GateError), (
        "a mixed prefix with one compliant @prefactoring row and one plain "
        f"row must still be refused -- observed {result!r}"
    )
    assert result.exit_code == 44, result.payload
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload
    message = str(result.payload.get("error", ""))
    assert "slice-02" in message, (
        "the rejection must NAME the non-@prefactoring row ('slice-02') as "
        f"the disqualifying one -- observed message={message!r}"
    )


@pytest.mark.negative_at
def test_prefactoring_row_with_empty_justification_still_flags_missing_justification() -> (
    None
):
    """N4 -- end-to-end via `check_carpaccio`, guarding the EXISTING
    mechanism: a `@prefactoring` row at index 0 with an EMPTY Justification
    cell, `@walking-skeleton` at index 1 -- must still be refused by the
    EXISTING `_check_value_annotation` (assertion 4) missing-justification
    message, proving the ordering fix does NOT silently bypass it. This is
    NOT `_check_walking_skeleton_first`'s job to duplicate -- assertion 4
    already rejects a malformed `@prefactoring` row and runs immediately
    after assertion 3 in `check_carpaccio`.
    """
    plan = _plan(
        _row("slice-01", annotation="@prefactoring", justification=""),
        _row("slice-02", annotation="@walking-skeleton"),
    )
    scenarios = [
        Scenario(
            slice_tags=("slice-01",),
            has_coupled_tag=False,
            normalized_body="given step\nwhen step\nthen step",
        ),
        Scenario(
            slice_tags=("slice-02",),
            has_coupled_tag=False,
            normalized_body="given step\nwhen step\nthen step",
        ),
    ]

    try:
        result: dict[str, object] | GateError = check_carpaccio(
            plan, scenarios, "slice-02", _SLICE_MAX
        )
    except GateError as exc:
        result = exc

    assert isinstance(result, GateError), (
        "a @prefactoring row with an empty Justification cell must still "
        f"be refused end-to-end via check_carpaccio -- observed {result!r}"
    )
    assert result.exit_code == 44, result.payload
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload
    message = str(result.payload.get("error", ""))
    assert "slice-01" in message, (
        "the existing missing-justification rejection must still NAME the "
        f"offending row ('slice-01') -- observed message={message!r}"
    )
    assert "@prefactoring" in message, (
        "the existing missing-justification rejection must still name the "
        f"annotation ('@prefactoring') -- observed message={message!r}"
    )
    assert "no justification" in message, (
        "the ordering fix must not bypass the EXISTING missing-justification "
        f"wording -- observed message={message!r}"
    )
