"""des.domain.conversion_planner -- pure classic->atdd_pure conversion planner.

Feature `classic-spine-decommission`, slice-05. The conversion of a classic
feature onto the atdd_pure spine is split into two halves:

  * `dry_run(...)` -- a PURE planner. It reads the feature's recovered slice
    plan and roadmap, reconciles each slice's status, and returns an immutable
    `ConversionPlan` describing the side effects a conversion WOULD apply. It
    never mutates anything (contract shape: unbounded-preservation -- the
    v3.15.1 dry-run-wrote-to-disk bug class is structurally impossible because
    the planner has no write port).

  * `execute(plan, fs)` -- the single impure path. It applies the plan's four
    journalled side-effect steps through a write-scoped `SafeFileSystem`:
    promote the slice-plan heading, seed the AT-completion ledger, flip the
    workflow mode, archive the classic roadmap artifacts.

The N:1 roadmap-step->slice cardinality rule lives in `dry_run`: a slice is
reconciled `shipped` only when ALL its constituent roadmap steps reached
COMMIT/PASS with a green-verdict SHA; otherwise it is `pending` and the
committed constituent SHAs are recorded as provenance.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from des.domain.feature_classifier import SLICE_PLAN_HEADING


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.at_completion_ledger_port import LedgerFactoryPort
    from des.ports.driven_ports.safe_file_system import SafeFileSystem


# A re-verification callable: maps a committed-step SHA to its re-verified
# verdict string (`green` / `reverted` / `absent` / `tests_red`). The pure
# planner depends on this driven-port-shaped callable, not on git directly --
# `GitHistoryProbe.verify_sha` is the production implementation.
ShaVerifier = Callable[[str], str]


# The DISCUSS Slice Plan heading is owned by `feature_classifier`
# (SLICE_PLAN_HEADING) -- the converter promotes to exactly the string the
# classifier later detects, so there is one definition, not two that can drift.
_RECOMMENDED_HEADING = "[REF] Recommended Slice Plan"


class ConversionOutcome(str, Enum):
    """The user-observable outcome of one `des-convert-to-atdd-pure` run.

    CONVERTED        -- the feature is now on the atdd_pure spine.
    BLOCKED_TAGGING  -- a drained feature's `.feature` scenarios carry no
                        ``@slice-NN`` tag -- it is parked, returned to DISTILL.
    BLOCKED_MANUAL   -- a drained feature's classic artifacts are malformed
                        (``classic-needs-manual-review``) -- it is parked
                        pending human attention.
    REFUSED_STALE    -- the feature dir changed since classification (M7
                        ``git_state`` mismatch) -- the converter refuses the
                        stale manifest row before any side effect.
    REFUSED_READONLY -- the feature dir is not writable; the converter refuses
                        cleanly (C7a) before any journalled side effect,
                        leaving the classic artifacts intact.
    ROLLED_BACK      -- a `--rollback` run un-did a partial conversion.
    """

    CONVERTED = "converted"
    BLOCKED_TAGGING = "blocked-needs-distill-tagging"
    BLOCKED_MANUAL = "blocked-needs-manual-review"
    REFUSED_STALE = "refused-stale-manifest"
    REFUSED_READONLY = "refused-read-only-feature-dir"
    ROLLED_BACK = "rolled-back"


@dataclass(frozen=True)
class PlannedSlice:
    """One slice row of a `ConversionPlan` -- its reconciled status + provenance."""

    slice_id: str
    status: str
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversionPlan:
    """An immutable description of the side effects a conversion would apply.

    Returned by the pure `dry_run`; consumed by the impure `execute`. A
    `ConversionPlan` writes nothing -- it is a value, not an action.
    """

    feature_id: str
    slices: tuple[PlannedSlice, ...] = ()
    promoted_heading: str = SLICE_PLAN_HEADING
    workflow_mode: str = "atdd_pure"
    blocker: str | None = None
    derived_from_roadmap: bool = False
    feature_delta_text: str = ""
    archive_artifacts: tuple[str, ...] = ()


def dedup_committed_steps(
    step_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Collapse a roadmap's `steps` list into one record per step id (S6).

    An entry-gate restart re-runs a step and re-logs its COMMIT/PASS, so the
    roadmap can carry the same step twice. Two entries for one step that agree
    on their `sha` are an idempotent re-commit -- they collapse to a single
    record so the slice's COMMIT/PASS count is exact, never doubled. If the
    duplicate entries disagree on `sha` the re-commit is NOT idempotent: the
    later record's `committed` flag is cleared so the slice cannot ship on an
    ambiguous history (a divergent retry is treated as not-yet-committed).
    """
    deduped: dict[str, dict[str, Any]] = {}
    for record in step_records:
        step_id = str(record["step_id"])
        previous = deduped.get(step_id)
        if previous is None:
            deduped[step_id] = dict(record)
            continue
        if str(previous.get("sha", "")) != str(record.get("sha", "")):
            deduped[step_id] = {**dict(record), "committed": False}
    return deduped


