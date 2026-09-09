"""GitCommitDiffAdapter -- git implementation of CommitDiffPort (D8).

`f-prefactoring-dispatch-clears-honestly` slice-02 (Green-to-Green Seal,
D7-D12). The concrete git side of the changed-path boundary the green-to-
green seal's anti-gaming fact needs (D10): did THIS commit's diff touch a
test file? Mirrors the established ``CommittedScopePort`` <->
``GitCommittedScopeAdapter`` shape: the application layer (``check_at_review``
/ ``_check_green_to_green``) depends on the ``CommitDiffPort`` ABC; this
adapter implements it with ``git diff-tree``.

git enters here ONLY (AD-21 git-free mandate; the gate logic stays git-free).
Per `feedback_target_machine_independence_2026_05_15` (AD-21) git is an
OPTIONAL dependency: every git failure -- binary absent (``FileNotFoundError``)
or a non-zero exit (unresolvable commit / not a work-tree) -- degrades LOUD to
``Indeterminate(reason)``, mirroring ``GitCommitTrailerReadAdapter``'s own
uniform-INDETERMINATE contract (AD-24). The consulting gate
(``_check_green_to_green``) then fails closed on ``Indeterminate`` -- NEVER a
silent pass.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.commit_diff_port import CommitDiffPort, Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


class GitCommitDiffAdapter(CommitDiffPort):
    """Reads a single commit's changed-path set out of git (``git diff-tree``).

    ``changed_paths`` returns the repo-relative paths ``commit_sha`` changed
    (``git diff-tree --no-commit-id --name-only -r --root <commit_sha>`` --
    the ``--root`` flag so a repo-root commit diffs against the empty tree
    instead of failing), or an ``Indeterminate`` on any git failure (binary
    absent, ``repo`` not a work-tree, or an unresolvable ``commit_sha``).
    Pure read of the git history -- no filesystem mutation.
    """

    def changed_paths(self, repo: Path, commit_sha: str) -> list[str] | Indeterminate:
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    "--root",
                    commit_sha,
                ],
                cwd=repo,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        if result.returncode != 0:
            return Indeterminate(
                f"git diff-tree failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        return [line for line in result.stdout.splitlines() if line]


__all__ = ["GitCommitDiffAdapter"]
