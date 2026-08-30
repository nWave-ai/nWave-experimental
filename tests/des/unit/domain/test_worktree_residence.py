from __future__ import annotations

from pathlib import Path

import pytest

from des.domain.worktree_anti_rot_triage import (
    TriageState,
    WorktreeAntiRotReceipt,
)
from des.domain.worktree_residence import (
    DurableResidence,
    LeaseEvidence,
    OwnerLease,
    ResidenceAdmission,
    ResidenceDurability,
    ResidenceRefusal,
    lease_from_receipt,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driven_ports.residence_durability_port import ResidenceDurabilityPort


class _Durability(ResidenceDurabilityPort):
    def __init__(self, answer: ResidenceDurability, default: Path | None) -> None:
        self.answer = answer
        self.default = default

    def classify(self, root: Path) -> ResidenceDurability:
        return self.answer

    def durable_default(self, repo: Path) -> Path | None:
        return self.default

    def freeze(self, root: Path) -> bool | Indeterminate:
        return True


@pytest.mark.parametrize(
    "answer", [ResidenceDurability.EPHEMERAL, ResidenceDurability.UNKNOWN]
)
def test_admission_refuses_every_non_durable_observation(
    tmp_path: Path, answer: ResidenceDurability
) -> None:
    result = ResidenceAdmission(_Durability(answer, tmp_path)).admit(tmp_path / "lane")

    assert isinstance(result, ResidenceRefusal)
    assert result.observed is answer
    assert result.what and result.why and result.how


def test_durable_residence_cannot_be_forged_through_public_constructor(
    tmp_path: Path,
) -> None:
    with pytest.raises(TypeError):
        DurableResidence(tmp_path, _token=object())

    result = ResidenceAdmission(
        _Durability(ResidenceDurability.DURABLE, tmp_path)
    ).admit(tmp_path / "lane")
    assert isinstance(result, DurableResidence)


@pytest.mark.parametrize("lane", ["", ".", "..", "a/b", "a\\b"])
def test_default_admission_rejects_non_component_lane_names(
    tmp_path: Path, lane: str
) -> None:
    result = ResidenceAdmission(
        _Durability(ResidenceDurability.DURABLE, tmp_path)
    ).admit_default(tmp_path, lane)

    assert isinstance(result, ResidenceRefusal)


def test_lease_projection_reads_only_retained_liveness_fields() -> None:
    clean = WorktreeAntiRotReceipt(
        state=TriageState.CLEAN, process_matches=(), locked=False
    )
    risk_indeterminate = WorktreeAntiRotReceipt(
        state=TriageState.INDETERMINATE,
        process_matches=(),
        locked=False,
    )

    assert lease_from_receipt(clean, OwnerLease.RELEASED) is LeaseEvidence.FREE
    assert (
        lease_from_receipt(risk_indeterminate, OwnerLease.RELEASED)
        is LeaseEvidence.FREE
    )
    assert lease_from_receipt(clean, OwnerLease.HELD) is LeaseEvidence.HELD
    assert lease_from_receipt(clean, OwnerLease.INDETERMINATE) is LeaseEvidence.UNPROVEN


@pytest.mark.parametrize(
    "processes,locked",
    [
        (Indeterminate("proc failed"), False),
        ((), Indeterminate("lock failed")),
    ],
)
def test_any_unknown_liveness_signal_is_unproven(
    processes: tuple[()] | Indeterminate,
    locked: bool | Indeterminate,
) -> None:
    receipt = WorktreeAntiRotReceipt(
        state=TriageState.INDETERMINATE,
        process_matches=processes,
        locked=locked,
    )

    assert lease_from_receipt(receipt, OwnerLease.RELEASED) is LeaseEvidence.UNPROVEN
