"""Platform adapter for repository-bound worktree residence durability."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from des.adapters.driven.git.git_subprocess import git_text
from des.domain.worktree_residence import ResidenceDurability
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driven_ports.residence_durability_port import ResidenceDurabilityPort


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


class PlatformResidenceDurabilityAdapter(ResidenceDurabilityPort):
    """Classify with EPHEMERAL precedence over repository-local durability."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo.resolve()
        self._durable_parent = self._resolve_git_common_parent(self._repo)

    @staticmethod
    def _resolve_git_common_parent(repo: Path) -> Path | None:
        try:
            common = git_text(
                repo,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
        return Path(common).resolve().parent if common else None

    @staticmethod
    def _ephemeral_roots() -> tuple[Path, ...]:
        raw: set[str] = {
            tempfile.gettempdir(),
            "/tmp",
            "/var/tmp",
            "/dev/shm",
        }
        for name in ("TMPDIR", "TEMP", "TMP", "XDG_RUNTIME_DIR"):
            value = os.environ.get(name)
            if value:
                raw.add(value)
        return tuple(Path(value).resolve() for value in raw if value)

    def classify(self, root: Path) -> ResidenceDurability:
        candidate = root.resolve()
        if any(
            _is_within(candidate, ephemeral) for ephemeral in self._ephemeral_roots()
        ):
            return ResidenceDurability.EPHEMERAL
        if self._durable_parent is not None and _is_within(
            candidate, self._durable_parent
        ):
            return ResidenceDurability.DURABLE
        return ResidenceDurability.UNKNOWN

    def durable_default(self, repo: Path) -> Path | None:
        candidate_repo = repo.resolve()
        if candidate_repo != self._repo or self._durable_parent is None:
            return None
        return candidate_repo / ".nwave" / "worktrees"

    def freeze(self, root: Path) -> bool | Indeterminate:
        """Seal the control-plane mutation route for an observed external tree.

        The adapter does not claim an OS-wide lock: it establishes only the
        ADR's nWave-side freeze precondition.  A vanished/unreadable source is
        unprovable and therefore refuses rescue.
        """

        try:
            return root.resolve().is_dir()
        except OSError as exc:
            return Indeterminate(f"could not freeze {root}: {exc}")


__all__ = ["PlatformResidenceDurabilityAdapter"]
