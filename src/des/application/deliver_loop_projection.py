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

Per-slice scope covers the FOUR mid-loop states for a single Slice-Plan row:
AT-authoring absent (-> DISTILL), GREEN absent (-> DELIVER), EXAMINE absent
(-> DELIVER), and EXAMINE-verified-but-not-yet-committed (-> the mechanical
``des commit-slice`` producing tool). TERMINAL ledger evidence
(``SliceCommitVerified``) always wins over a stale markdown ``Status``
column: a row still marked ``pending`` whose slice already carries
``SliceCommitVerified`` is drift, not a step, and is reported
``INDETERMINATE`` naming the disagreement rather than re-prescribing
already-shipped work (fix-des-next-honours-terminal-evidence). The
feature-end branch remains a later slice's scope (feature-delta.md [REF]
Slice Plan slice-03/04).

WHICH slice is projected comes from the caller's DECLARED ``slice_id``, never
from table position and never inferred from the worktree
(fix-des-next-lane-awareness). A Slice Plan whose rows are all ``pending``
is produced BOTH by a single sequential lane -- where the first row genuinely
is next -- AND by a parallel worktree delivering row 06, where every row it
does not own stays ``pending`` forever because no predecessor is ever
committed there. The two are indistinguishable in the data, so the owning
lane can only be a declared fact. Undeclared, the projection answers only
when exactly one pending row leaves no choice to make, and otherwise degrades
LOUD (``INDETERMINATE``) naming every candidate evenly.

