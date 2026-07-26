"""The one place that decides where a telemetry ledger lives.

Six resolvers used to answer this question independently -- one per CLI that
happened to need it -- and the `atdd-pure` family alone was spelled out at
fifteen call sites. Nothing was wrong at any single site; what was missing was
somewhere that answered for the shape of the whole. Move the root, rename a
family, or change the per-feature file convention, and you had to find every
copy: the change was cheap and finding it was not.

This module is pure: it computes paths and touches no filesystem, so it may sit
in the domain layer and be imported by application, ports and adapters alike
without inverting the declared dependency direction.

The families are an ENUM rather than free strings on purpose. A caller that
passes an unknown family gets a refusal naming what exists, instead of silently
constructing a path under a directory nobody writes -- which reads, downstream,
as "this feature has no evidence".
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["TELEMETRY_ROOT_PARTS", "LedgerFamily", "ledger_path", "telemetry_root"]

#: Repo-relative parts of the telemetry root. Kept as parts, not a string, so a
#: caller never has to know the separator, and so `telemetry_root` is the only
#: place that joins them.
TELEMETRY_ROOT_PARTS: tuple[str, ...] = (".nwave", "telemetry")


class LedgerFamily(str, Enum):
    """The ledger families this product actually writes.

    `str` mixin so an existing call site that formats the value keeps working
    byte-identically during the migration -- the point of a prefactoring is that
    behaviour does not move while the shape does.
    """

    ATDD_PURE = "atdd-pure"
    EXAMINE = "examine"
    REVIEW = "review"
    RED_GREEN = "red-green"
    FEATURE_END = "feature-end"


def telemetry_root(repo: Path) -> Path:
    """The telemetry root under ``repo``. The ONLY place these parts are joined."""
    return repo.joinpath(*TELEMETRY_ROOT_PARTS)


def ledger_path(repo: Path, family: LedgerFamily, feature_id: str) -> Path:
    """The per-feature ledger file for ``family``.

    Raises TypeError on a family that is not a `LedgerFamily`, naming the
    accepted set. A silently-constructed path under an unwritten directory is
    indistinguishable downstream from a feature that produced no evidence, and
    that confusion is exactly what a single home exists to prevent.
    """
    if not isinstance(family, LedgerFamily):
        accepted = ", ".join(sorted(member.value for member in LedgerFamily))
        raise TypeError(
            f"WHAT: ledger_path was given family {family!r}, which is not a "
            "LedgerFamily. "
            "WHY: an unrecognised family would build a path under a directory "
            "nothing writes, and an empty ledger reads downstream as 'this "
            "feature produced no evidence' rather than as a caller mistake. "
            f"HOW: pass one of LedgerFamily -- accepted values: {accepted}."
        )
    return telemetry_root(repo) / family.value / f"{feature_id}.jsonl"
