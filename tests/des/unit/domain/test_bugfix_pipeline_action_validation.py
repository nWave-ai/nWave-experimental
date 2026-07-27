"""Regression: evaluate_and_record refuses an unknown ``action`` with a
self-explaining ValueError instead of leaking a bare KeyError.

techdebt.md id: evaluate-and-record-bare-keyerror-instead-of-what-why-how-refusal
Defect: src/des/domain/bugfix_pipeline.py:186 looked up
``_EVENT_BY_ACTION[action]`` unguarded -- any caller passing an action
outside the CLI's own argparse ``choices=`` (e.g. a direct domain caller
such as consolidation_queue_intake.py) got a raw ``KeyError`` instead of a
domain-level refusal, violating GDP-3 (self-explaining rejection) and this
repo's standing that every failure explains WHAT/WHY/HOW.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from des.domain.bugfix_pipeline import evaluate_and_record


class _FakeLedger:
    """Minimal AtCompletionLedgerPort double: no records, records appends."""

    def __init__(self) -> None:
        self.appended: list[dict[str, Any]] = []

    def read_records(self, *, feature_id: str | None = None, **_: Any) -> list[dict]:
        return []

    def append_bugfix_pipeline_event(self, event: str, **fields: Any) -> None:
        self.appended.append({"event": event, **fields})


def test_unknown_action_raises_value_error_not_keyerror() -> None:
    ledger = _FakeLedger()

    with pytest.raises(ValueError, match="action"):
        evaluate_and_record(
            ledger=ledger,
            feature_id="feature-x",
            defect_id="defect-1",
            action="totally-unknown-action",
            stage=None,
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
            reason=None,
        )

    assert ledger.appended == []


@pytest.mark.parametrize(
    "action",
    ["stage-started", "stage-completed", "stage-failed", "claim-drained"],
)
def test_known_actions_still_evaluate_without_raising(action: str) -> None:
    ledger = _FakeLedger()

    evaluate_and_record(
        ledger=ledger,
        feature_id="feature-x",
        defect_id="defect-1",
        action=action,
        stage="rca" if action != "claim-drained" else None,
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        reason="some reason" if action == "stage-failed" else None,
    )
