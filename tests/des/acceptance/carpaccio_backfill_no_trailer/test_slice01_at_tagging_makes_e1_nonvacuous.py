"""Regression (bugfix lane, des-refactor-fixer-swarm-slice01-at-tagging).

E1 (``missing_at_files`` via ``feature_files_for_slice``) was VACUOUSLY empty
for the target feature's slice-01 -- blocking that feature's own slice-02
carpaccio dispatch. RCA: the 7 slice-01 pytest AT files under
``tests/des/refactor/`` never carried the head-comment attribution tag
``feature_at_files.feature_tagged_test_files`` / ``resolve_test_file_attribution``
scan for (see ``_FEATURE_ID``/``_SLICE_ID`` below for the exact ids). Their
existing docstrings carried ``@driving_port @contract-shape:...`` tags but no
feature/slice attribution, so discovery returned ``[]`` -- and because
"missing" is computed as "expected minus delivered", an empty expected set
makes it return ``[]`` for ANY commit, including one that delivers nothing.
E1 could never actually refuse a genuinely incomplete predecessor commit for
this feature.

FIX: tagging-only. The 7 files gain two head-comment lines; zero test logic,
assertions, or production code changed. Deliberately, THIS file carries no
attribution tag of its own -- spelling one out here would substring-match
the same lookup (a plain substring, not a word-boundary match) and falsely
count this bugfix's own regression file as one of the target feature's
delivered slice-01 AT files. See below (past the resolver's bounded
head-scan window) for the concrete ids and immutable anchor commits.

GIT SAFETY: every assertion below reads the REAL project repo via read-only
git plumbing (``git cat-file -e``, ``git show --name-only``) through the
production ``missing_at_files``/``feature_files_for_slice`` functions -- no
git WRITE, mirrors the read-only-verification pattern already used by
``carpaccio_predecessor_lookup_feature_scoped`` (RCA "verified against a
read-only clone of the real repo").
"""

# Two real, immutable commits anchor the discrimination proof below:
# * 610ea4d75 -- 1ad46e416's PARENT. Predates all 7 slice-01 AT files
#   entirely (none tracked yet) -- the commit that must be reported as
#   missing ALL 7, proving E1 no longer vacuously returns [] for it.
# * 1ad46e416 -- the slice-01 walking-skeleton commit itself. Delivers 6 of
#   the 7 files (the 7th, the pile-grammar-refusal AT, landed in a later
#   bugfix commit) -- proving E1's granularity, not just "always non-empty."

from __future__ import annotations

from pathlib import Path

from des.application.slice_at_completeness import (
    feature_files_for_slice,
    missing_at_files,
)


# tests/des/acceptance/carpaccio_backfill_no_trailer/<this file>
#   parents[4] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[4]

_FEATURE_ID = "des-refactor-fixer-swarm"
_SLICE_ID = "slice-01"

_ALL_SEVEN = frozenset(
    {
        "tests/des/refactor/test_slice_01_worktree_and_green_to_green.py",
        "tests/des/refactor/test_slice_01_observability.py",
        "tests/des/refactor/test_slice_01_merge_and_cleanup.py",
        "tests/des/refactor/test_slice_01_walking_skeleton.py",
        "tests/des/refactor/test_slice_01_pile_move.py",
        "tests/des/refactor/test_slice_01_safety_and_isolation.py",
        "tests/des/refactor/test_slice_01_pile_grammar_refusal.py",
    }
)

#: 1ad46e416's parent -- predates every one of the 7 AT files.
_PRE_SLICE01_ANCESTOR = "610ea4d75"

#: The slice-01 walking-skeleton commit -- delivers 6 of the 7 files.
_SLICE01_WALKING_SKELETON_COMMIT = "1ad46e416"

_SIX_DELIVERED_BY_WALKING_SKELETON = _ALL_SEVEN - {
    "tests/des/refactor/test_slice_01_pile_grammar_refusal.py"
}


def test_tagged_slice01_at_files_are_discovered_nonvacuously() -> None:
    found = feature_files_for_slice(REPO_ROOT, _SLICE_ID, _FEATURE_ID)

    assert found, (
        "feature_files_for_slice must find the head-comment-tagged slice-01 "
        "AT files -- got [] (the vacuous-E1 defect this fix closes)."
    )
    assert set(found) >= _ALL_SEVEN, (
        f"expected all 7 tagged slice-01 AT files to be discovered; "
        f"missing from result: {_ALL_SEVEN - set(found)!r}"
    )


def test_missing_at_files_discriminates_a_commit_that_predates_every_at_file() -> None:
    outcome = missing_at_files(REPO_ROOT, _PRE_SLICE01_ANCESTOR, _SLICE_ID, _FEATURE_ID)

    assert set(outcome.missing) == _ALL_SEVEN, (
        f"a commit ({_PRE_SLICE01_ANCESTOR}) that predates every slice-01 AT "
        "file must report ALL 7 as missing -- a vacuous E1 would have "
        f"returned [] here regardless of input. got missing={outcome.missing!r}"
    )
    assert outcome.verifiable is True, (
        "7 genuine AT candidates exist for this feature/slice -- E1 must "
        f"report verifiable=True, never the vacuous-empty sentinel. "
        f"outcome={outcome!r}"
    )


def test_missing_at_files_discriminates_the_walking_skeleton_commit_granularly() -> (
    None
):
    outcome = missing_at_files(
        REPO_ROOT, _SLICE01_WALKING_SKELETON_COMMIT, _SLICE_ID, _FEATURE_ID
    )

    assert set(outcome.missing) == {
        "tests/des/refactor/test_slice_01_pile_grammar_refusal.py"
    }, (
        f"{_SLICE01_WALKING_SKELETON_COMMIT} delivers 6 of the 7 files "
        "directly and none of the 7th (a later bugfix commit) -- E1 must "
        f"report exactly that one file missing. got missing={outcome.missing!r}"
    )
    assert not (_SIX_DELIVERED_BY_WALKING_SKELETON & set(outcome.missing)), (
        "the 6 files genuinely delivered by the walking-skeleton commit "
        f"must never be reported missing. got missing={outcome.missing!r}"
    )
    assert outcome.verifiable is True, (
        "6 of the 7 genuine AT candidates are present at this commit -- E1 "
        f"must report verifiable=True, never the vacuous-empty sentinel. "
        f"outcome={outcome!r}"
    )
