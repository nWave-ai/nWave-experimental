"""Typed residence and owner-lease facts for nWave worktrees.

The module is intentionally free of platform paths and filesystem policy.  A
``DurableResidence`` can only be minted by ``ResidenceAdmission``, which asks
the injected durability port itself; callers cannot pass a favourable enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from des.ports.driven_ports.residence_durability_port import (
        ResidenceDurabilityPort,
    )


class ResidenceDurability(str, Enum):
    DURABLE = "DURABLE"
    EPHEMERAL = "EPHEMERAL"
    UNKNOWN = "UNKNOWN"


_ADMISSION_TOKEN = object()


@dataclass(frozen=True, init=False)
class DurableResidence:
    """A root measured durable by ``ResidenceAdmission``.

    The private token makes the unsafe ``DurableResidence(path)`` shape
    uninhabitable through the public API.  Python reflection can always break
    encapsulation; ordinary production construction cannot.
    """

    root: Path

    def __init__(self, root: Path, *, _token: object) -> None:
        if _token is not _ADMISSION_TOKEN:
            raise TypeError("DurableResidence is constructed by ResidenceAdmission")
        object.__setattr__(self, "root", root.resolve())


@dataclass(frozen=True)
class ResidenceRefusal:
    observed: ResidenceDurability
    what: str
    why: str
    how: str


@dataclass(frozen=True)
class RescuedResidence:
    source: Path
    residence: DurableResidence


@dataclass(frozen=True)
class ExternalResidenceLost:
    source: Path
    what: str
    why: str
    how: str


class ResidenceAdmission:
    """The sole public constructor boundary for durable residence."""

    def __init__(self, durability: ResidenceDurabilityPort) -> None:
        self._durability = durability

    def admit(self, root: Path) -> DurableResidence | ResidenceRefusal:
        candidate = root.resolve()
        observed = self._durability.classify(candidate)
        if observed is ResidenceDurability.DURABLE:
            return DurableResidence(candidate, _token=_ADMISSION_TOKEN)
        return ResidenceRefusal(
            observed=observed,
            what=f"worktree residence {candidate} was not admitted",
            why=f"the platform classified it {observed.value}, not DURABLE",
            how=(
                "For new work, use `des worktree-admit --repo <root> --lane "
                "<name>`. If this path already carries WIP, freeze it and use "
                "the copy-verify-switch rescue; never mutate it in place."
            ),
        )

    def admit_default(
        self, repo: Path, lane_name: str
    ) -> DurableResidence | ResidenceRefusal:
        if not _is_single_component(lane_name):
            return ResidenceRefusal(
                observed=ResidenceDurability.UNKNOWN,
                what=f"lane name {lane_name!r} was not admitted",
                why="a lane name must be one non-special path component",
                how="Pass a single component without separators, '.' or '..'.",
            )
        default_root = self._durability.durable_default(repo.resolve())
        if default_root is None:
            return ResidenceRefusal(
                observed=ResidenceDurability.UNKNOWN,
                what="no durable default residence could be derived",
                why=f"the platform could not bind a durable root to {repo.resolve()}",
                how="Move the repository to durable storage, then retry admission.",
            )
        return self.admit(default_root / lane_name)


def _is_single_component(value: str) -> bool:
    if not value or value in {".", ".."}:
        return False
    return Path(value).name == value and "/" not in value and "\\" not in value


class OwnerLease(str, Enum):
    HELD = "HELD"
    RELEASED = "RELEASED"
    INDETERMINATE = "INDETERMINATE"


class LeaseEvidence(str, Enum):
    FREE = "FREE"
    HELD = "HELD"
    UNPROVEN = "UNPROVEN"


@dataclass(frozen=True)
class LaneIdentity:
    """Git-observable identity recorded inside one linked worktree."""

    lane_name: str
    worktree_root: str
    git_dir: str

    @classmethod
    def observe(cls, root: Path, lane_name: str | None = None) -> LaneIdentity:
        resolved = root.resolve()
        git_marker = resolved / ".git"
        try:
            if git_marker.is_file():
                content = git_marker.read_text(encoding="utf-8").strip()
                prefix = "gitdir:"
                git_dir = (
                    str(Path(content[len(prefix) :].strip()).resolve())
                    if content.startswith(prefix)
                    else ""
                )
            elif git_marker.is_dir():
                git_dir = str(git_marker.resolve())
            else:
                git_dir = ""
        except OSError:
            git_dir = ""
        return cls(
            lane_name=lane_name or resolved.name,
            worktree_root=str(resolved),
            git_dir=git_dir,
        )


def lease_from_receipt(receipt: object, owner: OwnerLease) -> LeaseEvidence:
    """Project retained typed liveness signals onto cleanup lease evidence."""

    process_matches = getattr(receipt, "process_matches", Indeterminate("missing"))
    locked = getattr(receipt, "locked", Indeterminate("missing"))
    if (
        isinstance(process_matches, Indeterminate)
        or isinstance(locked, Indeterminate)
        or owner is OwnerLease.INDETERMINATE
    ):
        return LeaseEvidence.UNPROVEN
    if owner is OwnerLease.HELD or bool(process_matches) or locked is True:
        return LeaseEvidence.HELD
    if owner is OwnerLease.RELEASED and process_matches == () and locked is False:
        return LeaseEvidence.FREE
    return LeaseEvidence.UNPROVEN


__all__ = [
    "DurableResidence",
    "ExternalResidenceLost",
    "LaneIdentity",
    "LeaseEvidence",
    "OwnerLease",
    "RescuedResidence",
    "ResidenceAdmission",
    "ResidenceDurability",
    "ResidenceRefusal",
    "lease_from_receipt",
]
