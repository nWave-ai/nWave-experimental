"""Guards the canonical short-sha derivation for the `+atddpure.<sha>` label.

Bug reproduction (run 34587462454, revision
f28ccc77f5e9c2fabc2721d62a1ad56b5ba13f85): experimental publication refused
with "migration decision candidate does not match this projected source", even
though the candidate was the correct revision.

Git's `rev-parse --short` abbreviation width is NOT a constant -- it depends
on the object count of the repository it runs against. Measured on this exact
revision:

* local full clone (`git rev-parse --short f28ccc77f5e9c2fabc2721d62a1ad56b5ba13f85`)
  -> `f28ccc77f`, NINE characters.
* CI's `actions/checkout` clone (`fetch-depth: 1`, far fewer objects) ->
  `f28ccc7`, SEVEN characters (git's ordinary default).

`projected_candidate` used to accept that caller-supplied abbreviation as a
trusted parameter, so the local publisher (full clone) and the CI gate
(shallow clone) composed two DIFFERENT `+atddpure.<sha>` labels for the
IDENTICAL commit, and the equality check refused a valid candidate.

The fix derives the abbreviation from the FULL sha, once, in one function
(`short_sha_of`), at a FIXED length -- no caller parameter exists to diverge.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.release.experimental_migration_decision import (
    SHORT_SHA_LENGTH,
    projected_candidate,
    short_sha_of,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURED_FULL_SHA = "f28ccc77f5e9c2fabc2721d62a1ad56b5ba13f85"
MEASURED_LOCAL_FULL_CLONE_ABBREVIATION = "f28ccc77f"  # 9 chars
MEASURED_CI_SHALLOW_CLONE_ABBREVIATION = "f28ccc7"  # 7 chars, git's own default


def test_short_sha_is_fixed_at_nine_and_ignores_the_ambient_git_abbreviation():
    assert SHORT_SHA_LENGTH == 9
    assert short_sha_of(MEASURED_FULL_SHA) == MEASURED_LOCAL_FULL_CLONE_ABBREVIATION
    assert short_sha_of(MEASURED_FULL_SHA) != MEASURED_CI_SHALLOW_CLONE_ABBREVIATION


def test_projected_candidate_takes_no_caller_supplied_short_sha():
    """No parameter through which a shallow clone's narrower abbreviation

    could reach the composed version -- the call succeeds with (repo_root,
    source_sha) only, and the label it composes is the one `short_sha_of`
    derives, regardless of what any caller's own `git rev-parse --short`
    would have produced.
    """
    candidate = projected_candidate(REPO_ROOT, MEASURED_FULL_SHA)
    assert candidate.version.endswith(
        f"+atddpure.{MEASURED_LOCAL_FULL_CLONE_ABBREVIATION}"
    )
