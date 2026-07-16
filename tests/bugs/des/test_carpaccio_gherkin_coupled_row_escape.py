"""Regression -- `check_carpaccio`'s Gherkin branch (Path B, the
`_check_slice_size` -> `_check_slice_size_count` chain) computes
`all_coupled` from PER-SCENARIO `@coupled` tags, ignoring the ENTERING
slice's own Slice-Plan ROW annotation -- even though the pytest-regression
branch (Path A) was fixed (b85dee0f9) to read the row instead. The gate's own
`CARPACCIO_SLICE_TOO_LARGE` rejection message instructs the operator to
"annotate the slice-plan row @coupled with a recorded justification" -- true
for pytest-regression mode, FALSE for Gherkin mode. A Gherkin slice whose
Slice-Plan ROW carries `@coupled` + a justification, but whose individual
`.feature` scenarios are NOT each re-tagged `@coupled`, is still refused over
the ceiling: the gate's own escape instructions do not work for the mode
they are shown to.

Found in `src/des/cli/carpaccio_format.py`:

* Path A (`check_carpaccio`, ~line 880, pytest-regression branch)::

      all_coupled = bool(_COUPLED_TAG_RE.search(entering_row.annotation))

  -- reads `@coupled` from the SLICE-PLAN ROW. This is the correct,
  already-fixed shape (b85dee0f9: "the signal is in the plan row").

* Path B (`_check_slice_size`, ~line 1030, Gherkin branch)::

      all_coupled = bool(slice_scenarios) and all(
          s.has_coupled_tag for s in slice_scenarios
      )

  -- BUG: requires EVERY scenario to carry its own `@coupled` tag; the
  entering row's `annotation` is never consulted on this path.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero `src/` edits): Path B must derive `all_coupled` from the SLICE-PLAN ROW
(`entering_row.annotation`, mirroring Path A) so the row alone suffices for
every `at_kind` -- the design signal lives in the plan, mode-agnostic.
Per-scenario `@coupled` tags may remain an optional/deprecated mirror, but
must not be REQUIRED. The mandatory-justification guard (assertion 4,
`_check_value_annotation`) is unaffected and must keep firing regardless of
this fix.

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
`des.cli.carpaccio_format.check_carpaccio` directly -- the SAME production
function `carpaccio_slice_gate.main` calls at assertion 1, and the SAME
driving-port precedent the sibling pytest-regression regression AT
(`tests/bugs/test_carpaccio_pytest_regression_coupled_ceiling.py`, the
already-fixed Path-A twin of this exact defect family) established for this
identical fix locus.

RED-for-right-reason: the core scenario (`test_gherkin_row_level_...`) and
the message-self-consistency scenario's second half
(`test_gherkin_ceiling_rejection_names_row_escape_and_the_named_escape_
actually_clears_it`) both assert `result.get("event") ==
"CoupledSliceAccepted"` against a call that TODAY raises `GateError`
(`CARPACCIO_SLICE_TOO_LARGE`) instead -- a genuine semantic `AssertionError`,
never an import/collection error. The pytest-regression pin
(`test_pytest_regression_row_level_coupled_escape_still_clears`) and the two
negative guards are GREEN today and after the fix -- they lock the fix does
not regress Path A or open a blanket, unconditional escape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from des.cli.carpaccio_format import (
    GateError,
    Scenario,
    SlicePlan,
    SlicePlanRow,
    check_carpaccio,
)


if TYPE_CHECKING:
    from pathlib import Path


_ENTERING_SLICE = "slice-01"
_SLICE_MAX = 7
_OVER_CEILING_COUNT = 8  # > _SLICE_MAX -- engages the size-ceiling branch

_COUPLING_JUSTIFICATION = (
    "a cohesive end-to-end Gherkin scenario group covering one user "
    "journey's full happy-path and error-path; splitting it across slices "
    "would break the single vertical it proves"
)


# --- shared fixture builders ---------------------------------------------


def _plan(annotation: str, justification: str) -> SlicePlan:
    """A single-row Slice Plan whose entering-slice row carries `annotation`
    and `justification` -- the only two inputs the scenarios below vary."""
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=_ENTERING_SLICE,
                value_statement="a cohesive end-to-end Gherkin scenario group",
                status="pending",
                annotation=annotation,
                justification=justification,
            ),
        )
    )


def _scenarios(count: int, *, coupled_tag_each: bool = False) -> list[Scenario]:
    """`count` parsed `.feature` scenarios, each tagged for the entering
    slice. `coupled_tag_each=False` (the default, and the exact shape of a
    real-world slice whose author annotated the PLAN ROW but never went back
    to re-tag every individual scenario) is the shape that exercises the
    defect; `coupled_tag_each=True` is never needed below because the fix
    under test must clear the ceiling from the ROW alone."""
    return [
        Scenario(
            slice_tags=(_ENTERING_SLICE,),
            has_coupled_tag=coupled_tag_each,
            normalized_body=f"given step {i}\nwhen step {i}\nthen step {i}",
        )
        for i in range(count)
    ]


def _invoke(
    plan: SlicePlan, scenarios: list[Scenario]
) -> dict[str, object] | GateError:
    """Best-effort `check_carpaccio` call in (default) gherkin mode,
    `GateError` captured as a return value (mirrors the sibling
    pytest-regression driving-port helper)."""
    try:
        return check_carpaccio(plan, scenarios, _ENTERING_SLICE, _SLICE_MAX)
    except GateError as exc:
        return exc


# ===========================================================================
# 1 -- RED-today core: the SLICE-PLAN ROW escape must be honored in Gherkin
# mode, exactly like it already is in pytest-regression mode
# ===========================================================================


def test_gherkin_row_level_coupled_escape_clears_ceiling_without_per_scenario_tags() -> (
    None
):
    """A Gherkin slice with MORE scenarios than the ceiling, whose entering
    Slice-Plan row is annotated `@coupled` with a non-empty Justification,
    must clear via `CoupledSliceAccepted` even though NOT ONE of its
    `.feature` scenarios carries its own `@coupled` tag -- the row alone is
    authoritative, mirroring the pytest-regression branch (ADR-028 D2).

    RED TODAY: `_check_slice_size`'s `all_coupled` derivation requires EVERY
    scenario to carry `has_coupled_tag=True`; since none do here, it computes
    `all_coupled=False` and `_check_slice_size_count` raises `GateError`
    (`CARPACCIO_SLICE_TOO_LARGE`) instead of returning the acceptance dict --
    even though `SlicePlanRow.annotation` already carries the exact
    `@coupled` signal the pytest-regression path reads for the same escape.
    """
    plan = _plan(annotation="@coupled", justification=_COUPLING_JUSTIFICATION)
    scenarios = _scenarios(_OVER_CEILING_COUNT, coupled_tag_each=False)

    result = _invoke(plan, scenarios)

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "a Gherkin slice whose entering Slice-Plan ROW carries @coupled + a "
        "recorded justification must clear via CoupledSliceAccepted even "
        "when no individual scenario carries a @coupled tag -- observed "
        f"{result!r} (a raised GateError means Path B still derives "
        "all_coupled from per-scenario tags instead of the plan row)"
    )
    assert result.get("at_count") == _OVER_CEILING_COUNT, (
        "CoupledSliceAccepted must report the true scenario count -- "
        f"observed {result.get('at_count')!r}"
    )


# ===========================================================================
# 2 -- pin: the pytest-regression row-level escape (Path A, already fixed)
# must NOT regress while Path B is being fixed
# ===========================================================================


def test_pytest_regression_row_level_coupled_escape_still_clears(
    tmp_path: Path,
) -> None:
    """The SAME row-level `@coupled` + justification escape, in
    `at_kind="pytest-regression"` mode, must keep clearing exactly as it does
    today (Path A, `check_carpaccio` ~line 880) -- this AT locks that fixing
    Path B (the Gherkin branch) does not disturb the already-correct Path A.
    """
    plan = _plan(annotation="@coupled", justification=_COUPLING_JUSTIFICATION)
    regression_file = tmp_path / "test_regression_fixture.py"
    functions = "\n\n".join(
        f"def test_case_{i}():\n    assert {i} == {i}"
        for i in range(_OVER_CEILING_COUNT)
    )
    regression_file.write_text(functions + "\n", encoding="utf-8")

    try:
        result: dict[str, object] | GateError = check_carpaccio(
            plan,
            [],
            _ENTERING_SLICE,
            _SLICE_MAX,
            at_kind="pytest-regression",
            regression_test_file=regression_file,
        )
    except GateError as exc:
        result = exc

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "a pytest-regression slice with an entering-slice row annotated "
        "@coupled + a recorded justification must keep clearing via "
        f"CoupledSliceAccepted -- observed {result!r} (Path A must be "
        "unaffected by the Path-B fix)"
    )
    assert result.get("at_count") == _OVER_CEILING_COUNT, result


# ===========================================================================
# 3 -- escape is not a free pass: no row-level @coupled (or @coupled without
# a justification) must still refuse an over-ceiling Gherkin slice
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("annotation", "justification"),
    [
        pytest.param("", "", id="no-annotation-at-all"),
        pytest.param("@coupled", "", id="coupled-annotation-but-no-justification"),
    ],
)
def test_gherkin_over_ceiling_slice_without_a_valid_row_escape_still_rejected(
    annotation: str, justification: str
) -> None:
    """GUARD: the SAME over-ceiling Gherkin slice, but the entering
    Slice-Plan row carries no VALID `@coupled` + justification escape (either
    no annotation at all, or `@coupled` with an empty Justification cell),
    must still raise `CARPACCIO_SLICE_TOO_LARGE` -- both BEFORE and AFTER the
    fix. Proves the fix reads the row's own annotation+justification rather
    than opening the escape to every over-ceiling Gherkin slice
    unconditionally, and that the mandatory-justification guard (assertion
    4) keeps firing regardless of `at_kind`.
    """
    plan = _plan(annotation=annotation, justification=justification)
    scenarios = _scenarios(_OVER_CEILING_COUNT, coupled_tag_each=False)

    result = _invoke(plan, scenarios)

    assert isinstance(result, GateError), (
        "an over-ceiling Gherkin slice with no valid row-level @coupled + "
        f"justification escape must still be rejected -- observed {result!r}"
    )
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload


# ===========================================================================
# 4 -- message<->behavior self-consistency: the rejection names the ROW
# annotation as the escape, and the ROW annotation is what actually clears it
# ===========================================================================


def test_gherkin_ceiling_rejection_names_row_escape_and_the_named_escape_actually_clears_it() -> (
    None
):
    """The `CARPACCIO_SLICE_TOO_LARGE` rejection instructs the operator to
    "annotate the slice-plan row @coupled with a recorded justification" --
    this instruction names the ROW, not per-scenario tags. Doing EXACTLY
    what the message says (annotating the row, touching no scenario tags)
    must then actually clear the gate -- message and honored escape must
    agree, for Gherkin mode exactly as they already do for pytest-regression
    mode.

    RED TODAY (second half only): the message already names the row (GREEN
    today -- this AT locks that wording does not regress), but following it
    exactly does NOT clear the gate in Gherkin mode -- the same Path-B defect
    as the core scenario above.
    """
    unescaped_plan = _plan(annotation="", justification="")
    scenarios = _scenarios(_OVER_CEILING_COUNT, coupled_tag_each=False)

    rejection = _invoke(unescaped_plan, scenarios)

    assert isinstance(rejection, GateError), (
        "an over-ceiling Gherkin slice with no row annotation must be "
        f"rejected before this message-content check can run -- got {rejection!r}"
    )
    message = (
        str(rejection.payload.get("error", ""))
        + " "
        + str(rejection.payload.get("instruction", ""))
    ).lower()
    assert "slice-plan row" in message and "@coupled" in message, (
        "the CARPACCIO_SLICE_TOO_LARGE rejection must name the SLICE-PLAN "
        f"ROW as the @coupled escape locus -- observed message={message!r}"
    )

    escaped_plan = _plan(annotation="@coupled", justification=_COUPLING_JUSTIFICATION)

    result = _invoke(escaped_plan, scenarios)

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "doing EXACTLY what the gate's own rejection message instructs -- "
        "annotating the slice-plan ROW with @coupled + a justification, "
        "touching no scenario tags -- must clear the gate via "
        f"CoupledSliceAccepted; observed {result!r} instead. The message "
        "promises a row-level escape that Path B does not honor: message "
        "and behavior disagree"
    )
