"""DEVOPS-named binding of the shared review-verdict ledger reader (slice-02).

The scan, the keyless startup probe and the verdict delegation live once in
``WaveReviewLedgerReader``; this module only pins that reader to the DEVOPS
spec and keeps the ``DevopsReviewLedgerReader`` name its consumers
(``service_factory``, ``verify_devops_review``) already import.
"""

from __future__ import annotations

from des.adapters.driven.logging.wave_review_ledger_reader import (
    WaveReviewLedgerReader,
)
from des.domain.wave_review_spec import DEVOPS_REVIEW_SPEC


__all__ = ["DEVOPS_REVIEW_EVENT", "DevopsReviewLedgerReader"]


# The DEVOPS review verdict event name -- the record-family discriminant the
# reader selects on. Re-exported from the spec so the constant has ONE origin.
DEVOPS_REVIEW_EVENT = DEVOPS_REVIEW_SPEC.event


class DevopsReviewLedgerReader(WaveReviewLedgerReader):
    """Reads the latest DEVOPS platform-architect-review verdict off the ledger."""

    def __init__(self) -> None:
        super().__init__(DEVOPS_REVIEW_SPEC)
