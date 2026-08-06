"""Pure shared vocabulary for Codex host-parity evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, NewType

from des.domain.at_review_signing import canonical_signed_json


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class ParityEvidenceState(str, Enum):
    PROVED = "proved"
    DOCUMENTED = "documented"
    UNVERIFIED = "unverified"
    UNSUPPORTED = "unsupported"
    DEGRADED = "degraded"
    INDETERMINATE = "indeterminate"
    FAILED = "failed"


Digest = NewType("Digest", str)
ItemId = NewType("ItemId", str)
PolicyId = NewType("PolicyId", str)


class ProductSurface(str, Enum):
    CLI = "cli"
    DESKTOP = "desktop"


class OsFamily(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"


class RuntimeKind(str, Enum):
    LINUX_NATIVE = "linux-native"
    WSL2 = "wsl2"
    WINDOWS_NATIVE = "windows-native"
    MACOS_NATIVE = "macos-native"


class RequestedPlatform(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"


class ReceiptState(str, Enum):
    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    INDETERMINATE = "indeterminate"
    FAILED = "failed"


class CandidateOrigin(str, Enum):
    ASSEMBLED_DISTRIBUTION = "assembled-distribution"
    ISOLATED_INSTALL = "isolated-install"
    SOURCE_TREE = "source-tree"
    DEVELOPER_HOME = "developer-home"
    GLOBAL_INSTALL = "global-install"


@dataclass(frozen=True)
class HostFacts:
    vendor: str
    product_surface: ProductSurface
    binary_version: str
    binary_digest: Digest
    os_family: OsFamily
    os_version: str
    runtime_kind: RuntimeKind
    capability_fingerprint: Digest
    policy_profile: str


@dataclass(frozen=True)
class TargetSelection:
    requested_platform: RequestedPlatform
    detected_capabilities: frozenset[str]


@dataclass(frozen=True)
class WhatWhyHow:
    what: str
    why: str
    how: str

    def __post_init__(self) -> None:
        if not self.what or not self.why or not self.how:
            raise ValueError("WHAT/WHY/HOW fields must all be non-empty")


@dataclass(frozen=True)
class CandidateInputs:
    distribution_digest: Digest
    public_manifest_digest: Digest
    build_recipe_version: str


@dataclass(frozen=True)
class CandidateId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("CandidateId must be non-empty")


@dataclass(frozen=True)
class HostCompositionId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("HostCompositionId must be non-empty")


@dataclass(frozen=True)
class CandidateLocator:
    value: str
    origin: CandidateOrigin


@dataclass(frozen=True)
class MaterialDigestObservation:
    state: ReceiptState
    digest: Digest | None
    diagnostic: WhatWhyHow | None = None

    def __post_init__(self) -> None:
        if self.state is ReceiptState.SUCCEEDED:
            if self.digest is None or self.diagnostic is not None:
                raise ValueError("SUCCEEDED digest observation requires only digest")
        elif self.diagnostic is None:
            raise ValueError("non-success digest observation requires WHAT/WHY/HOW")


@dataclass(frozen=True)
class CandidateBuildReceipt:
    state: ReceiptState
    candidate_id: CandidateId | None
    candidate_inputs: CandidateInputs | None
    artifact_digest: Digest | None
    artifact: CandidateLocator
    diagnostic: WhatWhyHow | None = None

    def __post_init__(self) -> None:
        if self.state is ReceiptState.SUCCEEDED:
            if (
                self.candidate_id is None
                or self.candidate_inputs is None
                or self.artifact_digest is None
                or self.diagnostic is not None
            ):
                raise ValueError("successful build receipt is incomplete")
        elif self.diagnostic is None:
            raise ValueError("non-success build receipt requires WHAT/WHY/HOW")


@dataclass(frozen=True)
class CandidateDeploymentReceipt:
    state: ReceiptState
    candidate_id: CandidateId | None
    artifact_digest_reverified: Digest | None
    installed_tree_digest: Digest | None
    isolated_prefix: CandidateLocator
    diagnostic: WhatWhyHow | None = None

    def __post_init__(self) -> None:
        if self.state is ReceiptState.SUCCEEDED:
            if (
                self.candidate_id is None
                or self.artifact_digest_reverified is None
                or self.installed_tree_digest is None
                or self.isolated_prefix.origin is not CandidateOrigin.ISOLATED_INSTALL
                or self.diagnostic is not None
            ):
                raise ValueError("successful deployment receipt is incomplete")
        elif self.diagnostic is None:
            raise ValueError("non-success deployment receipt requires WHAT/WHY/HOW")


@dataclass(frozen=True)
class CandidateProbeReceipt:
    state: ReceiptState
    candidate_id: CandidateId | None
    installed_tree_digest_reverified: Digest | None
    observed_binary_digest: Digest | None
    provenance: CandidateOrigin
    diagnostic: WhatWhyHow | None = None

    def __post_init__(self) -> None:
        if self.state is ReceiptState.SUCCEEDED:
            if (
                self.candidate_id is None
                or self.installed_tree_digest_reverified is None
                or self.observed_binary_digest is None
                or self.provenance is not CandidateOrigin.ISOLATED_INSTALL
                or self.diagnostic is not None
            ):
                raise ValueError("successful probe receipt is incomplete")
        elif self.diagnostic is None:
            raise ValueError("non-success probe receipt requires WHAT/WHY/HOW")


@dataclass(frozen=True)
class ParitySubject:
    composition_id: HostCompositionId
    candidate_id: CandidateId
    manifest_digest: Digest
    target: TargetSelection

    def validation_error(self) -> str | None:
        if not self.composition_id.value:
            return "composition identity is empty"
        if not self.candidate_id.value:
            return "candidate identity is empty"
        if not self.manifest_digest:
            return "manifest identity is empty"
        if not isinstance(self.target.requested_platform, RequestedPlatform):
            return "requested platform is outside the closed target vocabulary"
        return None


@dataclass(frozen=True)
class EvidenceInput:
    kind: ParityEvidenceState
    policy_id: PolicyId | None = None
    reason: str | None = None
    remediation: str | None = None

    def __post_init__(self) -> None:
        state = ParityEvidenceState(self.kind)
        if state is ParityEvidenceState.DEGRADED:
            if (
                not self.policy_id
                or self.reason is not None
                or self.remediation is not None
            ):
                raise ValueError("DEGRADED requires only a non-empty policy_id")
            return
        if state in {ParityEvidenceState.INDETERMINATE, ParityEvidenceState.FAILED}:
            if self.policy_id is not None or not self.reason or not self.remediation:
                raise ValueError(
                    f"{state.value} requires reason/remediation and no policy_id"
                )
            return
        if (
            self.policy_id is not None
            or self.reason is not None
            or self.remediation is not None
        ):
            raise ValueError(f"{state.value} does not accept evidence payload fields")


@dataclass(frozen=True)
class DeclaredSurface:
    manifest_digest: Digest
    role_inventory_digest: Digest
    lifecycle_catalogue_digest: Digest
    loop_catalogue_digest: Digest
    items: frozenset[ItemId]


@dataclass(frozen=True)
class EvidenceRecord:
    item_id: ItemId
    kind: ParityEvidenceState
    subject: ParitySubject
    policy_id: PolicyId | None = None
    reason: str | None = None
    remediation: str | None = None

    def __post_init__(self) -> None:
        EvidenceInput(
            kind=self.kind,
            policy_id=self.policy_id,
            reason=self.reason,
            remediation=self.remediation,
        )


@dataclass(frozen=True)
class ClassifiedEvidence:
    state: ParityEvidenceState
    policy_id: str | None = None
    reason: str | None = None
    remediation: str | None = None

    @property
    def contributes_to_full_parity(self) -> bool:
        return self.state is ParityEvidenceState.PROVED


@dataclass(frozen=True)
class TargetVerdict:
    requested_platform: str
    is_refused: bool
    what: str = ""
    why: str = ""
    how: str = ""


@dataclass(frozen=True)
class InventoryVerdict:
    is_closed: bool
    declared_count: int
    accounted_count: int
    what: str = ""
    why: str = ""
    how: str = ""
    partitions: Mapping[ParityEvidenceState, frozenset[str]] | None = None

    @property
    def is_failed(self) -> bool:
        return not self.is_closed


@dataclass(frozen=True)
class ParityVerdict:
    is_full_parity: bool
    is_failed: bool
    state: ParityEvidenceState
    evidence_counts: Mapping[ParityEvidenceState, int]
    evidence_states: frozenset[ParityEvidenceState]
    what: str = ""
    why: str = ""
    how: str = ""


def content_identity(record: Mapping[str, object], fields: tuple[str, ...]) -> str:
    """Hash a typed record through the repository's canonical serializer."""
    return hashlib.sha256(canonical_signed_json(dict(record), fields)).hexdigest()


