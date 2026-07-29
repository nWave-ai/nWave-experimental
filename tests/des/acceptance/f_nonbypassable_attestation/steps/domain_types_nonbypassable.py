"""Typed domain vocabulary for the f-nonbypassable-attestation ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the four
slices' Gherkin names is expressed once here as a typed enum / NewType, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these enums (parameterized step templates over
typed parameters), NOT from decorator proliferation.

These types are TEST-LOCAL: they never import production code. The ATs drive the
SUT only through composition-root driving ports (Mandate-13):
  * the done-gate via ``des verify-integrity`` (Layer-3 composition: the real
    ``verify_deliver_integrity.main`` entry point reading a real ledger), and
  * the bypass-debt write via the REAL PreToolUse/Bash spine-ledger hook
    (Layer-3 subprocess: the shipped ``scripts.hooks.spine_ledger_pre_commit_hook``).

The done-gate's observable surface is its EXIT CODE (the GateVerdict projection,
0=PASS / 1=FAIL / 4=INDETERMINATE) plus the machine-readable record names it
prints. Universe entries the ATs track are those port-exposed names, never the
done-gate's internal struct fields.
"""

from __future__ import annotations

from enum import Enum


class DoneVerdict(Enum):
    """The observable done-gate verdict, projected onto the 5-value GateVerdict
    SSOT exit codes (ADR-GV-001 / ADR-NB-001 DDD-7).

    Only these three are reachable for this feature's scenarios; the value is the
    process EXIT CODE the real ``verify_deliver_integrity`` entry point returns.
    No sixth verdict (AT-A3).
    """

    PASS = 0  # the ledger carries every required record; nothing vetoes
    FAIL = 1  # a definite refusal (records absent / slice pending / unwired gate)
    INDETERMINATE = 4  # cannot certify (git/ledger unreadable OR unreconciled debt)


class FeatureEndRecord(Enum):
    """The named feature-end ledger records the done-gate `required` set demands.

    The 6 records present at HEAD plus the NEW ``FullSuiteLegRan`` /
    ``FullSuiteLegNotApplicable`` records slice-01 makes `required` (DDD-4). Each
    value is the exact ``event`` string the real ``AtCompletionLedger`` writes
    and the real done-gate reads.
    """

    COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT = "CoverageMapVerifiedAtDeliverExit"
    COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT = "CoverageMapVerifiedAtDistillExit"
    E_BATCH_REFACTOR_COMPLETED = "EBatchRefactorCompleted"
    ENVIRONMENTAL_E2E_GATE_RAN = "EnvironmentalE2eGateRan"
    FEATURE_END_REVIEW_VERDICT = "FeatureEndReviewVerdict"
    WALKING_SKELETON_GATE_RAN = "WalkingSkeletonGateRan"
    # NEW (fix-ws-done-gate-na-reconciliation slice-01) -- the PASS-only trust
    # anchor, now ALSO required alongside the WALKING_SKELETON_GATE_RAN heartbeat
    # (the heartbeat alone let a FAILED walking skeleton close).
    WALKING_SKELETON_TIER_VERIFIED = "WalkingSkeletonTierVerified"
    # NEW (DDD-4) — slice-01 emits this from run_feature_end_cycle and adds it to
    # the `required` set in BOTH SSOTs.
    FULL_SUITE_LEG_RAN = "FullSuiteLegRan"
    FULL_SUITE_LEG_NOT_APPLICABLE = "FullSuiteLegNotApplicable"


class FullSuiteOutcome(Enum):
    """The full-suite leg's outcome inside ``run_feature_end_cycle`` (DDD-4 / CT-5).

    GREEN  -> the cycle PROCEEDS and emits ``FullSuiteLegRan``.
    ABSENT -> the cycle PROCEEDS and emits ``FullSuiteLegNotApplicable`` (NA).
    RED    -> ``_run_full_suite_leg`` returns ``CycleRefusal`` (line 466); the
              cycle ABORTS and emits NO records at all (CT-5b record-ABSENCE).
    """

    GREEN = "green"
    ABSENT = "absent"
    RED = "red"


class BypassDebtState(Enum):
    """The reconciliation state of a ``--no-verify`` slice-commit (DDD-3 / CT-3/4).

    NONE        -> no bypass occurred (the happy path).
    UNRECONCILED-> a ``SliceCommitBypassed`` debt record exists with no matching
                   ``SliceCommitVerified`` -> done-gate INDETERMINATE.
    RECONCILED  -> ``des reverify-slice-commit`` emitted the matching
                   ``SliceCommitVerified`` -> the done-gate clears.
    """

    NONE = "none"
    UNRECONCILED = "unreconciled"
    RECONCILED = "reconciled"


class CommitKind(Enum):
    """How a slice commit is issued through the PreToolUse/Bash surface (CT-3)."""

    VERIFIED = "git commit"  # normal: stamping + verifying hooks run
    NO_VERIFY = "git commit --no-verify"  # skips git hooks; debt written pre-git
    NO_VERIFY_SHORT = "git commit -n"  # the -n alias