CONTRACT_SHAPE: pure-function -- reads only, returns a frozen ``NextStep``
value, zero mutation (nw-code-design-oo Effect Isolation, plan-value
pattern).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from des.adapters.driven.logging.at_completion_ledger import (
    EBATCH_REFACTOR_COMPLETED,
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.application.feature_context_bootstrap import classify as classify_bootstrap
from des.cli import carpaccio_slice_gate, feature_delta_doctor
from des.cli import commit_slice as _commit_slice
from des.cli.carpaccio_format import (
    REGRESSION_TEST_FILE_ANNOTATION_RE,
    GateError,
    SlicePlan,
    SlicePlanRow,
    parse_slice_plan,
)
from des.domain.atdd_pure_phases import ATDDPurePhase
from des.domain.repo_path_resolver import feature_delta_path as _feature_delta_path


if TYPE_CHECKING:
    from pathlib import Path


_EVENT = "NextStepProjected"
_SCHEMA_VERSION = "1.1.0"

_RED_OBSERVED_EVENT = "RedObserved"
_AT_REVIEW_VERDICT_EVENT = "ATReviewVerdict"
_PENDING_STATUS = "pending"

_NO_REMEDIATION = "no automatic remediation for this state -- see why"

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


def project_next_step(
    repo_root: Path, feature_id: str, slice_id: str | None = None
) -> NextStep:
    """The pure composition core: derive the single next legal loop step.

    ``slice_id`` is the lane the CALLER DECLARES it owns. It is optional, but
    it is the only thing that can identify the lane: a Slice Plan whose rows
    are all ``pending`` is produced both by a single sequential lane (where
    the first row IS next) and by a parallel worktree delivering row 06
    (where it is not), and nothing in the data separates the two. Undeclared,
    the projection answers only when exactly one pending row leaves no choice
    to make, and otherwise degrades LOUD (``INDETERMINATE``) rather than
    naming a slice by table position -- see ``_select_row``.

    (1) reads the feature-delta and runs the ``feature_delta_doctor``
    structural preflight -- a gap short-circuits to ``INDETERMINATE`` naming
    the doctor's own gap, never a re-derivation of its classification; (2)
    parses the Slice Plan; (3) reads the AT-completion ledger for the
    feature UNDER the M7 fail-closed integrity contract -- an unreadable
    ledger degrades LOUD to ``INDETERMINATE`` naming the read failure,
    never a raw traceback (GDP-6); (4) resolves TERMINAL ledger evidence
    (``SliceCommitVerified``) for every slice BEFORE trusting the markdown
    ``Status`` column -- a slice carrying terminal evidence whose ``Status``
    still reads ``pending`` is drift, not a step, and is reported
    ``INDETERMINATE`` naming the disagreement (feature-delta.md [REF]
    Per-slice precondition order); (5) walks the per-slice precondition
    order for the first genuinely pending row.
    """
    delta_path = _feature_delta_path(repo_root, feature_id)
    if not delta_path.is_file():
        return _indeterminate(
            feature_id,
            what=f"no feature-delta.md found for feature {feature_id!r}",
            why=f"expected {delta_path} to exist",
        )
    content = delta_path.read_text(encoding="utf-8")

    bootstrap = classify_bootstrap(content, feature_id)
    if bootstrap is not None:
        if bootstrap.state == "OPEN":
            return NextStep(
                event=_EVENT,
                feature_id=feature_id,
                loop_state="SLICE_IN_PROGRESS",
                slice_id=None,
                phase="DISCUSS",
                step_kind="wave-command",
                what="the feature context is open for DISCUSS.",
                why="the sole bootstrap document contains no delivery or completion evidence.",
                how=f"/nw-discuss --feature-id {feature_id}",
                schema_version=_SCHEMA_VERSION,
            )
        return _indeterminate(
            feature_id,
            what="adopted-wip-regression-evidence-unavailable",
            why="UNKNOWN inventory is provenance only and cannot authorise delivery or commit.",
        )

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

    try:
        records = AtCompletionLedger(feature_id, repo_root).read_records()
    except LedgerIntegrityViolation as exc:
        return _indeterminate(
            feature_id,
            what=(
                f"the AT-completion ledger for feature {feature_id!r} is "
                f"unreadable or malformed ({exc.args[0] if exc.args else 'unknown'})"
            ),
            why=(
                "read_records() raised LedgerIntegrityViolation while "
                f"consulting terminal ledger evidence: {exc}; a corrupt "
                "ledger must degrade LOUD to INDETERMINATE, never a "
                "confident next-step over unreadable evidence (GDP-6)"
            ),
        )

    terminal_slice_ids = frozenset(
        str(record["slice_id"])
        for record in records
        if record.get("event") == SLICE_COMMIT_VERIFIED
    )

    pending_row = _select_row(plan, terminal_slice_ids, slice_id)
    if isinstance(pending_row, _UnresolvableLane):
        return _indeterminate(
            feature_id,
            what=pending_row.what,
            why=pending_row.why,
            how=pending_row.how,
        )
    if isinstance(pending_row, _DriftedSlice):
        return _indeterminate(
            feature_id,
            what=(
                f"slice {pending_row.slice_id} carries a terminal "
                f"{SLICE_COMMIT_VERIFIED} ledger record but the Slice Plan "
                "Status column still reads 'pending'"
            ),
            why=(
                "the AT-completion ledger and the feature-delta.md Slice "
                "Plan disagree on whether this slice is done; "
                "feature-delta.md [REF] Per-slice precondition order "
                "requires this drift be reported, never silently resolved "
                "by trusting either source alone"
            ),
        )
    if pending_row is None:
        return _project_feature_end_branch(
            feature_id, plan, terminal_slice_ids, records
        )

    if isinstance(pending_row, _AssumedRow):
        step = _project_pending_slice(repo_root, feature_id, pending_row.row, records)
        return _state_the_assumption(step, pending_row)

    return _project_pending_slice(repo_root, feature_id, pending_row, records)


_NO_FURTHER_ACTION = "no further action -- the feature is DONE"


def _has_event(records: list[dict[str, Any]], event: str) -> bool:
    """True iff a feature-scoped ledger record with this exact event name
    exists (no ``slice_id`` filter -- feature-end events carry ``slice_id ==
    ""``, unlike the per-slice events ``_has_event_for_slice`` matches)."""
    return any(record.get("event") == event for record in records)


def _project_feature_end_branch(
    feature_id: str,
    plan: SlicePlan,
    terminal_slice_ids: frozenset[str],
    records: list[dict[str, Any]],
) -> NextStep:
    """Project the feature-end branch -- reached when ``_select_row`` finds
    no ``pending`` Slice Plan row (feature-delta.md [REF] Slice Plan
    slice-03).

    Every declared row must ALSO be ledger-confirmed shipped before this
    branch is trusted at all: a Status column that reads anything other than
    ``pending`` (e.g. ``shipped``) for a row the ledger has never sealed with
    a ``SliceCommitVerified`` record is the SAME drift class ``_select_row``'s
    ``_DriftedSlice`` already guards in the opposite direction (ledger ahead
    of the table) -- reported here, in the table-ahead-of-ledger direction,
    rather than silently trusted (GDP-6).

    Grounding correction (finding, not fabrication -- mirrors this same
    module's ADR-028 D6 finding): the DESIGN's AT pin assumed
    ``FeatureEndCycleComplete``/``FeatureEndCycleRefused`` were LEDGER event
    names. They are not -- ``src/des/cli/feature_end.py`` only ever prints
    them as stdout JSON payloads; the ledger only ever receives
    ``EBatchRefactorCompleted`` + ``FeatureEndReviewVerdict`` on success
    (``feature_end_cycle_service.py``), and a ``CycleRefusal`` writes NOTHING
    to the ledger. A refused cycle and a never-run cycle are therefore
    ledger-indistinguishable today; both share the identical correct
    remediation (``des feature-end run``), so folding them into one
    ``FEATURE_END_PENDING`` answer loses no honesty a distinct branch would
    have added -- the alternative (guessing DONE, or reporting INDETERMINATE
    over a legitimately actionable state) is the actual GDP-6 violation this
    branch exists to avoid.
    """
    undelivered = sorted(
        row.slice_id for row in plan.rows if row.slice_id not in terminal_slice_ids
    )
    if undelivered:
        return _indeterminate(
            feature_id,
            what=(
                f"{len(undelivered)} declared Slice Plan row(s) "
                f"({', '.join(undelivered)}) are not 'pending' but carry no "
                f"{SLICE_COMMIT_VERIFIED} ledger record"
            ),
            why=(
                "the Slice Plan Status column and the AT-completion ledger "
                "disagree on whether these slices shipped; feature-delta.md "
                "[REF] Per-slice precondition order requires this drift be "
                "reported, never silently resolved by trusting the markdown "
                "Status column alone"
            ),
        )

    if _has_event(records, EBATCH_REFACTOR_COMPLETED):
        return NextStep(
            event=_EVENT,
            feature_id=feature_id,
            loop_state="DONE",
            slice_id=None,
            phase=None,
            step_kind=None,
            what="every declared slice has shipped and the feature-end cycle completed.",
            why=(
                f"an {EBATCH_REFACTOR_COMPLETED} ledger record exists for "
                "this feature -- the feature-end cycle (batch refactor + "
                "deep review) already ran and recorded its verdict."
            ),
            how=_NO_FURTHER_ACTION,
            schema_version=_SCHEMA_VERSION,
        )

    return NextStep(
        event=_EVENT,
        feature_id=feature_id,
        loop_state="FEATURE_END_PENDING",
        slice_id=None,
        phase=None,
        step_kind="producing-tool",
        what="every declared slice has shipped -- the feature-end cycle has not completed.",
        why=(
            "every declared Slice Plan row carries a "
            f"{SLICE_COMMIT_VERIFIED} ledger record but no "
            f"{EBATCH_REFACTOR_COMPLETED} record exists yet; the feature-end "
            "cycle (walking-skeleton + environmental-e2e gates, then sign + "
            "emit) has not run to completion -- generalizing the F-56 "
            "FeatureEndPending last-slice notice from one transition to this "
            "loop's terminal branch."
        ),
        how=_commit_slice._FEATURE_END_RUN_HOW,
        schema_version=_SCHEMA_VERSION,
    )


def _state_the_assumption(step: NextStep, assumed: _AssumedRow) -> NextStep:
    """Re-issue a projected step with its selection assumption made VISIBLE.

    The assumption goes in ``what`` -- the field a caller reads first and
    sometimes the only one it reads -- so a parallel lane cannot act on the
    step without also seeing that the step assumed it was not parallel. Buried
    in ``why`` it would be technically disclosed and practically silent, which
    is the silent-wrong GDP-6 forbids wearing a disclosure label.
    """
    return dataclasses.replace(
        step,
        what=(
            f"ASSUMING single-lane sequential order -- {step.what} "
            f"(pass --slice slice-NN if this lane works in parallel)"
        ),
        why=(
            f"{step.why} SELECTION: {assumed.candidates} rows are pending and "
            f"no slice was declared, so {assumed.row.slice_id} was chosen by "
            "table position. That is correct for a sequential lane and WRONG "
            "for a parallel worktree, where every slice the lane does not own "
            "stays pending forever because no predecessor is committed there. "
            "The owning lane is a fact only the caller can declare"
        ),
    )


@dataclass(frozen=True)
class _DriftedSlice:
    """A markdown-``pending`` row whose slice already carries terminal
    (``SliceCommitVerified``) ledger evidence -- the ledger-vs-table
    disagreement feature-delta.md [REF] Per-slice precondition order names
    as "drift, not a step".
    """

    slice_id: str


@dataclass(frozen=True)
class _UnresolvableLane:
    """The projection cannot know WHICH slice the caller means.

    Carries the LOUD report (GDP-6) rather than a guessed row: either the
    declared slice does not resolve to a usable Slice-Plan row, or nothing
    was declared while two or more rows compete.
    """

    what: str
    why: str
    how: str = _NO_REMEDIATION


@dataclass(frozen=True)
class _AssumedRow:
    """The first pending row, selected under a STATED assumption.

    Nothing was declared and several rows compete, so table position picked
    this one -- which is right for a sequential lane and wrong for a parallel
    one. The projection still answers (refusing would break ``des next`` as an
    entry point on every fresh multi-slice feature), but the assumption rides
    in ``what``, the field a caller actually reads, never buried in ``why``.
    """

    row: SlicePlanRow
    candidates: int


_Selection = SlicePlanRow | _AssumedRow | _DriftedSlice | _UnresolvableLane | None


def _pending_rows(plan: SlicePlan) -> list[SlicePlanRow]:
    return [row for row in plan.rows if row.status.strip().lower() == _PENDING_STATUS]


def _select_row(
    plan: SlicePlan, terminal_slice_ids: frozenset[str], declared_slice_id: str | None
) -> _Selection:
    """Resolve the ONE row to project, from the caller's DECLARED slice.

    The lane is a declared fact, never an inferred one: the same Slice Plan
    (rows 01-06 all ``pending``) reads as "01 is next" for a single sequential
    lane and as "whatever you own is next" for a worktree delivering 06, and
    the two are indistinguishable in the data. Table position therefore
    cannot select the row, and neither can the current worktree path --
    deciding on that signal would be deciding on an inference (standing rule
    2026-07-23), and it silently misreads the first time a worktree is named
    for anything but its slice.

    With NOTHING declared and two or more rows competing, the projection still
    answers -- ``des next`` is the primary orientation command and a fresh
    7-slice feature has 7 pending rows, so refusing there would break the
    entry point in the commonest case -- but it answers with the ASSUMPTION
    STATED IN ``what`` (single-lane sequential order) and the remedy in the
    same breath. GDP-6 forbids the SILENT wrong, not the stated one: a lane
    that reads "assuming single-lane sequential order" can see the assumption
    does not hold for it, which the bare slice-01 answer never let it do.
    """
    if declared_slice_id is not None:
        return _select_declared_row(plan, terminal_slice_ids, declared_slice_id)

    pending = _pending_rows(plan)
    if not pending:
        return None

    row = pending[0]
    if row.slice_id in terminal_slice_ids:
        return _DriftedSlice(slice_id=row.slice_id)
    return _AssumedRow(row=row, candidates=len(pending)) if len(pending) > 1 else row


def _select_declared_row(
    plan: SlicePlan, terminal_slice_ids: frozenset[str], declared_slice_id: str
) -> _Selection:
    """Resolve the row the caller named -- or report why it cannot be used.

    Every rejection names the DECLARED slice, so the caller can tell which
    declaration was refused; none silently resolves to a different row, which
    would answer about a lane the caller never asked about.
    """
    row = next((row for row in plan.rows if row.slice_id == declared_slice_id), None)
    if row is None:
        known = ", ".join(r.slice_id for r in plan.rows) or "(none)"
        return _UnresolvableLane(
            what=(
                f"the declared slice {declared_slice_id} appears in no Slice Plan row"
            ),
            why=(
                f"the Slice Plan carries {known}; a declared slice that "
                "matches none of them is a caller error, and resolving it to "
                "some other row would answer confidently about a lane the "
                "caller never asked about"
            ),
            how=(
                "declare a slice the Slice Plan carries, or author the missing "
                "row in the feature-delta's `## Wave: DISCUSS / [REF] Slice "
                "Plan` table -- `des feature-delta-schema inject --wave "
                "discuss` emits that canonical heading, and `des "
                "feature-delta-doctor <path>` then reports every remaining "
                "structural gap in one pass"
            ),
        )
    if declared_slice_id in terminal_slice_ids:
        return _DriftedSlice(slice_id=declared_slice_id)
    if row.status.strip().lower() != _PENDING_STATUS:
        return _UnresolvableLane(
            what=(
                f"the declared slice {declared_slice_id} is not pending -- "
                f"its Slice Plan Status reads {row.status.strip()!r}"
            ),
            why=(
                "the per-slice precondition walk projects mid-loop steps for "
                "a pending row only; a non-pending row carrying no terminal "
                "ledger evidence is neither shipped nor in flight, and "
                "guessing which it is would be a confident answer over "
                "unreadable state (GDP-6)"
            ),
        )
    return row


def _project_pending_slice(
    repo_root: Path,
    feature_id: str,
    pending_row: SlicePlanRow,
    records: list[dict[str, Any]],
) -> NextStep:
    """Walk the per-slice precondition order for a row already confirmed
    genuinely pending (``_select_row`` has already ruled out terminal-
    evidence drift for this row's slice -- reaching the end of this walk
    means RedObserved, ATReviewVerdict, and an ExamineVerdict are ALL
    recorded with no SliceCommitVerified yet: purely mechanical, never a
    raw ``NotImplementedError`` traceback).
    """
    slice_id = pending_row.slice_id

    if not _has_event_for_slice(
        records, _RED_OBSERVED_EVENT, slice_id
    ) and not _mechanical_seal_clears_red(repo_root, pending_row):
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

    if not _has_approved_review_verdict_for_slice(records, slice_id):
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

    return _producing_tool_step(
        feature_id=feature_id,
        slice_id=slice_id,
        phase=ATDDPurePhase.D_REFACTOR_COMMIT,
        what=(
            f"slice {slice_id} is EXAMINE-verified but not yet committed "
            "(no SliceCommitVerified ledger record)."
        ),
        why=(
            "RedObserved, ATReviewVerdict, and an ExamineVerdict are all "
            "recorded for this slice with nothing left to author; the "
            "remaining step is purely mechanical (feature-delta.md [REF] "
            "Per-slice precondition order)."
        ),
        how=(
            f"des commit-slice --repo {repo_root} --feature-id {feature_id} "
            f'--slice-id {slice_id} --message "<commit message>" --all'
        ),
    )


def _mechanical_seal_clears_red(repo_root: Path, pending_row: SlicePlanRow) -> bool:
    """True when the pending row's mechanical RED seal satisfies precondition-1
    (the ``RedObserved`` requirement) WITHOUT a ledger record.

    Reuses ``carpaccio_slice_gate._mechanical_seal_satisfied`` -- the EXACT
    predicate the DELIVER-entry carpaccio gate (``check_at_review``) and the
    G-DISTILL-EXIT hook (``subagent_stop_handler._mechanical_seal_cleared_
    slices``) already trust -- never a parallel re-derivation of the same
    fact (SSOT). Fail-closed on every degraded input: no ``@regression-test-
    file:`` annotation token, or the seal itself absent/stale/unwitnessed,
    both resolve to ``False`` (still route to ``/nw-distill``), matching the
    mechanical-seal route's existing fail-closed semantics.
    """
    match = REGRESSION_TEST_FILE_ANNOTATION_RE.search(pending_row.annotation)
    if match is None:
        return False
    regression_test_file = repo_root / match.group(1)
    return carpaccio_slice_gate._mechanical_seal_satisfied(
        repo_root, regression_test_file
    )


def _has_event_for_slice(
    records: list[dict[str, Any]], event: str, slice_id: str
) -> bool:
    return any(
        record.get("event") == event and record.get("slice_id") == slice_id
        for record in records
    )


def _has_approved_review_verdict_for_slice(
    records: list[dict[str, Any]], slice_id: str
) -> bool:
    """True iff an APPROVED `ATReviewVerdict` record exists for `slice_id`.

    D04b consumer sweep (declared-facts-reachable-recorded slice-01's DD-1
    follow-up, mirrors D04a's `AtCompletionLedger.review_verdict_slices()`
    finding in a second, independent consumer): before DD-1 (commit
    0303ecea5) only an APPROVED verdict ever wrote an `ATReviewVerdict`
    record, so presence-only (`_has_event_for_slice`) was equivalent to
    APPROVED. DD-1 made NEEDS_REVISION also write a record, silently
    widening presence-only to include rejected slices -- exactly the branch
    below's own docstring already claimed ("APPROVED ATReviewVerdict") while
    the implementation checked presence only. A `NEEDS_REVISION` record must
    NOT satisfy this predicate.
    """
    return any(
        record.get("event") == _AT_REVIEW_VERDICT_EVENT
        and record.get("slice_id") == slice_id
        and record.get("verdict") == "APPROVED"
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


def _producing_tool_step(
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
        step_kind="producing-tool",
        what=what,
        why=why,
        how=how,
        schema_version=_SCHEMA_VERSION,
    )


def _indeterminate(
    feature_id: str, *, what: str, why: str, how: str = _NO_REMEDIATION
) -> NextStep:
    return NextStep(
        event=_EVENT,
        feature_id=feature_id,
        loop_state="INDETERMINATE",
        slice_id=None,
        phase=None,
        step_kind=None,
        what=what,
        why=why,
        how=how,
        schema_version=_SCHEMA_VERSION,
    )
