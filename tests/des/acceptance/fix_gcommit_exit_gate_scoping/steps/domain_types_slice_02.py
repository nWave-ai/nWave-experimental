"""Domain types for fix-gcommit-exit-gate-scoping slice-02 (Mandate-12 criterion 1).

slice-02 (WIRING) -- the G_COMMIT exit-gate verify check
(`run_contract_gate._mode_verify_gate_scope:488`, `--verify-gate-scope`) and the
terminating Gate-Scope trailer compute (`:547`) must derive the committed-scope
digest shipped in slice-01, NOT the working-tree `gate_scope_digest(repo)`. The
observable outcome: one pinned commit carrying a `Gate-Scope:` trailer verifies
the SAME way whether or not untracked co-resident work-in-progress sits in the
working tree.

The slice-01 vocabulary (`WorkingTreeState`, `CommittedSuiteShape`, the
committed-scope INDETERMINATE event) is REUSED here verbatim by re-export
(Mandate-12 SSOT -- shared domain nouns across the feature). slice-02 ADDS only
the verify-verdict noun (`VerifyOutcome`) and the stale-trailer noun
(`TrailerState`) that the verify check introduces.

Every domain noun used in the slice-02 Gherkin is expressed once here as a typed
enum. Step bodies and the composition service consume these typed parameters --
no raw `str` where a domain enum exists (criterion 1 + 2).
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-01 vocabulary verbatim (Mandate-12 SSOT). The committed-tree
# perturbation domain (PRISTINE vs CORESIDENT_UNTRACKED), the mixed-suite shape
# (PY_ONLY vs MIXED_PY_AND_FEATURE), and the LOUD committed-scope INDETERMINATE
# health-event name are identical concepts for slice-02 -- importing them keeps
# one source of truth for the shared domain nouns.
from .domain_types import (  # noqa: F401  (re-exported as slice-02 vocabulary)
    COMMITTED_SCOPE_INDETERMINATE_EVENT,
    CommittedSuiteShape,
    WorkingTreeState,
)


class VerifyOutcome(str, Enum):
    """How `des run-contract-gate --verify-gate-scope` resolves -- EXIT-CODE-EXACT.

    The verify check has three observable verdicts, each pinned to an exit code
    so a verdict assertion never passes for the wrong reason:

    * VERIFIED (exit 0, `GateScopeVerified`) -- the commit's `Gate-Scope:`
      trailer matched the fresh digest. The verdict slice-02 AT-1 requires to be
      INVARIANT across the untracked-WIP perturbation.
    * UNVERIFIED (exit 1, `GateScopeUnverified`) -- the trailer was absent or
      mismatched the fresh digest. At HEAD this is what an untracked co-resident
      file PROVOKES (the working-tree perturbation, the RED witness); after
      GREEN it should fire ONLY for a genuine committed-tree change (AT-2).
    * REFUSED (exit 2, fail-closed `MalformedInput` / committed-scope
      INDETERMINATE) -- the verify check could not pin the commit to a committed
      revision (git absent, AT-3) and refused loudly.
    * UNEXPECTED -- any other exit code: a WRONG failure mode, surfaced so a
      verdict assertion is never satisfied for the wrong reason.
    """

    VERIFIED = "verified"  # exit 0 -- GateScopeVerified
    UNVERIFIED = "unverified"  # exit 1 -- GateScopeUnverified (absent / mismatch)
    REFUSED = "refused"  # exit 2 -- fail-closed refusal (git-absent INDETERMINATE)
    UNEXPECTED = "unexpected"  # any other exit -- a WRONG failure mode


class TrailerState(str, Enum):
    """Whether a commit's `Gate-Scope:` trailer matches its committed tree.

    slice-02 AT-2 (whole-committed-tree breadth, OPT-b guard): the verify check
    must STILL fail a commit whose trailer no longer matches its COMMITTED
    contract suite -- the committed-tree regression witness is preserved, only
    the untracked-WIP noise is removed.

    * MATCHING -- the trailer pins the commit's actual committed-scope digest
      (the AT-1 happy path; verify should return VERIFIED).
    * STALE -- the trailer pins a digest that does NOT match the commit's
      committed contract suite (a committed change moved the real digest); the
      verify check must report UNVERIFIED (AT-2).
    """

    MATCHING = "matching"  # trailer == the commit's committed-scope digest
    STALE = "stale"  # trailer != the commit's committed-scope digest
