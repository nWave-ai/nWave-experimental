"""des.ports.driven_ports.feature_scan_port -- read-only feature-tree scan port.

Feature `classic-spine-decommission`, slice-01/slice-03. The driven port the
`des-classify-features` CLI uses to enumerate and read feature directories
under a `docs/feature/*` tree.

Reuse Analysis (DESIGN hard gate): the port exposes READ methods ONLY -- no
write methods. The classification manifest is written by the CLI driving
adapter, not through this port; coupling a write surface onto the read port
would let the pure classifier reach a mutation it must never have.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class FeatureScanPort(ABC):
    """Read-only port over a `docs/feature/*` legacy-feature tree."""

    @abstractmethod
    def feature_dirs(self, features_root: Path) -> list[Path]:
        """Enumerate the feature directories directly under `features_root`.

        Args:
            features_root: Absolute path to a `docs/feature` tree.

        Returns:
            The child directories of `features_root`, sorted by name. Empty
            when `features_root` does not exist or holds no subdirectories.
        """

    @abstractmethod
    def read_text(self, path: Path) -> str | None:
        """Read a UTF-8 text file under the feature tree.

        Args:
            path: Absolute path to a file.

        Returns:
            The file's text, or ``None`` when the file does not exist.
        """

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Whether a path exists under the feature tree."""

    @abstractmethod
    def git_tree_sha(self, feature_dir: Path) -> str:
        """The git tree-object SHA of a feature directory at ``HEAD``.

        The migration manifest stamps this value as a feature row's
        ``git_state`` so the converter's M7 staleness guard can compare it
        against the live tree. Read-only by construction -- it inspects git
        history, never mutates.

        Args:
            feature_dir: Absolute path to a feature directory inside a repo.

        Returns:
            The 40-char hex tree-object SHA, or ``""`` when the directory is
            untracked, not inside a git repository, or the repo has no
            ``HEAD`` (a fresh repo). An empty stamp is symmetric with the
            converter's comparator, which treats an unstampable feature as
            never-stale rather than refusing it.
        """
