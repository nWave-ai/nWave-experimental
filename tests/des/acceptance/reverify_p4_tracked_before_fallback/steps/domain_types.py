"""Domain types for the P4 tracked-before fallback acceptance suite.

Mandate-12 (SSOT via Types + Services + DSL): every domain noun the Gherkin
speaks is a typed value here. The four AT-presence states P4 must verdict over
(feature-delta sec.98 Contract table) are an enum -- the parametrize-collapse
in slice-02 ranges over a subset of it, and the step DSL coerces the Gherkin
token to the typed value at parse time.
"""

from __future__ import annotations

from enum import Enum


class AtPresenceState(Enum):
    """The four AT-presence states P4 verdicts over a slice's `.feature`.

    Maps 1:1 to the feature-delta DESIGN Contract table (the 4-state SSOT):

    - IN_COMMIT: the `@slice-NN .feature` is touched by `commit` and present
      in the commit tree, tag present -> ACCEPT (existing behaviour).
    - TRACKED_BEFORE_UNMODIFIED: the `.feature` existed as a tracked blob in
      `commit~1` carrying `@slice-NN`, and is NOT touched by `commit`
      -> ACCEPT (the slice-01 recovery-enabling behaviour).
    - NEVER_AUTHORED: no `@slice-NN .feature` anywhere -- not in the commit
      tree, not tracked in `commit~1` -> REFUSE (slice-02).
    - TAG_DROPPED_BY_COMMIT: a `.feature` tracked in `commit~1` carried the
      `@slice-NN` tag, but `commit` MODIFIED it to drop the tag -> REFUSE
      -- disownership; clause-3 (unmodified-by-commit) fails (slice-02).
    """

    IN_COMMIT = "in-commit"
    TRACKED_BEFORE_UNMODIFIED = "tracked-before-unmodified"
    NEVER_AUTHORED = "never-authored"
    TAG_DROPPED_BY_COMMIT = "tag-dropped-by-commit"


class P4Verdict(Enum):
    """P4's two observable verdicts at the CLI port.

    ACCEPT  -- P4 returns no refusal; reverify proceeds past the precondition.
    REFUSE  -- P4 emits a `SliceReverifyRefused` event and `main` exits 1.
    """

    ACCEPT = "accept"
    REFUSE = "refuse"
