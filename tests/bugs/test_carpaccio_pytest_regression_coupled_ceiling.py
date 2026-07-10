"""Regression -- `check_carpaccio`'s pytest-regression branch hardcodes
``all_coupled=False``, so a cohesive over-ceiling pytest-regression slice can
NEVER use the ``@coupled`` ceiling-escape the gate's own rejection message
explicitly promises: "only @coupled + justification lifts the ceiling".
Self-contradicting gate.

Found in ``src/des/cli/carpaccio_format.py::check_carpaccio`` (~line 619-626)::

    if at_kind == "pytest-regression":
        at_count = count_pytest_regression_ats(regression_test_file)
        ...
        return _check_slice_size_count(plan, entering_slice, slice_max, at_count, all_coupled=False)  # BUG

The ``_check_slice_size_count`` docstring (~line 782-784) admits it: "pytest-
regression mode ... passes all_coupled=False -- no @coupled-tag vocabulary
exists for a plain pytest regression file". That is wrong: ``SlicePlanRow``
already carries an ``annotation: str`` field, and the module already has
``_COUPLED_TAG_RE = re.compile(r"@coupled\\b")`` -- the signal exists, it is
just never read on this branch. The intended fix (NOT made by this AT --
DELIVER's job) derives ``all_coupled`` from
``_COUPLED_TAG_RE.search(row.annotation)`` for the entering slice's own
Slice-Plan row, mirroring how the gherkin path (``_check_slice_size``) derives
``all_coupled`` from the ``.feature`` scenarios' ``@coupled`` tags.

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
``des.cli.carpaccio_format.check_carpaccio`` directly -- the SAME production
function ``carpaccio_slice_gate.main`` calls at assertion 1 -- never a
re-implemented shadow check. ``count_pytest_regression_ats`` is exercised for
REAL (an on-disk regression file with N ``test_*`` functions, never mocked) so
the AT count driving the ceiling comparison is the true AST count.

Note: case 3 below (``@coupled`` annotation, empty justification) is already
rejected TODAY by assertion 4 (``_check_value_annotation``, which runs before
the size check for every ``at_kind``) -- it is an invariant-preserved guard,
not a currently-red case; it locks that the fix does not accidentally bypass
assertion 4's mandatory-justification requirement for the escape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from des.cli.carpaccio_format import (
    GateError,
    SlicePlan,
    SlicePlanRow,
    check_carpaccio,
    count_pytest_regression_ats,
)


if TYPE_CHECKING:
    from pathlib import Path


_ENTERING_SLICE = "slice-01"
_SLICE_MAX = 7
_OVER_CEILING_COUNT = 8  # > _SLICE_MAX -- engages the size-ceiling branch


# --- shared fixture builders ---------------------------------------------


def _plan(annotation: str, justification: str) -> SlicePlan:
    """A single-row Slice Plan whose entering-slice row carries `annotation`
    and `justification` -- the only two inputs the three cases below vary."""
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=_ENTERING_SLICE,
                value_statement="a cohesive pytest-regression AT group",
                status="pending",
                annotation=annotation,
                justification=justification,
            ),
        )
    )


def _write_regression_file(tmp_path: Path, count: int) -> Path:
    """A real pytest regression file with `count` module-level `test_*`
    functions -- exercised through the REAL `count_pytest_regression_ats` AST
    counter (never mocked), so the AT count driving the ceiling comparison in
    every case below is the true count, not a stand-in."""
    path = tmp_path / "test_regression_fixture.py"
    functions = "\n\n".join(
        f"def test_case_{i}():\n    assert {i} == {i}" for i in range(count)
    )
    path.write_text(functions + "\n", encoding="utf-8")
    return path


def _invoke(plan: SlicePlan, regression_file: Path) -> dict[str, object] | GateError:
    """Best-effort `check_carpaccio` call in pytest-regression mode, `GateError`
    captured as a return value (mirrors the sibling carpaccio driving-port
    helpers in `tests/des/cli/f_prefactoring_dispatch_clears_honestly/`)."""
    try:
        return check_carpaccio(
            plan,
            [],
            _ENTERING_SLICE,
            _SLICE_MAX,
            at_kind="pytest-regression",
            regression_test_file=regression_file,
        )
    except GateError as exc:
        return exc


# --- self-check: the fixture truly engages the size-ceiling branch --------


def test_fixture_regression_file_at_count_exceeds_slice_max(tmp_path: Path) -> None:
    """Setup invariant: `_OVER_CEILING_COUNT` must exceed `_SLICE_MAX`, and the
    REAL AST counter must agree -- guards every case below from a silently
    miscounted fixture that would make the ceiling comparison a no-op."""
    regression_file = _write_regression_file(tmp_path, _OVER_CEILING_COUNT)

    assert _OVER_CEILING_COUNT > _SLICE_MAX, (
        "test setup invariant broken: the fixture AT count must exceed "
        f"_SLICE_MAX ({_SLICE_MAX}) so the size-ceiling branch is actually "
        "engaged, not the plain in-ceiling pass-through"
    )
    assert count_pytest_regression_ats(regression_file) == _OVER_CEILING_COUNT, (
        "count_pytest_regression_ats must AST-count exactly the module-level "
        "test_* functions the fixture wrote"
    )


# --- case 1: POSITIVE -- @coupled + justification must lift the ceiling ---


def test_coupled_annotated_over_ceiling_pytest_slice_is_accepted(
    tmp_path: Path,
) -> None:
    """A pytest-regression slice with MORE ATs than the ceiling, whose
    entering Slice-Plan row is annotated `@coupled` with a non-empty
    Justification, must clear via `CoupledSliceAccepted` -- exactly the
    escape the gate's own `CARPACCIO_SLICE_TOO_LARGE` rejection message
    promises ("only @coupled + justification lifts the ceiling").

    RED TODAY: `check_carpaccio`'s pytest-regression branch hardcodes
    `all_coupled=False`, so this call raises `GateError`
    (`CARPACCIO_SLICE_TOO_LARGE`) instead of returning the acceptance dict,
    even though `SlicePlanRow.annotation` already carries the exact `@coupled`
    signal the gherkin path reads for the same escape.
    """
    plan = _plan(
        annotation="@coupled",
        justification=(
            "a cohesive regression-test group covering one bug's full "
            "reproduction and fix verification; splitting it across slices "
            "would break the single end-to-end repro it proves"
        ),
    )
    regression_file = _write_regression_file(tmp_path, _OVER_CEILING_COUNT)

    result = _invoke(plan, regression_file)

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "a pytest-regression slice with an entering-slice row annotated "
        "@coupled + a recorded justification must clear via "
        f"CoupledSliceAccepted -- observed {result!r} (a raised GateError "
        "means the pytest-regression branch is still hardcoding "
        "all_coupled=False, contradicting the gate's own rejection message)"
    )
    assert result.get("at_count") == _OVER_CEILING_COUNT, (
        "CoupledSliceAccepted must report the true AST-counted AT count -- "
        f"observed {result.get('at_count')!r}"
    )


# --- case 2: NEGATIVE (invariant-preserved) -- no @coupled still rejects --


@pytest.mark.negative_at
def test_unannotated_over_ceiling_pytest_slice_still_rejected(
    tmp_path: Path,
) -> None:
    """GUARD: the SAME over-ceiling pytest-regression slice, but the entering
    Slice-Plan row carries NO `@coupled` annotation, must still raise
    `CARPACCIO_SLICE_TOO_LARGE` -- both BEFORE and AFTER the fix. Proves the
    fix reads the row's own annotation rather than opening the escape to
    every pytest-regression slice unconditionally.
    """
    plan = _plan(annotation="", justification="")
    regression_file = _write_regression_file(tmp_path, _OVER_CEILING_COUNT)

    result = _invoke(plan, regression_file)

    assert isinstance(result, GateError), (
        "an over-ceiling pytest-regression slice with NO @coupled annotation "
        f"must still raise CARPACCIO_SLICE_TOO_LARGE -- observed {result!r}"
    )
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload
    assert result.payload.get("at_count") == _OVER_CEILING_COUNT, result.payload


# --- case 3: NEGATIVE (invariant-preserved) -- @coupled without justification --


@pytest.mark.negative_at
def test_coupled_annotated_but_unjustified_over_ceiling_pytest_slice_still_rejected(
    tmp_path: Path,
) -> None:
    """GUARD: an over-ceiling pytest-regression slice whose entering row IS
    annotated `@coupled` but records an EMPTY Justification cell must still
    raise `CARPACCIO_SLICE_TOO_LARGE` -- the justification is mandatory for
    the escape (mirrors the gherkin path's `row.justification` requirement in
    `_check_slice_size_count`). Already enforced TODAY by assertion 4
    (`_check_value_annotation`, which runs before the size check regardless
    of `at_kind`) -- this AT locks that the fix does not accidentally bypass
    that earlier, mandatory-justification guard.
    """
    plan = _plan(annotation="@coupled", justification="")
    regression_file = _write_regression_file(tmp_path, _OVER_CEILING_COUNT)

    result = _invoke(plan, regression_file)

    assert isinstance(result, GateError), (
        "an over-ceiling pytest-regression slice annotated @coupled but with "
        f"an EMPTY justification must still be rejected -- observed {result!r}"
    )
    assert result.payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", result.payload
