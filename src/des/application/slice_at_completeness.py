"""SSOT for slice-commit AT completeness -- pure read-only computation.

Closes F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION (PRR D2 blocker).

This module is the application-layer SSOT for the pure read-only functions that
compute the missing `.feature` AT files for a slice commit. DESIGN DDD-1 / DDD-9
promoted the functions out of ``des.cli.verify_slice_commit_completeness`` (the
F2-drift vector) into this layer so multiple CLI consumers can import a single
physical home -- ``verify_slice_commit_completeness`` then re-exports the
symbols (DDD-3 identity guarantee) and ``check_slice_at_completeness`` imports
them directly (DDD-2).

Contract shape: pure-function (return-only). Inputs: ``(repo, commit, slice_id,
feature_id)``. Outputs: ``list[str]``. No filesystem mutation beyond git's read
cache. The driving-port wrapper (``des.cli.check_slice_at_completeness``)
inherits this read-only contract by construction (principle 12 effect-isolation
-- arch-test enforced via the no-``AtCompletionLedger``-import rule).

stdlib-only (per the DES-bundle contract). The only intra-package import is
``feature_at_files.feature_tag_files`` -- the application-layer ``@feature-{id}``
resolver ``run_contract_gate`` uses for its ``--feature-id`` scope, itself
stdlib-only.
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.application.feature_at_files import feature_tag_files


if TYPE_CHECKING:
    from pathlib import Path


_SLICE_TAG_RE = re.compile(r"@(slice-\d+)\b")


def feature_files_for_slice(
    repo: Path, slice_id: str, feature_id: str | None = None
) -> list[str]:
    """Return repo-relative paths of `.feature` files tagging the slice.

    A `.feature` file belongs to the slice when any of its scenarios carry the
    ``@slice-NN`` tag matching ``slice_id``. The working tree is walked, NOT just
    ``git ls-files`` -- an authored-but-never-committed AT file is untracked yet
    is exactly the RCA Branch-A defect this gate must catch. A file the slice
    authored on disk but kept out of every commit MUST be reported missing.

    When ``feature_id`` is given the candidate set is scoped to that feature's
    `.feature` files via the ``@feature-{id}`` tag (the
    ``feature_at_files.feature_tag_files`` resolver) -- a ``@slice-NN`` tag
    is reused across features, so a global ``rglob`` would cross-bind another
    feature's slice file into this commit's completeness check (wall W5).
    """
    if feature_id is not None:
        candidates = feature_tag_files(repo, feature_id)
    else:
        candidates = [p for p in repo.rglob("*.feature") if ".git" not in p.parts]
    matched: list[str] = []
    for path in sorted(candidates):
        text = path.read_text(encoding="utf-8", errors="replace")
        if slice_id in _SLICE_TAG_RE.findall(text):
            matched.append(str(path.relative_to(repo)))
    return sorted(matched)


def files_in_commit(repo: Path, commit: str) -> set[str]:
    """Return the set of repo-relative paths touched by ``commit``."""
    output = _git(repo, "show", "--name-only", "--pretty=format:", commit)
    return {line for line in output.splitlines() if line}


def missing_at_files(
    repo: Path, commit: str, slice_id: str, feature_id: str | None = None
) -> list[str]:
    """Return `.feature` AT files for the slice that the commit fails to carry.

    A file is complete when it is present in this commit. A file already
    tracked before this commit AND unmodified by it is also complete -- the
    commit need not re-touch ATs delivered by an earlier slice commit. The
    incomplete case is the RCA Branch-A defect: an AT file the slice authored
    but never persisted into any commit.

    When ``feature_id`` is given the slice's `.feature` candidate set is
    scoped to that feature (wall W5 -- see ``feature_files_for_slice``).
    """
    at_files = feature_files_for_slice(repo, slice_id, feature_id)
    in_commit = files_in_commit(repo, commit)
    missing: list[str] = []
    for rel_path in at_files:
        if rel_path in in_commit:
            continue
        if _tracked_before_commit(repo, commit, rel_path):
            continue
        missing.append(rel_path)
    return sorted(missing)


def _tracked_before_commit(repo: Path, commit: str, rel_path: str) -> bool:
    """True iff ``rel_path`` existed as a tracked file in ``commit``'s parent."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}~1:{rel_path}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
