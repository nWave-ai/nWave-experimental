from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from des.application.rescue_worktree_residence import rescue_worktree_residence
from des.domain.worktree_residence import (
    DurableResidence,
    ExternalResidenceLost,
    RescuedResidence,
    ResidenceDurability,
    ResidenceRefusal,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driven_ports.residence_durability_port import ResidenceDurabilityPort


class _Durability(ResidenceDurabilityPort):
    def __init__(self, source: Path, default: Path, freeze: bool = True) -> None:
        self.source = source.resolve()
        self.default = default.resolve()
        self.freeze_answer = freeze

    def classify(self, root: Path) -> ResidenceDurability:
        return (
            ResidenceDurability.EPHEMERAL
            if root.resolve() == self.source
            else ResidenceDurability.DURABLE
        )

    def durable_default(self, repo: Path) -> Path | None:
        return self.default

    def freeze(self, root: Path) -> bool | Indeterminate:
        return self.freeze_answer


def _prepare(residence: DurableResidence) -> bool:
    residence.root.mkdir(parents=True)
    (residence.root / ".git").mkdir()
    return True


def test_rescue_copies_tracked_untracked_and_ignored_bytes_without_moving_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "external"
    source.mkdir()
    (source / ".git").write_text("source control metadata", encoding="utf-8")
    (source / "tracked.txt").write_bytes(b"tracked\x00bytes")
    (source / "untracked.bin").write_bytes(b"untracked\xff")
    ignored = source / "ignored"
    ignored.mkdir()
    (ignored / "cache.dat").write_bytes(b"ignored")
    default = tmp_path / "durable"
    result = rescue_worktree_residence(
        source=source,
        repo=tmp_path,
        lane_name="rescued",
        durability=_Durability(source, default),
        prepare_destination=_prepare,
    )

    assert isinstance(result, RescuedResidence)
    destination = default / "rescued"
    assert source.is_dir()
    assert (source / "untracked.bin").read_bytes() == b"untracked\xff"
    assert (destination / "tracked.txt").read_bytes() == b"tracked\x00bytes"
    assert (destination / "untracked.bin").read_bytes() == b"untracked\xff"
    assert (destination / "ignored" / "cache.dat").read_bytes() == b"ignored"
    assert (destination / ".git").is_dir()


def test_freeze_or_destination_failure_refuses_without_touching_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "external"
    source.mkdir()
    (source / "wip.txt").write_text("untouched", encoding="utf-8")
    default = tmp_path / "durable"

    freeze_refusal = rescue_worktree_residence(
        source=source,
        repo=tmp_path,
        lane_name="rescued",
        durability=_Durability(source, default, freeze=False),
        prepare_destination=_prepare,
    )
    destination_refusal = rescue_worktree_residence(
        source=source,
        repo=tmp_path,
        lane_name="rescued",
        durability=_Durability(source, default),
        prepare_destination=lambda residence: False,
    )

    assert isinstance(freeze_refusal, ResidenceRefusal)
    assert isinstance(destination_refusal, ResidenceRefusal)
    assert (source / "wip.txt").read_text(encoding="utf-8") == "untouched"


def test_source_disappearance_is_external_loss_never_success(tmp_path: Path) -> None:
    source = tmp_path / "external"
    source.mkdir()
    (source / "wip.txt").write_text("at risk", encoding="utf-8")
    default = tmp_path / "durable"

    def _external_reaper(residence: DurableResidence) -> bool:
        residence.root.mkdir(parents=True)
        shutil.rmtree(source)
        return True

    result = rescue_worktree_residence(
        source=source,
        repo=tmp_path,
        lane_name="rescued",
        durability=_Durability(source, default),
        prepare_destination=_external_reaper,
    )

    assert isinstance(result, ExternalResidenceLost)
    assert "external" in result.how


def test_prepare_destination_subprocess_failure_is_a_residence_refusal(
    tmp_path: Path,
) -> None:
    source = tmp_path / "external"
    source.mkdir()
    (source / "wip.txt").write_text("untouched", encoding="utf-8")
    default = tmp_path / "durable"

    def _failing_prepare(residence: DurableResidence) -> bool:
        raise subprocess.CalledProcessError(128, ["git", "worktree", "add"])

    result = rescue_worktree_residence(
        source=source,
        repo=tmp_path,
        lane_name="rescued",
        durability=_Durability(source, default),
        prepare_destination=_failing_prepare,
    )

    assert isinstance(result, ResidenceRefusal)
    assert (source / "wip.txt").read_text(encoding="utf-8") == "untouched"
