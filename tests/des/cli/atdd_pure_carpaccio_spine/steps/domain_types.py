"""Domain types for the simplify-atdd-pure-carpaccio-spine acceptance set.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE (Mandate-12 criterion 1). Every domain
noun used in the five slices' Gherkin is expressed once here as a typed enum /
NewType / frozen dataclass. The composition root consumes these typed
parameters; step bodies coerce a Gherkin phrase to a typed value via the
``*_BY_PHRASE`` maps and delegate -- no raw ``str`` where a domain enum exists,
no inline business logic.

Vocabulary shared across all four slice feature files (slice-01..slice-04) and
their step modules -- the SSOT for the simplified spine's domain language.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "simplify-atdd-pure-carpaccio-spine").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice tag (e.g. "slice-01").
SliceTag = NewType("SliceTag", str)

# A git commit SHA or ref (e.g. "HEAD").
CommitRef = NewType("CommitRef", str)


class GateVerdict(str, Enum):
    """The exit-code contract shared by the two simplified-spine gate CLIs.

    The orchestrator reads the exit code; the JSON ``cause`` field names the
    repair. The codes are the SSOT both the spine and the M-2 backstop rely on.
    """

    CLEARED = "cleared"  # exit 0 -- the gate passed
    MALFORMED = "malformed"  # exit 2 -- input could not be trusted (M-1/M-8 floor)
    REFUSED = "refused"  # exit 1 -- a substantive gate refusal


# GateVerdict -> process exit code (SSOT for the gate exit-code contract).
EXIT_CODE_BY_VERDICT: dict[GateVerdict, int] = {
    GateVerdict.CLEARED: 0,
    GateVerdict.REFUSED: 1,
    GateVerdict.MALFORMED: 2,
}


class ContractGateOutcome(str, Enum):
    """The verdict of a ``run_contract_gate --feature-id`` invocation (slice-01).

    The M-1/M-8 non-vacuity floor: a feature-scoped collection that resolves
    zero node-ids, or whose collected set does not intersect the entering
    slice's ``@slice-NN`` tag, is ``malformed`` -- never a silent ``pass``.
    """

    SCOPED_PASS = "scoped-pass"  # node-ids collected, intersect slice tag
    ZERO_COLLECTED = "zero-collected"  # no .feature resolves -> malformed
    EMPTY_INTERSECTION = "empty-intersection"  # collected but no slice-tag overlap
    MALFORMED_SLICE_TAG = "malformed-slice-tag"  # collected, tag is @slice-abc
    SLICE_NOT_DECLARED = "slice-not-declared"  # --feature-id, no --entering-slice
    ZERO_NODE_IDS = "zero-node-ids"  # tagged file resolves + intersects, 0 node-ids
    COLLECTION_FAILED = "collection-failed"  # a feature test module has a syntax error


class LedgerRecordOutcome(str, Enum):
    """Whether ``verify_slice_commit`` appended a ``SliceCommitVerified`` record.

    DDD-3 atomic verify-then-record: the record is appended IFF E1 exit==0 AND
    E2 exit==0. On any non-zero the CLI exits non-zero and appends nothing.
    """

    RECORD_APPENDED = "record-appended"  # E1==0 AND E2==0 -> record written
    NO_RECORD_E1_FAILED = "no-record-e1-failed"  # E1 non-zero -> nothing appended
    NO_RECORD_E2_FAILED = "no-record-e2-failed"  # E2 non-zero -> nothing appended


class CommitBackstopOutcome(str, Enum):
    """The M-2 involuntary pre-commit hook verdict (slice-03).

    The hook refuses a ``Slice-Id:``-trailer commit unless a matching
    ``SliceCommitVerified`` ledger record exists -- the involuntariness the
    removed U1/U2/U4 sequencer hooks provided, restored fail-closed.
    """

    COMMIT_ALLOWED = "commit-allowed"  # matching record present
    COMMIT_REFUSED = "commit-refused"  # Slice-Id trailer, no matching record
    NOT_A_SLICE_COMMIT = "not-a-slice-commit"  # no Slice-Id trailer -> hook abstains


class NewSpineFlaw(str, Enum):
    """A way the slice-04 new-spine flow can fail to ship a verified slice.

    The simplified four-phase flow produces a ``SliceCommitVerified`` record
    only when every phase clears AND the exit gate runs. Either flaw below
    starves the ledger of that record, so the M-2 backstop refuses the commit
    from within the flow -- the flow-owned ``unverified`` decision-table row.
    """

    ACCEPTANCE_TESTS_RED = "acceptance-tests-red"  # ATs never GREEN at A_GREEN
    EXIT_GATE_SKIPPED = "exit-gate-skipped"  # exit gate skipped before commit


class IntegrityOutcome(str, Enum):
    """The DDD-10 feature-end reconciliation verdict (slice-03, slice-04).

    ``verify_deliver_integrity`` reconciles every ``Slice-Id:``-trailer commit
    against the ledger AND asserts the feature-end cycle ran. The verdict is
    the composition of two checks -- the per-slice reconciliation sweep and the
    feature-end-cycle completeness check -- and a feature passes only when BOTH
    clear.
    """

    RECONCILED = "reconciled"  # every Slice-Id commit recorded AND cycle ran
    UNRECONCILED = "unreconciled"  # a Slice-Id commit lacks a ledger record
    # Every Slice-Id commit IS recorded -- the reconciliation sweep would pass
    # -- but the ledger carries no EBatchRefactorCompleted / FeatureEndReviewVerdict
    # record: the feature-end cycle (batch refactor + deep review) never ran, so
    # the feature is NOT closeable. Without this outcome the verifier false-PASSes
    # an all-slices-shipped-but-unrefactored feature (slice-05 Finding 1).
    FEATURE_END_CYCLE_INCOMPLETE = "feature-end-cycle-incomplete"


# Gherkin phrase -> ContractGateOutcome (slice-01 malformed Scenario Outline rows).
CONTRACT_GATE_OUTCOME_BY_PHRASE: dict[str, ContractGateOutcome] = {
    "no test collects under the feature id": ContractGateOutcome.ZERO_COLLECTED,
    "the collected tests carry no entering-slice tag": (
        ContractGateOutcome.EMPTY_INTERSECTION
    ),
    "the collected tests carry a malformed slice tag": (
        ContractGateOutcome.MALFORMED_SLICE_TAG
    ),
    "the entering slice is not declared": ContractGateOutcome.SLICE_NOT_DECLARED,
    "a tagged feature file collects zero runnable node-ids": (
        ContractGateOutcome.ZERO_NODE_IDS
    ),
    "a feature test module has a syntax error": (ContractGateOutcome.COLLECTION_FAILED),
}

# Gherkin word -> count of .feature files the feature genuinely collects from
# (slice-01 happy-path Scenario Outline rows -- C3 multi-file union coverage).
FEATURE_FILE_COUNT_BY_WORD: dict[str, int] = {
    "one": 1,
    "two": 2,
}

# Gherkin phrase -> the failing exit-gate half (slice-02 negative-case rows).
FAILING_GATE_HALF_BY_PHRASE: dict[str, LedgerRecordOutcome] = {
    "the completeness check fails": LedgerRecordOutcome.NO_RECORD_E1_FAILED,
    "the contract gate fails": LedgerRecordOutcome.NO_RECORD_E2_FAILED,
}

# Gherkin phrase -> CommitBackstopOutcome (slice-03 M-2 decision-table rows).
# Each phrase names a commit the M-2 backstop inspects; the outcome is the
# verdict the involuntary hook must reach.
COMMIT_BACKSTOP_OUTCOME_BY_PHRASE: dict[str, CommitBackstopOutcome] = {
    "a slice commit whose exit gate produced a ledger record": (
        CommitBackstopOutcome.COMMIT_ALLOWED
    ),
    "a slice commit whose exit gate was skipped": (
        CommitBackstopOutcome.COMMIT_REFUSED
    ),
    "an ordinary commit carrying no slice-id trailer": (
        CommitBackstopOutcome.NOT_A_SLICE_COMMIT
    ),
}

# Gherkin phrase -> NewSpineFlaw (slice-04 unverified-slice Outline rows).
NEW_SPINE_FLAW_BY_PHRASE: dict[str, NewSpineFlaw] = {
    "the slice acceptance tests left RED": NewSpineFlaw.ACCEPTANCE_TESTS_RED,
    "the slice-commit exit gate skipped": NewSpineFlaw.EXIT_GATE_SKIPPED,
}

# Gherkin phrase -> IntegrityOutcome (slice-03 DDD-10 reconciliation rows).
INTEGRITY_OUTCOME_BY_PHRASE: dict[str, IntegrityOutcome] = {
    "every slice commit has a ledger record": IntegrityOutcome.RECONCILED,
    "a slice commit has no ledger record": IntegrityOutcome.UNRECONCILED,
    "every slice commit is recorded but the feature-end cycle never ran": (
        IntegrityOutcome.FEATURE_END_CYCLE_INCOMPLETE
    ),
}
