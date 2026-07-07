"""Regression: the carpaccio gate reports a lane-exemption clearance as PASS, not FAIL.

A ``@prefactoring`` 0-AT slice clears via the lane exemption -- ``_emit`` receives a
``LaneAtExemptionAccepted`` event and exits 0 (the slice IS cleared). Before the fix,
``LaneAtExemptionAccepted`` was absent from ``_CLEAR_CLASS_EVENTS``, so ``_emit``
printed "❌ FAIL -- carpaccio gate refused (LaneAtExemptionAccepted)" while the exit
code was 0 -- a paying user saw a slice that HAD cleared reported as refused.

Finding: F-GATE-CARPACCIO-FALSE-FAIL-TEXT-ON-EXIT-0 (Vera, 2026-07-07). The human
surface text MUST agree with the exit code.
"""

from des.cli.carpaccio_slice_gate import _CLEAR_CLASS_EVENTS, _emit


def test_lane_at_exemption_accepted_is_a_clear_class_event() -> None:
    """The verdict mapping treats a lane-exemption clearance as a clear (PASS)."""
    assert "LaneAtExemptionAccepted" in _CLEAR_CLASS_EVENTS


def test_lane_at_exemption_accepted_prints_pass_not_refused(capsys) -> None:
    """The human summary reads ✅ PASS + 'cleared', never ❌ FAIL + 'refused'."""
    _emit(
        {
            "event": "LaneAtExemptionAccepted",
            "feature_id": "unified-language-adapter-registry",
            "slice_id": "slice-01",
            "lane": "prefactoring",
            "at_evidence": "green-to-green-pending",
        }
    )
    err = capsys.readouterr().err
    assert "✅ PASS" in err, err
    assert "❌ FAIL" not in err, err
    assert "refused" not in err, err
    assert "cleared via the prefactoring lane exemption" in err, err
