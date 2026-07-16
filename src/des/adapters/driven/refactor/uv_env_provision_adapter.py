"""UvEnvProvisionAdapter -- EnvProvisionPort implementation via ``uv sync``.

CREATE_NEW file (des-refactor-fixer-swarm slice-01, ADR-SWARM-001 Decision 2).
``uv sync`` is hardcoded for this slice per the feature-delta's Open Question 1
(Recommendation A): ``des refactor`` is a nWave-repo-internal tool, not a
shipped target-project gate, so a general package-manager detector is
speculative generality with a zero-count second caller today.

A worktree that carries its own ``pyproject.toml`` (the real nWave-dev repo)
gets a full ``uv sync`` (installs the project's declared dependencies, D2's
literal intent). A worktree with no ``pyproject.toml`` (a hermetic fixture
repo, or any target this harness is pointed at that is not itself a uv
project) falls back to ``uv venv`` -- a bare, real, non-symlink ``.venv`` still
gets provisioned (AT-2's isolation contract), it is simply empty of installed
dependencies.

``.venv`` hygiene is OWNED by the harness (D4 / GitWorktreeAdapter's staged-
``.venv`` refusal), NOT delegated to uv's convenience ``.venv/.gitignore``
(which ``uv`` drops with a ``*`` pattern that self-ignores the whole tree). If
that auto-gitignore were left in place, an agent that accidentally staged its
own ``.venv`` would be SILENTLY neutralised -- git would refuse the add with no
persistent trace, so the harness's own LOUD hygiene guard (the merge-back
refusal) could never observe the defect. Stripping it makes a staged ``.venv``
visible to git, so the harness's single-source-of-truth guard is the one that
decides (LOUD refusal), never a hidden convenience file.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

from des.ports.driven_ports.env_provision_port import EnvProvisionPort


class UvEnvProvisionAdapter(EnvProvisionPort):
    """Real adapter -- provisions a per-worktree venv via ``uv sync``/``uv venv``."""

    def probe(self) -> bool:
        return shutil.which("uv") is not None

    def provision(self, worktree_path: Path) -> Path:
        command = (
            ["uv", "sync"]
            if (worktree_path / "pyproject.toml").is_file()
            else ["uv", "venv"]
        )
        subprocess.run(
            command, cwd=worktree_path, check=True, capture_output=True, text=True
        )
        self._surrender_venv_hygiene_to_harness(worktree_path)
        return worktree_path / ".venv" / "bin" / "python"

    def _surrender_venv_hygiene_to_harness(self, worktree_path: Path) -> None:
        """Remove uv's self-ignoring ``.venv/.gitignore`` so the harness's own
        staged-``.venv`` guard is the single source of hygiene truth (D4)."""
        auto_gitignore = worktree_path / ".venv" / ".gitignore"
        if auto_gitignore.is_file():
            auto_gitignore.unlink()
