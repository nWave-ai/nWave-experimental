"""Domain types for autonomous-consolidation-and-bugfix-loops slice-03
(the bugfix loop drains the defect queue as a pipeline, charter
`the-bugfix-loop-drains-the-queue-as-a-pipeline.md`).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun
the slice-03 ``.feature`` scenarios speak lives here as a typed enum or
frozen dataclass. Step methods + composition consume these typed parameters;
raw ``str`` parameters are avoided wherever a domain enum exists.

── The two-lane pipeline (D-4, verbatim) ──
``PipelineStage`` below IS the concrete, testable resolution of "cloud lane
vs box lane": RCA / charter-authoring / AT-authoring are CLOUD lane (fan out
concurrently, near-zero box cost); RED-seal / crafter-GREEN / Vera-examine /
commit-slice are BOX lane (strictly serialized to exactly ONE in-flight item
-- a LOCAL invariant the pipeline itself enforces, no cross-instance
coordination required). Full contract:
``src/des/cli/bugfix_pipeline_tick.py`` module docstring.

── The D-8 no-orphan guard ──
A defect is "drained" iff the ledger carries a `PipelineStageCompleted`
record for the terminal box-lane stage (`COMMIT_SLICE`) -- the
`SliceCommitVerified`-class record this charter's Negative-1 names. A
`claim-drained` action with no such record MUST be refused, never silently
accepted (`DrainClaimRejectedNoAttestation`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case defect identifier (arbitrary per-scenario fixture key, not a
# real backlog/ledger defect ID).
DefectId = NewType("DefectId", str)

# A kebab-case feature identifier.
FeatureId = NewType("FeatureId", str)


class PipelineStage(str, Enum):
    """One stage of the two-lane bugfix pipeline (D-4 resolution).

    Each value is BOTH the CLI's ``--stage`` wire value AND the Gherkin
    phrase the ``.feature`` file speaks -- Mandate-12 DSL emergence (one
    typed vocabulary, no separate business-phrase-to-enum table needed
    because the enum value already IS the readable phrase).
    """

    RCA = "rca"
    CHARTER_AUTHORING = "charter-authoring"
    AT_AUTHORING = "at-authoring"
    RED_SEAL = "red-seal"
    CRAFTER_GREEN = "crafter-green"
    VERA_EXAMINE = "vera-examine"
    COMMIT_SLICE = "commit-slice"

    @property
    def is_cloud_lane(self) -> bool:
        """True for RCA / charter-authoring / AT-authoring (fan-out lane)."""
        return self in _CLOUD_LANE_STAGES

    @property
    def is_box_lane(self) -> bool:
        """True for RED-seal / crafter-GREEN / Vera-examine / commit-slice
        (the strictly-serialized-to-one lane, D-4).
        """
        return self in _BOX_LANE_STAGES


_CLOUD_LANE_STAGES = frozenset(
    {PipelineStage.RCA, PipelineStage.CHARTER_AUTHORING, PipelineStage.AT_AUTHORING}
)
_BOX_LANE_STAGES = frozenset(
    {
        PipelineStage.RED_SEAL,
        PipelineStage.CRAFTER_GREEN,
        PipelineStage.VERA_EXAMINE,
        PipelineStage.COMMIT_SLICE,
    }
)

# Ordered full-chain sequence a fully-drained defect walks (charter
# Positive-2: "a traceable chain of ledger records").
FULL_CHAIN_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.RCA,
    PipelineStage.CHARTER_AUTHORING,
    PipelineStage.AT_AUTHORING,
    PipelineStage.RED_SEAL,
    PipelineStage.CRAFTER_GREEN,
    PipelineStage.VERA_EXAMINE,
    PipelineStage.COMMIT_SLICE,
)


class PipelineAction(str, Enum):
    """The action a single ``des bugfix-pipeline-tick`` invocation performs."""

    STAGE_STARTED = "stage-started"
    STAGE_COMPLETED = "stage-completed"
    STAGE_FAILED = "stage-failed"
    CLAIM_DRAINED = "claim-drained"


@dataclass(frozen=True)
class PipelineOutcome:
    """Observable outcome of a SEQUENCE of bugfix-pipeline ticks (Layer 3/4).

    The driving port is the real ``des bugfix-pipeline-tick`` CLI entry
    (``des.cli.bugfix_pipeline_tick.main``), driven IN-PROCESS once per tick.
    Universe entries ``assert_state_delta`` tracks are built from THIS
    dataclass's port-exposed fields ONLY -- never a Popen handle, an argv
    list, or the raw ledger file path (Mandate 8).

    - `cloud_lane_concurrent_count`     -- distinct defects with an OPEN
                                           cloud-lane stage (started, not yet
                                           completed/failed) at the sampled
                                           instant.
    - `box_lane_concurrent_count`       -- distinct defects with an OPEN
                                           box-lane stage at the sampled
                                           instant. MUST never exceed 1
                                           (D-4's core invariant).
    - `box_lane_activity_observed`      -- True iff at least one box-lane
                                           `PipelineStageStarted` record was
                                           actually appended anywhere in the
                                           sequence -- the discriminator
                                           (Closure Obligations,
                                           SILENCE/ABSENCE) that makes a
                                           "box lane never exceeds 1" reading
                                           MEANINGFUL rather than vacuously
                                           true against a scaffold that
                                           writes nothing at all.
    - `box_lane_entry_deferred`         -- True iff a concurrent second
                                           box-lane-entry attempt was
                                           correctly REJECTED (an explicit
                                           `BoxLaneEntryDeferred` record was
                                           appended) rather than silently
                                           admitted or silently dropped.
    - `deferred_reason_named`           -- True iff the deferred record
                                           carries a non-empty ``reason``
                                           naming which defect currently
                                           occupies the box lane.
    - `full_chain_traceable`            -- True iff the ledger carries the
                                           full ordered chain RCA -> charter
                                           -> AT -> RED-seal -> GREEN ->
                                           examine -> commit-slice for ONE
                                           defect, each individually
                                           attributable to that defect_id.
    - `slice_commit_verified_present`   -- True iff a `PipelineStageCompleted`
                                           record for `COMMIT_SLICE` (the
                                           `SliceCommitVerified`-class
                                           record) exists for that defect.
    - `drain_claim_rejected`            -- True iff a `claim-drained` action
                                           with no prior commit-slice
                                           attestation was REFUSED
                                           (`DrainClaimRejectedNoAttestation`
                                           appended) -- D-8's no-orphan guard,
                                           proven as a positive enforcement,
                                           not an absence check.
    - `rejection_reason_named`          -- True iff that rejection record
                                           carries a non-empty ``reason``.
    - `mid_pipeline_failure_recorded`   -- True iff a `PipelineStageFailed`
                                           record was appended, carrying a
                                           non-empty ``reason`` (charter:
                                           "does the pipeline correctly route
                                           it out (fail loud)").
    - `box_lane_freed_after_failure`    -- True iff, AFTER a box-lane stage
                                           failure released its slot, a
                                           SUBSEQUENT defect's box-lane entry
                                           was ADMITTED (not deferred) --
                                           proving the slot genuinely freed
                                           rather than staying stuck.
    - `new_record_count`                -- total ledger records appended
                                           across every tick this outcome
                                           observed.
    """

    cloud_lane_concurrent_count: int
    box_lane_concurrent_count: int
    box_lane_activity_observed: bool
    box_lane_entry_deferred: bool
    deferred_reason_named: bool
    full_chain_traceable: bool
    slice_commit_verified_present: bool
    drain_claim_rejected: bool
    rejection_reason_named: bool
    mid_pipeline_failure_recorded: bool
    box_lane_freed_after_failure: bool
    new_record_count: int


# --- Phrase -> typed-value lookup table (Mandate-12 DSL emergence) --------

STAGE_BY_PHRASE: dict[str, PipelineStage] = {
    "RCA": PipelineStage.RCA,
    "charter authoring": PipelineStage.CHARTER_AUTHORING,
    "AT authoring": PipelineStage.AT_AUTHORING,
    "RED seal": PipelineStage.RED_SEAL,
    "crafter's GREEN pass": PipelineStage.CRAFTER_GREEN,
    "Vera's examine": PipelineStage.VERA_EXAMINE,
    "commit-slice": PipelineStage.COMMIT_SLICE,
}


__all__ = [
    "FULL_CHAIN_ORDER",
    "STAGE_BY_PHRASE",
    "DefectId",
    "FeatureId",
    "PipelineAction",
    "PipelineOutcome",
    "PipelineStage",
]
