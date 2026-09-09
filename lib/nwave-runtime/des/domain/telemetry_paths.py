"""The one place that decides where current telemetry subtrees live.

This module is pure: it computes paths and touches no filesystem, so it may sit
in the domain layer and be imported by application, ports and adapters alike
without inverting the declared dependency direction.

The subtrees are an enum rather than free strings so an unknown value fails
loudly instead of silently constructing a path under a directory nobody
writes.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "TELEMETRY_ROOT_PARTS",
    "TelemetrySubtree",
    "subtree_dir",
    "telemetry_root",
]

#: Repo-relative parts of the telemetry root. Kept as parts, not a string, so a
#: caller never has to know the separator, and so `telemetry_root` is the only
#: place that joins them.
TELEMETRY_ROOT_PARTS: tuple[str, ...] = (".nwave", "telemetry")


class TelemetrySubtree(str, Enum):
    """Current non-ledger directories under the telemetry root.

    `red-green/` is a last-write-wins cache of JSON seal files, not an
    append-only workflow ledger.
    """

    RED_GREEN = "red-green"


def telemetry_root(repo: Path) -> Path:
    """The telemetry root under ``repo``. The ONLY place these parts are joined."""
    return repo.joinpath(*TELEMETRY_ROOT_PARTS)


def subtree_dir(repo: Path, subtree: TelemetrySubtree) -> Path:
    """The non-ledger telemetry subtree directory, with no filename appended.

    Raises TypeError on a value that is not a `TelemetrySubtree`, naming the
    accepted set.
    """
    if not isinstance(subtree, TelemetrySubtree):
        accepted = ", ".join(sorted(member.value for member in TelemetrySubtree))
        raise TypeError(
            f"WHAT: subtree_dir was given subtree {subtree!r}, which is not a "
            "TelemetrySubtree. "
            "WHY: an unrecognised subtree would build a path under a "
            "directory nothing writes. "
            f"HOW: pass one of TelemetrySubtree -- accepted values: {accepted}."
        )
    return telemetry_root(repo) / subtree.value
