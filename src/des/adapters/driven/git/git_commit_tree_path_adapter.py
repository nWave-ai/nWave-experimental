"""GitCommitTreePathAdapter -- git implementation of CommitTreePathPort.

`lane-seal-refuses-premature` (part B of `fix-slice-seal-carries-commit-sha`).
The concrete git side of "did this path exist in that commit's tree?". Two
git calls, not one, because a single `git cat-file -e {sha}:{path}` call
cannot distinguish "the commit itself is bogus/unresolvable" from "the commit
is real but the path is genuinely absent" -- both exit non-zero. Splitting
the question preserves the three-state contract (EXISTS / NOT_EXISTS /
INDETERMINATE, GDP-8):

1. Resolve ``commit_sha`` itself (`git cat-file -e {sha}^{commit}`). Any
   failure here (binary absent, not a work-tree, sha unresolvable/GC'd) means
   the fact truly cannot be established -- ``Indeterminate``.
2. Only once the commit is confirmed real does a miss on
   `git cat-file -e {sha}:{path}` become a DEFINITIVE ``False`` -- the tree
   genuinely lacks that path, never an artifact of a bad sha.

git enters here ONLY (AD-21 git-free mandate; the gate logic stays
git-free). Per `feedback_target_machine_independence_2026_05_15` (AD-21) git
is an OPTIONAL dependency: every git failure degrades LOUD to
``Indeterminate(reason)``, mirroring ``GitCommitDiffAdapter``'s own
uniform-INDETERMINATE contract. The consulting check then treats
``Indeterminate`` as "could not verify" -- NEVER a silent pass and NEVER a
retroactive FAIL.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.commit_tree_path_port import (
    CommitTreePathPort,
    Indeterminate,
)
from des.runtime.spawn import spawn


#: Wall-clock bound for one `git cat-file -e` plumbing query -- always a
#: sub-second local read; 30s is generous headroom on a loaded/shared box,
#: never the multi-minute tier a real test/agent spawn needs.
_CAT_FILE_TIMEOUT_SECONDS = 30.0


if TYPE_CHECKING:
    from pathlib import Path


class GitCommitTreePathAdapter(CommitTreePathPort):
    """Reads "does path P exist in commit C's tree?" out of git.

    ``path_exists_at_commit`` resolves ``commit_sha`` first, then probes the
    path -- see module docstring for why the split matters. Pure read of the
    git object store -- no filesystem mutation.
    """

    def path_exists_at_commit(
        self, repo: Path, commit_sha: str, rel_path: str
    ) -> bool | Indeterminate:
        commit_check = self._cat_file_exists(repo, f"{commit_sha}^{{commit}}")
        if isinstance(commit_check, Indeterminate):
            return commit_check
        if not commit_check:
            return Indeterminate(
                f"commit `{commit_sha}` does not resolve in this repository "
                "(GC'd, shallow clone, or never existed here)"
            )
        path_check = self._cat_file_exists(repo, f"{commit_sha}:{rel_path}")
        if isinstance(path_check, Indeterminate):
            return path_check
        return path_check

    @staticmethod
    def _cat_file_exists(repo: Path, object_spec: str) -> bool | Indeterminate:
        try:
            result = spawn(
                ["git", "cat-file", "-e", object_spec],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=_CAT_FILE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except subprocess.TimeoutExpired as exc:
            return Indeterminate(f"git cat-file timed out: {exc}")
        if result.returncode == 0:
            return True
        # A non-zero exit here is git's normal "does not exist" signal for
        # `cat-file -e` -- NOT an error. `repo` not being a work-tree at all
        # is the one genuine indeterminate case, distinguished by stderr
        # naming it explicitly.
        stderr = result.stderr.strip()
        if "not a git repository" in stderr.lower():
            return Indeterminate(f"`{repo}` is not a git work-tree: {stderr[:200]}")
        return False


__all__ = ["GitCommitTreePathAdapter"]
