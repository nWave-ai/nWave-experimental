"""Domain types for fix-gcommit-exit-gate-scoping slice-03 (Mandate-12 criterion 1).

slice-03 (E1 cross-feature scoping) -- the G_COMMIT exit-gate completeness check
(E1, `verify_slice_commit_completeness`) must be invoked SCOPED to the committing
feature (`resolved.project_id`, the feature id carried by the crafter's
`DES-PROJECT-ID` marker), so its `.feature` candidate scan no longer collides
with a CO-RESIDENT feature's `@slice-NN` tags.

At HEAD the hook invokes E1 with `--repo --commit --expected-head` and NO feature
scope (`subagent_stop_handler.py:618-630`), so E1 falls back to a WHOLE-TREE
`rglob("*.feature")` (`slice_at_completeness.feature_files_for_slice:74`). A
co-resident feature B that carries the SAME `@slice-NN` value as the committing
feature A is then demanded inside feature A's commit -> E1 reports A's commit
INCOMPLETE, naming feature B's `.feature` file -> the operator is forced to hold
feature B off-tree to commit feature A.

The fix wires `resolved.project_id` to E1 via the Seam-A E1-ONLY scoping path
(NOT the existing `--feature-id`, which flips the CLI into verify-then-record and
would double-run E2 + write a DUPLICATE ledger record).

The slice-02 vocabulary (the committed-scope INDETERMINATE event) is REUSED here
by re-export (Mandate-12 SSOT). slice-03 ADDS the E1-verdict noun
(`E1Outcome`), the cross-feature collision-state noun (`CoResidentState`), and the
own-slice completeness noun (`OwnSliceState`) the E1 scoping introduces.

Every domain noun used in the slice-03 Gherkin is expressed once here as a typed
enum. Step bodies and the composition service consume these typed parameters --
no raw `str` where a domain enum exists (criterion 1 + 2).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType

# Reuse the shared committed-scope vocabulary verbatim (Mandate-12 SSOT). The
# LOUD committed-scope INDETERMINATE health-event name is the same concept the
# E2 half emits; re-exporting keeps one source of truth for the shared noun.
from .domain_types import (  # noqa: F401  (re-exported as slice-03 vocabulary)
    COMMITTED_SCOPE_INDETERMINATE_EVENT,
)


# A feature id as carried by the crafter's `DES-PROJECT-ID` marker -- the value
# `resolved.project_id` resolves to, the scope the E1 fix must thread through.
FeatureId = NewType("FeatureId", str)


class GcommitGateOutcome(str, Enum):
    """How the U2 G_COMMIT SubagentStop intercept resolves -- decision-EXACT.

    The driving port (`handle_subagent_stop`) blocks via `{"decision":"block"}`
    + exit 0 and allows via no block body (exit 0). The intercept's observable
    verdict is therefore the presence/absence of a block decision:

    * ALLOWED -- no block body; the slice commit cleared both halves.
    * BLOCKED -- a `{"decision":"block"}` body; the gate rejected the commit.
    * UNEXPECTED -- a non-zero exit / crash with no decision body, surfaced so a
      verdict assertion never passes for the wrong reason.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNEXPECTED = "unexpected"


class E1Outcome(str, Enum):
    """How the E1 (slice-commit completeness) half resolved inside the intercept.

    The intercept's block reason carries the E1 exit code verbatim
    (`... gate failed (e1=N, e2=M)`); a verified commit carries `e1=0` and no
    block. This noun lifts that into the domain so the AT reads the E1 verdict
    directly rather than substring-matching the raw reason:

    * COMPLETE -- E1 found no missing `.feature` for the committing feature
      (`e1=0`); the slice commit's completeness half cleared.
    * INCOMPLETE -- E1 reported the slice commit missing a `.feature`
      (`e1=1`). At HEAD this fires on a CO-RESIDENT FOREIGN feature's file (the
      cross-feature collision RED witness); after the fix it fires ONLY for the
      committing feature's OWN genuinely-missing `.feature` (AT-B).
    * INDETERMINATE -- E1 could not be evaluated (the verdict could not be
      derived), surfaced so an assertion never passes for the wrong reason.
    """

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    INDETERMINATE = "indeterminate"


class CoResidentState(str, Enum):
    """Whether a co-resident foreign feature sharing the slice tag sits on-tree.

    slice-03 AT-A quantifies the cross-feature isolation property over this
    domain: with a foreign feature B present on-tree carrying the SAME
    `@slice-NN` value as the committing feature A, E1 (scoped to A) must STILL
    find A's commit complete -- B's tag must not cross-bind into A's
    completeness check.

    * ABSENT -- only the committing feature's `.feature` files are on-tree.
    * PRESENT_SHARING_SLICE_TAG -- a co-resident foreign feature is on-tree AND
      carries the SAME `@slice-NN` value as the committing feature (the exact
      collision the unscoped whole-tree `rglob` provokes at HEAD).
    """

    ABSENT = "absent"
    PRESENT_SHARING_SLICE_TAG = "present_sharing_slice_tag"


class OwnSliceState(str, Enum):
    """Whether the committing feature's OWN `@slice-NN` `.feature` is in the commit.

    slice-03 AT-B (genuine incompleteness still caught -- the anti-vacuity
    guard): scoping E1 to the committing feature must NOT mask a genuinely
    incomplete commit. When the committing feature authored its own
    `@slice-NN` `.feature` on disk but kept it OUT of the commit, E1 (scoped to
    that feature) must STILL report the commit INCOMPLETE.

    * COMMITTED -- the committing feature's own slice `.feature` is in the commit.
    * AUTHORED_BUT_NOT_COMMITTED -- the committing feature's own slice `.feature`
      exists on disk but was never persisted into any commit (the RCA Branch-A
      genuine-incompleteness shape).
    """

    COMMITTED = "committed"
    AUTHORED_BUT_NOT_COMMITTED = "authored_but_not_committed"
