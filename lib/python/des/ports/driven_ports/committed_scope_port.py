"""CommittedScopePort -- driven port over the committed contract file-set.

AD-22 (ARCH_TECH_DEBT): the former ``CommittedScopePort`` was a CONCRETE class
living in the APPLICATION layer that shelled ``git ls-tree`` inline -- named a
"Port" but structurally an adapter in the wrong layer, with no ABC in
``ports/`` and no adapter in ``adapters/driven/git/``. This module restores the
real boundary: ``CommittedScopePort`` is now the abstract driven port; the git
implementation lives in
``des.adapters.driven.git.committed_scope_adapter.GitCommittedScopeAdapter``
(mirroring the established ``scope_checker.ScopeChecker`` ABC <->
``git_scope_checker.GitScopeChecker`` pattern).

The ``--committed-scope-digest`` / ``--verify-gate-scope`` gate roles collect
ONLY the committed contract-suite file-set at a commit so the digest is
reproducible across checkouts and stable across the compute->verify window
regardless of untracked co-resident WIP. Determining "what is committed" needs
git; per ``feedback_target_machine_independence_2026_05_15`` (AD-21) the gate
LOGIC stays git-free and git enters ONLY behind this read-only driven port,
whose ABSENCE degrades LOUD (``Indeterminate`` -> the fail-closed gate refuses),
never silent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CommittedFileSet:
    """The set of repo-relative contract-suite paths present in a commit."""

    paths: tuple[str, ...]


@dataclass(frozen=True)
class Indeterminate:
    """git could not establish the committed contract (degrade-LOUD signal).

    The gate MUST convert this into a LOUD
    ``health.gate.committed-scope.indeterminate`` event and, in a fail-closed
    context, REFUSE -- never silently fall back to the working tree.
    """

    reason: str


class CommittedScopePort(ABC):
    """Driven, read-only port over the committed contract file-set (git).

    The application layer defines WHAT the committed contract-suite is; the
    adapter decides HOW to read it out of git. ``committed_contract_files``
    returns the committed contract-suite paths at ``commit``, or an
    ``Indeterminate`` when git is absent / the path is not a work-tree / the SHA
    is unresolvable. Pure read of the git index -- no filesystem mutation.
    """

    @abstractmethod
    def committed_contract_files(
        self, repo: Path, commit: str
    ) -> CommittedFileSet | Indeterminate:
        """Return the committed contract-suite file-set, or Indeterminate.

        Callers resolve the commit (the gate shells ``git rev-parse HEAD``)
        before reaching here, so git is established. git exiting non-zero -- the
        path is not a work-tree, or the commit was raced/GC'd between resolution
        and listing -- yields ``Indeterminate``: the gate degrades LOUD rather
        than fingerprint a tree it cannot list.
        """
        ...
