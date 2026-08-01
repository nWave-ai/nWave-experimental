"""SafeFileSystemAdapter -- real, write-scoped filesystem for the converter.

Feature `classic-spine-decommission`, slice-05. Implements the `SafeFileSystem`
driven port against the real filesystem, confining every write to the three
regions the `des-convert-to-atdd-pure` converter is permitted to mutate:

  * the feature directory ``docs/feature/{feature_id}/``,
  * the project config file ``.nwave/config.yaml``,
  * the conversion journal directory ``.nwave/conversion-journal/``.

A write outside that scope raises `OutOfScopeWrite` -- so a hand-edited
`ConversionPlan` can never make `execute(plan)` clobber an arbitrary path.
Reads and existence probes are unrestricted; only mutations are scoped.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from des.domain.telemetry_paths import LedgerFamily, ledger_dir
from des.ports.driven_ports.safe_file_system import OutOfScopeWrite, SafeFileSystem


class SafeFileSystemAdapter(SafeFileSystem):
    """A real filesystem whose writes are confined to a converter's scope.

    Constructed with the workspace root and the feature id; the three allowed
    write regions are derived from those two values.
    """

    def __init__(self, workspace: Path, feature_id: str) -> None:
        self._workspace = Path(workspace)
        self._feature_dir = self._workspace / "docs" / "feature" / feature_id
        self._config_path = self._workspace / ".nwave" / "config.yaml"
        self._journal_dir = self._workspace / ".nwave" / "conversion-journal"
        self._telemetry_dir = ledger_dir(self._workspace, LedgerFamily.ATDD_PURE)

    def read_text(self, path: Path) -> str:
        """Read a UTF-8 text file. Reads are unrestricted."""
        return Path(path).read_text(encoding="utf-8")

    def exists(self, path: Path) -> bool:
        """Whether a path exists. Probes are unrestricted."""
        return Path(path).exists()

    def write_text(self, path: Path, content: str) -> None:
        """Write a UTF-8 text file inside the converter's write scope."""
        target = self._guard(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def make_dir(self, path: Path) -> None:
        """Create a directory (parents, idempotent) inside the write scope."""
        self._guard(path).mkdir(parents=True, exist_ok=True)

    def move(self, source: Path, destination: Path) -> None:
        """Move a file -- both endpoints confined to the write scope."""
        self._guard(source)
        target = self._guard(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(source)), str(target))

    def delete(self, path: Path) -> None:
        """Delete a file (idempotent) inside the converter's write scope."""
        target = self._guard(path)
        if target.is_file():
            target.unlink()

    def _guard(self, path: Path) -> Path:
        """Return the resolved path iff it lies within an allowed write region."""
        resolved = Path(path).resolve()
        if self._within(resolved, self._feature_dir):
            return resolved
        if self._within(resolved, self._journal_dir):
            return resolved
        if self._within(resolved, self._telemetry_dir):
            return resolved
        if resolved == self._config_path.resolve():
            return resolved
        raise OutOfScopeWrite(
            f"write to {resolved} is outside the converter's scope "
            f"(feature dir, .nwave/config.yaml, .nwave/conversion-journal/, "
            f"or .nwave/telemetry/atdd-pure/)"
        )

    @staticmethod
    def _within(candidate: Path, region: Path) -> bool:
        """Whether `candidate` is `region` itself or nested beneath it."""
        region_resolved = region.resolve() if region.exists() else region
        if candidate == region_resolved:
            return True
        return region_resolved in candidate.parents
