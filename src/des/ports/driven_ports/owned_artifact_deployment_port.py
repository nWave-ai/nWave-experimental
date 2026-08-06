"""Owned-artifact deployment transaction contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from des.domain.codex_parity import (
        Digest,
        ParitySubject,
        ReceiptState,
        WhatWhyHow,
    )


class ArtifactOperationKind(str, Enum):
    UPSERT = "upsert"
    REMOVE = "remove"


@dataclass(frozen=True)
class OwnedArtifactIntent:
    artifact_id: str
    owner_id: str
    target_key: str
    operation: ArtifactOperationKind
    expected_preimage_digest: Digest | None
    desired_content_digest: Digest | None


@dataclass(frozen=True)
class DeploymentPlan:
    plan_id: str
    subject: ParitySubject
    intents: tuple[OwnedArtifactIntent, ...]


@dataclass(frozen=True)
class ArtifactMutationReceipt:
    artifact_id: str
    target_key: str
    preimage_digest: Digest | None
    postimage_digest: Digest | None
    changed: bool


@dataclass(frozen=True)
class DeploymentReceipt:
    plan_id: str
    subject: ParitySubject
    state: ReceiptState
    mutations: tuple[ArtifactMutationReceipt, ...]
    rollback_token: str | None
    diagnostic: WhatWhyHow | None = None


@dataclass(frozen=True)
class RollbackReceipt:
    plan_id: str
    subject: ParitySubject
    state: ReceiptState
    restored_artifact_ids: tuple[str, ...]
    diagnostic: WhatWhyHow | None = None


class OwnedArtifactDeploymentPort(Protocol):
    def deploy(self, plan: DeploymentPlan) -> DeploymentReceipt: ...

    def rollback(self, receipt: DeploymentReceipt) -> RollbackReceipt: ...


__all__ = [
    "ArtifactMutationReceipt",
    "ArtifactOperationKind",
    "DeploymentPlan",
    "DeploymentReceipt",
    "OwnedArtifactDeploymentPort",
    "OwnedArtifactIntent",
    "RollbackReceipt",
]
