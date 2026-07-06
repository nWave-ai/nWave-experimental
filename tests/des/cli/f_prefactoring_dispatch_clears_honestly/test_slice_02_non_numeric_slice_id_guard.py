"""slice-02 AT -- D5 guard: a letter-suffixed slice id must never crash the seal.

# @feature-f-prefactoring-dispatch-clears-honestly
# @slice-02

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone). `_SLICE_ID_RE`
(`des.cli.carpaccio_format.py`) accepts a letter-suffixed slice id
(`^slice-\\d+(?:[a-z])?$`, friction #10) -- `slice-02b` is a VALID slice id
throughout the rest of the carpaccio machinery. But
`_check_green_to_green` (`des.cli.carpaccio_slice_gate.py`) calls the hook
module's `_slice_number(entering_slice)` unconditionally once `commit_sha` is
given (`int(slice_id.split("-", 1)[1])`) -- `int("02b")` raises a bare,
uncaught `ValueError`, not a `GateError`. A green-to-green consultation for a
COMMIT-time (`commit_sha` given) `@prefactoring` slice whose id carries a
letter suffix crashes the gate outright instead of returning a clean refusal.

Driving port (Mandate 16, no-direct-domain-testing): drives
`des.cli.carpaccio_slice_gate.check_at_review` directly -- the SAME
production function both `carpaccio_slice_gate.main` (ENTRY) and
`verify_commit_trailers._audit_slice` (COMMIT) call -- mirroring the sibling
`test_slice_02_green_to_green_seal.py`'s own driving-port choice (that file
drives the identical function; this AT isolates the ONE additional guard a
letter-suffixed id needs at COMMIT time).

Active-RED today: `int("02b")` raises `ValueError: invalid literal for int()
with base 10: '02b'`, an unhandled exception -- never a `GateError`, never a
clean refusal.

CONTRACT_SHAPE: bounded-change
Outcome anchor: docs/feature/f-prefactoring-dispatch-clears-honestly/
feature-delta.md (Wave: DESIGN / [REF] Green-to-Green Seal, slice-02 REDUCED
SCOPE), D5 (letter-suffixed slice ids, friction #10 parity with
`_SLICE_ID_RE`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.cli.carpaccio_format import GateError, SlicePlan, SlicePlanRow
from des.cli.carpaccio_slice_gate import check_at_review


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "synthetic-letter-suffix-feature"
_SLICE_ID = "slice-02b"


class _FakeCommitDiffPort:
    """Duck-typed fake -- never reached: the crash fires before any diff read."""

    def changed_paths(self, repo: Path, commit_sha: str) -> list[str]:
        return []


def _prefactoring_plan(entering_slice: str) -> SlicePlan:
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=entering_slice,
                value_statement="a behavior-preserving refactor introduces the seam",
                status="pending",
                annotation="@prefactoring",
                justification="letter-suffix guard AT fixture (D5)",
            ),
        )
    )


def test_letter_suffixed_slice_id_refuses_cleanly_never_raw_valueerror(
    tmp_path: Path,
) -> None:
    """`check_at_review` for a `@prefactoring` slice-02b, COMMIT-time
    (`commit_sha` given), must surface a clean `GateError` -- NEVER let a bare
    `ValueError` from `_slice_number("02b")` escape uncaught.

    The exact refusal reason is not the point here (this is a crash-guard, not
    a semantic-outcome AT) -- ANY well-formed `GateError` is acceptable; a
    naked `ValueError` propagating out of `check_at_review` is the ONE
    unacceptable outcome.
    """
    plan = _prefactoring_plan(_SLICE_ID)

    try:
        result = check_at_review(
            tmp_path,
            _FEATURE_ID,
            _SLICE_ID,
            [],
            plan=plan,
            commit_sha="deadbeef",
            commit_diff_port=_FakeCommitDiffPort(),
        )
    except GateError as exc:
        result = exc
    except ValueError as exc:
        raise AssertionError(
            "D5 REOPENED: check_at_review must never let a bare ValueError "
            "escape for a letter-suffixed slice id (int('02b') fails inside "
            "_slice_number) -- it must surface a clean GateError instead. "
            f"observed=ValueError({exc!r})"
        ) from exc

    assert isinstance(result, GateError), (
        "check_at_review must refuse a letter-suffixed @prefactoring slice id "
        f"(slice-02b) with a well-formed GateError, not clear it silently. "
        f"observed={result!r}"
    )
