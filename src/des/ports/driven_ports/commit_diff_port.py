"""CommitDiffPort -- driven port over a single commit's changed-path diff (D8).

`f-prefactoring-dispatch-clears-honestly` slice-02 (Green-to-Green Seal, D7-D12).
The anti-gaming fact `check_at_review`'s green-to-green seal needs is: did THIS
commit's diff touch a test file? A behavior-preserving prefactoring that also
weakens/adds a test is a disguised behavior change (D10). Determining a
commit's changed-path set needs git; per
`feedback_target_machine_independence_2026_05_15` (AD-21) the gate LOGIC stays
git-free and git enters ONLY behind this read-only driven port, whose ABSENCE
degrades LOUD (``Indeterminate`` -- REUSED from ``committed_scope_port``, the
same degrade-LOUD VO every sibling port reuses) -- never silent.

Mirrors the established ``CommittedScopePort`` shape (abstract driven port in
`ports/`, a real adapter in `adapters/driven/git/`): the application layer
defines WHAT the changed-path set is; the adapter decides HOW to read it out
of git.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["CommitDiffPort", "Indeterminate"]


class CommitDiffPort(ABC):
    """Driven, read-only port over one commit's changed-path set (git).

    ``changed_paths`` returns the repo-relative paths ``commit_sha`` touched,
    or an ``Indeterminate`` when git is absent / the path is not a work-tree /
    the SHA is unresolvable. Pure read of the git history -- no filesystem
    mutation.
    """

    @abstractmethod
    def changed_paths(self, repo: Path, commit_sha: str) -> list[str] | Indeterminate:
        """Return the repo-relative paths ``commit_sha`` changed, or Indeterminate.

        A degrade to ``Indeterminate`` (ANY reason git could not answer) must
        surface fail-closed at the consulting gate -- never a silent pass.
        """
        ...
