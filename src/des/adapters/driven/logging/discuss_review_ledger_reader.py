"""DISCUSS-named binding of the shared review-verdict ledger reader (slice-07b).

The scan, the keyless startup probe and the verdict delegation live once in
``WaveReviewLedgerReader``; this module only pins that reader to the DISCUSS
spec and keeps the ``DiscussReviewLedgerReader`` name its consumers
(``service_factory``) already import.
"""

from __future__ import annotations

from des.adapters.driven.logging.wave_review_ledger_reader import (
    WaveReviewLedgerReader,
)
from des.domain.discuss_review_gate import DISCUSS_REVIEW_EVENT
from des.domain.wave_review_spec import DISCUSS_REVIEW_SPEC


__all__ = ["DISCUSS_REVIEW_EVENT", "DiscussReviewLedgerReader"]


class DiscussReviewLedgerReader(WaveReviewLedgerReader):
    """Reads the latest DISCUSS PO-review verdict off the JSONL ledger."""

    def __init__(self) -> None:
        super().__init__(DISCUSS_REVIEW_SPEC)
