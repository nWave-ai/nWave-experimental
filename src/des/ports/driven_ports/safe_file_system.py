"""SafeFileSystem -- a write-scoped driven port for the conversion CLI.

Feature `classic-spine-decommission`, slice-05. The `des-convert-to-atdd-pure`
converter mutates exactly three regions of a workspace:

  * the feature directory ``docs/feature/{feature_id}/`` (heading promotion,
    roadmap archival),
  * the project config ``.nwave/config.yaml`` (the workflow.mode flip),
  * the conversion journal ``.nwave/conversion-journal/`` (the M3 resumable
    side-effect ledger).

DESIGN Reuse Analysis (capability-injection): rather than hand the impure
``execute(plan)`` a raw filesystem, it is handed a `SafeFileSystem` whose every
write is checked against those three allowed regions. A write outside the
scope raises `OutOfScopeWrite` -- a hand-edited plan can never make the
converter clobber an arbitrary path. The pure ``dry_run`` planner never touches
this port at all (unbounded-preservation contract shape).

The port is deliberately small: text read/write, an existence probe, a move,
and an mkdir -- exactly the operations the converter's four journalled steps
need.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class OutOfScopeWrite(Exception):
    """Raised when a `SafeFileSystem` write targets a path outside its scope.

    Fail-closed: the converter refuses a write the moment it would land
    outside the feature directory, the project config, or the conversion
    journal -- it never silently clobbers an arbitrary workspace path.
    """


class SafeFileSystem(ABC):
    """A filesystem driven port whose writes are confined to a known scope."""

    @abstractmethod
    def read_text(self, path: Path) -> str:
        """Read a UTF-8 text file. Reads are unrestricted."""

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Whether a path exists. Probes are unrestricted."""

    @abstractmethod
    def write_text(self, path: Path, content: str) -> None:
        """Write a UTF-8 text file. Raises `OutOfScopeWrite` outside scope."""

    @abstractmethod
    def make_dir(self, path: Path) -> None:
        """Create a directory (parents, idempotent). Scoped like `write_text`."""

    @abstractmethod
    def move(self, source: Path, destination: Path) -> None:
        """Move a file. Both endpoints must lie within scope."""

    @abstractmethod
    def delete(self, path: Path) -> None:
        """Delete a file (idempotent). Scoped like `write_text`.

        Used by the converter's ``--rollback`` inverse ops to remove the
        seeded ledger and the conversion journal -- both inside the write
        scope -- so a rolled-back feature carries no conversion residue.
        """
