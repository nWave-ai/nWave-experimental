"""Unit tests for the F2 carpaccio-intercept ledger emission (slice-05 revision).

slice-05 of F-DES-ATDD-PURE-HOOK-GATES -- closes deep-review Finding 2.

Before this revision the U1 carpaccio intercept produced
`CarpaccioGateCleared` / `CarpaccioGateRejected` only as in-memory
`InterceptDecision.event` strings -- `evaluate_atdd_pure_dispatch` never called
`append_gate_event`, so `reconcile_dispatch_count` had no carpaccio records to
reconcile against and the M4 R3-fix signal was inert.

Finding 2 requires U1 to emit a `CarpaccioGateCleared` / `CarpaccioGateRejected`
ledger record per intercept. The emission is **fail-OPEN on the audit write**
(mirroring U2's pattern) -- a ledger write failure must not change the gate
verdict.

Port-to-port: the driving port is `evaluate_atdd_pure_dispatch`; the U3 ledger
JSONL file is the observable driven-port surface.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    evaluate_atdd_pure_dispatch,
)


_FEATURE_ID = "demo-feature"


def _atdd_pure_prompt(slice_id: str = "slice-01") -> str:
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
    )


def _carpaccio_gate_event_for(tmp_path: Path, slice_id: str) -> str | None:
    """The latest carpaccio gate event the intercept emitted for ``slice_id``."""
    records = AtCompletionLedger(_FEATURE_ID, tmp_path).read_records()
    for record in reversed(records):
        if record.get("slice_id") == slice_id and record.get("event") in (
            "CarpaccioGateCleared",
            "CarpaccioGateRejected",
        ):
            return str(record["event"])
    return None


def _latest_record_for(
    tmp_path: Path, slice_id: str, event: str
) -> dict[str, object] | None:
    """The latest ledger record of ``event`` for ``slice_id``, full fields."""
    records = AtCompletionLedger(_FEATURE_ID, tmp_path).read_records()
    for record in reversed(records):
        if record.get("slice_id") == slice_id and record.get("event") == event:
            return record
    return None


def test_cleared_dispatch_emits_carpaccio_gate_cleared_record(
    tmp_path: Path,
) -> None:
    """A cleared A_GREEN_ATS dispatch writes a CarpaccioGateCleared ledger record."""
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    assert not decision.is_block
    assert _carpaccio_gate_event_for(tmp_path, "slice-01") == "CarpaccioGateCleared"


def test_rejected_dispatch_emits_carpaccio_gate_rejected_record(
    tmp_path: Path,
) -> None:
    """A rejected A_GREEN_ATS dispatch writes a CarpaccioGateRejected ledger record."""
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (1, '{"event": "SliceNotThin"}'),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    assert decision.is_block
    assert _carpaccio_gate_event_for(tmp_path, "slice-01") == "CarpaccioGateRejected"


def test_rejected_dispatch_ledger_record_carries_the_rejection_reason(
    tmp_path: Path,
) -> None:
    """D04b (canali muti class-scope): the ledger record must persist the
    SAME reason the operator saw in ``InterceptDecision.reason`` -- before
    this fix ``_emit_carpaccio_gate_event`` threaded only ``event`` +
    ``slice_id``, so every ``CarpaccioGateRejected`` / ``ReadinessGateRejected``
    record told THAT a rejection happened but never WHY (live telemetry,
    2026-07-28/29: 60/60 CarpaccioGateRejected + 82/82 ReadinessGateRejected
    carried no reason field at all)."""
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (1, '{"event": "SliceNotThin"}'),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    assert decision.is_block
    record = _latest_record_for(tmp_path, "slice-01", "CarpaccioGateRejected")
    assert record is not None, "expected a CarpaccioGateRejected ledger record"
    assert record.get("reason") == decision.reason, (
        f"the ledger record must carry the reason the operator saw -- got "
        f"record reason={record.get('reason')!r}, "
        f"decision.reason={decision.reason!r}"
    )


def test_readiness_rejected_dispatch_ledger_record_carries_the_rejection_reason(
    tmp_path: Path,
) -> None:
    """D04b: same reason-persistence fix, readiness-gate rejection branch."""
    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (1, '{"event": "ReadinessRefused"}'),
    )

    assert decision.is_block
    assert decision.event == "ReadinessGateRejected"
    record = _latest_record_for(tmp_path, "slice-01", "ReadinessGateRejected")
    assert record is not None, "expected a ReadinessGateRejected ledger record"
    assert record.get("reason") == decision.reason, (
        f"the ledger record must carry the reason the operator saw -- got "
        f"record reason={record.get('reason')!r}, "
        f"decision.reason={decision.reason!r}"
    )


def test_emitted_carpaccio_event_makes_reconciliation_meaningful(
    tmp_path: Path,
) -> None:
    """The emitted record makes reconcile_dispatch_count see the slice as gated."""
    evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    ledger = AtCompletionLedger(_FEATURE_ID, tmp_path)
    # slice-01 is now gated; an un-gated slice-02 surfaces as a discrepancy.
    assert ledger.reconcile_dispatch_count(
        frozenset({"slice-01", "slice-02"})
    ) == frozenset({"slice-02"})


def test_a_mode_less_dispatch_is_refused_and_writes_no_carpaccio_record(
    tmp_path: Path,
) -> None:
    """A dispatch with no mode marker is REFUSED, and leaves no ledger record.

    This scenario used to read "a non-atdd_pure dispatch passes through (classic
    path unchanged)". Since the classic removal there is no other path to pass
    through TO: an absent mode is a declared refusal (DispatchModeUnresolved),
    never a fallback. Keeping the old premise would have asserted the absence of
    a workflow the product deliberately stopped having.

    The property worth holding survives the change and is what is pinned here: a
    dispatch that never cleared the gate must leave the carpaccio ledger empty.
    A refusal that still emitted a record would make the ledger say a gate ran on
    a dispatch it actually turned away.
    """
    decision = evaluate_atdd_pure_dispatch(
        prompt="ordinary prompt, no DES markers at all",
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    assert decision.is_block, (
        "a dispatch carrying no DES-MODE marker must be REFUSED -- absence "
        f"cannot select a retired workflow; got {decision}"
    )
    assert decision.event == "DispatchModeUnresolved", (
        "the refusal must name the mode as the unresolved thing, not blame a "
        f"marker the prompt was never asked to carry; got {decision.event!r}"
    )
    assert AtCompletionLedger(_FEATURE_ID, tmp_path).read_records() == []


def test_ledger_emission_is_fail_open_on_audit_write_error(
    tmp_path: Path, monkeypatch
) -> None:
    """A ledger-write failure does NOT change the gate verdict (fail-OPEN audit).

    The carpaccio verdict already stands; the ledger emission is audit. A
    failing append must be swallowed -- the cleared dispatch stays cleared.
    """

    def _boom(*_args, **_kwargs):
        raise OSError("simulated ledger write failure")

    monkeypatch.setattr(AtCompletionLedger, "append_gate_event", _boom)

    decision = evaluate_atdd_pure_dispatch(
        prompt=_atdd_pure_prompt("slice-01"),
        feature_id=_FEATURE_ID,
        project_root=tmp_path,
        carpaccio_runner=lambda _f, _s: (0, "{}"),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    # The gate verdict is unaffected by the audit-write failure.
    assert not decision.is_block
    assert decision.is_atdd_pure
