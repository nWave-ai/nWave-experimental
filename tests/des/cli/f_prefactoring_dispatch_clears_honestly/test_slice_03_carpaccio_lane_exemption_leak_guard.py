"""slice-03 AT -- the negative leak-guard on ``check_carpaccio``'s lane exemption.

# @feature-f-prefactoring-dispatch-clears-honestly
# @slice-03

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone). Design reference:
`docs/feature/f-prefactoring-dispatch-clears-honestly/feature-delta.md`
(`## Wave: DESIGN / [REF] Per-Locus Consulting Mechanism`, slice-03a code
block: `_lane_profile_for_slice` + `check_carpaccio`'s
`LaneAtExemptionAccepted` branch).

Reconciliation note (2026-07-05, feature-delta `[REF] Slice Plan` slice-03
row + the "DELIVER reconciliation" note): the slice-03 carpaccio-consultation
MECHANISM already landed bundled inside commit `d41531cf8` -- `_lane_profile_
for_slice` exists and `check_carpaccio` already consults it (verified by
direct read of `src/des/cli/carpaccio_format.py:626-636` before authoring
this file). What is MISSING for the slice-03 seal is this file: the dedicated
AT proving (a) the positive lane exemption, and, the slice's own keystone,
(b) the NEGATIVE leak-guard -- an ordinary un-annotated 0-AT row, and a 0-AT
row carrying an UNRELATED recognized annotation token (`@coupled`), must both
still be rejected the ordinary way. Outcome KPI 2 (feature-delta `[REF]
Outcome KPIs`): "0 leaked exemptions across every non-lane slice dispatch."

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
`des.cli.carpaccio_format.check_carpaccio` directly -- the SAME production
function `carpaccio_slice_gate.main` calls at assertion 4 -- never a bare
`_lane_profile_for_slice`/`LaneProfile` shape assertion with no port between.
Mirrors the established driving-port precedent in the sibling slice-02 file
`test_slice_02_green_to_green_seal.py`'s `_invoke_check_carpaccio` helper
(same production function, same GateError-captured-as-return-value shape).

GREEN note: since the mechanism already exists, AT-1 (positive) and AT-2
(unannotated leak-guard) may run GREEN immediately -- that pins the already-
delivered behavior, it does not indicate nothing was missing (the FILE
itself, tagged @slice-03, is what closes the seal-discovery gap). AT-3 (the
`@coupled`-annotation leak-guard) is a genuinely NEW assertion never
previously exercised anywhere in this feature's test suite (confirmed by
grep across `tests/des/cli/f_prefactoring_dispatch_clears_honestly/` before
authoring) -- if `_lane_profile_for_slice` or its caller ever loosens to
treat ANY recognized annotation token as the prefactoring exemption (instead
of `@prefactoring` specifically), this is the one AT that goes RED.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.cli.carpaccio_format import (
    GateError,
    SlicePlan,
    SlicePlanRow,
    check_carpaccio,
)


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "synthetic-carpaccio-leak-guard-feature"
_SLICE_MAX = 10


# --- fixtures ----------------------------------------------------------------


def _plan(entering_slice: str, annotation: str, justification: str) -> SlicePlan:
    """A single-row Slice Plan whose entering-slice row carries ``annotation``.

    Mirrors the sibling `_prefactoring_plan`/`_unannotated_plan` helpers in
    `test_slice_02_green_to_green_seal.py` -- one shared shape, parametrized
    over the Annotation cell so the three ATs below differ ONLY in that one
    input.
    """
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=entering_slice,
                value_statement="a 0-AT slice exercising the carpaccio lane exemption",
                status="pending",
                annotation=annotation,
                justification=justification,
            ),
        )
    )


def _invoke(repo: Path, plan: SlicePlan, entering_slice: str):
    """Best-effort `check_carpaccio` call, `GateError` captured as a return value."""
    try:
        return check_carpaccio(
            plan, [], entering_slice, _SLICE_MAX, repo=repo, feature_id=_FEATURE_ID
        )
    except GateError as exc:
        return exc


# AT-1 (positive -- @prefactoring annotation clears the AT-count check) -------


def test_prefactoring_annotated_zero_at_slice_clears_carpaccio(tmp_path: Path) -> None:
    """A 0-AT slice-plan row annotated `@prefactoring` CLEARS `check_carpaccio`
    -- no `no-scenarios-for-slice` rejection -- because `_lane_profile_for_
    slice` resolves the datum's `AtRequirement.EXEMPT` entry.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: feature-delta.md (Wave: DESIGN / [REF] Per-Locus
    Consulting Mechanism, slice-03a code block).
    """
    plan = _plan(
        "slice-03",
        annotation="@prefactoring",
        justification="a behavior-preserving refactor",
    )

    result = _invoke(tmp_path, plan, "slice-03")

    assert (
        isinstance(result, dict) and result.get("event") == "LaneAtExemptionAccepted"
    ), (
        "a @prefactoring-annotated 0-AT slice must clear check_carpaccio's "
        "no-scenarios-for-slice branch with a LaneAtExemptionAccepted event -- "
        f"the lane-datum exemption did not fire. observed={result!r}"
    )
    assert result.get("lane") == "prefactoring", (
        "the cleared payload must name the lane the exemption came from -- "
        f"observed lane={result.get('lane')!r}"
    )


# AT-2 (negative leak-guard -- unannotated 0-AT row still rejected) -----------


def test_unannotated_zero_at_slice_still_rejected_the_ordinary_way(
    tmp_path: Path,
) -> None:
    """KPI-2 keystone: a 0-AT slice-plan row with NO `@prefactoring`
    annotation is STILL rejected `no-scenarios-for-slice` -- the exemption
    does NOT leak to an ordinary un-annotated 0-AT slice.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: feature-delta.md (Wave: DISCUSS / [REF] Outcome KPIs,
    KPI 2 guardrail: "0 leaked exemptions across every non-lane slice
    dispatch").
    """
    plan = _plan("slice-03", annotation="", justification="")

    result = _invoke(tmp_path, plan, "slice-03")

    assert (
        isinstance(result, GateError)
        and result.payload.get("reason") == "no-scenarios-for-slice"
    ), (
        "an un-annotated 0-AT slice must still be rejected no-scenarios-for-"
        "slice -- the @prefactoring lane exemption must not leak to a plain "
        f"slice carrying no lane annotation at all. observed={result!r}"
    )


# AT-3 (negative leak-guard -- an unrelated recognized annotation token does --
# NOT get the prefactoring exemption) -----------------------------------------


def test_coupled_annotation_does_not_get_prefactoring_exemption(
    tmp_path: Path,
) -> None:
    """A 0-AT slice-plan row annotated `@coupled` (a DIFFERENT recognized
    Annotation-column token, sibling to `@prefactoring` in the SAME
    `_ANNOTATION_ESCAPE_RE` grammar) does NOT get the prefactoring AT-count
    exemption -- it is still rejected `no-scenarios-for-slice`, exactly like
    the wholly-unannotated case (AT-2). `_lane_profile_for_slice` resolves
    ONLY the `@prefactoring` token to `LANE_PROFILES["prefactoring"]`;
    recognizing ANY escape-grammar token as the lane exemption would be the
    leak this AT exists to catch.

    A non-empty `justification` isolates the annotation-TOKEN as the sole
    variable under test: `_check_value_annotation` (assertion 4) demands a
    justification for any `_ANNOTATION_ESCAPE_RE` match, so an empty
    justification here would raise `CARPACCIO_SLICE_TOO_LARGE` for an
    unrelated reason before ever reaching the no-scenarios-for-slice branch
    this AT is pinning.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: feature-delta.md (Wave: DISCUSS / [REF] Outcome KPIs,
    KPI 2 guardrail) + `_lane_profile_for_slice`'s own docstring ("the
    negative path -- an unannotated 0-AT slice -- then falls through to the
    existing rejection").
    """
    plan = _plan(
        "slice-03",
        annotation="@coupled",
        justification="an unrelated coupled-AT-group annotation, not a lane",
    )

    result = _invoke(tmp_path, plan, "slice-03")

    assert (
        isinstance(result, GateError)
        and result.payload.get("reason") == "no-scenarios-for-slice"
    ), (
        "a 0-AT slice annotated @coupled (an unrelated recognized "
        "Annotation-column token) must still be rejected "
        "no-scenarios-for-slice -- ONLY @prefactoring resolves the lane "
        f"exemption, no other escape-grammar token does. observed={result!r}"
    )
