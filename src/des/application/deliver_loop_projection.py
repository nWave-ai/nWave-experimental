"""``des next`` -- read-only advisory projection of the atdd_pure loop state.

Composes FOUR existing SSOTs at call-time (no caching, no persisted snapshot)
into a single ``NextStep`` value: the Slice Plan (``carpaccio_format.
parse_slice_plan``), the AT-completion ledger (``AtCompletionLedger.
read_records``), the per-slice phase order (``atdd_pure_phases.
ATDDPurePhase``), and the examine-verdict predicate already shipped by
``commit_slice`` (reused verbatim -- M1: never a parallel re-derivation of
the SAME predicate a gate already gates on).

Reference: docs/feature/des-next-loop-projection/feature-delta.md
  ([REF] Component Overview, [REF] Options Considered -- Option 1,
  [REF] Per-slice precondition order, [REF] Three-layer contract).

NON-GOAL (pinned, load-bearing -- feature-delta.md [REF] Non-Goals): ``des
next`` MUST NOT be wrapped in an automated poll-and-auto-execute loop within
nwave-dev, even for ``step_kind=producing-tool`` steps -- doing so recreates
the rejected sequencer (ADR-FLOW-001, the OSS hook-only mandate). It returns
a copy-paste-able command precisely because pasting is a human/agent decision
point; a wrapper that reads a ``NextStep`` and immediately invokes ``how``
collapses that decision point into automation.

Slice-01 scope: the THREE mid-loop judgment-bearing phases (AT-authoring
absent, GREEN absent, EXAMINE absent) for a single ``pending`` Slice-Plan
row. The producing-tool branch (D_REFACTOR_COMMIT, all preconditions met),
the feature-end branch, and the drift/absent-ledger INDETERMINATE branches
are later slices' scope (feature-delta.md [REF] Slice Plan slice-02/03/04)
-- reaching one of them here raises ``NotImplementedError`` naming the
follow-on slice rather than fabricating untested behaviour.

CONTRACT_SHAPE: pure-function -- reads only, returns a frozen ``NextStep``
value, zero mutation (nw-code-design-oo Effect Isolation, plan-value
pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import commit_slice as _commit_slice
from des.cli import feature_delta_doctor
from des.cli.carpaccio_format import (
    GateError,
    SlicePlan,
    SlicePlanRow,
    parse_slice_plan,
)
from des.domain.atdd_pure_phases import ATDDPurePhase


if TYPE_CHECKING:
    from pathlib import Path


_EVENT = "NextStepProjected"
_SCHEMA_VERSION = "1.1.0"

_RED_OBSERVED_EVENT = "RedObserved"
_AT_REVIEW_VERDICT_EVENT = "ATReviewVerdict"
_PENDING_STATUS = "pending"

#: The exact ``GateError`` payload ``error`` text
#: ``carpaccio_format._build_slice_rows`` raises when the Slice Plan
#: heading is present but the table carries zero data rows. Matched
#: narrowly (not a broad ``except GateError``) so an UNRELATED malformed-
#: table gate error (duplicate slice id, missing slice-NN cell, missing
#: heading) still degrades LOUD -- an unhandled traceback -- rather than
#: being silently reclassified as INDETERMINATE.
_EMPTY_SLICE_PLAN_TABLE_ERROR = "the slice-plan table has no slice rows"

LoopState = Literal[
    "SLICE_IN_PROGRESS",
    "FEATURE_END_PENDING",
    "FEATURE_END_IN_PROGRESS",
    "DONE",
    "INDETERMINATE",
]
StepKind = Literal["wave-command", "producing-tool"]


@dataclass(frozen=True)
class NextStep:
    """One projected loop step -- the published ``NextStepProjected`` contract.

    Frozen (plan-value pattern): ``project_next_step`` returns this value, it
    never mutates state itself.
    """

    event: str
    feature_id: str
    loop_state: LoopState
    slice_id: str | None
    phase: str | None
    step_kind: StepKind | None
    what: str
    why: str
    how: str
    schema_version: str


def project_next_step(repo_root: Path, feature_id: str) -> NextStep:
    """The pure composition core: derive the single next legal loop step.

    (1) reads the feature-delta and runs the ``feature_delta_doctor``
    structural preflight -- a gap short-circuits to ``INDETERMINATE`` naming
    the doctor's own gap, never a re-derivation of its classification; (2)
    parses the Slice Plan; (3) reads the AT-completion ledger for the
    feature; (4) walks the per-slice precondition order (feature-delta.md
    "Per-slice precondition order") for the first ``pending`` row.
    """
    delta_path = _feature_delta_path(repo_root, feature_id)
    if not delta_path.is_file():
        return _indeterminate(
            feature_id,
            what=f"no feature-delta.md found for feature {feature_id!r}",
            why=f"expected {delta_path} to exist",
        )
    content = delta_path.read_text(encoding="utf-8")

    gaps = feature_delta_doctor.diagnose(content)
    if gaps:
        first_gap = gaps[0]
        return _indeterminate(
            feature_id,
            what=f"feature-delta.md has a structural gap: {first_gap['what']}",
            why=first_gap["why"],
        )

    try:
        plan = parse_slice_plan(content)
    except GateError as exc:
        if exc.payload.get("error") != _EMPTY_SLICE_PLAN_TABLE_ERROR:
            raise
        return _indeterminate(
            feature_id,
            what=(
                "the Slice Plan table is empty -- the heading is present "
                "but the table carries zero slice rows"
            ),
            why=(
                "carpaccio_format.parse_slice_plan raised a malformed-table "
                f"gate error: {exc.payload.get('error')!r}; an empty slice "
                "plan has no pending row to project a next step for"
            ),
        )
    pending_row = _first_pending_row(plan)
    if pending_row is None:
        return _indeterminate(
            feature_id,
            what="no pending slice found in the Slice Plan",
            why=(
                "slice-01 of des-next-loop-projection only projects a single "
                "mid-loop pending slice; the all-shipped feature-end branch "
                "is a later slice's scope (feature-delta.md [REF] Slice Plan "
                "slice-03)"
            ),
        )

    return _project_pending_slice(repo_root, feature_id, pending_row.slice_id)


def _feature_delta_path(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "feature" / feature_id / "feature-delta.md"


def _first_pending_row(plan: SlicePlan) -> SlicePlanRow | None:
    for row in plan.rows:
        if row.status.strip().lower() == _PENDING_STATUS:
            return row
    return None


def _project_pending_slice(repo_root: Path, feature_id: str, slice_id: str) -> NextStep:
    ledger = AtCompletionLedger(feature_id, repo_root)
    records = ledger.read_records()

    if not _has_event_for_slice(records, _RED_OBSERVED_EVENT, slice_id):
        return _wave_command_step(
            feature_id=feature_id,
            slice_id=slice_id,
            phase=ATDDPurePhase.D_DISTILL,
            what=f"slice {slice_id}'s acceptance tests are not yet authored.",
            why=(
                "the per-slice cycle requires a RedObserved ledger record "
                "before A_GREEN can begin (ADR-001 3-phase canon); AT "
                "authoring is judgment-bearing and must run through the "
                "DISTILL wave, never a raw dispatch envelope."
            ),
            how=f"/nw-distill --feature-id {feature_id} --slice {slice_id}",
        )

    if not _has_event_for_slice(records, _AT_REVIEW_VERDICT_EVENT, slice_id):
        return _wave_command_step(
            feature_id=feature_id,
            slice_id=slice_id,
            phase=ATDDPurePhase.A_GREEN,
            what=f"slice {slice_id}'s ATs are authored but not yet GREEN.",
            why=(
                "the crafter has not yet made the ATs pass and produced an "
                "APPROVED ATReviewVerdict; GREEN-ing the ATs is judgment-"
                "bearing and must run through the DELIVER wave, never a raw "
                "dispatch envelope."
            ),
            how=f"/nw-deliver --feature-id {feature_id}",
        )

    if _commit_slice._latest_examine_verdict(repo_root, feature_id, slice_id) is None:
        return _wave_command_step(
            feature_id=feature_id,
            slice_id=slice_id,
            phase=ATDDPurePhase.EXAMINE,
            what=(
                f"slice {slice_id} is AT-review-verified but not yet EXAMINE-verified."
            ),
            why=(
                "the per-slice cycle requires an ExamineVerdictRecorded "
                "ledger record before commit-slice will accept (ADR-001 "
                "3-phase canon); the EXAMINE observation is judgment-"
                "bearing and must run through the DELIVER wave, never a raw "
                "dispatch envelope."
            ),
            how=f"/nw-deliver --feature-id {feature_id}",
        )

    raise NotImplementedError(
        f"slice {slice_id} is EXAMINE-verified -- the producing-tool commit "
        "step (D_REFACTOR_COMMIT) is out of slice-01's scope; see "
        "feature-delta.md [REF] Slice Plan slice-02."
    )


def _has_event_for_slice(
    records: list[dict[str, Any]], event: str, slice_id: str
) -> bool:
    return any(
        record.get("event") == event and record.get("slice_id") == slice_id
        for record in records
    )


def _wave_command_step(
    *,
    feature_id: str,
    slice_id: str,
    phase: ATDDPurePhase,
    what: str,
    why: str,
    how: str,
) -> NextStep:
    return NextStep(
        event=_EVENT,
        feature_id=feature_id,
        loop_state="SLICE_IN_PROGRESS",
        slice_id=slice_id,
        phase=phase.value,
        step_kind="wave-command",
        what=what,
        why=why,
        how=how,
        schema_version=_SCHEMA_VERSION,
    )


def _indeterminate(feature_id: str, *, what: str, why: str) -> NextStep:
    return NextStep(
        event=_EVENT,
        feature_id=feature_id,
        loop_state="INDETERMINATE",
        slice_id=None,
        phase=None,
        step_kind=None,
        what=what,
        why=why,
        how="no automatic remediation for this state -- see why",
        schema_version=_SCHEMA_VERSION,
    )