def dry_run(
    feature_id: str,
    feature_delta_text: str,
    roadmap_steps: dict[str, dict[str, Any]],
    slice_map: dict[str, tuple[str, ...]],
    verify_sha: ShaVerifier,
    untagged: bool = False,
) -> ConversionPlan:
    """Plan the conversion of one classic feature -- pure, never mutates.

    ``roadmap_steps`` maps a roadmap step id to a record carrying its
    ``committed`` flag and its ``sha``. ``slice_map`` maps a slice id to the
    tuple of roadmap step ids that constitute it. ``verify_sha`` re-verifies a
    committed SHA against git history (M2) -- the planner NEVER trusts a
    logged ``sha_verdict``; a COMMIT/PASS log entry is a claim, not proof.

    Each slice is reconciled `shipped` iff ALL constituent steps reached
    COMMIT/PASS AND each SHA re-verifies ``green`` NOW; otherwise `pending`,
    recording the committed constituent SHAs as provenance.

    ``untagged`` is the single-feature-path equivalent of the ``--drain``
    tagging check (D2-Step-3): the CLI reads the feature's ``.feature`` files
    from the filesystem and passes ``True`` when an acceptance scenario carries
    no ``@slice-NN`` tag. The planner itself stays pure -- it only stamps the
    ``BLOCKED_TAGGING`` blocker on the plan; the execute path honours it.
    """
    promoted_text, derived = _promote_heading(feature_delta_text)
    effective_slices = _recover_slice_map(roadmap_steps, slice_map)
    planned = tuple(
        _reconcile_slice(slice_id, step_ids, roadmap_steps, verify_sha)
        for slice_id, step_ids in effective_slices
    )
    return ConversionPlan(
        feature_id=feature_id,
        slices=planned,
        blocker=ConversionOutcome.BLOCKED_TAGGING.value if untagged else None,
        derived_from_roadmap=derived,
        feature_delta_text=promoted_text,
        archive_artifacts=("roadmap.json", "execution-log.json"),
    )


