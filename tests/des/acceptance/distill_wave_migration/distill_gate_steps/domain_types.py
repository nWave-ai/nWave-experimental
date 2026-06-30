"""Typed domain vocabulary for f-distill-wave-migration ATs (Mandate-12 c1).

Every domain noun the Gherkin uses is expressed once here as an enum / typed
constant. The composition root consumes these typed parameters (Mandate-12 c2 —
no raw `str` where an enum exists); step bodies pass them through (c3).

The driving surface is the REAL `des skill-normative-gate` dispatcher subcommand
(Layer-3 subprocess, Mandate-13). f-distill's deliverable is normative prose in
`nw-distill/SKILL.md` + `nw-acceptance-designer.md` (DESIGN: zero new src/des
module). The gate is the mechanical witness over that prose: a clause registers a
discriminating marker an asset MUST carry; the gate reports PASS (marker present),
FAIL (marker absent), or INDETERMINATE (asset/marker unreadable).

Two induction directions encode this feature's two correspondence classes:

  • PRESENCE clauses (slice-01/02): the f-distill normative markers (the 3-source
    induction map, the gate-G review-rubric, the §17 verdict mapping, active-RED-
    never-@skip). These are ABSENT from the shipped prose TODAY (not yet migrated),
    so the gate returns FAIL and the AT — which expects PASS — is active-RED. When
    DELIVER migrates the prose, the gate returns PASS and the AT goes green.

  • ABSENCE clauses (slice-03): the legacy NON-inducing AT-authoring marker that
    exists TODAY and MUST be gone post-migration (C8/G-1/G-3). Absence is the
    desired end state → the gate returns FAIL (marker absent) → the AT asserts FAIL.
    TODAY the legacy marker is still present → the gate returns PASS → the AT
    (expecting FAIL) is active-RED. When DELIVER removes the legacy prose, the gate
    returns FAIL and the AT goes green.

Real-Surface Binding (Mandate-13 protocol-driver contract): every marker below is
a multi-word DISCRIMINATING phrase (never a bare common token), authored against
the REAL shipped `nWave/skills/nw-distill/SKILL.md` and `nWave/agents/
nw-acceptance-designer.md`. The ATs read those real files via the real gate
subprocess — never a fabricated oracle.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


# tests/des/acceptance/distill_wave_migration/distill_gate_steps/domain_types.py
#   parents[0]=distill_gate_steps [1]=distill_wave_migration [2]=acceptance
#   [3]=des [4]=tests [5]=nWave-dev
REPO_ROOT = Path(__file__).resolve().parents[5]
NW_DISTILL_SKILL = REPO_ROOT / "nWave" / "skills" / "nw-distill" / "SKILL.md"
NW_ACCEPTANCE_DESIGNER_AGENT = (
    REPO_ROOT / "nWave" / "agents" / "nw-acceptance-designer.md"
)


class Verdict(str, Enum):
    """The closed gate verdict the dispatcher emits (reuses GateVerdict exit codes)."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# Exit-code contract (DESIGN: reuse gate_outcome._EXIT_BY_VERDICT — empirically
# confirmed against the real `des skill-normative-gate` dispatcher).
EXIT_BY_VERDICT: dict[Verdict, int] = {
    Verdict.PASS: 0,
    Verdict.FAIL: 1,
    Verdict.INDETERMINATE: 4,
}


class NormativeSurface(str, Enum):
    """A shipped prose surface f-distill migrates (resolves to a real .md asset)."""

    DISTILL_SKILL = "nw-distill"  # nWave/skills/nw-distill/SKILL.md
    ACCEPTANCE_DESIGNER_AGENT = (
        "nw-acceptance-designer"  # the agent .md (explicit asset)
    )


# Resolve a surface to its real shipped asset path.
ASSET_BY_SURFACE: dict[NormativeSurface, Path] = {
    NormativeSurface.DISTILL_SKILL: NW_DISTILL_SKILL,
    NormativeSurface.ACCEPTANCE_DESIGNER_AGENT: NW_ACCEPTANCE_DESIGNER_AGENT,
}


class PresenceClause(str, Enum):
    """A f-distill normative marker the migrated prose MUST carry (absent today).

    Each value pairs a stable clause-id (the verdict line names it) with a
    discriminating marker phrase asserted PRESENT in the real shipped surface.
    """

    # slice-01 — the 3-source induction map (the gate-IN consume + author activity)
    INDUCTION_MAP = "induction:three-source-map"
    EXAMPLE_TABLE_BIJECTION = "induction:example-table-scenario-bijection"
    CONTRACT_SHAPE_TREATMENT = "induction:contract-shape-treatment"
    SLICE_PLAN_ACTIVE_RED = "induction:slice-plan-active-red"
    # slice-02 — the gate-OUT coherence rubric + §17 verdict mapping
    DEVOPS_INDUCED_FIRST_CLASS = "coherence:devops-induced-first-class"
    NO_COUPLING_UNVERIFIED = "coherence:no-coupling-unverified-branch"
    GATE_G_REVIEW_RUBRIC = "coherence:gate-g-review-rubric"
    INDETERMINATE_DEGRADE_LOUD = "coherence:indeterminate-degrade-loud"


