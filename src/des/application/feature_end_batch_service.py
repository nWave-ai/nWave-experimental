"""Batched feature-end via a shared use-case + full-suite hoist.

many-features-close-for-one-full-suite slice-01 (the walking skeleton --
feature-delta Slice Plan row slice-01, Locked Decisions D-1/D-3,
ADR-FEATURE-END-BATCH-001-shared-use-case-full-suite-hoist.md).

DDD-7 sibling module (D-D3, Decisions Table): houses the batch-orchestration
concern -- manifest parsing (structural validation only, GDP-1), running the
whole-tree full-suite leg EXACTLY ONCE per batch, and fanning out each
member's own cycle -- kept separate from `feature_end_cycle_service.py`
(already 1875 lines) rather than growing that file further.

REUSE, not rebuild (D-D2): `_run_full_suite_leg` (UNCHANGED) and
`_run_feature_end_member_cycle` (the many-features-close-for-one-full-suite
@prefactoring extraction) are the SAME functions `run_feature_end_cycle`
itself now delegates to -- the single-feature path and the batch path
exercise IDENTICAL machinery, closing the single/batch divergence risk by
construction (ADR-FEATURE-END-BATCH-001).

D-2 (locked): this module reads ONLY in-process function results (the shared
leg's return value) and manifest JSON -- it never calls a `GitWorktreePort`
or reads/mutates worktree state. No driven port is added by this feature.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.application import feature_end_cycle_service as _fecs
from des.cli.verify_deliver_integrity import _undelivered_slice_plan_slices


if TYPE_CHECKING:
    # Annotation-only since 2026-08-06: the runtime `isinstance` checks that
    # needed these at import time belonged to the shared full-suite leg, which
    # this module no longer runs.
    from des.application.feature_end_cycle_service import (
        CycleIndeterminate,
        CycleRefusal,
        CycleSuccess,
    )


# Module-qualified access (never `from ... import _run_full_suite_leg` /
# `_run_feature_end_member_cycle` directly): several EXISTING tests
# monkeypatch `feature_end_cycle_service._run_full_suite_leg` (the module
# ATTRIBUTE) to stub the shared leg. A name-bound-at-import-time copy would
# keep calling the REAL function regardless of that monkeypatch -- looking
# these up through `_fecs.<name>` at CALL time honours the stub exactly like
# every sibling leg-stub in this bounded context already relies on.


@dataclass(frozen=True)
class FeatureEndBatchSpec:
    """One manifest entry -- the batch-shaped restatement of the 4 keyword
    arguments `run_feature_end_cycle` already takes today (D-D3)."""

    feature_id: str
    feature_dir: Path
    reviewer_agent_id: str | None
    verdict: str | None


@dataclass(frozen=True)
class BatchManifestRefused:
    """The manifest failed STRUCTURAL validation ONLY (shape/type/duplicate-id,
    D-D7/D-D8) -- raised BEFORE the shared full-suite leg is spent (GDP-1).

    Deliberately does NOT check feature *readiness* (SliceCommitVerified /
    deep-review / charter state) -- that is slice-02's eligibility precheck,
    out of scope here (keeps the carpaccio boundary honest).
    """

    error: str


@dataclass(frozen=True)
class BatchRefused:
    """The batch's shared full-suite leg went RED; the WHOLE batch refuses
    (D-4, D-D5). ZERO member cycles run, ZERO FeatureEnd records emitted for
    ANY feature -- never bisected, never a silent partial emit.

    Carries the SAME JUnit-enrichment `_run_full_suite_leg` already gives the
    single-feature refusal (`failing_tests`/`failing_count`/`junit_artifact`
    via `_full_suite_failure_refusal`, reused verbatim), batch-scoped.
    """

    error: str
    failing_tests: tuple[str, ...] | None = None
    failing_count: int | None = None
    junit_artifact: str | None = None


@dataclass(frozen=True)
class BatchIndeterminate:
    """The batch's shared full-suite leg is INDETERMINATE (DDD-CERT-2/3): a
    real, runnable suite this leg did not observe. ZERO member cycles run --
    the same fail-closed guarantee as :class:`BatchRefused`."""

    reason: str


@dataclass(frozen=True)
class BatchIneligible:
    """A batch member failed the D-5 batch-eligibility precheck, evaluated at
    RUN START -- BEFORE the shared full-suite leg is spent (GDP-1). Names the
    ineligible ``feature_id`` and WHAT/WHY/HOW the failed check names (GDP-3).

    ZERO gates dispatched, ZERO member cycles run, ZERO FeatureEnd records
    emitted for ANY feature in the batch when any member is ineligible (D-5
    locked) -- never a silent partial emit for the eligible subset.
    """

    feature_id: str
    error: str


@dataclass(frozen=True)
class BatchCompleted:
    """The shared full-suite leg PASSED or was NOT_APPLICABLE; every member
    ran its OWN cycle independently (D-3, D-D6).

    ``members`` is a tuple of ``(feature_id, CycleSuccess | CycleRefusal |
    CycleIndeterminate)`` in MANIFEST ORDER -- the EXISTING per-member outcome
    vocabulary, unchanged, reused verbatim per member. One member's own
    refusal never suppresses or merges into another member's outcome.
    """

    members: tuple[tuple[str, CycleSuccess | CycleIndeterminate | CycleRefusal], ...]


_REQUIRED_KEYS = ("feature_id", "feature_dir", "reviewer_agent_id", "verdict")


def parse_batch_manifest(
    manifest_path: Path,
) -> list[FeatureEndBatchSpec] | BatchManifestRefused:
    """Parse + structurally validate a `run-batch` manifest (D-D7/D-D8, GDP-1).

    Structural validation ONLY -- shape/type/duplicate-id. Never checks
    feature readiness (slice-02's concern). A malformed manifest is refused
    BEFORE the (expensive) shared full-suite leg is ever spent, naming WHAT
    is wrong, WHY, and HOW to fix it (GDP-3).
    """
    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        return BatchManifestRefused(
            f"cannot read manifest {str(manifest_path)!r}: {exc} -- WHAT: the "
            "manifest file could not be opened; WHY: it is missing or "
            "unreadable; HOW: pass a path to an existing, readable JSON "
            "manifest file."
        )
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return BatchManifestRefused(
            f"manifest {str(manifest_path)!r} is not valid JSON: {exc} -- "
            "WHAT: the manifest failed to parse; WHY: malformed JSON syntax; "
            "HOW: fix the JSON syntax error the message names and re-run."
        )
    if not isinstance(payload, list) or not payload:
        got = "an empty array" if isinstance(payload, list) else type(payload).__name__
        return BatchManifestRefused(
            f"manifest {str(manifest_path)!r} must be a non-empty JSON array "
            f"of feature entries -- WHAT: the manifest's top-level shape is "
            f"wrong (got {got}); WHY: run-batch needs >=1 feature entry to "
            "batch; HOW: supply a JSON array with at least one "
            "{feature_id, feature_dir, reviewer_agent_id, verdict} object."
        )

    specs: list[FeatureEndBatchSpec] = []
    seen_feature_ids: dict[str, int] = {}
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            return BatchManifestRefused(
                f"manifest entry #{index} is not a JSON object -- WHAT: entry "
                f"#{index} has shape {type(entry).__name__}; WHY: every "
                "manifest entry must be an object with feature_id/"
                "feature_dir/reviewer_agent_id/verdict; HOW: fix entry "
                f"#{index} to be a JSON object with those 4 keys."
            )
        missing = [key for key in _REQUIRED_KEYS if key not in entry]
        if missing:
            named = entry.get("feature_id", f"entry #{index}")
            return BatchManifestRefused(
                f"manifest entry #{index} ({named!r}) is missing required "
                f"field(s) {missing} -- WHAT: entry #{index} does not carry "
                "every required key; WHY: run-batch needs feature_id, "
                "feature_dir, reviewer_agent_id, and verdict on EVERY "
                f"entry; HOW: add {missing} to entry #{index} ({named!r}) "
                "in the manifest."
            )
        non_string = [key for key in _REQUIRED_KEYS if not isinstance(entry[key], str)]
        if non_string:
            named = entry.get("feature_id", f"entry #{index}")
            return BatchManifestRefused(
                f"manifest entry #{index} ({named!r}) has non-string "
                f"value(s) for {non_string} -- WHAT: entry #{index}'s field "
                f"types are wrong; WHY: every field must be a string; HOW: "
                f"fix {non_string} on entry #{index} ({named!r}) to be "
                "strings."
            )
        feature_id = entry["feature_id"]
        if feature_id in seen_feature_ids:
            first_index = seen_feature_ids[feature_id]
            return BatchManifestRefused(
                f"manifest has a duplicate feature_id {feature_id!r} at "
                f"entries #{first_index} and #{index} -- WHAT: the same "
                "feature_id appears twice; WHY: two entries could carry two "
                "different verdicts for the same feature, an unreported "
                "ambiguity; HOW: remove or merge the duplicate entry for "
                f"{feature_id!r} (entries #{first_index}, #{index})."
            )
        seen_feature_ids[feature_id] = index
        specs.append(
            FeatureEndBatchSpec(
                feature_id=feature_id,
                feature_dir=Path(entry["feature_dir"]),
                reviewer_agent_id=entry["reviewer_agent_id"],
                verdict=entry["verdict"],
            )
        )
    return specs


def _batch_artifact_key(feature_ids: list[str]) -> str:
    """The deterministic, git-free key threaded through `_run_full_suite_leg`'s
    existing `feature_id` parameter (D-D4) -- whose only role is naming the
    persisted JUnit XML artifact.

    A batch of exactly ONE feature reuses the real `feature_id` verbatim
    (D-1: byte-identical on-disk artifact naming to the pre-batching
    single-feature invocation). A genuine batch (>=2 features) synthesizes a
    short hash of the SORTED feature-id set -- deterministic, no commit-sha
    dependency (D-2: git-free).
    """
    if len(feature_ids) == 1:
        return feature_ids[0]
    ids = sorted(feature_ids)
    digest = hashlib.sha256(",".join(ids).encode("utf-8")).hexdigest()[:12]
    return f"_batch-{digest}"


def _check_slice_commit_verified(
    repo_root: Path, spec: FeatureEndBatchSpec
) -> BatchIneligible | None:
    """D-5 check 1 (HOISTED from the existing per-member truncation oracle,
    `[REF] Design Discovery (slice-02)`): every Slice-Plan slice must carry a
    `SliceCommitVerified` attestation.

    Error text carries both the D-5/slice-02 vocabulary (SliceCommitVerified,
    undelivered) AND the pre-existing "TRUNCATED" vocabulary the per-member
    truncation oracle's own refusal used
    (`test_feature_end_cycle_truncation_refusal.py`, root-fix-truncated-
    feature-refused) -- this precheck now answers that SAME scenario earlier
    (also for a batch-of-one via `run_feature_end_cycle`), so it preserves
    the existing contract's asserted substrings rather than diverging from
    it.
    """
    undelivered = _undelivered_slice_plan_slices(repo_root, spec.feature_id)
    if not undelivered:
        return None
    return BatchIneligible(
        feature_id=spec.feature_id,
        error=(
            f"batch-eligibility precheck (D-5) refuses {spec.feature_id!r}: "
            f"WHAT: its Slice-Plan declares {sorted(undelivered)} with no "
            "SliceCommitVerified attestation on the AT-completion ledger -- "
            "the feature is TRUNCATED (undelivered slice(s)); WHY: D-5 "
            "requires every batch member's Slice-Plan slices to be "
            "SliceCommitVerified BEFORE the whole-tree suite runs; HOW: "
            f"deliver {sorted(undelivered)} for {spec.feature_id!r} (or "
            "remove it from the manifest) before re-running the batch."
        ),
    )


def _check_deep_review_approved(
    repo_root: Path, spec: FeatureEndBatchSpec
) -> BatchIneligible | None:
    """D-5 check 2 (NEW, `[REF] Design Discovery (slice-02)`): the
    manifest-declared deep-review verdict must be APPROVED specifically.

    ``repo_root`` is unused -- accepted only to keep a uniform
    ``(repo_root, spec) -> BatchIneligible | None`` shape with its two
    sibling checks so `_ELIGIBILITY_CHECKS` can dispatch all three
    uniformly, in D-5's own declared order.
    """
    if spec.verdict == "APPROVED":
        return None
    return BatchIneligible(
        feature_id=spec.feature_id,
        error=(
            f"batch-eligibility precheck (D-5) refuses {spec.feature_id!r}: "
            f"WHAT: its manifest-declared deep-review verdict is "
            f"{spec.verdict!r}, not APPROVED; WHY: D-5 requires every batch "
            "member's deep-review verdict to be APPROVED at run start; HOW: "
            f"set {spec.feature_id!r}'s manifest entry verdict to APPROVED "
            "(or remove it from the manifest) before re-running the batch."
        ),
    )


def _check_charter_examine_passed(
    repo_root: Path, spec: FeatureEndBatchSpec
) -> BatchIneligible | None:
    """D-5 check 3 (HOISTED from the existing per-member examine leg,
    `[REF] Design Discovery (slice-02)`): every critical charter must carry a
    fresh feature-end PASS ExamineVerdict."""
    refusal = _fecs._run_feature_end_examine_leg(
        repo_root=repo_root, feature_id=spec.feature_id
    )
    if refusal is None:
        return None
    return BatchIneligible(
        feature_id=spec.feature_id,
        error=(
            f"batch-eligibility precheck (D-5) refuses {spec.feature_id!r}: "
            + refusal.error
        ),
    )


#: D-5's own declared check order: Slice-Plan SliceCommitVerified, then
#: deep-review APPROVED, then critical-charter EXAMINE-PASSed. Every entry
#: shares the `(repo_root, spec) -> BatchIneligible | None` shape.
_ELIGIBILITY_CHECKS = (
    _check_slice_commit_verified,
    _check_deep_review_approved,
    _check_charter_examine_passed,
)


def _batch_eligibility_precheck(
    repo_root: Path, specs: list[FeatureEndBatchSpec]
) -> BatchIneligible | None:
    """D-5 (locked): every batch member's Slice-Plan slices must be
    SliceCommitVerified, its deep-review verdict must be APPROVED, and its
    critical charters must be EXAMINE-PASSed -- evaluated at RUN START,
    BEFORE the (expensive) shared full-suite leg is spent (GDP-1).

    Two of the three checks HOIST an existing per-member gate to whole-batch,
    run-start scope; the deep-review-APPROVED check is genuinely new
    (`[REF] Design Discovery (slice-02)`). Members are walked in manifest
    order; within a member the checks run in D-5's own declared order. The
    FIRST ineligible member found refuses the WHOLE batch (D-5 locked) --
    never a silent partial emit for the eligible subset.
    """
    for spec in specs:
        for check in _ELIGIBILITY_CHECKS:
            ineligible = check(repo_root, spec)
            if ineligible is not None:
                return ineligible
    return None


def run_feature_end_batch(
    repo_root: Path, specs: list[FeatureEndBatchSpec]
) -> BatchIneligible | BatchRefused | BatchIndeterminate | BatchCompleted:
    """Run the D-5 eligibility precheck, then the shared full-suite leg ONCE,
    then each member's own cycle (D-3).

    Computes the deterministic batch-scoped artifact key (D-D4) and threads
    the full-suite leg's outcome into EVERY member's own
    `_run_feature_end_member_cycle` call as the `shared_full_suite`
    parameter, instead of each member computing it internally.

    On an ineligible member the WHOLE batch refuses with ZERO gates
    dispatched (D-5, GDP-1) -- before the full-suite leg is even computed. On
    a RED or INDETERMINATE shared suite the WHOLE batch refuses with ZERO
    member cycles run (D-4, D-D5) -- never bisected to eject or blame a
    single feature. On a PASS/NOT_APPLICABLE shared suite every member runs
    its own cycle independently (D-D6): one member's own refusal never
    suppresses another member's successful close.
    """
    ineligible = _batch_eligibility_precheck(repo_root, specs)
    if ineligible is not None:
        return ineligible

    # The shared full-suite leg ran HERE until 2026-08-06 -- one whole-tree
    # `des run-contract-gate` invocation for the whole batch, whose outcome was
    # then threaded into every member cycle. It duplicated CI, and it was this
    # vertical's largest hold on the condemned run-contract provider. CI is now
    # the terminal whole-tree evidence; the batch runs only the per-feature legs.

    members: list[tuple[str, CycleSuccess | CycleIndeterminate | CycleRefusal]] = []
    for spec in specs:
        outcome = _fecs._run_feature_end_member_cycle(
            repo_root=repo_root,
            feature_id=spec.feature_id,
            feature_dir=spec.feature_dir,
            reviewer_agent_id=spec.reviewer_agent_id,
            verdict=spec.verdict,
        )
        members.append((spec.feature_id, outcome))
    return BatchCompleted(members=tuple(members))


__all__ = [
    "BatchCompleted",
    "BatchIndeterminate",
    "BatchIneligible",
    "BatchManifestRefused",
    "BatchRefused",
    "FeatureEndBatchSpec",
    "parse_batch_manifest",
    "run_feature_end_batch",
]