def _recover_slice_map(
    roadmap_steps: dict[str, dict[str, Any]],
    slice_map: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Recover the full slice plan -- explicit slices plus a row per orphan step.

    The classic roadmap's ``slices`` mapping is only ever fully populated for
    the slices DELIVER has already worked. A 12-step roadmap whose ``slices``
    map names only ``slice-01`` still implies the eleven remaining slices: the
    worked conversion must reconcile EVERY roadmap step, not just the mapped
    ones. Each roadmap step ``NN-MM`` that no explicit slice claims is recovered
    as its own ``slice-NN`` row (a step's phase number is its slice id) so the
    converted feature carries a plan row for slice-02..slice-N as ``pending``.

    Explicit slice_map entries are preserved verbatim and ordered first; the
    recovered orphan slices follow in roadmap order, de-duplicated by id.
    """
    claimed = {step_id for step_ids in slice_map.values() for step_id in step_ids}
    recovered: dict[str, list[str]] = {}
    for step_id in roadmap_steps:
        if step_id in claimed:
            continue
        slice_id = f"slice-{step_id.split('-', 1)[0]}"
        recovered.setdefault(slice_id, []).append(step_id)
    explicit = tuple(slice_map.items())
    explicit_ids = {slice_id for slice_id, _ in explicit}
    orphans = tuple(
        (slice_id, tuple(step_ids))
        for slice_id, step_ids in recovered.items()
        if slice_id not in explicit_ids
    )
    return explicit + orphans


def _reconcile_slice(
    slice_id: str,
    step_ids: tuple[str, ...],
    roadmap_steps: dict[str, dict[str, Any]],
    verify_sha: ShaVerifier,
) -> PlannedSlice:
    """Reconcile one slice's status against its constituent roadmap steps.

    Every committed step's SHA is RE-VERIFIED against git history (M2) -- the
    logged ``sha_verdict`` is never trusted. A slice ships only when every
    constituent step is committed AND its SHA re-verifies ``green`` now.
    """
    committed_shas: list[str] = []
    all_green = bool(step_ids)
    for step_id in step_ids:
        step = roadmap_steps.get(step_id, {})
        sha = str(step.get("sha", ""))
        if step.get("committed") and sha:
            committed_shas.append(sha)
            if verify_sha(sha) != "green":
                all_green = False
            continue
        all_green = False
    status = "shipped" if all_green else "pending"
    return PlannedSlice(
        slice_id=slice_id,
        status=status,
        provenance=tuple(committed_shas),
    )


def _promote_heading(feature_delta_text: str) -> tuple[str, bool]:
    """Promote the DESIGN ``[REF] Recommended Slice Plan`` heading.

    Conversion procedure Step 1 (slice-plan recovery): the DESIGN wave records
    a ``[REF] Recommended Slice Plan`` heading; conversion promotes it to the
    canonical ``## Wave: DISCUSS / [REF] Slice Plan`` heading the carpaccio
    gate reads. Returns the promoted text and whether a promotion happened.
    """
    if SLICE_PLAN_HEADING in feature_delta_text:
        return feature_delta_text, False
    lines = feature_delta_text.splitlines()
    promoted: list[str] = []
    did_promote = False
    for line in lines:
        if not did_promote and _RECOMMENDED_HEADING in line and line.startswith("#"):
            promoted.append(SLICE_PLAN_HEADING)
            did_promote = True
            continue
        promoted.append(line)
    text = "\n".join(promoted)
    if did_promote and not text.endswith("\n"):
        text += "\n"
    return text, did_promote


class ConversionInterrupted(Exception):
    """Raised by `execute` when an `abort_after` hook fires mid-conversion (S16).

    Models a process kill / crash after a journalled side-effect step but
    before the next: the journal is left partial on disk, and the next
    `execute` run resumes from it. Test-armed via the converter CLI's
    ``DES_CONVERT_ABORT_AFTER`` env hook -- production runs never set it.
    """


def execute(
    plan: ConversionPlan,
    feature_dir: Path,
    config_path: Path,
    journal_dir: Path,
    ledger_root: Path,
    fs: SafeFileSystem,
    ledger_factory: LedgerFactoryPort,
    abort_after: str | None = None,
) -> tuple[str, ...]:
    """Apply a `ConversionPlan`'s four journalled side-effect steps (M3).

    Each step is journalled to ``.nwave/conversion-journal/{feature_id}.json``
    BEFORE the next begins, together with a backup of whatever it overwrote --
    so an interrupted conversion resumes from the journal and a ``--rollback``
    restores the classic artifacts from it. Returns the completed journal steps.

    Idempotent (C4): a re-run reads the existing journal and resumes from the
    last completed step -- it never infers progress from heading presence.
    Converting an already-converted feature replays no side effect and leaves
    the journal byte-for-byte unchanged.

    ``abort_after`` names a journalled step after which `execute` raises
    `ConversionInterrupted` (S16 partial-failure injection) -- the journal is
    left partial, never half-applied. Production conversions pass ``None``.

    ``ledger_root`` is the project root the seeded AT-completion ledger is
    rooted at (``.nwave/telemetry/atdd-pure/`` lives beneath it) -- separate
    from ``feature_dir`` because the carpaccio entry gate reads the ledger at
    a workspace-relative path, not inside the feature directory.

    ``ledger_factory`` is the injected `LedgerFactoryPort` the ledger-seeding
    step uses to build the per-feature ledger (AD-02 DIP fix) -- the domain
    depends only on the abstraction and never constructs the concrete adapter.
    """
    fs.make_dir(journal_dir)
    journal, backups = _resume_journal(fs, journal_dir, plan.feature_id)

    if "promote-slice-plan-heading" not in journal:
        delta_path = feature_dir / "feature-delta.md"
        backups["promote-slice-plan-heading"] = {
            "feature-delta.md": fs.read_text(delta_path)
            if fs.exists(delta_path)
            else None
        }
        fs.write_text(delta_path, plan.feature_delta_text)
        _journal(fs, journal_dir, plan, journal, backups, "promote-slice-plan-heading")
    _abort_if_armed(abort_after, "promote-slice-plan-heading")

    if "seed-at-completion-ledger" not in journal:
        _seed_ledger(plan, ledger_root, ledger_factory)
        _journal(fs, journal_dir, plan, journal, backups, "seed-at-completion-ledger")
    _abort_if_armed(abort_after, "seed-at-completion-ledger")

    if "flip-workflow-mode" not in journal:
        backups["flip-workflow-mode"] = {
            "config.yaml": fs.read_text(config_path) if fs.exists(config_path) else None
        }
        _flip_config(config_path, fs)
        _journal(fs, journal_dir, plan, journal, backups, "flip-workflow-mode")
    _abort_if_armed(abort_after, "flip-workflow-mode")

    if "archive-roadmap" not in journal:
        _archive_roadmap(plan, feature_dir, fs)
        _journal(fs, journal_dir, plan, journal, backups, "archive-roadmap")
    _abort_if_armed(abort_after, "archive-roadmap")

    return tuple(journal)


def _abort_if_armed(abort_after: str | None, just_completed: str) -> None:
    """Raise `ConversionInterrupted` if the abort hook is armed at this step."""
    if abort_after == just_completed:
        raise ConversionInterrupted(
            f"conversion aborted after {just_completed} (S16 injection)"
        )


def rollback(
    feature_id: str,
    feature_dir: Path,
    config_path: Path,
    journal_dir: Path,
    ledger_root: Path,
    fs: SafeFileSystem,
) -> tuple[str, ...]:
    """Undo a partial (or complete) conversion from its journal (C4b / M3).

    Replays every journalled side-effect step in INVERSE order, restoring the
    pre-conversion classic artifacts from the backups the journal recorded:

      * archive-roadmap        -- move the archived artifacts back to ``deliver/``
      * flip-workflow-mode     -- restore the pre-conversion ``config.yaml``
      * seed-at-completion-ledger -- delete the seeded AT-completion ledger
      * promote-slice-plan-heading -- restore the pre-conversion feature delta

    Finally deletes the journal so the feature is unambiguously back on the
    classic spine -- never left in a half-converted limbo. Returns the tuple
    of undone steps (inverse-order).
    """
    fs.make_dir(journal_dir)
    journal, backups = _resume_journal(fs, journal_dir, feature_id)
    context = _RollbackContext(
        feature_id=feature_id,
        feature_dir=feature_dir,
        config_path=config_path,
        ledger_root=ledger_root,
        backups=backups,
        fs=fs,
    )
    undone: list[str] = []
    for step in reversed(journal):
        _UNDO_STEPS[step](context)
        undone.append(step)
    journal_path = journal_dir / f"{feature_id}.json"
    if fs.exists(journal_path):
        fs.delete(journal_path)
    return tuple(undone)


@dataclass(frozen=True)
class _RollbackContext:
    """The inputs one `--rollback` inverse op needs to undo a journalled step."""

    feature_id: str
    feature_dir: Path
    config_path: Path
    ledger_root: Path
    backups: dict[str, Any]
    fs: SafeFileSystem


def _undo_archive_roadmap(context: _RollbackContext) -> None:
    """Move the archived classic roadmap artifacts back to ``deliver/``."""
    deliver = context.feature_dir / "deliver"
    archive = deliver / ".classic-archive"
    for artifact in ("roadmap.json", "execution-log.json"):
        archived = archive / artifact
        if context.fs.exists(archived):
            context.fs.move(archived, deliver / artifact)


def _undo_flip_config(context: _RollbackContext) -> None:
    """Restore the pre-conversion ``.nwave/config.yaml`` from the journal backup."""
    original = context.backups.get("flip-workflow-mode", {}).get("config.yaml")
    if original is not None:
        context.fs.write_text(context.config_path, original)


def _undo_seed_ledger(context: _RollbackContext) -> None:
    """Delete the AT-completion ledger seeded by the conversion."""
    ledger_path = (
        context.ledger_root
        / ".nwave"
        / "telemetry"
        / "atdd-pure"
        / f"{context.feature_id}.jsonl"
    )
    if context.fs.exists(ledger_path):
        context.fs.delete(ledger_path)


def _undo_promote_heading(context: _RollbackContext) -> None:
    """Restore the pre-conversion ``feature-delta.md`` from the journal backup."""
    original = context.backups.get("promote-slice-plan-heading", {}).get(
        "feature-delta.md"
    )
    if original is not None:
        context.fs.write_text(context.feature_dir / "feature-delta.md", original)


# Inverse-op dispatch table -- one undo per journalled side-effect step (M3).
_UNDO_STEPS: dict[str, Any] = {
    "archive-roadmap": _undo_archive_roadmap,
    "flip-workflow-mode": _undo_flip_config,
    "seed-at-completion-ledger": _undo_seed_ledger,
    "promote-slice-plan-heading": _undo_promote_heading,
}


def _resume_journal(
    fs: SafeFileSystem, journal_dir: Path, feature_id: str
) -> tuple[list[str], dict[str, Any]]:
    """Read the completed side-effect steps + their backups from the journal.

    Returns ``([], {})`` when no journal exists (a first run); the recorded
    steps and per-step backups when a prior run -- possibly interrupted --
    left a journal behind. The caller skips every step already present, so a
    re-run resumes rather than restarts (C4 idempotency / S16 resume); the
    backups feed `rollback`'s inverse ops (C4b).
    """
    journal_path = journal_dir / f"{feature_id}.json"
    if not fs.exists(journal_path):
        return [], {}
    parsed = json.loads(fs.read_text(journal_path))
    steps = [str(step) for step in parsed.get("steps", [])]
    backups = dict(parsed.get("backups", {}))
    return steps, backups


def _seed_ledger(
    plan: ConversionPlan,
    ledger_root: Path,
    ledger_factory: LedgerFactoryPort,
) -> None:
    """Seed the AT-completion ledger through the M7 API for every shipped slice.

    The M7 ledger write API is used directly -- a hand-written JSONL would
    carry neither `seq` nor `record_hash` (re-implementing it IS F-13). AD-02
    DIP fix: the ledger writer is built through the injected `ledger_factory`
    port, so the domain depends only on the abstraction (never on the concrete
    `AtCompletionLedger` adapter).
    """
    ledger = ledger_factory.create_for_seeding(
        feature_id=plan.feature_id, project_root=ledger_root
    )
    for planned in plan.slices:
        if planned.status == "shipped":
            ledger.append_gate_event(
                event="CarpaccioGateCleared", slice_id=planned.slice_id
            )


def _flip_config(config_path: Path, fs: SafeFileSystem) -> str:
    """Flip ``workflow.mode`` to ``atdd_pure`` in ``.nwave/config.yaml``.

    Conversion procedure Step 5 (config flip). Reads the existing config,
    rewrites the ``workflow.mode`` value (or appends a ``workflow`` block when
    absent), and writes it back through the scoped filesystem.
    """
    existing = fs.read_text(config_path) if fs.exists(config_path) else ""
    flipped = _rewrite_workflow_mode(existing)
    fs.write_text(config_path, flipped)
    return flipped


def _rewrite_workflow_mode(config_text: str) -> str:
    """Set ``workflow.mode: atdd_pure`` in a config text -- stdlib line-scan.

    Honours the two-level block-mapping shape ``.nwave/config.yaml`` carries.
    Rewrites an existing ``mode:`` under a ``workflow:`` block, or appends a
    fresh ``workflow`` block when the key is absent.
    """
    lines = config_text.splitlines()
    out: list[str] = []
    in_workflow = False
    rewrote = False
    for raw in lines:
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if indent == 0 and stripped:
            in_workflow = stripped.rstrip(":") == "workflow" and stripped.endswith(":")
        if in_workflow and indent > 0 and stripped.startswith("mode:"):
            out.append(f"{' ' * indent}mode: atdd_pure")
            rewrote = True
            continue
        out.append(raw)
    if not rewrote:
        if out and out[-1].strip():
            out.append("")
        out.append("workflow:")
        out.append("  mode: atdd_pure")
    text = "\n".join(out)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _archive_roadmap(
    plan: ConversionPlan, feature_dir: Path, fs: SafeFileSystem
) -> None:
    """Move the classic roadmap artifacts under ``.classic-archive/``.

    Conversion procedure: a converted feature keeps its classic roadmap +
    execution log for audit, archived under ``deliver/.classic-archive/`` so
    the live feature dir is unambiguously on the atdd_pure spine.
    """
    deliver = feature_dir / "deliver"
    archive = deliver / ".classic-archive"
    fs.make_dir(archive)
    for artifact in plan.archive_artifacts:
        source = deliver / artifact
        if fs.exists(source):
            fs.move(source, archive / artifact)


def _journal(
    fs: SafeFileSystem,
    journal_dir: Path,
    plan: ConversionPlan,
    completed: list[str],
    backups: dict[str, Any],
    step: str,
) -> None:
    """Record one completed side-effect step + its backups in the journal (M3).

    The backup of whatever the step overwrote is persisted alongside the step
    name so a ``--rollback`` can restore the classic artifacts from the
    journal without re-deriving the pre-conversion state.
    """
    completed.append(step)
    fs.write_text(
        journal_dir / f"{plan.feature_id}.json",
        json.dumps(
            {
                "feature_id": plan.feature_id,
                "steps": completed,
                "backups": backups,
            },
            indent=2,
        )
        + "\n",
    )
