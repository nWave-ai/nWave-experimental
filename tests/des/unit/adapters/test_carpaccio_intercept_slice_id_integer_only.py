"""Regression guard -- integer-only slice ids in the U1 carpaccio order check.

`_carpaccio_order_block` (`des.adapters.drivers.hooks.carpaccio_intercept`)
refuses a non-integer slice id (letter-suffix `slice-04a`, decimal
`slice-04.1`) with a self-explaining `CarpaccioSliceNonInteger` GATE block
instead of crashing the downstream integer-only ordering machinery
(`_slice_number` -> `int()`). The guard fires FIRST, before any
predecessor/ledger lookup -- a non-integer slice id never reaches
`AtCompletionLedger`.

This is a REGRESSION LOCK, not a RED scaffold: the fix is already shipped
(`_carpaccio_order_block` lines ~537-550, `_slice_number` lines ~489-511 of
`carpaccio_intercept.py`). Every assertion below is GREEN today -- no
production code changes accompany this test.

Policy pinned: slice ids are INTEGER-ONLY (`slice-NN`, digits only). To
insert an intermediate slice, RENUMBER the plan (shift later slices up by
one); never mint a letter-suffixed or decimal sub-slice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    _carpaccio_order_block,
    _slice_number,
)
from des.domain.des_marker_parser import DesMarkers


_FEATURE_ID = "regression-lock-nonexistent-feature-slice-id-integer-only"


def _markers(slice_id: str) -> DesMarkers:
    """A well-formed atdd_pure A_GREEN marker set carrying ``slice_id``."""
    return DesMarkers(
        is_des_task=True,
        is_orchestrator_mode=False,
        project_id=_FEATURE_ID,
        feature_id=_FEATURE_ID,
        step_id=None,
        project_root=None,
        mode="atdd_pure",
        atdd_pure_phase="A_GREEN",
        slice_id=slice_id,
        has_des_markers=True,
        carries_validation_marker=True,
        declared_wave=None,
        wave=None,
        bootstrap_gate=None,
        bootstrap_justification=None,
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "slice_id",
    ["slice-04a", "slice-04.1"],
    ids=["letter-suffix", "decimal"],
)
def test_carpaccio_order_block_rejects_non_integer_slice_id(
    slice_id: str, tmp_path: Path
) -> None:
    """A non-integer slice id blocks with `CarpaccioSliceNonInteger`, not a crash.

    ``tmp_path`` is a fresh, non-existent-ledger project root -- the
    non-integer guard must fire BEFORE any predecessor/ledger lookup, so no
    ledger state is required to observe this block.
    """
    decision = _carpaccio_order_block(_markers(slice_id), _FEATURE_ID, tmp_path)

    assert decision is not None, (
        f"a non-integer slice id {slice_id!r} must be blocked, not silently "
        "cleared (returned None)"
    )
    assert isinstance(decision, InterceptDecision)
    assert decision.is_block
    assert decision.event == "CarpaccioSliceNonInteger", (
        f"expected event='CarpaccioSliceNonInteger' for slice id {slice_id!r}; "
        f"got {decision.event!r}"
    )
    assert decision.reason is not None
    assert "RENUMBER" in decision.reason, (
        "the block reason must name the RENUMBER remediation (shift later "
        f"slices up by one) -- got: {decision.reason!r}"
    )
    assert "sub-slice" in decision.reason, (
        "the block reason must warn against minting a sub-slice -- got: "
        f"{decision.reason!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "slice_id",
    ["slice-04a", "slice-04.1"],
    ids=["letter-suffix", "decimal"],
)
def test_slice_number_rejects_non_integer_suffix_with_self_explaining_error(
    slice_id: str,
) -> None:
    """`_slice_number` raises a self-explaining `ValueError` on a non-integer id.

    Names the integer-only constraint AND the renumber fix, so the error is
    never a cryptic `invalid literal for int()` in isolation.
    """
    with pytest.raises(ValueError) as exc_info:
        _slice_number(slice_id)

    message = str(exc_info.value)
    assert "integer" in message, (
        f"the ValueError must name the integer-only constraint; got: {message!r}"
    )
    assert "RENUMBER" in message, (
        f"the ValueError must name the RENUMBER remediation; got: {message!r}"
    )
    assert "sub-slice" in message, (
        f"the ValueError must warn against minting a sub-slice; got: {message!r}"
    )


def test_carpaccio_order_block_does_not_trip_non_integer_guard_on_plain_integer(
    tmp_path: Path,
) -> None:
    """A plain integer slice id (`slice-02`) never triggers the non-integer guard.

    With an empty ledger and a non-existent predecessor commit, `slice-02`
    proceeds past the non-integer guard into the normal order check and
    blocks on `CarpaccioSliceOutOfOrder` instead (its predecessor `slice-01`
    has no `SliceCommitVerified`-equivalent record) -- the diagnostic proof
    that the non-integer guard was never the one that fired.
    """
    decision = _carpaccio_order_block(_markers("slice-02"), _FEATURE_ID, tmp_path)

    assert decision is not None, (
        "slice-02 with an unsatisfied predecessor must still block (on the "
        "order check), not clear"
    )
    assert decision.event != "CarpaccioSliceNonInteger", (
        "a plain integer slice id must never trip the non-integer guard; "
        f"got event={decision.event!r}"
    )
    assert decision.event == "CarpaccioSliceOutOfOrder", (
        f"expected the normal order check to fire instead; got {decision.event!r}"
    )


@pytest.mark.parametrize(
    "slice_id, expected",
    [("slice-02", 2), ("slice-01", 1)],
)
def test_slice_number_parses_plain_integer_slice_ids(
    slice_id: str, expected: int
) -> None:
    """`_slice_number` parses a well-formed integer `slice-NN` id correctly."""
    assert _slice_number(slice_id) == expected
