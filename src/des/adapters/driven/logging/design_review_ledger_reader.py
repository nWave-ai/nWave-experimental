"""DESIGN-named binding of the shared review-verdict ledger reader (slice-01).

The scan, the keyless startup probe and the verdict delegation live once in
``WaveReviewLedgerReader``; this module only pins that reader to the DESIGN
spec and keeps the ``DesignReviewLedgerReader`` name its consumers
(``service_factory``, ``verify_design_review``) already import.
"""

from __future__ import annotations

from des.adapters.driven.logging.wave_review_ledger_reader import (
    WaveReviewLedgerReader,
)
from des.domain.wave_review_spec import DESIGN_REVIEW_SPEC


__all__ = ["DESIGN_REVIEW_EVENT", "DesignReviewLedgerReader"]


# The DESIGN review verdict event name -- the record-family discriminant the
# reader selects on. Re-exported from the spec so the constant has ONE origin.
DESIGN_REVIEW_EVENT = DESIGN_REVIEW_SPEC.event


class DesignReviewLedgerReader(WaveReviewLedgerReader):
    """Reads the latest DESIGN architect-review verdict off the JSONL ledger."""

    def __init__(self) -> None:
        super().__init__(DESIGN_REVIEW_SPEC)