class SlicePlanStatus(Enum):
    """The canonical Slice-Plan ``Status`` column value the done-gate reads (CT-6 /
    DDD-5). ``shipped`` is the only value that clears the all-shipped assertion.
    """

    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    SHIPPED = "shipped"


class GitState(Enum):
    """The mechanism-presence axis for the degrade-LOUD contract (CT-7 / AT-A4)."""

    PRESENT = "present"  # a real work-tree -> trailer history readable
    ABSENT = "absent"  # not a work-tree -> CommitTrailerReadPort -> INDETERMINATE


class CatalogWiring(Enum):
    """A catalogued gate's wiring state for the coherence arch-test (AT-A1 / DDD-6)."""

    WIRED = "wired"  # invoked by a live hook -> coherent
    DORMANT_ANNOTATED = "dormant_annotated"  # carries `dormant: <rationale>` -> excused
    UNWIRED = "unwired"  # neither -> the authored-but-unwired failure class -> FAIL


# --- slice-05: wave-dispatch guard (DDD-8/9, CT-8/9/10, AT-A7/A8) -----------


class WaveOwner(Enum):
    """A wave-OWNER subagent the generalized guard recognizes (DDD-8 wave->owner map).

    Each value is the exact ``subagent_type`` the orchestrator dispatches. A
    dispatch of one of these WITHOUT the matching ``DES-WAVE: <wave>`` marker is
    off-spine wave entry -> BLOCK. (Reviewers are deliberately ABSENT -- they are
    §22.0 controls, never wave-authoring, so their hand-dispatch stays exempt.)
    """

    PRODUCT_DISCOVERER = "nw-product-discoverer"  # DISCOVER
    DIVERGER = "nw-diverger"  # DIVERGE
    PRODUCT_OWNER = "nw-product-owner"  # DISCUSS
    SOLUTION_ARCHITECT = "nw-solution-architect"  # DESIGN (application)
    DDD_ARCHITECT = "nw-ddd-architect"  # DESIGN (domain modelling)
    SYSTEM_DESIGNER = "nw-system-designer"  # DESIGN (infra-level)
    ACCEPTANCE_DESIGNER = "nw-acceptance-designer"  # DISTILL
    PLATFORM_ARCHITECT = "nw-platform-architect"  # DESIGN (infra) + DEVOPS


class GuardDecision(Enum):
    """The observable wave-dispatch-guard decision (CT-8/9/10).

    RE-HOMED (orchestrator augment 2026-06-16): the SUT is now the IN-TREE
    ``des.cli.verify_wave_dispatch`` gate, which MIRRORS
    ``verify_readiness_pre_dispatch.py``'s exit-code convention -- 0 ALLOW /
    1 BLOCK / 2 malformed-input (§22.0 H-2). The intercept maps the gate's
    non-zero (1) onto the PreToolUse ``decision:block`` (DDD-7, no sixth verdict).
    The guard's observable surface is its EXIT CODE + the one JSON line printed
    on stdout ({event, subagent_type, wave, verdict, reason}). Universe entries
    the ATs track are this exit code + the printed verdict/reason token, never the
    gate's internal regex objects.

    (NB: the pre-re-home personal-hook convention was BLOCK=exit 2; the in-tree
    gate uses BLOCK=exit 1 so that 2 is reserved for argparse malformed-input,
    matching the readiness gate template.)
    """

    ALLOW = 0  # on-spine (marker present) OR exempt agent OR valid skip/grant
    BLOCK = 1  # off-spine wave entry with no marker, no witness, no grant
    MALFORMED = 2  # argparse failure on a missing required arg (§22.0 H-2)


class WaveMarker(Enum):
    """Whether a wave-owner dispatch carries the matching ``DES-WAVE`` marker (CT-8/9)."""

    PRESENT = "present"  # carries <!-- DES-WAVE: <wave> --> matching the owner
    ABSENT = "absent"  # no matching marker -> off-spine entry


class SkipAuthorization(Enum):
    """The off-spine skip-authorization state a marker-less dispatch may carry (CT-10).

    FORM-only per the honest scope (DDD-9 / AT-A8): the guard verifies the witness
    FORM (canonical heading + non-empty rationale) or a non-expired session
    pre-grant. It CANNOT verify source-authorship of plain markdown -- that is
    review-enforced, not guard-enforced.
    """

    NONE = "none"  # no witness, no grant -> BLOCK
    FORM_VALID_WITNESS = "form_valid_witness"  # canonical heading + non-empty rationale
    FORM_INVALID_WITNESS = (
        "form_invalid_witness"  # heading present, rationale EMPTY -> BLOCK
    )
    VALID_PRE_GRANT = "valid_pre_grant"  # non-expired session-scoped grant -> ALLOW
    EXPIRED_PRE_GRANT = (
        "expired_pre_grant"  # TTL-elapsed grant reads as ABSENT -> BLOCK
    )


class DispatchAgentKind(Enum):
    """Whether a dispatched agent is a wave-OWNER (gated) or a REVIEWER (exempt) (CT-9)."""

    WAVE_OWNER = "wave_owner"  # in the map -> gated
    REVIEWER = "reviewer"  # §22.0 control, never in the map -> always allowed
