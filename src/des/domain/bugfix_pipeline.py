"""des.domain.bugfix_pipeline -- the two-lane bugfix pipeline (D-4).

autonomous-consolidation-and-bugfix-loops slice-03 (charter
`the-bugfix-loop-drains-the-queue-as-a-pipeline.md`, feature-delta Slice
Plan row slice-03). This is the DELIVER seam `des.cli.bugfix_pipeline_tick`
lazily imported while it did not exist -- the RED scaffold's own
DELIVER-pinned assumption:

    evaluate_and_record(*, ledger, feature_id, defect_id, action, stage,
                         now, reason) -> None

── The two-lane pipeline (D-4, verbatim) ──
RCA / charter-authoring / AT-authoring are CLOUD lane -- fired with NO
concurrency ceiling, always admitted. RED-seal / crafter-GREEN /
Vera-examine / commit-slice are BOX lane -- strictly serialized to exactly
ONE in-flight item, a LOCAL invariant this module enforces itself (no
cross-instance coordination required): a `stage-started` for a box-lane
stage while ANOTHER defect already holds one open is DEFERRED
(`BoxLaneEntryDeferred`, naming the current occupant), never silently
admitted, never silently dropped.

── The D-8 no-orphan guard ──
A `claim-drained` action is refused (`DrainClaimRejectedNoAttestation`,
carrying a named reason) unless the ledger already carries a
`PipelineStageCompleted` record for the terminal `commit-slice` stage for
that defect -- the `SliceCommitVerified`-class record this charter's
Negative-1 names. A legitimately-attested claim (the record IS present)
appends nothing further -- no record kind is named for that path by this
slice's ATs.

── Fail loud, free the slot (charter "What to explore") ──
A `stage-failed` action is recorded loudly (`PipelineStageFailed`, carrying
a non-empty `reason`), never silently marked done. For a box-lane stage
this ALSO releases the slot: box-lane occupancy is replayed from the
ledger's own recorded content (the LAST started/completed/failed record per
defect among box-lane-stage records), so a failed defect's slot is open
again the moment its `PipelineStageFailed` record lands -- no separate
bookkeeping needed (D-8 no-orphan discipline).

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/
           feature-delta.md, slice-03; src/des/cli/bugfix_pipeline_tick.py
           module docstring; tests/des/acceptance/
           autonomous_consolidation_and_bugfix_loops/steps/
           domain_types_slice_03.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from des.domain.iso_utc import format_iso_utc


if TYPE_CHECKING:
    from datetime import datetime

    from des.ports.driven_ports.at_completion_ledger_port import AtCompletionLedgerPort


# The pipeline's event vocabulary -- the DELIVER-pinned record kinds.
STAGE_STARTED = "PipelineStageStarted"
STAGE_COMPLETED = "PipelineStageCompleted"
STAGE_FAILED = "PipelineStageFailed"
BOX_LANE_ENTRY_DEFERRED = "BoxLaneEntryDeferred"
DRAIN_CLAIM_REJECTED_NO_ATTESTATION = "DrainClaimRejectedNoAttestation"

_PIPELINE_EVENTS = frozenset(
    {
        STAGE_STARTED,
        STAGE_COMPLETED,
        STAGE_FAILED,
        BOX_LANE_ENTRY_DEFERRED,
        DRAIN_CLAIM_REJECTED_NO_ATTESTATION,
    }
)

# The D-4 box-lane stage vocabulary (wire values), verbatim from
# PipelineStage.is_box_lane in the DISTILL domain types.
_BOX_LANE_STAGES = frozenset(
    {"red-seal", "crafter-green", "vera-examine", "commit-slice"}
)

_COMMIT_SLICE_STAGE = "commit-slice"

# The action -> event-kind map for the two plain pass-through actions this
# module records unconditionally (subject to the box-lane admission check
# for `stage-started`).
_EVENT_BY_ACTION = {
    "stage-started": STAGE_STARTED,
    "stage-completed": STAGE_COMPLETED,
    "stage-failed": STAGE_FAILED,
}

# The full closed set of actions evaluate_and_record accepts -- the two
# plain pass-through actions above PLUS the `claim-drained` action handled
# separately. This is the SSOT a caller-supplied `action` is validated
# against; the CLI's own argparse `choices=` (bugfix_pipeline_tick.py) is
# an additional, non-exclusive guard, not the only one -- domain callers
# such as consolidation_queue_intake.py call evaluate_and_record directly,
# bypassing argparse entirely.
_KNOWN_ACTIONS = frozenset({*_EVENT_BY_ACTION, "claim-drained"})


def _current_box_lane_occupant(
    records: list[dict[str, Any]], exclude_defect_id: str
) -> str | None:
    """The defect_id currently holding an OPEN box-lane stage, if any OTHER
    than ``exclude_defect_id`` -- replayed from the ledger's own recorded
    content only (D-8 no-orphan discipline): the LAST
    started/completed/failed record per defect among box-lane-stage
    records; a defect whose last such record is `PipelineStageStarted`
    still holds its slot open.
    """
    last_by_defect: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("event") not in (STAGE_STARTED, STAGE_COMPLETED, STAGE_FAILED):
            continue
        if record.get("stage") not in _BOX_LANE_STAGES:
            continue
        defect_id = record.get("defect_id")
        if isinstance(defect_id, str):
            last_by_defect[defect_id] = record

    for defect_id, record in last_by_defect.items():
        if defect_id == exclude_defect_id:
            continue
        if record.get("event") == STAGE_STARTED:
            return defect_id
    return None


def _has_commit_slice_attestation(
    records: list[dict[str, Any]], defect_id: str
) -> bool:
    return any(
        record.get("event") == STAGE_COMPLETED
        and record.get("defect_id") == defect_id
        and record.get("stage") == _COMMIT_SLICE_STAGE
        for record in records
    )


def evaluate_and_record(
    *,
    ledger: AtCompletionLedgerPort,
    feature_id: str,
    defect_id: str,
    action: str,
    stage: str | None,
    now: datetime,
    reason: str | None,
) -> None:
    """Evaluate one bugfix-pipeline tick against the D-4 two-lane invariant
    and append whichever record the action produces -- box-lane occupancy
    and commit-slice attestation are both replayed from the ledger's own
    recorded content only, never from caller-side bookkeeping (D-8
    no-orphan discipline).
    """
    if action not in _KNOWN_ACTIONS:
        raise ValueError(
            f"action {action!r} is not a recognised bugfix-pipeline action. "
            f"WHY: evaluate_and_record only knows how to evaluate "
            f"{sorted(_KNOWN_ACTIONS)!r} -- any other value would otherwise "
            "reach an unguarded dict lookup and raise a bare KeyError "
            "instead of a self-explaining refusal (GDP-3). HOW: pass one of "
            "the known actions, or -- if this is a genuinely new action -- "
            "add it to _EVENT_BY_ACTION (or the claim-drained branch) in "
            "src/des/domain/bugfix_pipeline.py."
        )

    records = [
        record
        for record in ledger.read_records(feature_id=feature_id)
        if record.get("event") in _PIPELINE_EVENTS
    ]
    timestamp = format_iso_utc(now)

    if action == "claim-drained":
        if _has_commit_slice_attestation(records, defect_id):
            return
        ledger.append_bugfix_pipeline_event(
            DRAIN_CLAIM_REJECTED_NO_ATTESTATION,
            defect_id=defect_id,
            timestamp=timestamp,
            reason=(
                f"no commit-slice PipelineStageCompleted record for "
                f"{defect_id} (D-8 no-orphan guard)"
            ),
            feature_id=feature_id,
        )
        return

    if action == "stage-started" and stage in _BOX_LANE_STAGES:
        occupant = _current_box_lane_occupant(records, defect_id)
        if occupant is not None:
            ledger.append_bugfix_pipeline_event(
                BOX_LANE_ENTRY_DEFERRED,
                defect_id=defect_id,
                stage=stage,
                timestamp=timestamp,
                reason=f"box lane occupied by {occupant}",
                feature_id=feature_id,
            )
            return

    ledger.append_bugfix_pipeline_event(
        _EVENT_BY_ACTION[action],
        defect_id=defect_id,
        stage=stage,
        timestamp=timestamp,
        reason=reason,
        feature_id=feature_id,
    )


__all__ = [
    "BOX_LANE_ENTRY_DEFERRED",
    "DRAIN_CLAIM_REJECTED_NO_ATTESTATION",
    "STAGE_COMPLETED",
    "STAGE_FAILED",
    "STAGE_STARTED",
    "evaluate_and_record",
]
