"""Regression guard -- swarm-isolated-dispatch exemption for the M8 order check.

Under the swarm-parallel-delivery operating model a carpaccio slice N>1 is
developed in an ISOLATED parallel worktree that does NOT see the predecessor
slice-(N-1)'s `SliceCommitVerified` record until a later, in-order integration
step folds it onto the shared line. The M8 `_carpaccio_order_block` (in
`des.adapters.drivers.hooks.carpaccio_intercept`) therefore fires a STRUCTURAL
false positive there: the true ordering is still guaranteed at integration, not
in the isolated worktree.

The dedicated `DES-SWARM-ISOLATED-DISPATCH: <justification>` marker exempts ONLY
the M8 order check (no other gate), deferring the order verification to the
integrator. Unlike DES-BOOTSTRAP (rare, reuse-capped at 1 per feature+gate),
this exemption is ROUTINE by design -- every slice N>1 of a swarmed feature
needs it -- so it carries NO reuse cap. A malformed marker (empty/absent
justification) fails CLOSED: the order check blocks exactly as before.

RED-not-BROKEN discipline: the marker-carrying markers are built through the
REAL `DesMarkerParser.parse`, never by constructing `DesMarkers` with the
new field at module scope -- before the fix the parser simply ignores the
unknown marker, `_carpaccio_order_block` blocks as today, and the deferral
assertions fail with a semantic `AssertionError`, not a collection error.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    _carpaccio_order_block,
)
from des.domain.des_marker_parser import DesMarkerParser


_FEATURE_ID = "regression-swarm-isolated-dispatch-nonexistent-feature"
_JUSTIFICATION = (
    "slice developed in an isolated swarm worktree; predecessor slice-01 is "
    "committed on the shared line and order is verified at integration"
)
_DEFERRAL_EVENT = "CarpaccioOrderCheckDeferredToIntegration"


def _prompt(slice_id: str, *, swarm_marker: str | None = None) -> str:
    """A well-formed atdd_pure A_GREEN dispatch prompt carrying ``slice_id``.

    When ``swarm_marker`` is given it is appended verbatim as the raw
    `DES-SWARM-ISOLATED-DISPATCH` marker line, so a present-but-empty
    justification can be expressed at the prompt layer too.
    """
    lines = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-MODE : atdd_pure -->",
        "<!-- DES-PHASE : A_GREEN_ATS -->",
        f"<!-- DES-SLICE : {slice_id} -->",
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->",
        f"<!-- DES-FEATURE-ID : {_FEATURE_ID} -->",
    ]
    if swarm_marker is not None:
        lines.append(swarm_marker)
    return "\n".join(lines) + "\n"


def _markers(slice_id: str, *, swarm_marker: str | None = None):
    return DesMarkerParser().parse(_prompt(slice_id, swarm_marker=swarm_marker))


def _deferral_records(tmp_path: Path) -> list[dict]:
    records = AtCompletionLedger(_FEATURE_ID, tmp_path).read_records()
    return [r for r in records if r.get("event") == _DEFERRAL_EVENT]


def test_slice_n_without_swarm_marker_still_blocks(tmp_path: Path) -> None:
    """Regression pin: an unmarked slice N>1 with an unshipped predecessor blocks.

    The invariant the fix must NOT weaken -- without the swarm marker the M8
    order check fires exactly as before (`CarpaccioSliceOutOfOrder`), and no
    deferral audit record is written.
    """
    decision = _carpaccio_order_block(_markers("slice-02"), _FEATURE_ID, tmp_path)

    assert decision is not None, (
        "an unmarked slice-02 with an unsatisfied predecessor must still block"
    )
    assert isinstance(decision, InterceptDecision)
    assert decision.is_block
    assert decision.event == "CarpaccioSliceOutOfOrder", (
        f"expected the normal order block; got event={decision.event!r}"
    )
    assert _deferral_records(tmp_path) == [], (
        "an unmarked dispatch must emit NO deferral audit record"
    )


def test_swarm_isolated_marker_defers_to_integration_and_allows(
    tmp_path: Path,
) -> None:
    """A `DES-SWARM-ISOLATED-DISPATCH` marker clears M8 and defers to integration.

    The order check returns None (allow) instead of blocking, and a distinct
    `CarpaccioOrderCheckDeferredToIntegration` audit record is written carrying
    the gate, justification, entering slice, and predecessor.
    """
    marker = f"<!-- DES-SWARM-ISOLATED-DISPATCH : {_JUSTIFICATION} -->"
    decision = _carpaccio_order_block(
        _markers("slice-02", swarm_marker=marker), _FEATURE_ID, tmp_path
    )

    assert decision is None, (
        "a swarm-isolated slice must clear the M8 order check (deferred to "
        f"integration), not block; got {decision!r}"
    )

    records = _deferral_records(tmp_path)
    assert len(records) == 1, (
        "exactly one deferral audit record must be written; got "
        f"{len(records)}: {records!r}"
    )
    record = records[0]
    assert record.get("gate") == "carpaccio-order-gate", (
        f"deferral record must name the order gate; got gate={record.get('gate')!r}"
    )
    assert record.get("justification") == _JUSTIFICATION, (
        "deferral record must carry the operator justification verbatim; got "
        f"{record.get('justification')!r}"
    )
    assert record.get("slice_id") == "slice-02", (
        f"deferral record must name the entering slice; got {record.get('slice_id')!r}"
    )
    assert record.get("predecessor") == "slice-01", (
        "deferral record must name the deferred predecessor; got "
        f"{record.get('predecessor')!r}"
    )


def test_swarm_isolated_marker_carries_no_reuse_cap(tmp_path: Path) -> None:
    """The exemption is ROUTINE: a second swarm-isolated dispatch also clears.

    Unlike DES-BOOTSTRAP (reuse cap = 1 per feature+gate), the swarm exemption
    is expected on every slice N>1 of a swarmed feature, so a prior deferral
    record never blocks the next -- both slice-02 and slice-03 clear.
    """
    marker = f"<!-- DES-SWARM-ISOLATED-DISPATCH : {_JUSTIFICATION} -->"

    first = _carpaccio_order_block(
        _markers("slice-02", swarm_marker=marker), _FEATURE_ID, tmp_path
    )
    second = _carpaccio_order_block(
        _markers("slice-03", swarm_marker=marker), _FEATURE_ID, tmp_path
    )

    assert first is None and second is None, (
        "the swarm exemption must not be reuse-capped; both dispatches clear -- "
        f"got first={first!r} second={second!r}"
    )
    assert len(_deferral_records(tmp_path)) == 2, (
        "each deferred dispatch writes its own audit record (no cap)"
    )


@pytest.mark.negative_at
def test_empty_swarm_justification_fails_closed_and_blocks(tmp_path: Path) -> None:
    """A present-but-empty justification fails CLOSED -- the order check blocks.

    Same fail-closed principle as a malformed DES-BOOTSTRAP marker: an empty
    justification carries no audit-able reason, so it must never earn the
    exemption. The empty-justification markers are built via
    ``dataclasses.replace`` at RUNTIME (never at module scope) so this guard's
    reliance on the post-fix field does not poison collection of the RED pair.
    """
    base = _markers("slice-02")
    markers = dataclasses.replace(base, swarm_isolated_justification="")

    decision = _carpaccio_order_block(markers, _FEATURE_ID, tmp_path)

    assert decision is not None and decision.is_block, (
        "an empty swarm-isolated justification must fail closed and block"
    )
    assert decision.event == "CarpaccioSliceOutOfOrder", (
        f"expected the normal order block on empty justification; got {decision.event!r}"
    )
    assert _deferral_records(tmp_path) == [], (
        "a fail-closed empty-justification dispatch must emit NO deferral record"
    )
