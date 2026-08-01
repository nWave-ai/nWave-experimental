"""Shared real-host probe contract for all parity witness lanes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from des.domain.codex_parity import (
        CandidateDeploymentReceipt,
        CandidateProbeReceipt,
        Digest,
        ItemId,
        ParityEvidenceState,
        ParitySubject,
        WhatWhyHow,
    )
    from des.ports.driven_ports.native_execution_port import NativeExecutionReceipt


class ProbeArmKind(str, Enum):
    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass(frozen=True)
class ProbeArmDescriptor:
    kind: ProbeArmKind
    deployment_receipt: CandidateDeploymentReceipt
    workload_digest: Digest
    nonce: str


@dataclass(frozen=True)
class WitnessDescriptor:
    witness_id: str
    item_id: ItemId
    suite_id: str
    timeout_seconds: float


@dataclass(frozen=True)
class ProbeRequest:
    subject: ParitySubject
    arms: tuple[ProbeArmDescriptor, ...]
    witnesses: tuple[WitnessDescriptor, ...]


@dataclass(frozen=True)
class WitnessObservation:
    witness_id: str
    item_id: ItemId
    arm: ProbeArmKind
    echoed_nonce: str
    state: ParityEvidenceState
    lineage_receipt: CandidateProbeReceipt
    execution_receipt: NativeExecutionReceipt
    observable_digest: Digest | None = None
    diagnostic: WhatWhyHow | None = None


@dataclass(frozen=True)
class ParityAttestation:
    subject: ParitySubject
    observations: tuple[WitnessObservation, ...]


class RealHostProbePort(Protocol):
    def probe(self, request: ProbeRequest) -> ParityAttestation:
        """Run queued witness descriptors against the exact request subject."""
        ...


__all__ = [
    "ParityAttestation",
    "ProbeArmDescriptor",
    "ProbeArmKind",
    "ProbeRequest",
    "RealHostProbePort",
    "WitnessDescriptor",
    "WitnessObservation",
]
