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

stdlib-only (per the DES-bundle contract). The intra-package imports are all
``feature_at_files`` resolvers: ``feature_tag_files`` (the application-layer
``@feature-{id}`` resolver for Gherkin ``.feature`` files, itself stdlib-only),
plus ``feature_tagged_test_files`` / ``resolve_test_file_attribution`` (the
pytest-side mirror, WTBD-168) added to close
F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND -- a slice delivered only by a
head-comment-tagged pytest AT file was invisible to this oracle.
"""

from __future__ import annotations

import fnmatch
import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.application.feature_at_files import (
    feature_tag_files,
    feature_tagged_test_files,
    resolve_test_file_attribution,
)
from des.domain.slice_id_trailer import SLICE_TAG_RE


if TYPE_CHECKING:
    from pathlib import Path


#: Imported from the domain SSOT (fix-slice-id-grammar-drift-ssot) so a
#: letter-suffixed `@slice-04a` tag resolves identically to `@slice-NN`.
_SLICE_TAG_RE = SLICE_TAG_RE

_PYTEST_COLLECTIBLE_PATTERNS = ("test_*.py", "*_test.py")


def _is_pytest_collectible(path: Path) -> bool:
    """True iff ``path``'s filename matches the pytest collection convention.

    ``feature_tagged_test_files`` walks every file with no filename/extension
    restriction, matching purely on a head-comment tag substring. Without this
    filter a non-test file (a doc, an ADR, a plain module) whose head merely
    *mentions* the tag convention is wrongly counted as a delivered AT --
    F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND AT-D1. Restricting to the
    pytest-collectible filename convention (``test_*.py`` / ``*_test.py``)
    keeps this oracle bound to real, delivered test artifacts.
    """
    name = path.name
    return any(
        fnmatch.fnmatch(name, pattern) for pattern in _PYTEST_COLLECTIBLE_PATTERNS
    )


def feature_files_for_slice(
    repo: Path, slice_id: str, feature_id: str | None = None
) -> list[str]:
    """Return repo-relative paths of the AT files delivering the slice.

    Two discovery paths, UNIONed:

    1. Gherkin -- `.feature` files tagging the slice. A `.feature` file
       belongs to the slice when any of its scenarios carry the
       ``@slice-NN`` tag matching ``slice_id``. The working tree is walked,
       NOT just ``git ls-files`` -- an authored-but-never-committed AT file
       is untracked yet is exactly the RCA Branch-A defect this gate must
       catch. A file the slice authored on disk but kept out of every commit
       MUST be reported missing.

    2. pytest -- test files head-comment-tagged ``@feature-{feature_id}``
       (``feature_at_files.feature_tagged_test_files``, WTBD-168) whose
       ``@slice-NN`` sub-tag (``feature_at_files.resolve_test_file_attribution``)
       matches ``slice_id``. Closes
       F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND -- a slice delivered
       exclusively by a pytest AT was previously invisible to this oracle.
       Only active when ``feature_id`` is given: the ``@feature-{id}`` head
       tag is the discovery key, so a pytest file with no such tag never
       counts (no silent over-match; wall W5 -- ``@slice-NN`` alone is reused
       across features). ``feature_tagged_test_files`` itself applies no
       filename/extension restriction (any file's head window may match), so
       this loop additionally restricts matches to the pytest-collectible
       filename convention (``test_*.py`` / ``*_test.py``, see
       ``_is_pytest_collectible``) -- a doc, an ADR, or a non-test module that
       merely *mentions* the tag convention in its head must never count as a
       delivered AT (the un-gameable truncation guard).

    The unioned candidate set is deduplicated before returning: a `.feature`
    file can legitimately be matched by BOTH paths (Gherkin tags precede
    ``Feature:`` within the pytest head-window scan too), and each delivered
    AT artifact must be reported EXACTLY ONCE.

    When ``feature_id`` is given the Gherkin candidate set is likewise scoped
    to that feature's `.feature` files via the ``@feature-{id}`` tag (the
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
    if feature_id is not None:
        for test_path in feature_tagged_test_files(repo, feature_id):
            if not _is_pytest_collectible(test_path):
                continue
            attribution = resolve_test_file_attribution(test_path)
            if attribution.slice_id == slice_id:
                matched.append(str(test_path.relative_to(repo)))
    return sorted(set(matched))


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
