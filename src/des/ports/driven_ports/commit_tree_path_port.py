"""CommitTreePathPort -- driven port over "did path P exist in commit C's tree?"

`lane-seal-refuses-premature` (part B of the two-lane
`fix-slice-seal-carries-commit-sha` chain). Part A threaded `commit_sha` into
the `SliceCommitVerified` ledger record -- the join key a later check needs
now EXISTS. Part B is that later check: given a seal's `commit_sha`, did the
AT file(s) the seal attests actually exist in the repo tree AT that commit?
A seal recorded before its own AT was ever committed (the slice-03 defect --
55 minutes premature, invisible for two months because the record carried no
sha to join against) is exactly the fact this port answers NO to.

Mirrors the established ``CommittedScopePort`` / ``CommitDiffPort`` shape
(abstract driven port in ``ports/``, a real adapter in
``adapters/driven/git/``): the application layer defines WHAT "existed at
that commit" means; the adapter decides HOW to read it out of git. Per
`feedback_target_machine_independence_2026_05_15` (AD-21) git enters ONLY
behind this read-only driven port, whose ABSENCE degrades LOUD
(``Indeterminate`` -- REUSED from ``committed_scope_port``, the same
degrade-LOUD VO every sibling port reuses) -- never silent, and never a
retroactive FAIL: "I could not tell" and "it did not exist" are two distinct
outcomes (GDP-8), and only the latter licenses a REJECT.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["CommitTreePathPort", "Indeterminate"]


class CommitTreePathPort(ABC):
    """Driven, read-only port: does ``rel_path`` resolve to a blob in
    ``commit_sha``'s tree (git)?

    ``path_exists_at_commit`` returns ``True``/``False`` when ``commit_sha``
    itself resolves cleanly (a definitive EXISTS / NOT_EXISTS -- the commit
    is real, so a miss is a genuine tree fact, never an artifact of a bad
    sha), or an ``Indeterminate`` when git is absent / the path is not a
    work-tree / ``commit_sha`` itself is unresolvable (GC'd, shallow clone,
    truncated). Pure read of the git history -- no filesystem mutation.
    """

    @abstractmethod
    def path_exists_at_commit(
        self, repo: Path, commit_sha: str, rel_path: str
    ) -> bool | Indeterminate:
        """Return whether ``rel_path`` existed in ``commit_sha``'s tree.

        A degrade to ``Indeterminate`` (git absent, ``commit_sha``
        unresolvable) must surface fail-closed at the consulting gate as
        "could not verify" -- never collapsed into either ``True`` or
        ``False``, and never a silent pass.
        """
        ...
