"""Domain types for the classic-spine-decommission acceptance suite.

Mandate-12 criterion 1: every domain noun used in the Gherkin of the seven
slice `.feature` files is expressed once here as a typed enum or NewType. Step
bodies and the composition services consume these typed parameters -- no raw
`str` where a domain enum exists.

The epic (release N of the staged ADR-032 cutover) makes the `atdd_pure`
DELIVER spine the default, deprecates the `classic` roadmap spine to a
non-default fallback floor, converts every legacy `classic` feature to
`atdd_pure`, and closes F-13. The DELETE sweep is the N+1 sibling epic.

Shared-vocabulary contract (Mandate 10): the same step-method names are used
across all seven slice step files; the types below are the single SSOT for the
parameters those step methods accept.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "walking-skeleton-production-like-gate").
FeatureId = NewType("FeatureId", str)

# A slice identifier as carried by a `Slice-Id:` commit trailer (e.g. "slice-01").
SliceId = NewType("SliceId", str)

# A roadmap step identifier (classic spine, e.g. "01-01").
RoadmapStepId = NewType("RoadmapStepId", str)

# A git commit SHA (abbreviated or full, e.g. "c631692f5").
CommitSha = NewType("CommitSha", str)


# --- Feature classification (DESIGN: Legacy-Feature Detection Mechanism) ------


class FeatureClass(str, Enum):
    """The five classes `des-classify-features` assigns to a feature dir.

    CLASSIC_MID_IMPLEMENTATION -- has roadmap.json AND execution-log.json with
                                  >=1 EXECUTED event AND >=1 step without
                                  COMMIT/PASS. Full conversion + reconciliation.
    CLASSIC_DISTILL_DONE       -- has `.feature` ATs AND no deliver/ (or empty
                                  execution-log). Convert; DELIVER not started.
    ATDD_PURE                  -- has an atdd_pure telemetry file OR a Slice
                                  Plan heading AND no roadmap.json. No
                                  conversion -- already migrated.
    PRE_DISTILL                -- no `.feature` files AND no roadmap.json.
                                  Re-enters waves born atdd_pure.
    CLASSIC_NEEDS_MANUAL_REVIEW -- any artifact malformed/unparseable. Never an
                                  exception -- emitted as a manifest row;
                                  blocks slice-06 drain completion.
    """

    CLASSIC_MID_IMPLEMENTATION = "classic-mid-implementation"
    CLASSIC_DISTILL_DONE = "classic-distill-done"
    ATDD_PURE = "atdd_pure"
    PRE_DISTILL = "pre-distill"
    CLASSIC_NEEDS_MANUAL_REVIEW = "classic-needs-manual-review"


class CorruptionKind(str, Enum):
    """How a feature dir's classic artifacts are malformed (probe fault set).

    A malformed artifact never crashes the classifier -- it yields a
    CLASSIC_NEEDS_MANUAL_REVIEW row (Earned-Trust probe()).

    Naming note (feature-end review D4): ``LOG_EMPTY`` is NOT a malformed
    artifact -- an empty `{}` execution-log.json is well-formed JSON that
    simply records no progress. It reaches CLASSIC_NEEDS_MANUAL_REVIEW via the
    normal no-EXECUTED-event fall-through, not a corruption guard. It is kept
    in this enum because the probe fault set drives it as one input row, but
    semantically it means "no progress", not "corrupt".
    """

    ROADMAP_TRUNCATED = "roadmap-truncated"  # F-17 stale stub
    ROADMAP_NOT_JSON = "roadmap-not-json"  # not valid JSON at all
    ROADMAP_HAND_EDITED = "roadmap-hand-edited"  # schema-valid, log-inconsistent
    LOG_MIXED_VERSION = "log-mixed-version"  # mixed v2.0-pipe / v3.0 events
    # No-progress, NOT corrupt: a well-formed `{}` log with no EXECUTED event.
    LOG_EMPTY = "log-empty"  # execution-log.json is `{}` or empty -- no progress


# --- Conversion procedure (DESIGN: The Conversion Procedure) ------------------


class SliceStatus(str, Enum):
    """The reconciled status of a slice row in a converted feature's plan.

    SHIPPED -- ALL constituent roadmap steps reached COMMIT/PASS AND each SHA
               re-verified green NOW (M2). Structurally impossible without
               current green code.
    PENDING -- any constituent step missing, partial, or failed re-verification;
               committed constituent SHAs recorded as `provenance`.
    """

    SHIPPED = "shipped"
    PENDING = "pending"


class ShaVerdict(str, Enum):
    """The outcome of one M2 commit-SHA re-verification through GitHistoryProbe.

    GREEN          -- SHA exists, reachable from current branch, tests green now.
    REVERTED       -- SHA exists but is not reachable (commit was reverted).
    ABSENT         -- SHA does not exist in git history.
    TESTS_RED      -- SHA exists and reachable, but tests at that SHA fail now.
    """

    GREEN = "green"
    REVERTED = "reverted"
    ABSENT = "absent"
    TESTS_RED = "tests_red"


class ConversionOutcome(str, Enum):
    """The user-observable outcome of one `des-convert-to-atdd-pure` run.

    CONVERTED          -- the feature is now on the atdd_pure spine.
    BLOCKED_TAGGING    -- `.feature` scenarios lack `@slice-NN` tags; returns
                          to DISTILL (`conversion-blocked: needs-distill-tagging`).
    BLOCKED_MANUAL     -- a CLASSIC_NEEDS_MANUAL_REVIEW row cannot convert.
    BLOCKED_GATE       -- the carpaccio entry-gate dry-run failed.
    REFUSED_STALE      -- the feature dir changed since classification (M7
                          git_state mismatch) -- the converter refuses the row.
    REFUSED_READONLY   -- the feature dir is not writable; the converter
                          refuses cleanly (C7a) before any journalled side
                          effect, leaving the classic artifacts intact.
    ROLLED_BACK        -- a `--rollback` run un-did a partial conversion.
    """

    CONVERTED = "converted"
    BLOCKED_TAGGING = "blocked-needs-distill-tagging"
    BLOCKED_MANUAL = "blocked-needs-manual-review"
    BLOCKED_GATE = "blocked-carpaccio-gate"
    REFUSED_STALE = "refused-stale-manifest"
    REFUSED_READONLY = "refused-read-only-feature-dir"
    ROLLED_BACK = "rolled-back"


class ConversionStep(str, Enum):
    """The four journalled side-effecting steps of `execute(plan)` (M3).

    Each is written to `.nwave/conversion-journal/{id}.json` BEFORE the next
    starts; a re-run resumes from the last completed step.
    """

    PROMOTE_HEADING = "promote-slice-plan-heading"
    SEED_LEDGER = "seed-at-completion-ledger"
    FLIP_CONFIG = "flip-workflow-mode"
    ARCHIVE_ROADMAP = "archive-roadmap"


class InterruptPoint(str, Enum):
    """Where a conversion `execute()` is interrupted mid-run (S16 / C7b).

    Used to arm the partial-failure scenarios -- the next run must resume from
    the journal, never leave a half-converted limbo.
    """

    AFTER_PROMOTE = "after-promote-heading"
    AFTER_SEED = "after-seed-ledger"
    AFTER_FLIP = "after-flip-config"
    NONE = "none"


# --- F-13 closure (DESIGN: slice-02) -----------------------------------------


class LedgerWriter(str, Enum):
    """The two writers that append to the same AT-completion ledger (F-13).

    AT_REVIEW_VERDICT  -- the `at_review_verdict` CLI, writing an
                          `ATReviewVerdict` HMAC-signed friction-log record.
    AT_COMPLETION      -- the `AtCompletionLedger` API, writing gate-event
                          records (`seq` + `record_hash`).
    """

    AT_REVIEW_VERDICT = "at_review_verdict"
    AT_COMPLETION = "at_completion_ledger"


class LedgerReadOutcome(str, Enum):
    """What U1's M8 carpaccio-order read sees when it consumes the ledger.

    ACCEPTED        -- the mixed-writer ledger read cleanly; carpaccio order
                       resolved without raising.
    INTEGRITY_RAISED -- the read raised `LedgerIntegrityViolation` (the F-13
                        defect -- a fixed slice-02 must NOT produce this).
    """

    ACCEPTED = "accepted"
    INTEGRITY_RAISED = "integrity_raised"


# --- Deprecation marking (DESIGN: slice-07) ----------------------------------


class WorkflowMode(str, Enum):
    """The DELIVER spine selected by `.nwave/config.yaml:workflow.mode`.

    ATDD_PURE  -- the carpaccio slice-based spine. Default after release N.
    CLASSIC    -- the roadmap-based spine. Deprecated-but-present in release N:
                  resolves and runs, non-default, emits a per-dispatch advisory.
    ABSENT     -- the `workflow.mode` key is absent -> resolves to ATDD_PURE
                  (the release-N default flip).
    """

    ATDD_PURE = "atdd_pure"
    CLASSIC = "classic"
    ABSENT = "absent"


class AdvisoryState(str, Enum):
    """Whether the `ClassicSpineDeprecated` per-dispatch advisory fired.

    FIRED       -- a `classic` dispatch emitted the loud advisory to stderr +
                   the audit log.
    NOT_FIRED   -- an `atdd_pure` dispatch -- no advisory (orthogonality).
    """

    FIRED = "fired"
    NOT_FIRED = "not_fired"


# --- Audit-log replay (DESIGN: slice-05 / M5) --------------------------------


class ReplayOutcome(str, Enum):
    """The outcome of replaying a pre-2026-05-07 commit (M5 verification gate).

    GREEN   -- `verify_commit_trailers` + the `PhaseEventParser` MARK-HISTORICAL
               path interpreted the legacy 5-phase / v2.0-pipe commit cleanly.
    RED     -- replay failed -- the N+1 DELETE sweep precondition is unmet.
    """

    GREEN = "green"
    RED = "red"


# --- CLI exit codes (DESIGN: CLI contract) -----------------------------------


class ExitCode(int, Enum):
    OK = 0
    FAIL = 1  # classification crash-free but a manual-review row exists / conversion blocked
    USAGE = 2  # malformed argv


# --- Gherkin-phrase -> typed-value lookups -----------------------------------
# Module-level dicts keep each step body a single typed lookup + a single
# composition call (Mandate-12 criterion 3: no control flow in step bodies).

FEATURE_CLASS_BY_PHRASE: dict[str, FeatureClass] = {
    "a classic feature mid-implementation": FeatureClass.CLASSIC_MID_IMPLEMENTATION,
    "a classic feature whose DISTILL is done": FeatureClass.CLASSIC_DISTILL_DONE,
    "a feature already on the atdd_pure spine": FeatureClass.ATDD_PURE,
    "a feature that has not reached DISTILL": FeatureClass.PRE_DISTILL,
    "a classic feature with a corrupt roadmap": (
        FeatureClass.CLASSIC_NEEDS_MANUAL_REVIEW
    ),
}

CORRUPTION_BY_PHRASE: dict[str, CorruptionKind] = {
    "a truncated roadmap": CorruptionKind.ROADMAP_TRUNCATED,
    "a roadmap that is not valid JSON": CorruptionKind.ROADMAP_NOT_JSON,
    "a hand-edited roadmap inconsistent with its log": (
        CorruptionKind.ROADMAP_HAND_EDITED
    ),
    "an execution log with mixed-version events": CorruptionKind.LOG_MIXED_VERSION,
    "an empty execution log": CorruptionKind.LOG_EMPTY,
}

SHA_VERDICT_BY_PHRASE: dict[str, ShaVerdict] = {
    "exists and is reachable with green tests": ShaVerdict.GREEN,
    "was reverted": ShaVerdict.REVERTED,
    "does not exist in history": ShaVerdict.ABSENT,
    "has red tests now": ShaVerdict.TESTS_RED,
}

SLICE_STATUS_BY_PHRASE: dict[str, SliceStatus] = {
    "shipped": SliceStatus.SHIPPED,
    "pending": SliceStatus.PENDING,
}

INTERRUPT_BY_PHRASE: dict[str, InterruptPoint] = {
    "after the slice plan heading is promoted": InterruptPoint.AFTER_PROMOTE,
    "after the ledger is seeded": InterruptPoint.AFTER_SEED,
    "after the config is flipped": InterruptPoint.AFTER_FLIP,
}

WORKFLOW_MODE_BY_PHRASE: dict[str, WorkflowMode] = {
    "the atdd_pure spine": WorkflowMode.ATDD_PURE,
    "the classic spine": WorkflowMode.CLASSIC,
    "no workflow mode configured": WorkflowMode.ABSENT,
}

CONVERSION_OUTCOME_BY_PHRASE: dict[str, ConversionOutcome] = {
    "converted onto the atdd_pure spine": ConversionOutcome.CONVERTED,
    "blocked pending DISTILL tagging": ConversionOutcome.BLOCKED_TAGGING,
    "blocked pending manual review": ConversionOutcome.BLOCKED_MANUAL,
    "blocked on the carpaccio entry gate": ConversionOutcome.BLOCKED_GATE,
    "refused as a stale manifest row": ConversionOutcome.REFUSED_STALE,
    "refused because the feature directory is not writable": (
        ConversionOutcome.REFUSED_READONLY
    ),
}
