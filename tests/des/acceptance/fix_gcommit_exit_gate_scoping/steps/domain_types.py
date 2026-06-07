"""Domain types for fix-gcommit-exit-gate-scoping (Mandate-12 criterion 1).

slice-01 (#2) -- the `Gate-Scope` digest must be REPRODUCIBLE: it must
fingerprint the COMMITTED contract suite at HEAD, NOT the live working tree.
This is delivered as a NEW, DISTINCT mode (`des run-contract-gate
--committed-scope-digest`), separate from the general `--collect-only
--print-digest` (which stays working-tree, non-git-OK, collect-then-classify --
the dogfood + backward-compat contract). The general working-tree digest
includes UNTRACKED co-resident `.feature`/test files -- making a committed
`Gate-Scope:` trailer bound to it non-reproducible on any other checkout
(target-machine-independence violation, the ~36-min amend-loop). The new
committed-scope mode collects only the committed file-set at HEAD, so its
digest is stable across that perturbation.

Every domain noun used in the Gherkin is expressed once here as a typed enum /
NewType. Step bodies and the composition service consume these typed
parameters -- no raw `str` where a domain enum exists (criterion 1 + 2).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A SHA-256 hex digest as printed by `des run-contract-gate --print-digest`.
Digest = NewType("Digest", str)


class WorkingTreeState(str, Enum):
    """Whether an UNTRACKED co-resident contract file sits in the working tree.

    The slice-01 reproducibility property quantifies over this domain: for
    EVERY working-tree state (untracked co-resident present OR absent), the
    committed-tree digest at one pinned commit must be BYTE-IDENTICAL. Today
    the two states yield DIFFERENT digests (the RED witness); GREEN makes them
    coincide because the digest collects only the committed file-set.
    """

    PRISTINE = "pristine"  # only committed files on disk -- no untracked WIP
    CORESIDENT_UNTRACKED = "coresident_untracked"  # +1 untracked co-resident file


class DigestOutcome(str, Enum):
    """How `des run-contract-gate --collect-only --print-digest` resolves.

    Exit-code-EXACT: the gate either prints a digest (exit 0), or it REFUSES
    fail-closed (exit 2 -- `MalformedInput`, e.g. the git-absent INDETERMINATE
    path, slice-01 AT-3). Any OTHER non-zero exit is a WRONG failure mode and
    surfaces as UNEXPECTED so a fail-closed assertion is never satisfied for
    the wrong reason.
    """

    DIGEST_PRINTED = "digest_printed"  # exit 0 -- a digest of the committed scope
    REFUSED = "refused"  # exit 2 -- fail-closed refusal (git-absent INDETERMINATE)
    UNEXPECTED = "unexpected"  # any other non-zero -- a WRONG failure mode


class CommittedContent(str, Enum):
    """The committed state of a contract test the digest must (not) cover.

    slice-01 AT-2 (whole-committed-tree breadth, OPT-a guard): a test that is
    COMMITTED anywhere in the tree MUST be in the digest, so committing a new
    test MOVES the digest. The OPT-a regression (feature-scoping the digest)
    would let an UNRELATED committed test fall outside the digest -- this is
    the breadth this AT pins.
    """

    NEW_COMMITTED_TEST = "new_committed_test"  # a freshly committed contract test


class CommittedSuiteShape(str, Enum):
    """The file-kind composition of a committed contract suite.

    The genuine-witness AT pins the composition the small `.py`-only fixtures
    could never witness: the real committed contract suite MIXES `.py` test
    modules with specification `.feature` files (the real tree has 227 committed
    `.feature`). Passing a committed `.feature` to pytest as a `--path` makes
    pytest exit 4 (it cannot collect a `.feature` directly), so the digest mode
    fails closed instead of fingerprinting the committed suite. This is the
    fixture-isolation masking class the feature exists to prevent.
    """

    PY_ONLY = "py_only"  # only `.py` test modules (the masking-prone shape)
    MIXED_PY_AND_FEATURE = "mixed_py_and_feature"  # `.py` tests + `.feature` specs


# The structured health event the gate MUST emit when it cannot establish the
# committed contract (git absent / not a git work-tree / commit unresolvable).
# It is LOUD (a single stderr/stdout JSON line), never silent (the degrade-LOUD
# contract -- `feedback_oss_acl_published_language_cross_tier_2026_05_31`).
COMMITTED_SCOPE_INDETERMINATE_EVENT = "health.gate.committed-scope.indeterminate"
