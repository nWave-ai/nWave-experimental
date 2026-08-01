"""Acceptance vocabulary imported directly from the production SSOT."""

from des.domain.codex_parity import (
    CandidateId,
    CandidateInputs,
    DeclaredSurface,
    Digest,
    EvidenceInput,
    EvidenceRecord,
    HostCompositionId,
    HostFacts,
    ItemId,
    OsFamily,
    ParityEvidenceState,
    ParitySubject,
    PolicyId,
    ProductSurface,
    RequestedPlatform,
    RuntimeKind,
    TargetSelection,
)


EvidenceKind = ParityEvidenceState
EvidenceBuckets = dict[ParityEvidenceState | str, object]

__all__ = [
    "CandidateId",
    "CandidateInputs",
    "DeclaredSurface",
    "Digest",
    "EvidenceBuckets",
    "EvidenceInput",
    "EvidenceKind",
    "EvidenceRecord",
    "HostFacts",
    "HostCompositionId",
    "ItemId",
    "OsFamily",
    "ParitySubject",
    "PolicyId",
    "ProductSurface",
    "RequestedPlatform",
    "RuntimeKind",
    "TargetSelection",
]