def mint_candidate_id(inputs: CandidateInputs) -> CandidateId:
    """Mint once from exact distribution bytes plus its public build contract."""
    record = {
        "distribution_digest": str(inputs.distribution_digest),
        "public_manifest_digest": str(inputs.public_manifest_digest),
        "build_recipe_version": inputs.build_recipe_version,
    }
    fields = (
        "distribution_digest",
        "public_manifest_digest",
        "build_recipe_version",
    )
    return CandidateId(content_identity(record, fields))


def close_population(
    declared: Iterable[str], buckets: Mapping[object, Iterable[str]]
) -> InventoryVerdict:
    declared_sequence = tuple(declared)
    declared_items = set(declared_sequence)
    if len(declared_sequence) != len(declared_items):
        return InventoryVerdict(
            False,
            len(declared_items),
            0,
            "declared inventory contains duplicates",
            "item identity is not unique",
            "deduplicate the declared manifest",
        )
    canonical_buckets: dict[ParityEvidenceState, frozenset[str]] = {}
    accounted: set[str] = set()
    duplicates: set[str] = set()
    for raw_state, items in buckets.items():
        try:
            state = ParityEvidenceState(
                raw_state.value if hasattr(raw_state, "value") else str(raw_state)
            )
        except ValueError:
            return InventoryVerdict(
                False,
                len(declared_items),
                len(accounted),
                "inventory contains an unknown evidence bucket",
                f"unknown bucket={raw_state!r}",
                "use only ParityEvidenceState buckets",
            )
        sequence = tuple(items)
        current = set(sequence)
        if len(sequence) != len(current):
            duplicates.update(current)
        canonical_buckets[state] = frozenset(current)
        duplicates.update(accounted.intersection(current))
        accounted.update(current)
    missing = declared_items - accounted
    unknown = accounted - declared_items
    if missing or unknown or duplicates:
        return InventoryVerdict(
            is_closed=False,
            declared_count=len(declared_items),
            accounted_count=len(accounted),
            what="parity inventory is not a closed exact partition",
            why=(
                f"missing={sorted(missing)!r}, unknown={sorted(unknown)!r}, "
                f"duplicates={sorted(duplicates)!r}"
            ),
            how="account for each declared item exactly once and remove undeclared evidence",
        )
    return InventoryVerdict(
        True, len(declared_items), len(accounted), partitions=canonical_buckets
    )


__all__ = [
    "CandidateBuildReceipt",
    "CandidateDeploymentReceipt",
    "CandidateId",
    "CandidateInputs",
    "CandidateLocator",
    "CandidateOrigin",
    "CandidateProbeReceipt",
    "ClassifiedEvidence",
    "DeclaredSurface",
    "Digest",
    "EvidenceInput",
    "EvidenceRecord",
    "HostCompositionId",
    "HostFacts",
    "InventoryVerdict",
    "ItemId",
    "MaterialDigestObservation",
    "OsFamily",
    "ParityEvidenceState",
    "ParitySubject",
    "ParityVerdict",
    "PolicyId",
    "ProductSurface",
    "ReceiptState",
    "RequestedPlatform",
    "RuntimeKind",
    "TargetSelection",
    "TargetVerdict",
    "WhatWhyHow",
    "close_population",
    "content_identity",
    "mint_candidate_id",
]
