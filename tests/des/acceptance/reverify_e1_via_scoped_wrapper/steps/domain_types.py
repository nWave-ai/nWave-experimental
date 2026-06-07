"""Domain types for the reverify-E1-via-scoped-wrapper acceptance suite.

Mandate-12 (SSOT via Types + Services + DSL): every domain noun the Gherkin
speaks is a typed value here. The wrapper CLI's verdict is a 3-state enum
(complete / incomplete / malformed) and the cross-feature-collision shape is
a typed dataclass -- the step DSL coerces Gherkin tokens at parse time, no
inline business logic in step bodies.

Scope: F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION decision-table rows R3 (single-
feature feature-scoped) + R4 (cross-feature-collision feature-scoped) plus
slice-01's pure-function SSOT scoping property + wrapper malformed-input path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WrapperVerdict(Enum):
    """The three observable verdicts of the check_slice_at_completeness CLI port.

    Maps 1:1 to the JSON ``verdict`` field + exit code contract (DDD-2):

    - COMPLETE   -- exit 0, ``missing == []`` -- every slice .feature is
      carried by the commit (or tracked-before-unmodified).
    - INCOMPLETE -- exit 1, ``missing`` lists the .feature files the slice
      commit fails to carry.
    - MALFORMED  -- exit 2, ``MalformedInput`` shape; covers argparse failures
      (e.g. omitted ``--feature-id``) and git-side failures (unreadable repo,
      unresolvable commit).
    """

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    MALFORMED = "malformed"


class ReverifyE1Outcome(Enum):
    """Reverify's observable outcome at the CLI port for the E1 gate row.

    SUCCESS -- ``SliceReverified`` event, exit 0; both gates cleared, the
        recovery ledger pair (``SliceCommitVerified`` + ``SliceReverified``)
        was appended.
    E1_BLOCKED -- ``SliceReverifyBlocked`` event with
        ``failing_gate`` naming the completeness gate; exit 1.
    """

    SUCCESS = "success"
    E1_BLOCKED = "e1-blocked"


@dataclass(frozen=True)
class FeatureUnderSlice:
    """One feature contributing a `.feature` file tagged with a slice id.

    Used by the cross-feature-collision fixture builder to enumerate the
    ``N`` features sharing the same ``@slice-NN`` tag in the same repo.
    ``feature_id`` is the value the wrapper CLI's ``--feature-id`` flag (or
    reverify's plumbed-through ``--feature-id``) MUST scope E1 to.
    """

    feature_id: str
    feature_file_rel: str  # e.g. "tests/feat_a/acceptance/slice_01.feature"


@dataclass
class WrapperOutcome:
    """The observable outcome of one check_slice_at_completeness invocation.

    Captured from the subprocess: exit code + parsed JSON payload (which the
    CLI emits on stdout as exactly one single-line object). ``verdict`` is
    derived; raw fields preserved so step methods assert on the contract
    shape without re-parsing.
    """

    exit_code: int
    raw_stdout: str
    raw_stderr: str
    payload: dict[str, object] = field(default_factory=dict)

    @property
    def verdict(self) -> WrapperVerdict:
        """Map exit code + payload onto the typed verdict enum."""
        if self.exit_code == 0:
            return WrapperVerdict.COMPLETE
        if self.exit_code == 1:
            return WrapperVerdict.INCOMPLETE
        return WrapperVerdict.MALFORMED

    @property
    def missing(self) -> list[str]:
        """The .feature files the slice commit fails to carry (empty on COMPLETE)."""
        raw = self.payload.get("missing", [])
        return list(raw) if isinstance(raw, list) else []
