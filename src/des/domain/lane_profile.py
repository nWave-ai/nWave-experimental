"""LaneProfile -- queryable lane-definition datum (RED scaffold, slice-01).

DISTILL scaffold for feature `f-prefactoring-dispatch-clears-honestly`
(epic `non-slice-dispatch-exemption-model`, row 1 keystone). Real shape per
`docs/feature/f-prefactoring-dispatch-clears-honestly/feature-delta.md`
(`Wave: DESIGN / [REF] LANE_PROFILES Datum Shape`). DELIVER populates the
`"prefactoring"` entry with the exact fields the DESIGN table names; this
scaffold defines the enums + frozen dataclass shape and an EMPTY registry so
slice-01's ATs fail with ``AssertionError`` (impl missing), never
``ImportError`` (Mandate 7 -- RED-not-BROKEN).

Pure -- zero I/O, zero upward dependency (D1: domain must not import the
application/cli layers that consult this datum). Beyond `dataclasses`/`enum`
it imports exactly one sibling DOMAIN module, `expectation_charter_mapping`,
for the `CharterObligation` vocabulary: the obligation is declared where the
charter subject already lives, so there is one place to look, and the edge
points domain->domain (acyclic: that module imports nothing from here).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from des.domain.expectation_charter_mapping import CharterObligation


class GuardKind(Enum):
    """The mechanical guard a lane's dispatch is verified against."""

    RED_TO_GREEN = "RED_TO_GREEN"  # bugfix lane shape (epic row 3, not populated here)
    GREEN_TO_GREEN = "GREEN_TO_GREEN"  # prefactoring: suite green before AND after
    NONE = "NONE"


class AtRequirement(Enum):
    """Whether a lane's dispatch is required to own at least one AT."""

    EXEMPT = "EXEMPT"
    REQUIRED = "REQUIRED"


@dataclass(frozen=True)
class LaneProfile:
    """One row of the queryable lane-definition datum every consulting locus reads."""

    lane_id: str
    required_sections: tuple[str, ...]
    guard_kind: GuardKind
    feature_readiness: bool
    at_requirement: AtRequirement
    skipped_invariants: tuple[str, ...]
    annotation_token: str
    #: Whether work dispatched on this lane OWES an expectation charter -- the
    #: FOURTH sibling ceremony declaration on the same row, read as a
    #: consequence of the lane the operator already chose rather than asked as
    #: a second question. Deliberately NO default: a lane added later without
    #: one fails LOUD at construction, never defaults into a silent value.
    charter_obligation: CharterObligation


