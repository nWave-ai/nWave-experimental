"""ATDD-Pure phase model — declarative domain types.

Domain types for the ATDD-pure workflow (ADR-027, reduced to the canonical
3-phase DELIVER vocabulary by ADR-001 — fix-atdd-pure-spine-phase-count-
reduction). Defines the canonical phase enum, the 3-link legal transition
matrix, the legacy→canonical replay reader (``resolve_phase`` /
``LEGACY_PHASE_ALIASES``), gap/verdict/event dataclasses, and routing-exit
sentinels.

NO business logic, NO TDD cycle implementation: this module is pure
data + enum. Orchestrator state-machine implementation lands in Phase 2
(`src/des/application/atdd_pure_runner.py`).

References:
- ADR-027: docs/architecture/adrs/adr-027-atdd-pure-7-phase-extension.md
- Design: docs/feature/atdd-pure-7-phase-scaffolding/design/wave-decisions.md
- Plan v3: docs/proposals/atdd-pure-workflow-restructure-v3-2026-05-19.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

from des.domain.value_objects import AgentName, FeatureName, StepId


if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


# ---------------------------------------------------------------------------
# Type aliases (per architect Reuse Analysis Table §6)
# ---------------------------------------------------------------------------

# Plan v3 vocabulary uses `feature_id`; existing DES uses FeatureName.
# Alias preserves call-site terminology without renaming 30+ existing uses.
FeatureId = FeatureName

# ADR-027 §Decision: workflow_mode opt-in dispatch selector.
WorkflowMode = Literal["atdd_pure"]

# ---------------------------------------------------------------------------
# Phase enum + routing-exit sentinel
# ---------------------------------------------------------------------------


class ATDDPurePhase(str, Enum):
    """The 3 canonical ATDD-pure delivery phases (ADR-001 7→3 reduction).

    Per-slice carpaccio order (deliver_phase_shape, velocity-v2): A_GREEN → EXAMINE
    → COMMIT. The middle slot is now EXAMINE (cleared via an ExamineVerdict — see
    EXAMINE below — an independent execution-observation, NOT an LLM reviewer-audit).
    D_REFACTOR_COMMIT is RETAINED as the per-slice COMMIT step (it lands the code);
    only the MANDATORY empty refactor is dropped — the refactor is now OPTIONAL
    (skip when there is nothing to refactor). Grinding was slice-07's retag-only
    D_REFACTOR_COMMIT, but slice-09-class D_REFACTOR_COMMITs land real production
    code, so the commit step must stay (sister dogfood counter-data 2026-07-04).
    The per-slice DELIVER carpaccio collapses the legacy 7-phase vocabulary
    (A_GREEN_ATS, B_COVERAGE_CLEANUP, D_GAP_ROUTING, E_BATCH_REFACTOR,
    F_FINAL_REVIEW, G_COMMIT) onto these three; the legacy names replay
    losslessly through ``resolve_phase`` / ``LEGACY_PHASE_ALIASES``.

    ``D_DISTILL`` is a routing-only node (oss-hook-side-phase-injection
    slice-01): it names the upstream DISTILL-wave acceptance-designer return
    the SubagentStop G-DISTILL-EXIT gate intercepts. It is NOT a carpaccio
    edge -- it is an EXPLICIT ASSERTED EXCLUSION from ``LEGAL_TRANSITIONS``
    (DISTILL is upstream of the per-slice cycle, not a member of it).
    """

    A_GREEN = "A_GREEN"
    C_REVIEWER_AUDIT = "C_REVIEWER_AUDIT"
    D_REFACTOR_COMMIT = "D_REFACTOR_COMMIT"
    D_DISTILL = "D_DISTILL"

    # feature-end-examine-phase slice-01 (DESIGN Decision D1): the feature-end
    # EXAMINE phase word -- an independent, execution-observing walk of the
    # FINISHED feature (step 2 of the /nw-deliver feature-end cycle). DISTINCT
    # from the per-slice ``EXAMINE`` alias below: reusing ``C_REVIEWER_AUDIT``
    # here would make every per-slice examine dispatch ILLEGAL the moment that
    # word also became a ``FEATURE_END_PHASES`` member. Like ``D_DISTILL``, this
    # is a per-FEATURE routing node -- excluded from ``CANONICAL_PHASES`` via
    # ``_NON_DELIVER_PHASES`` the same way, and NOT a member of the per-slice
    # carpaccio cycle (absent from ``LEGAL_TRANSITIONS``).
    FEATURE_END_EXAMINE = "FEATURE_END_EXAMINE"

    # evolution-plan P1.2 (User-Examiner spine wiring): ``EXAMINE`` is a VALUE
    # ALIAS of ``C_REVIEWER_AUDIT`` -- the SAME phase slot in the 3-link
    # sequence, cleared going forward via a recorded execution-observation
    # ExamineVerdict (see ``des.cli.commit_slice.check_examine_verdict``)
    # rather than a code-reading review. Python enum aliasing binds a second
    # name sharing an existing member's value to THAT member, so
    # ``ATDDPurePhase.EXAMINE is ATDDPurePhase.C_REVIEWER_AUDIT`` -- iteration
    # (``list(ATDDPurePhase)``), ``CANONICAL_PHASES`` (len 3, the ADR-001 7->3
    # reduction deletion-test), and every ``LEGAL_TRANSITIONS`` /
    # ``CANONICAL_TRANSITIONS`` entry keyed on ``C_REVIEWER_AUDIT`` are
    # UNCHANGED by this alias -- zero drift, zero shotgun surgery across the
    # 15+ modules/tests that already pin ``C_REVIEWER_AUDIT``. New code
    # spells the clearing route ``ATDDPurePhase.EXAMINE``; every existing
    # caller/test naming ``ATDDPurePhase.C_REVIEWER_AUDIT`` keeps resolving to
    # the identical member.
    EXAMINE = "C_REVIEWER_AUDIT"


class PhaseExit(str, Enum):
    """Non-phase routing outcomes (architect choice 3).

    Sentinel enum keeps `ATDDPurePhase` clean of non-phase routing
    targets. Routing returns one of these when the next step is NOT a
    forward phase transition.
    """

    RELOOP_A = "RELOOP_A"  # AT-gap-in-scope → re-enter A_GREEN with refined ATs
    REROUTE_DISCUSS = "REROUTE_DISCUSS"  # specification ambiguity upstream
    REROUTE_DESIGN = "REROUTE_DESIGN"  # architecture-scope-miss upstream
    REROUTE_DEVOPS = "REROUTE_DEVOPS"  # platform/infra ambiguity upstream
    HUMAN_ESCALATION = "HUMAN_ESCALATION"  # halt + human review
    CHECKPOINT_TIMEOUT = "CHECKPOINT_TIMEOUT"  # wall-clock budget exceeded
    TERMINAL = "TERMINAL"  # D_REFACTOR_COMMIT reached — end of cycle


# ---------------------------------------------------------------------------
# Legal transition matrix (architect §1.3)
# ---------------------------------------------------------------------------

# The canonical 3-link DELIVER transition matrix (ADR-001 §Sequencing).
# A_GREEN → EXAMINE (= C_REVIEWER_AUDIT) → D_REFACTOR_COMMIT → TERMINAL. deliver_phase_shape
# (velocity-v2): the middle slot is EXAMINE (execution-observation, not an LLM reviewer-audit);
# the refactor in D_REFACTOR_COMMIT is OPTIONAL but the COMMIT step STAYS (it lands the code).
# The EXAMINE/reviewer-audit
# node may also halt to HUMAN_ESCALATION. ``D_DISTILL`` is an EXPLICIT ASSERTED
# EXCLUSION from this matrix (it is an upstream-wave routing node, not a
# per-slice carpaccio edge — see oss-hook-side-phase-injection slice-01).
LEGAL_TRANSITIONS: dict[ATDDPurePhase, frozenset[ATDDPurePhase | PhaseExit]] = {
    ATDDPurePhase.A_GREEN: frozenset({ATDDPurePhase.C_REVIEWER_AUDIT}),
    ATDDPurePhase.C_REVIEWER_AUDIT: frozenset(
        {ATDDPurePhase.D_REFACTOR_COMMIT, PhaseExit.HUMAN_ESCALATION}
    ),
    ATDDPurePhase.D_REFACTOR_COMMIT: frozenset({PhaseExit.TERMINAL}),
}


class IllegalPhaseTransition(Exception):
    """Raised when orchestrator attempts a transition not in LEGAL_TRANSITIONS.

    Narrow exception (architect §7 justified divergence): orchestrator needs
    to discriminate this failure mode from generic value errors at the
    routing call site.
    """


# ---------------------------------------------------------------------------
# Canonical 3-phase delivery projection + legacy replay
# (fix-atdd-pure-spine-phase-count-reduction slice-02, ATOMIC 7→3 reduction)
# ---------------------------------------------------------------------------
#
# slice-01 shipped the operator-observable projection of the reduction while the
# legacy 7-phase enum members were still live (ADDITIVE). slice-02 performs the
# ATOMIC removal: the enum now carries only the canonical delivery phases
# (A_GREEN, C_REVIEWER_AUDIT, D_REFACTOR_COMMIT) + the upstream-wave D_DISTILL
# routing node. The legacy vocabulary survives ONLY as a read-only replay map
# (``LEGACY_PHASE_ALIASES`` + ``resolve_phase``), so a pre-reduction ledger or a
# returning agent that still speaks the old words replays losslessly.
#
# KEY INVARIANT (architect-mandated): the canonical phase list is DERIVED from
# the LIVE enum by exclusion, never a hand-restated literal. ``CANONICAL_PHASES``
# is exactly the live DELIVER carpaccio members (all enum members EXCEPT
# D_DISTILL, which is upstream of the per-slice cycle). The derivation yields
# ("A_GREEN", "C_REVIEWER_AUDIT", "D_REFACTOR_COMMIT") = 3.
#
# DELETION-TEST: the count cannot silently drift — it equals the live enum size
# minus the asserted D_DISTILL exclusion. Adding a fourth DELIVER phase or
# re-introducing a retired one bumps the count above 3 -> the slice-01 AT reds.

# The non-DELIVER enum members: upstream-wave / per-feature routing nodes,
# excluded from the per-slice canonical projection and from LEGAL_TRANSITIONS.
# D_DISTILL is the upstream DISTILL-wave return; FEATURE_END_EXAMINE
# (feature-end-examine-phase slice-01) is the per-feature examine routing node
# -- neither is a member of the per-slice carpaccio A_GREEN -> ... cycle.
_NON_DELIVER_PHASES: frozenset[ATDDPurePhase] = frozenset(
    {ATDDPurePhase.D_DISTILL, ATDDPurePhase.FEATURE_END_EXAMINE}
)

# Member names excluded from the canonical DELIVER vocabulary (upstream wave).
_NON_DELIVER_NAMES: frozenset[str] = frozenset(
    member.value for member in _NON_DELIVER_PHASES
)

# Canonical DELIVER phase tuple, derived from the live enum by exclusion.
CANONICAL_PHASES: tuple[str, ...] = tuple(
    member.value for member in ATDDPurePhase if member not in _NON_DELIVER_PHASES
)

# Live enum member names — the canonical vocabulary the runtime now speaks.
_CANONICAL_NAMES: frozenset[str] = frozenset(member.value for member in ATDDPurePhase)

# Legacy 7-phase vocabulary → canonical phase replay map (lossless backward
# compat). Each retired name replays onto the canonical phase it collapsed into:
#   - A_GREEN_ATS, B_COVERAGE_CLEANUP            -> "A_GREEN"
#   - E_BATCH_REFACTOR, F_FINAL_REVIEW, G_COMMIT -> "D_REFACTOR_COMMIT"
# ``D_GAP_ROUTING`` is the retired routing node: it maps to None (the
# routing/seam outcome), NOT to a canonical phase and NOT to a rejection.
LEGACY_PHASE_ALIASES: dict[str, str | None] = {
    "A_GREEN_ATS": "A_GREEN",
    "B_COVERAGE_CLEANUP": "A_GREEN",
    "E_BATCH_REFACTOR": "D_REFACTOR_COMMIT",
    "F_FINAL_REVIEW": "D_REFACTOR_COMMIT",
    "G_COMMIT": "D_REFACTOR_COMMIT",
    "D_GAP_ROUTING": None,
}


class UnknownPhaseName(Exception):
    """Raised by ``resolve_phase`` for a name that is neither canonical, a
    known legacy alias, nor the retired routing marker.

    Narrow typed error (mirrors ``IllegalPhaseTransition``): the replay caller
    discriminates an unknown phase from a routing/seam outcome at the call site,
    so an unrecognised name is refused outright rather than silently mapped to a
    wrong phase.
    """


# Sentinel returned by ``resolve_phase`` for the retired routing marker — the
# THIRD outcome, observably distinct from both a canonical phase and an
# UnknownPhaseName rejection.
ROUTING_SEAM: str = "__ROUTING_SEAM__"


class PhaseResolutionKind(Enum):
    """Which of the three resolution outcomes occurred."""

    CANONICAL = "canonical"
    ROUTING = "routing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PhaseResolution:
    """The outcome of resolving a phase name, as DATA rather than control flow.

    All three outcomes are returned. None is thrown, and that is the point: an
    ``except`` clause matches on class IDENTITY, so a raised outcome couples the
    caller to the exact module object the raiser was loaded from. Where the same
    package is reachable by more than one path -- a source tree plus an installed
    runtime, a test harness that adjusts ``sys.path`` -- that identity is not
    guaranteed, the ``except`` silently fails to match, and a handled outcome
    escapes as a crash.

    Measured, 2026-08-06: CI reported `UnknownPhaseName` propagating out of
    `des.cli.phases._resolve` from the line INSIDE its own `try`, with the
    matching `except` on the very next line. Returning the outcome removes the
    coupling entirely, so the failure class cannot recur regardless of how the
    module came to be loaded twice.

    Illegal combinations are unrepresentable by construction: only CANONICAL
    carries a phase, and it always carries one.
    """

    kind: PhaseResolutionKind
    requested: str
    canonical: str | None = None

    def __post_init__(self) -> None:
        has_phase = self.canonical is not None
        if (self.kind is PhaseResolutionKind.CANONICAL) != has_phase:
            raise ValueError(
                f"PhaseResolution({self.kind}) carries canonical="
                f"{self.canonical!r}: only CANONICAL has a phase, and always has one"
            )

    # Discriminators, deliberately evaluated HERE. `kind is
    # PhaseResolutionKind.X` compares enum-member IDENTITY, which is exactly the
    # coupling the returned outcome exists to remove: where the module is loaded
    # twice, a caller's `PhaseResolutionKind.UNKNOWN` is a different object from
    # the one inside this instance and the comparison silently answers False.
    #
    # Measured 2026-08-06: the first version of this change had `phases.py`
    # branch on `resolution.kind is PhaseResolutionKind.UNKNOWN`. CI then
    # reported an unknown phase ACCEPTED with exit 0 -- the same defect the
    # `except` had, in new syntax. Identity comparison is safe only inside the
    # module that owns both sides, so callers ask these questions instead of
    # touching the enum.

    @property
    def is_canonical(self) -> bool:
        """Whether the name resolved to a canonical phase (carried in `canonical`)."""
        return self.kind is PhaseResolutionKind.CANONICAL

    @property
    def is_routing(self) -> bool:
        """Whether the name is the retired routing marker: recognised, no phase."""
        return self.kind is PhaseResolutionKind.ROUTING

    @property
    def is_unknown(self) -> bool:
        """Whether the name was refused -- never a silent map to a wrong phase."""
        return self.kind is PhaseResolutionKind.UNKNOWN


def resolve_phase(name: str) -> PhaseResolution:
    """Resolve a (possibly legacy) phase name to its canonical phase.

    Read-only replay reader (mirrors the per-log dispatch precedent in
    ``validator.py:_resolve_active_phases``). THREE outcomes, all RETURNED:

    * a canonical name (or a legacy alias) -> ``CANONICAL`` with the phase;
    * the retired routing marker ``D_GAP_ROUTING`` -> ``ROUTING`` (recognised,
      but no canonical phase);
    * any other name -> ``UNKNOWN`` (refused outright; never a silent map to a
      wrong phase).

    The docstring previously described three outcomes while returning two and
    throwing the third. That asymmetry was the defect -- see ``PhaseResolution``.
    """
    normalised = name.strip().upper().replace("-", "_")
    if normalised in _CANONICAL_NAMES and normalised not in _NON_DELIVER_NAMES:
        return PhaseResolution(PhaseResolutionKind.CANONICAL, name, normalised)
    if normalised in LEGACY_PHASE_ALIASES:
        canonical = LEGACY_PHASE_ALIASES[normalised]
        if canonical is None:
            return PhaseResolution(PhaseResolutionKind.ROUTING, name)
        return PhaseResolution(PhaseResolutionKind.CANONICAL, name, canonical)
    return PhaseResolution(PhaseResolutionKind.UNKNOWN, name)


# The three-link canonical transition map (architect §Sequencing / ADR-001).
# TERMINAL marks the end of the per-slice cycle. The optional HUMAN_ESCALATION
# halt edge is out of slice-01 scope (the AT is silent on it).
CANONICAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "A_GREEN": frozenset({"C_REVIEWER_AUDIT"}),
    "C_REVIEWER_AUDIT": frozenset({"D_REFACTOR_COMMIT"}),
    "D_REFACTOR_COMMIT": frozenset({"TERMINAL"}),
}


# ---------------------------------------------------------------------------
# Phase-routing groups — the ONE SSOT for the hook-side dispatch subsets
# (SSOT/DRY consolidation 2026-05-31)
# ---------------------------------------------------------------------------
#
# The U1 carpaccio intercept, the U2 commit-gate / U4 feature-end SubagentStop
# intercepts, and the marker-parser feature-end-coherence check each route a
# returning agent by the phase word it carries. Historically each hook re-listed
# the routing subset as RAW STRING LITERALS (`_CARPACCIO_ENTRY_PHASES`,
# `_COMMIT_GATE_PHASES`, `_FEATURE_END_PHASES`, plus a bare `== "F_FINAL_REVIEW"`
# literal). That was the phase-identity multi-representation: the same routing
# concept in N hand-maintained copies.
#
# These frozensets are now the SINGLE SOURCE. Each group is DERIVED:
#   * its CANONICAL members come from the live ``ATDDPurePhase`` enum (so a
#     renamed/added canonical phase propagates here, not into each hook);
#   * its LEGACY members are SELECTED from ``LEGACY_PHASE_ALIASES`` via
#     ``_legacy_words`` — which asserts every named word is a real alias key, so
#     the legacy vocabulary is single-sourced in the alias map and a drift there
#     breaks the derivation LOUDLY rather than leaving a stale literal in a hook.
#
# The groups are CURATED subsets (not "all aliases of canonical X"): the
# carpaccio-entry group is the A_GREEN ENTRY word only (NOT B_COVERAGE_CLEANUP,
# which also collapsed onto A_GREEN); the commit-gate group is the per-slice
# commit phase (NOT the feature-end words). The behaviour is byte-identical to
# the pre-consolidation hardcoded sets — the words moved to one place, none were
# added or removed.


def _legacy_words(*names: str) -> frozenset[str]:
    """Select legacy phase words from ``LEGACY_PHASE_ALIASES``, single-sourced.

    Each ``name`` MUST be a known key of ``LEGACY_PHASE_ALIASES`` — the alias
    map is the SSOT for the retired 7-phase vocabulary, so a routing group
    references that vocabulary by selection rather than by a private restated
    literal. A name that is not (or no longer) an alias key raises, surfacing
    the drift at import time rather than as a silently-stale hook set.
    """
    for name in names:
        if name not in LEGACY_PHASE_ALIASES:
            raise UnknownPhaseName(
                f"{name!r} is not a known LEGACY_PHASE_ALIASES key — a phase "
                "routing group may only select existing legacy vocabulary"
            )
    return frozenset(names)


# U1 carpaccio entry gate keys on the A_GREEN ENTRY phase. The canonical word is
# A_GREEN; the legacy A_GREEN_ATS word replays onto it (lossless 7→3 replay).
# B_COVERAGE_CLEANUP also collapsed onto A_GREEN but is NOT an entry word — it is
# deliberately excluded, preserving the pre-consolidation set membership.
CARPACCIO_ENTRY_PHASES: frozenset[str] = frozenset(
    {ATDDPurePhase.A_GREEN.value}
) | _legacy_words("A_GREEN_ATS")

# U2 per-slice commit exit-gate keys on the per-slice commit phase. The canonical
# word is D_REFACTOR_COMMIT; the legacy G_COMMIT word replays onto it. The
# feature-end words (E_BATCH_REFACTOR / F_FINAL_REVIEW) route elsewhere and are
# excluded, preserving the pre-consolidation set membership.
COMMIT_GATE_PHASES: frozenset[str] = frozenset(
    {ATDDPurePhase.D_REFACTOR_COMMIT.value}
) | _legacy_words("G_COMMIT")

# The feature-end-cycle phases (ADR-028 D6): the legacy F_FINAL_REVIEW word
# plus the canonical per-feature D_DISTILL routing node plus the per-feature
# FEATURE_END_EXAMINE routing node (feature-end-examine-phase slice-01,
# DESIGN Decision D1). A dispatch in one of these phases is per-FEATURE, so
# its only coherent scope is `feature-end`. The per-slice commit phase
# D_REFACTOR_COMMIT is NOT here.
#
# E_BATCH_REFACTOR is DELIBERATELY ABSENT (fix-dispatch-cannot-generate-
# feature-end-phases, Ale-ratified): the mandatory batch refactor is retired
# from both the per-slice and feature-end cycles, superseded by the
# prefactoring lane. It stays a valid LEGACY_PHASE_ALIASES replay key (a
# pre-retirement ledger entry still resolves), but it is no longer a live
# feature-end-coherent phase -- re-adding it here would resurrect a retired
# phase.
FEATURE_END_PHASES: frozenset[str] = frozenset(
    {ATDDPurePhase.D_DISTILL.value, ATDDPurePhase.FEATURE_END_EXAMINE.value}
) | _legacy_words("F_FINAL_REVIEW")

# The single phase word that routes a returning agent to the U4 feature-end
# terminal gate. The legacy F_FINAL_REVIEW word is the reviewer's feature-end
# return; selecting it from the alias map keeps it bound to the SSOT vocabulary
# rather than a bare literal at the dispatch call site.
FEATURE_END_RETURN_PHASE: str = next(iter(_legacy_words("F_FINAL_REVIEW")))


# ---------------------------------------------------------------------------
# Display-vocab -> canonical-slot alias (velocity-v2 EXAMINE/COMMIT rename,
# fix-docgen-phase-vocab-comparator)
# ---------------------------------------------------------------------------
#
# The `deliver_phase_shape` registry field (`nWave/flavors/*.yaml`) speaks the
# velocity-v2 DISPLAY vocabulary ("A_GREEN -> EXAMINE -> COMMIT"), never the
# internal canonical slot names. A literal string compare against
# `CANONICAL_PHASES` is alias-blind and false-fails on every display token.
# This map is the single SSOT a consumer (e.g. `scripts/docgen.py`) normalizes
# a declared display token through before comparing against the canonical
# vocabulary — no second hand-restated table.
#
# "EXAMINE" reuses the ATDDPurePhase enum's OWN existing value-alias (attribute
# lookup, since ``EXAMINE`` shares ``C_REVIEWER_AUDIT``'s value rather than
# being independently constructible via `ATDDPurePhase("EXAMINE")`).
# "COMMIT" has no enum-level alias (D_REFACTOR_COMMIT never gained one) — it is
# the missing entry this fix adds.
DISPLAY_VOCAB_ALIASES: dict[str, str] = {
    "EXAMINE": ATDDPurePhase["EXAMINE"].value,
    "COMMIT": ATDDPurePhase.D_REFACTOR_COMMIT.value,
}


def normalize_phase_token(token: str) -> str:
    """Resolve a (possibly display-vocab) phase token to its canonical slot.

    A token already spelling a canonical name (or an unrecognised token) is
    returned unchanged — only known display-vocab aliases are rewritten.
    """
    return DISPLAY_VOCAB_ALIASES.get(token, token)


# ---------------------------------------------------------------------------
# Gap classification enums
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """ATGap severity per plan v3 §7.2 routing predicate."""

    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ATGapKind(str, Enum):
    """Reviewer-authored gap kinds (plan v3 §7.1 + ADR-027 glossary).

    ARCHITECTURE_SCOPE_MISS is router-derived (Phase D second-order rule),
    not reviewer-authored — hence absent from this enum.
    """

    AT_GAP_IN_DELIVERY_SCOPE = "at_gap_in_delivery_scope"
    SPECIFICATION_AMBIGUITY = "specification_ambiguity"


# ---------------------------------------------------------------------------
# ATGap dataclass (architect §2.1 + choice 1: source_at_path included)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ATGap:
    """A single reviewer-identified gap in acceptance-test coverage.

    Per architect choice 1 (Ale ratified): `source_at_path` is INCLUDED
    as a `Path` field. Reviewer optionally populates with the offending
    AT file path; orchestrator ignores; audit-report renderer uses.
    """

    scenario_class: str
    current_at_count: int
    reason: str
    kind: ATGapKind
    severity: Severity
    source_at_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.scenario_class:
            raise ValueError("scenario_class must be non-empty")
        if self.current_at_count < 0:
            raise ValueError(f"current_at_count must be >= 0: {self.current_at_count}")
        if not self.reason:
            raise ValueError("reason must be non-empty")
        if len(self.reason) > 500:
            raise ValueError(
                f"reason exceeds 500-char telemetry bound: {len(self.reason)}"
            )
        if self.source_at_path is not None:
            if self.source_at_path.is_absolute():
                raise ValueError(
                    f"source_at_path must be repo-relative, not absolute: "
                    f"{self.source_at_path}"
                )
            if ".." in self.source_at_path.parts:
                raise ValueError(
                    f"source_at_path must not contain '..' segments: "
                    f"{self.source_at_path}"
                )


# ---------------------------------------------------------------------------
# Reviewer verdict shapes (architect choice 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseCReviewerVerdict:
    """Phase C audit verdict — verdict_hash OPTIONAL (architect choice 2).

    Phase C may halt before producing a verdict (e.g. reviewer LLM crash);
    in that path the halt event is the record of truth, not this verdict.
    """

    step_id: StepId
    feature_id: FeatureId
    findings: list[ATGap]
    approved: bool
    verdict_hash: str | None = None

    def __post_init__(self) -> None:
        # Invariant: approved=True ⇔ no BLOCKER findings.
        if self.approved and any(f.severity == Severity.BLOCKER for f in self.findings):
            raise ValueError(
                "PhaseCReviewerVerdict cannot be approved with BLOCKER findings"
            )
        if self.verdict_hash is not None and not _is_hex64(self.verdict_hash):
            raise ValueError(
                f"verdict_hash must be 64-char hex (SHA-256): {self.verdict_hash!r}"
            )


@dataclass(frozen=True)
class PhaseFReviewerVerdict:
    """Phase F terminal verdict — verdict_hash MANDATORY (architect choice 2).

    The G_COMMIT phase emits a `Reviewed-by:` trailer carrying this
    verdict_hash. Earned Trust APPROVAL gate requires it always present.
    """

    step_id: StepId
    feature_id: FeatureId
    approved: bool
    verdict_hash: str

    def __post_init__(self) -> None:
        if not _is_hex64(self.verdict_hash):
            raise ValueError(
                f"verdict_hash must be 64-char hex (SHA-256): {self.verdict_hash!r}"
            )


def _is_hex64(s: str) -> bool:
    """Validate string is 64-character lowercase hex (SHA-256 output)."""
    if len(s) != 64:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Domain events (architect §3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeliverBlocker:
    """Emitted by Phase D when a BLOCKER gap halts the cycle (plan v3 §7.2)."""

    feature_id: FeatureId
    step_id: StepId
    gaps: tuple[ATGap, ...]
    timestamp: datetime

    def __post_init__(self) -> None:
        _require_tz_aware(self.timestamp, "DeliverBlocker.timestamp")


@dataclass(frozen=True)
class AcceptanceTestGapIdentified:
    """Emitted by Phase D on AT-gap-in-delivery-scope (plan v3 §7.2 case 5)."""

    feature_id: FeatureId
    step_id: StepId
    gaps: tuple[ATGap, ...]
    cycle_n: int
    timestamp: datetime

    def __post_init__(self) -> None:
        _require_tz_aware(self.timestamp, "AcceptanceTestGapIdentified.timestamp")
        if self.cycle_n < 0:
            raise ValueError(f"cycle_n must be >= 0: {self.cycle_n}")


@dataclass(frozen=True)
class SpecificationAmbiguityDetected:
    """Emitted by Phase D on upstream ambiguity reroute (plan v3 §6.7)."""

    feature_id: FeatureId
    step_id: StepId
    gaps: tuple[ATGap, ...]
    upstream_wave: Literal["DISCUSS", "DESIGN", "DEVOPS"]
    timestamp: datetime

    def __post_init__(self) -> None:
        _require_tz_aware(self.timestamp, "SpecificationAmbiguityDetected.timestamp")


@dataclass(frozen=True)
class ArchitectureScopeMissDetected:
    """Emitted by Phase D on second-order architecture-scope-miss (plan v3 §7.1)."""

    feature_id: FeatureId
    step_id: StepId
    scenario_classes: tuple[str, ...]
    missing_components: tuple[str, ...]
    timestamp: datetime

    def __post_init__(self) -> None:
        _require_tz_aware(self.timestamp, "ArchitectureScopeMissDetected.timestamp")


@dataclass(frozen=True)
class DeliverTimeoutExceeded:
    """Emitted by Phase D on wall-clock budget breach (plan v3 §7.2 case 3)."""

    feature_id: FeatureId
    step_id: StepId
    wall_clock_s: float
    current_phase: ATDDPurePhase
    timestamp: datetime

    def __post_init__(self) -> None:
        _require_tz_aware(self.timestamp, "DeliverTimeoutExceeded.timestamp")
        if self.wall_clock_s < 0:
            raise ValueError(f"wall_clock_s must be >= 0: {self.wall_clock_s}")


def _require_tz_aware(ts: datetime, field_name: str) -> None:
    """Enforce tz-aware UTC timestamp invariant on event dataclasses."""
    if ts.tzinfo is None:
        raise ValueError(f"{field_name} must be tz-aware (UTC required)")


# ---------------------------------------------------------------------------
# Public exports (explicit for mypy strict + import hygiene)
# ---------------------------------------------------------------------------

__all__ = [
    "CANONICAL_PHASES",
    "CANONICAL_TRANSITIONS",
    "CARPACCIO_ENTRY_PHASES",
    "COMMIT_GATE_PHASES",
    "DISPLAY_VOCAB_ALIASES",
    "FEATURE_END_PHASES",
    "FEATURE_END_RETURN_PHASE",
    "LEGACY_PHASE_ALIASES",
    "LEGAL_TRANSITIONS",
    "ROUTING_SEAM",
    "ATDDPurePhase",
    "ATGap",
    "ATGapKind",
    "AcceptanceTestGapIdentified",
    "AgentName",
    "ArchitectureScopeMissDetected",
    "DeliverBlocker",
    "DeliverTimeoutExceeded",
    "FeatureId",
    "IllegalPhaseTransition",
    "PhaseCReviewerVerdict",
    "PhaseExit",
    "PhaseFReviewerVerdict",
    "PhaseResolution",
    "PhaseResolutionKind",
    "Severity",
    "SpecificationAmbiguityDetected",
    "StepId",
    "UnknownPhaseName",
    "WorkflowMode",
    "normalize_phase_token",
    "resolve_phase",
]
