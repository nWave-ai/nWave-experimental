"""Regression AT -- D04b consumer sweep (declared-facts-reachable-recorded
slice-01's DD-1 fix, commit 0303ecea5, extended to a THIRD consumer).

DEFECT: `_project_pending_slice` (`src/des/application/
deliver_loop_projection.py:567`) decided "the AT review is done" with
`_has_event_for_slice(records, "ATReviewVerdict", slice_id)` -- presence
only, never the record's `verdict` field. Before DD-1 (0303ecea5) this was
safe: only an APPROVED verdict ever wrote an `ATReviewVerdict` record. DD-1
made `record_review_outcome` append a record for BOTH APPROVED and
NEEDS_REVISION, so a REJECTED slice now ALSO satisfies "a record exists" --
`des next` then reports the slice ready for EXAMINE / commit instead of
sending the operator back to get the rejection addressed. The function's own
docstring for this branch already promised "APPROVED ATReviewVerdict" --
the implementation just never checked it.

This is the SAME defect class D04a found and fixed in `AtCompletionLedger.
review_verdict_slices()` (see `test_distill_exit_rejected_slice_not_counted_
signed.py`) -- "a record exists" silently read as "approved" -- occurring
independently in a SECOND, unrelated consumer of the same `ATReviewVerdict`
record shape. Found by the D04b consumer sweep across every reader of the
event, not by re-checking the one consumer already fixed.

THE FIX (implemented alongside this test): a new
`_has_approved_review_verdict_for_slice` predicate replaces the bare
presence check -- filters on `event == "ATReviewVerdict"` AND
`slice_id` match AND `verdict == "APPROVED"`.

RED-for-right-reason: before the fix, seeding ONLY a NEEDS_REVISION
`ATReviewVerdict` record for the pending slice makes `project_next_step`
report `phase == "C_REVIEWER_AUDIT"` (EXAMINE pending) instead of staying at
`phase == "A_GREEN"` -- a genuine semantic `AssertionError`, never an
import/collection error (confirmed interactively before authoring this
test).

Driving surface: the real `project_next_step` pure function (CONTRACT_SHAPE:
pure-function per its own docstring), fixture-repo shape mirrors
`tests/des/acceptance/test_des_next_loop_projection.py` verbatim.

covers: declared-facts-reachable-recorded slice-01 (DD-1 follow-up), D04b
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.deliver_loop_projection import project_next_step


_FEATURE_ID = "next-step-rejected-slice-probe"
_SLICE_ID = "slice-01"


def _feature_delta_text(slice_id: str) -> str:
    return (
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
        "\n"
        "Some architecture prose.\n"
        "\n"
        "## Wave: DESIGN / [REF] ADR Refs\n"
        "\n"
        "- ADR-001\n"
        "\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n"
        "\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {slice_id} | probe row | pending | @walking_skeleton | probe |\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _write_feature_delta(repo: Path) -> None:
    delta_path = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(_feature_delta_text(_SLICE_ID), encoding="utf-8")


def _ledger(repo: Path) -> AtCompletionLedger:
    return AtCompletionLedger(_FEATURE_ID, repo)


def _seed_red_observed(repo: Path) -> None:
    _ledger(repo).append_gate_event(
        event="RedObserved", slice_id=_SLICE_ID, feature_id=_FEATURE_ID
    )


def _seed_review_verdict(repo: Path, *, verdict: str) -> None:
    _ledger(repo).append_review_verdict(
        _SLICE_ID, {"verdict": verdict}, feature_id=_FEATURE_ID
    )


def test_needs_revision_verdict_keeps_the_slice_at_green_not_examine(
    tmp_path: Path,
) -> None:
    _write_feature_delta(tmp_path)
    _seed_red_observed(tmp_path)
    _seed_review_verdict(tmp_path, verdict="NEEDS_REVISION")

    step = project_next_step(tmp_path, _FEATURE_ID, slice_id=_SLICE_ID)

    assert step.phase == "A_GREEN", (
        "a slice whose ONLY ATReviewVerdict record is NEEDS_REVISION must "
        "stay at A_GREEN (not yet approved) -- 'a record exists' must never "
        f"be read as 'approved'. Got phase={step.phase!r}, what={step.what!r}"
    )
    assert step.how == f"/nw-deliver --feature-id {_FEATURE_ID}", step


def test_approved_verdict_still_advances_past_green(tmp_path: Path) -> None:
    """Regression pin: the narrowed predicate must not regress the ordinary
    approval path -- an APPROVED-only slice still leaves A_GREEN."""
    _write_feature_delta(tmp_path)
    _seed_red_observed(tmp_path)
    _seed_review_verdict(tmp_path, verdict="APPROVED")

    step = project_next_step(tmp_path, _FEATURE_ID, slice_id=_SLICE_ID)

    assert step.phase != "A_GREEN", (
        f"an APPROVED-only slice must advance past A_GREEN -- got {step!r}"
    )