# The queryable lane-definition datum. slice-01 (keystone) populates exactly ONE
# lane -- ``prefactoring`` -- with its ceremony profile; the section validator
# CONSULTS this datum (it never hand-branches ``if lane == "prefactoring"``).
# ``required_sections`` is a LITERAL tuple (D2: the domain must not import the
# application-layer ATDD_PURE_MANDATORY_SECTIONS to derive it) = the full 12 MINUS
# the 2 AT-recording sections a behavior-preserving prefactoring never writes
# (AT_COMPLETION_LEDGER, RECORDING_INTEGRITY), in the same order as the full set.
LANE_PROFILES: dict[str, LaneProfile] = {
    "prefactoring": LaneProfile(
        lane_id="prefactoring",
        required_sections=(
            "DES_METADATA",
            "AGENT_IDENTITY",
            "SKILL_LOADING",
            "TASK_CONTEXT",
            "DESIGN_CONTEXT",
            "ATDD_PURE_PHASES",
            "QUALITY_GATES",
            "BOUNDARY_RULES",
            "TERMINATING_RUN",
            "TIMEOUT_INSTRUCTION",
        ),
        guard_kind=GuardKind.GREEN_TO_GREEN,
        feature_readiness=False,
        at_requirement=AtRequirement.EXEMPT,
        skipped_invariants=(
            "slice_plan_section",
            "scenario_slice_tags",
            "reuse_first_or_design_skip",
            # A prefactoring-lane dispatch IS the recorded @prefactoring slice
            # doing the assessed reshaping work -- checking its OWN
            # feature-delta for a Prefactoring Assessment naming itself at
            # dispatch time is circular (prefactoring-enforcement-wiring).
            "prefactoring_assessment",
            "sustainability",
        ),
        annotation_token="prefactoring",
        # A prefactoring lane ALREADY declares behaviour-preservation
        # (GREEN_TO_GREEN): it changes no promised outcome, so there is no
        # outcome to charter.
        charter_obligation=CharterObligation.EXEMPT,
    ),
    # A bugfix writes code + records ATs -> the FULL section set (mirrors the
    # dispatch SSOT's `profiles.lane.bugfix` row under `nWave/dispatch/`,
    # which declares an empty drop set). See des-dispatch-ssot-renderer
    # Fase-1: this literal is a drift-checked PROJECTION of that SSOT row,
    # verified by `des.application.dispatch_lane_ssot.check_lane_profile_drift`.
    "bugfix": LaneProfile(
        lane_id="bugfix",
        required_sections=(
            "DES_METADATA",
            "AGENT_IDENTITY",
            "SKILL_LOADING",
            "TASK_CONTEXT",
            "DESIGN_CONTEXT",
            "ATDD_PURE_PHASES",
            "QUALITY_GATES",
            "AT_COMPLETION_LEDGER",
            "RECORDING_INTEGRITY",
            "BOUNDARY_RULES",
            "TERMINATING_RUN",
            "TIMEOUT_INSTRUCTION",
        ),
        guard_kind=GuardKind.RED_TO_GREEN,
        feature_readiness=True,
        at_requirement=AtRequirement.REQUIRED,
        skipped_invariants=(),
        annotation_token="bugfix",
        # A bugfix repairs something a user could observe going wrong, so the
        # repaired outcome is chartered. The known over-reach -- a purely
        # internal defect nobody can observe -- is escaped by declaring
        # `des dispatch --charter-exemption "<reason>"`, not by loosening this.
        charter_obligation=CharterObligation.REQUIRED,
    ),
    # The NON-CODE-FACING, PHASELESS cross-wave-child lane
    # (fix-po-charter-dispatch-marker-lane): a spine-MANDATED sub-dispatch of a
    # `nw-product-owner` authoring an expectation charter, issued INSIDE another
    # wave's active floor. It writes no code and records no ATs -> the full 12
    # MINUS the 5 implementation-only sections (the same drop the `review`
    # profile takes). Drift-checked PROJECTION of the dispatch SSOT's
    # `profiles.lane.charter` row, verified by
    # `des.application.dispatch_lane_ssot.check_lane_profile_drift` -- the SAME
    # projection contract the sibling lanes above are held to.
    "charter": LaneProfile(
        lane_id="charter",
        required_sections=(
            "DES_METADATA",
            "AGENT_IDENTITY",
            "SKILL_LOADING",
            "TASK_CONTEXT",
            "DESIGN_CONTEXT",
            "BOUNDARY_RULES",
            "TIMEOUT_INSTRUCTION",
        ),
        guard_kind=GuardKind.NONE,
        feature_readiness=False,
        at_requirement=AtRequirement.EXEMPT,
        skipped_invariants=(
            "slice_plan_section",
            "scenario_slice_tags",
            "reuse_first_or_design_skip",
            # Mirrors the prefactoring lane: a charter dispatch is phaseless,
            # non-code-facing, and writes no design -- it has no Prefactoring
            # Assessment to be held to either (prefactoring-enforcement-wiring).
            "prefactoring_assessment",
            "sustainability",
        ),
        annotation_token="charter",
        # This lane WRITES a charter; it does not owe one. Holding the
        # charter-authoring dispatch to producing a charter for itself is the
        # same circularity its skipped `prefactoring_assessment` names.
        charter_obligation=CharterObligation.EXEMPT,
    ),
}

# The lanes whose dispatch declares NO ``DES-PHASE`` marker at all
# (fix-po-charter-dispatch-marker-lane). Charter authoring is NOT one of the 3
# canonical DELIVER phases -- ``ATDDPurePhase`` stays DELIVER-carpaccio-scoped
# per its own docstring -- so a charter dispatch omits the phase marker rather
# than BORROWING an unrelated phase word (``D_DISTILL``, which specifically
# asserts "the upstream DISTILL-wave acceptance-designer RETURN"). This is the
# ONE definition of "phaseless" every consumer reads: the marker parser's
# coherence check (``classify_atdd_pure_dispatch``), the marker-completeness
# policy, and the ``des dispatch`` generator -- so they cannot drift.
PHASELESS_LANES: frozenset[str] = frozenset({"charter"})
