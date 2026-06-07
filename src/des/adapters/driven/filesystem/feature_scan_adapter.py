"""des.adapters.driven.filesystem.feature_scan_adapter -- real read-only scan.

Feature `classic-spine-decommission`, slice-01/slice-03. Production driven
adapter implementing `FeatureScanPort` over the real filesystem. Read-only by
construction -- it never writes, matching the port contract.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.feature_scan_port import FeatureScanPort


if TYPE_CHECKING:
    from pathlib import Path


class FeatureScanAdapter(FeatureScanPort):
    """Real read-only filesystem implementation of `FeatureScanPort`."""

    def feature_dirs(self, features_root: Path) -> list[Path]:
        """Enumerate the feature directories directly under `features_root`."""
        if not features_root.is_dir():
            return []
        return sorted(
            (child for child in features_root.iterdir() if child.is_dir()),
            key=lambda child: child.name,
        )

    def read_text(self, path: Path) -> str | None:
        """Read a UTF-8 text file, or return ``None`` when it is absent."""
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def exists(self, path: Path) -> bool:
        """Whether a path exists under the feature tree."""
        return path.exists()

    def git_tree_sha(self, feature_dir: Path) -> str:
        """The git tree-object SHA of ``feature_dir`` at ``HEAD``.

        Resolves the repo top-level the directory belongs to, then reads the
        directory's tree-object SHA with ``git rev-parse HEAD:{rel}``. Returns
        ``""`` on any non-zero git exit -- an untracked directory, a non-repo
        path, or a fresh repo with no ``HEAD``. Bundle-safe: stdlib
        ``subprocess`` over the ``git`` binary, the same dependency the
        converter's ``_feature_dir_tree_ish`` already assumes.
        """
        toplevel = subprocess.run(
            ["git", "-C", str(feature_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if toplevel.returncode != 0:
            return ""
        relative = feature_dir.resolve().relative_to(toplevel.stdout.strip()).as_posix()
        completed = subprocess.run(
            ["git", "-C", str(feature_dir), "rev-parse", f"HEAD:{relative}"],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()