# The discriminating marker each presence clause registers. Multi-word phrases the
# DELIVER migration must introduce verbatim into the prose (whitespace-normalized
# substring match — `nw-distill` requires ≥2 tokens). Grep-verified ABSENT from the
# shipped surface at HEAD (so the gate FAILs → the AT is active-RED today).
PRESENCE_MARKER: dict[PresenceClause, str] = {
    PresenceClause.INDUCTION_MAP: (
        "the acceptance-designer induces the acceptance tests from the design contract"
    ),
    PresenceClause.EXAMPLE_TABLE_BIJECTION: (
        "every example-table row maps to exactly one Given-When-Then scenario"
    ),
    PresenceClause.CONTRACT_SHAPE_TREATMENT: (
        "a declared law induces at least one property test; "
        "a declared error-encoding induces a sad-path scenario"
    ),
    PresenceClause.SLICE_PLAN_ACTIVE_RED: (
        "ATs are scaffolded per-slice per the Slice Plan enumeration, "
        "active-RED never skipped"
    ),
    PresenceClause.DEVOPS_INDUCED_FIRST_CLASS: (
        "DEVOPS-induced scenarios are first-class and trace to the DEVOPS status, "
        "not to a missing design row"
    ),
    PresenceClause.NO_COUPLING_UNVERIFIED: (
        "an AT coupling to a port-shaped surface not yet on the contract "
        "is UNVERIFIED, never a silent pass"
    ),
    PresenceClause.GATE_G_REVIEW_RUBRIC: (
        "the gate-G review-rubric witnesses the design to AT coherence at "
        "DISTILL gate-OUT"
    ),
    PresenceClause.INDETERMINATE_DEGRADE_LOUD: (
        "when the coherence mechanism cannot run the verdict is INDETERMINATE, "
        "degrade-LOUD, never a false green"
    ),
}

# Which surface each presence clause is asserted against.
SURFACE_BY_PRESENCE: dict[PresenceClause, NormativeSurface] = {
    PresenceClause.INDUCTION_MAP: NormativeSurface.DISTILL_SKILL,
    PresenceClause.EXAMPLE_TABLE_BIJECTION: NormativeSurface.DISTILL_SKILL,
    PresenceClause.CONTRACT_SHAPE_TREATMENT: NormativeSurface.DISTILL_SKILL,
    PresenceClause.SLICE_PLAN_ACTIVE_RED: NormativeSurface.DISTILL_SKILL,
    PresenceClause.DEVOPS_INDUCED_FIRST_CLASS: NormativeSurface.DISTILL_SKILL,
    PresenceClause.NO_COUPLING_UNVERIFIED: NormativeSurface.DISTILL_SKILL,
    PresenceClause.GATE_G_REVIEW_RUBRIC: NormativeSurface.DISTILL_SKILL,
    PresenceClause.INDETERMINATE_DEGRADE_LOUD: NormativeSurface.DISTILL_SKILL,
}


class LegacyClause(str, Enum):
    """A legacy NON-inducing AT-authoring marker that MUST be gone post-migration.

    ABSENCE is the desired end state (C8/G-1/G-3): the migrated prose authors ATs
    by INDUCING from the design contract, so the author-from-scratch-taxonomy
    wording is removed/reconciled. The gate FAILs when this marker is absent → the
    AT asserts FAIL. Present today → gate PASSes → the AT (expecting FAIL) is
    active-RED.
    """

    NON_INDUCING_AT_AUTHORING = "legacy:non-inducing-at-authoring"


# The legacy phrase grep-verified PRESENT at HEAD (so the gate PASSes → the AT,
# which expects FAIL-on-absence, is active-RED today). DELIVER removes/reconciles it.
LEGACY_MARKER: dict[LegacyClause, str] = {
    # nw-distill SKILL.md:856 (Scenario Writing Guidelines — the non-inducing
    # author-from-scratch wording with NO induction-from-[REF] Code-Design step).
    LegacyClause.NON_INDUCING_AT_AUTHORING: (
        "DISTILL creates the walking-skeleton scenarios itself, "
        "before milestone features"
    ),
}

SURFACE_BY_LEGACY: dict[LegacyClause, NormativeSurface] = {
    LegacyClause.NON_INDUCING_AT_AUTHORING: NormativeSurface.DISTILL_SKILL,
}


class FloorClause(str, Enum):
    """A keystone-reconciled marker that MUST remain present (C7/G-4 non-regression).

    The keystone (f-design-wave-migration, CLOSED) reconciled the DESIGN-absent
    BLOCK to an advisory. f-distill EXTENDS that floor and MUST NOT regress it: the
    advisory wording stays present (gate PASS). This is a PRESENT-and-stays-present
    floor — the AT asserts PASS and stays green across the migration (it pins the
    floor against regression, not a behaviour change).
    """

    DESIGN_ABSENT_ADVISORY = "floor:design-absent-advisory"


# The keystone-reconciled advisory phrase, grep-verified PRESENT at HEAD. It MUST
# stay present after f-distill's edits (C7). For active-RED today this clause is
# NOT the RED driver — slice-03's RED comes from the LEGACY-absence leg; the floor
# clause is the non-regression witness folded into the same slice run.
FLOOR_MARKER: dict[FloorClause, str] = {
    FloorClause.DESIGN_ABSENT_ADVISORY: (
        "DESIGN-absence is surfaced via the advisory soft-gate, never a block"
    ),
}

SURFACE_BY_FLOOR: dict[FloorClause, NormativeSurface] = {
    FloorClause.DESIGN_ABSENT_ADVISORY: NormativeSurface.DISTILL_SKILL,
}


class DeadMechanism(str, Enum):
    """The two ways the coherence mechanism cannot run → INDETERMINATE (AT-8)."""

    ASSET_ABSENT = "asset-absent"  # the referenced surface does not exist on disk
    ASSET_UNDECODABLE = "asset-undecodable"  # the surface exists but is not UTF-8
