"""EnvProvisionPort -- driven port for per-worktree isolated venv provisioning.

CREATE_NEW (des-refactor-fixer-swarm, ADR-SWARM-001 Decision 2). Each worktree
gets its OWN ``.venv`` (never a symlink into the parent's); the test runner
invokes ``<worktree>/.venv/bin/python -m pytest``, never ``uv run`` (which
re-syncs/re-points the editable install on every call -- under N concurrent
worktrees, N concurrent ``uv sync`` calls race on the SAME venv path family).

Pure interface -- no behavior to scaffold. The concrete adapter
(``des.adapters.driven.refactor.uv_env_provision_adapter.UvEnvProvisionAdapter``)
carries the Mandate-7 RED scaffold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class EnvProvisionPort(ABC):
    """Driven port: provisions an isolated venv inside a worktree."""

    @abstractmethod
    def probe(self) -> bool:
        """Earned-Trust startup probe: the package manager (``uv --version``)
        must be resolvable before the first item drains."""
        ...

    @abstractmethod
    def provision(self, worktree_path: Path) -> Path:
        """Provision an isolated venv rooted at ``worktree_path``. Returns the
        venv's python executable path (``<worktree>/.venv/bin/python``). A
        provisioning failure on one item is a per-item refusal
        (``RefactorItemFailed``), never a silent skip."""
        ...
