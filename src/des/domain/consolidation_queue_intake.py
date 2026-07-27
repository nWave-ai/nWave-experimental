"""des.domain.consolidation_queue_intake -- trunk-health signal-to-queue-item
intake (D-4/D-19).

autonomous-consolidation-and-bugfix-loops slice-04 (charter
`trunk-health-signals-become-queue-items-that-never-vanish.md`, feature-delta
Slice Plan row slice-04). This is the seam `des.cli.consolidation_signal_tick`
lazily imported while it did not exist -- the RED scaffold's own
DELIVER-pinned assumption:

    intake_signal(*, ledger, feature_id, signal_type, signal_key, now) -> IntakeResult

── EXAMINE fix (Vera FAIL, real-CLI-surface defect) ──
`intake_signal` returns a discriminated `IntakeResult` (never bare `None`) so
the CLI-facing driving port (`des.cli.consolidation_signal_tick.main`) can
observe what happened and surface it on the ONLY surface a real caller (or
Vera) sees -- exit code + emitted line -- not just the ledger. The ledger
write behavior itself is UNCHANGED: `ConsolidationSignalIntakeRejected` was
already appended correctly before this fix; only the CLI's silence on that
same outcome was the defect.

── REUSE, DON'T REBUILD (D-4/D-19, verbatim) ──
A detected trunk-health signal becomes exactly one queue item by entering
the SAME shared pipeline slice-03 built, at its FIRST cloud-lane stage
(RCA) -- via a DIRECT call into the SAME
``des.domain.bugfix_pipeline.evaluate_and_record`` seam slice-03 already
ships (GREEN today), never a bespoke per-signal-type runner and never a
second pipeline/ledger-event vocabulary. This module adds exactly ONE
net-new thing: signal-to-queue-item INTAKE -- the derivation of a stable
``defect_id`` from ``(signal_type, signal_key)`` plus the idempotency check
that stops a re-detected, still-unresolved signal from duplicating its
queue item.

── The D-8 loud-rejection guard ──
An unsupported ``signal_type`` is refused loudly
(``ConsolidationSignalIntakeRejected``, carrying a non-empty ``reason``),
never silently absent from the queue -- the exact class of false negative
this feature must not produce.

── The D-8/D-20 no-duplicate guard ──
A signal is "already queued" iff the ledger carries a
``PipelineStageStarted`` record for the deterministic ``defect_id`` derived
from ``(signal_type, signal_key)`` -- re-detecting it MUST NOT append a
second such record (idempotent recognition of the existing item).

Reference: docs/feature/autonomous-consolidation-and-bugfix-loops/
           feature-delta.md, slice-04; src/des/cli/consolidation_signal_tick.py
           module docstring; tests/des/acceptance/
           autonomous_consolidation_and_bugfix_loops/steps/
           domain_types_slice_04.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from des.domain.bugfix_pipeline import STAGE_STARTED, evaluate_and_record
from des.domain.iso_utc import format_iso_utc


if TYPE_CHECKING:
    from datetime import datetime

    from des.ports.driven_ports.at_completion_ledger_port import AtCompletionLedgerPort


# The intake's own net-new event kind (D-8: a loud, positive-enforcement
# rejection record, never a silent absence).
CONSOLIDATION_SIGNAL_INTAKE_REJECTED = "ConsolidationSignalIntakeRejected"


class IntakeDecision(str, Enum):
    """The three outcomes a single `intake_signal` call can reach -- the
    discriminator the CLI driving port branches on to decide its own exit
    code + emitted line (the EXAMINE fix: the ledger record alone is not
    enough, the CLI-facing surface must observe the SAME outcome).
    """

    ACCEPTED = "accepted"
    ALREADY_QUEUED = "already-queued"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IntakeResult:
    """The outcome of one `intake_signal` call.

    `reason` is populated on `REJECTED` (the same text appended to the
    `ConsolidationSignalIntakeRejected` ledger record) so the CLI can print
    the identical WHAT/WHY/HOW a ledger reader would see, never a bare
    "rejected" with the reason dropped.
    """

    decision: IntakeDecision
    defect_id: str
    reason: str | None = None


# The pipeline's own first cloud-lane stage every accepted signal enters at.
_RCA_STAGE = "rca"

# The four supported trunk-health signal classes (feature-delta Slice Plan
# row slice-04, verbatim: drift / un-merged work / stale branches / failing
# gates). An unsupported wire value is refused loudly (D-8), never silently
# absent from the queue.
SUPPORTED_SIGNAL_TYPES = frozenset(
    {"drift", "unmerged-work", "stale-branch", "failing-gate"}
)

_CONSOLIDATION_DEFECT_PREFIX = "consolidation-"


def _derive_defect_id(signal_type: str, signal_key: str) -> str:
    """The deterministic ``(signal_type, signal_key) -> defect_id``
    derivation (D-19): the SAME signal re-detected twice derives the SAME
    defect_id (idempotency), and two DIFFERENT signal_keys of the SAME
    signal_type derive two DIFFERENT defect_ids -- never collapsed into one.
    """
    return f"{_CONSOLIDATION_DEFECT_PREFIX}{signal_type}-{signal_key}"


def _already_queued(records: list[dict[str, Any]], defect_id: str) -> bool:
    """True iff the ledger already carries a ``PipelineStageStarted(rca)``
    record for ``defect_id`` -- replayed from the ledger's own recorded
    content only, mirroring ``des.domain.bugfix_pipeline``'s own D-8
    no-orphan discipline.
    """
    return any(
        record.get("event") == STAGE_STARTED
        and record.get("defect_id") == defect_id
        and record.get("stage") == _RCA_STAGE
        for record in records
    )


def intake_signal(
    *,
    ledger: AtCompletionLedgerPort,
    feature_id: str,
    signal_type: str,
    signal_key: str,
    now: datetime,
) -> IntakeResult:
    """Turn one already-detected trunk-health signal into exactly one queue
    item, entered at the shared pipeline's first cloud-lane stage (RCA) via
    a DIRECT call into ``des.domain.bugfix_pipeline.evaluate_and_record``
    (D-4/D-19) -- never a second pipeline, never a second ledger-event
    vocabulary.

    Returns an ``IntakeResult`` naming which of the three outcomes was
    reached, so the CLI driving port can surface it on its OWN
    exit-code/emitted-line surface -- never just the ledger (the EXAMINE
    fix: a caller who never reads the ledger must still observe a rejection
    loudly).
    """
    defect_id = _derive_defect_id(signal_type, signal_key)

    if signal_type not in SUPPORTED_SIGNAL_TYPES:
        reason = (
            f"unsupported signal_type {signal_type!r} -- supported: "
            f"{sorted(SUPPORTED_SIGNAL_TYPES)}"
        )
        ledger.append_bugfix_pipeline_event(
            CONSOLIDATION_SIGNAL_INTAKE_REJECTED,
            defect_id=defect_id,
            timestamp=format_iso_utc(now),
            reason=reason,
            feature_id=feature_id,
        )
        return IntakeResult(
            decision=IntakeDecision.REJECTED, defect_id=defect_id, reason=reason
        )

    records = ledger.read_records(feature_id=feature_id)
    if _already_queued(records, defect_id):
        return IntakeResult(decision=IntakeDecision.ALREADY_QUEUED, defect_id=defect_id)

    evaluate_and_record(
        ledger=ledger,
        feature_id=feature_id,
        defect_id=defect_id,
        action="stage-started",
        stage=_RCA_STAGE,
        now=now,
        reason=f"trunk-health signal {signal_type} detected for {signal_key}",
    )
    return IntakeResult(decision=IntakeDecision.ACCEPTED, defect_id=defect_id)


__all__ = [
    "CONSOLIDATION_SIGNAL_INTAKE_REJECTED",
    "SUPPORTED_SIGNAL_TYPES",
    "IntakeDecision",
    "IntakeResult",
    "intake_signal",
]
