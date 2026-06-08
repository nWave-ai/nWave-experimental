"""Domain types for the gate-trailer-read-git-port-extract slice-02 ATs.

Mandate-12 criterion 1: every domain noun used in the slice-02 Gherkin is
expressed once here as a typed enum. Step bodies and the composition service
consume these typed parameters -- no raw `str` where a domain enum exists.

slice-02 bounded context: the deliver-integrity done-gate's GIT-FREE CORE. Where
slice-01 proved git-absence degrades LOUD via the REAL git adapter through the
CLI, slice-02 proves the CORE is genuinely git-free -- a NON-git
CommitTrailerReadPort can feed the verdict and reconcile / refuse WITHOUT any git
involvement. The `NonGitTrailerSource` enum names the three materially-distinct
fake-port behaviors the core's verdict is derived from.

The GateVerdict enum + the event/exit-code markers are REUSED from
``domain_types`` (slice-01) -- the observable verdict vocabulary is shared across
both slices (the verdict model does not change; only the trailer SOURCE does).
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-01 verdict vocabulary verbatim -- the user-observable verdict
# model is identical; slice-02 only swaps the trailer SOURCE (git -> a fake
# non-git CommitTrailerReadPort). Importing (never redefining) keeps the verdict
# contract a single source of truth across both slices.
from .domain_types import (  # noqa: F401 -- re-exported for the slice-02 steps
    CANNOT_EVALUATE_EVENT,
    CANNOT_EVALUATE_EXIT,
    INDETERMINATE_JSON_EVENT,
    FeatureId,
    GateVerdict,
)


class NonGitTrailerSource(str, Enum):
    """The behavior of the NON-git CommitTrailerReadPort feeding the gate core.

    The whole point of slice-02: the gate core's verdict is derived purely from
    what a CommitTrailerReadPort returns -- git is just one swappable adapter.
    Each value is one materially-distinct port-contract outcome the core must
    honor identically whether the source is git or not.

    RECORDS_SHIPPED_SLICE -- the fake returns `CommitMessages` carrying a
                       `Slice-Id: slice-NN` trailer that MATCHES the slice the
                       ledger demands reconciliation for. The core reconciles
                       cleanly (exit 0, FeatureReconciled) -- the genericita
                       claim: a non-git source reconciles exactly as git would.
    MISSING_SHIPPED_SLICE -- the fake returns `CommitMessages` carrying a trailer
                       for a DIFFERENT slice (NOT the one the ledger demands).
                       The core leaves the delivery unreconciled (exit 1,
                       FeatureUnreconciled) -- the non-vacuity control: the
                       verdict genuinely depends on what the port returns, the
                       reconciliation is not vacuously always-on.
    CANNOT_READ      -- the fake returns the reused `Indeterminate` VO (it could
                       not read its source). The core refuses LOUD (exit 4,
                       FeatureIndeterminate) -- proving the degrade-LOUD path is a
                       PORT-CONTRACT property (any unreadable source refuses
                       LOUD), not a git-specific behavior.
    """

    RECORDS_SHIPPED_SLICE = "records_shipped_slice"
    MISSING_SHIPPED_SLICE = "missing_shipped_slice"
    CANNOT_READ = "cannot_read"


# Gherkin-phrase -> typed NonGitTrailerSource lookup. Keeping this a module-level
# dict lets each Given step body stay a single typed lookup + a single
# composition call (Mandate-12 criterion 3: no control flow in step bodies).
SOURCE_BY_PHRASE: dict[str, NonGitTrailerSource] = {
    "recording the shipped slice": NonGitTrailerSource.RECORDS_SHIPPED_SLICE,
    "missing the shipped slice": NonGitTrailerSource.MISSING_SHIPPED_SLICE,
    "cannot be read": NonGitTrailerSource.CANNOT_READ,
}
