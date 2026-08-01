"""Candidate/composition-scoped parity evidence ledger contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from des.domain.codex_parity import (
        Digest,
        ItemId,
        ParityEvidenceState,
        ParitySubject,
        ReceiptState,
        WhatWhyHow,
    )


@dataclass(frozen=True)
class EvidenceEnvelope:
    subject: ParitySubject
    witness_id: str
    item_id: ItemId
    state: ParityEvidenceState
    observable_digest: Digest | None
    diagnostic: WhatWhyHow | None


@dataclass(frozen=True)
class EvidenceWriteReceipt:
    subject: ParitySubject
    witness_id: str
    item_id: ItemId
    state: ReceiptState
    record_id: str | None
    diagnostic: WhatWhyHow | None = None


class ParityEvidenceLedgerPort(Protocol):
    def append(self, evidence: EvidenceEnvelope) -> EvidenceWriteReceipt:
        ...

    def records_for(self, subject: ParitySubject) -> tuple[EvidenceEnvelope, ...]:
        ...


__all__ = [
    "EvidenceEnvelope",
    "EvidenceWriteReceipt",
    "ParityEvidenceLedgerPort",
]
