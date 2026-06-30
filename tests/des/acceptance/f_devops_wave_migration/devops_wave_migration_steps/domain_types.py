"""Typed domain vocabulary for f-devops-wave-migration ATs (Mandate-12 c1).

Every domain noun the Gherkin uses is expressed once here as an enum / typed
constant. The composition root consumes these typed parameters (Mandate-12 c2 —
no raw `str` where an enum exists); step bodies pass them through (c3).

The driving surface is the REAL `des skill-normative-gate` dispatcher subcommand
(Layer-3 subprocess, Mandate-13). f-devops's deliverable is normative prose in
`nw-platform-architect.md` + `nWave/tasks/nw/devops.md` +
`nWave/skills/nw-infrastructure-and-observability/SKILL.md`, plus the Tier-B
DEVOPS advisory wording bound BY REFERENCE to the keystone's
`nw-distill/SKILL.md:727` `## Advisory-Skip-Gate Pattern (Tier-A)` anchor (DESIGN
OB-2). The DESIGN Code-Design is explicit: zero new src/des module — prose +
filesystem only. The gate is the mechanical witness over that prose: a clause
registers a discriminating marker an asset MUST carry; the gate reports PASS
(marker present), FAIL (marker absent), or INDETERMINATE (asset/marker unreadable).

Two induction directions encode this feature's two correspondence classes:

  • PRESENCE clauses (slice-01/02): the f-devops normative markers (gate-IN
    consume + applicability-first, the KPI→telemetry map, 2nd-Way observability
    around KPI signals, the explicit-N/A skip + Tier-B advisory, un-instrumentable-
    KPI→FAIL→redo, the language-agnostic security seam + INDETERMINATE degrade-
    LOUD, and the Tier-B advisory LITERAL wording). These are ABSENT from the
    shipped prose TODAY (not yet migrated), so the gate returns FAIL and the AT —
    which expects PASS — is active-RED. When DELIVER migrates the prose, the gate
    returns PASS and the AT goes green.

  • ABSENCE clause (slice-03): the legacy free-form `/nw-devops` decision-question
    prose (C7/G-1) that exists TODAY and MUST be gone post-migration. Absence is
    the desired end state → the gate returns FAIL (marker absent) → the AT asserts
    FAIL. TODAY the legacy marker is still present → the gate returns PASS → the AT
    (expecting FAIL) is active-RED. When DELIVER removes the legacy prose, the gate
    returns FAIL and the AT goes green.

  • FLOOR clause (slice-03 non-regression): a marker the migrated prose MUST carry
    (the KPI-traced observability wording) — its PRESENCE is the non-regression
    witness that DEVOPS still PASSes on an instrumenting feature after the legacy
    prose is removed. Folded into the same slice-03 run.

Real-Surface Binding (Mandate-13 protocol-driver contract): every marker below is
a multi-word DISCRIMINATING phrase (never a bare common token), authored against
the REAL shipped `nWave/agents/nw-platform-architect.md`, `nWave/tasks/nw/devops.md`,
and `nWave/skills/nw-infrastructure-and-observability/SKILL.md`. The ATs read those
real files via the real gate subprocess — never a fabricated oracle.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


# tests/des/acceptance/f_devops_wave_migration/devops_wave_migration_steps/domain_types.py
#   parents[0]=devops_wave_migration_steps [1]=f_devops_wave_migration
#   [2]=acceptance [3]=des [4]=tests [5]=nWave-dev
REPO_ROOT = Path(__file__).resolve().parents[5]
NW_PLATFORM_ARCHITECT_AGENT = (
    REPO_ROOT / "nWave" / "agents" / "nw-platform-architect.md"
)
NW_DEVOPS_COMMAND = REPO_ROOT / "nWave" / "tasks" / "nw" / "devops.md"
NW_INFRA_OBSERVABILITY_SKILL = (
    REPO_ROOT / "nWave" / "skills" / "nw-infrastructure-and-observability" / "SKILL.md"
)


class Verdict(str, Enum):
    """The closed gate verdict the dispatcher emits (reuses GateVerdict exit codes)."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# Exit-code contract (DESIGN: reuse gate_outcome._EXIT_BY_VERDICT — empirically
# confirmed against the real `des skill-normative-gate` dispatcher:
# PASS→0, FAIL→1, INDETERMINATE→4).
EXIT_BY_VERDICT: dict[Verdict, int] = {
    Verdict.PASS: 0,
    Verdict.FAIL: 1,
    Verdict.INDETERMINATE: 4,
}


class NormativeSurface(str, Enum):
    """A shipped prose surface f-devops migrates (resolves to a real .md asset)."""

    PLATFORM_ARCHITECT_AGENT = "nw-platform-architect"
    DEVOPS_COMMAND = "nw-devops"
    INFRA_OBSERVABILITY_SKILL = "nw-infrastructure-and-observability"


# Resolve a surface to its real shipped asset path (explicit asset per clause).
ASSET_BY_SURFACE: dict[NormativeSurface, Path] = {
    NormativeSurface.PLATFORM_ARCHITECT_AGENT: NW_PLATFORM_ARCHITECT_AGENT,
    NormativeSurface.DEVOPS_COMMAND: NW_DEVOPS_COMMAND,
    NormativeSurface.INFRA_OBSERVABILITY_SKILL: NW_INFRA_OBSERVABILITY_SKILL,
}


class PresenceClause(str, Enum):
    """A f-devops normative marker the migrated prose MUST carry (absent today).

    Each value pairs a stable clause-id (the verdict line names it) with a
    discriminating marker phrase asserted PRESENT in the real shipped surface.
    The clause-id maps 1:1 onto a FINAL-slice-plan AT.
    """

    # slice-01 (walking skeleton) — gate-IN consume + KPI→telemetry + 2nd-Way
    GATE_IN_CONSUME = "devops:gate-in-consume-design-out-and-outcome-kpis"  # AT-1
    KPI_TELEMETRY_MAP = "devops:kpi-to-telemetry-map"  # AT-2
    OBSERVABILITY_AROUND_KPIS = "devops:second-way-around-kpi-signals"  # AT-3
    # slice-02 — explicit N/A skip + un-instrumentable FAIL + security seam +
    # Tier-B advisory literal wording
    EXPLICIT_NA_SKIP = "devops:explicit-na-skip-tier-b-advisory"  # AT-4
    UNINSTRUMENTABLE_KPI_REDO = "devops:un-instrumentable-kpi-fail-redo"  # AT-5
    SECURITY_SEAM_DEGRADE_LOUD = "devops:security-seam-indeterminate-loud"  # AT-6
    TIER_B_ADVISORY_WORDING = "devops:tier-b-advisory-literal-wording"  # AT-7


# The discriminating marker each presence clause registers. Multi-word phrases the
# DELIVER migration must introduce verbatim into the prose (whitespace-normalized
# substring match — the gate requires ≥2 tokens). Grep-verified ABSENT from the
# shipped surface at HEAD (so the gate FAILs → the AT is active-RED today).
PRESENCE_MARKER: dict[PresenceClause, str] = {
    PresenceClause.GATE_IN_CONSUME: (
        "the DEVOPS gate-IN consumes the DESIGN-OUT pass and the DISCUSS outcome "
        "KPIs, running the applicability check first"
    ),
    PresenceClause.KPI_TELEMETRY_MAP: (
        "the platform-architect maps every outcome KPI to a concrete telemetry "
        "signal — a log event, a metric, a trace span, or a golden-signal threshold"
    ),
    PresenceClause.OBSERVABILITY_AROUND_KPIS: (
        "the second-way observability is designed around the outcome-KPI signals, "
        "not generic dashboards untraced to a KPI"
    ),
    PresenceClause.EXPLICIT_NA_SKIP: (
        "a feature with no infra, deploy, or observability delta records an "
        "explicit N/A DEVOPS skip, machine-distinguishable from a present status, "
        "and the Tier-B advisory notifies without blocking"
    ),
    PresenceClause.UNINSTRUMENTABLE_KPI_REDO: (
        "an outcome KPI with no witnessing signal fails the gate at gate-OUT and "
        "is routed to redo in-wave before the wave exits"
    ),
    PresenceClause.SECURITY_SEAM_DEGRADE_LOUD: (
        "the security gate resolves the target toolchain behind a per-language "
        "port and degrades LOUD as INDETERMINATE when the toolchain is "
        "unrecognized, never a silent pass"
    ),
    PresenceClause.TIER_B_ADVISORY_WORDING: (
        "DEVOPS not applicable (no infra/deploy/observability delta) — skipping. "
        "Run `/nw-devops` only if you intend to add instrumentation"
    ),
}

# Which surface each presence clause is asserted against.
SURFACE_BY_PRESENCE: dict[PresenceClause, NormativeSurface] = {
    PresenceClause.GATE_IN_CONSUME: NormativeSurface.PLATFORM_ARCHITECT_AGENT,
    PresenceClause.KPI_TELEMETRY_MAP: NormativeSurface.PLATFORM_ARCHITECT_AGENT,
    PresenceClause.OBSERVABILITY_AROUND_KPIS: (
        NormativeSurface.INFRA_OBSERVABILITY_SKILL
    ),
    PresenceClause.EXPLICIT_NA_SKIP: NormativeSurface.PLATFORM_ARCHITECT_AGENT,
    PresenceClause.UNINSTRUMENTABLE_KPI_REDO: (
        NormativeSurface.PLATFORM_ARCHITECT_AGENT
    ),
    PresenceClause.SECURITY_SEAM_DEGRADE_LOUD: (
        NormativeSurface.INFRA_OBSERVABILITY_SKILL
    ),
    PresenceClause.TIER_B_ADVISORY_WORDING: (NormativeSurface.PLATFORM_ARCHITECT_AGENT),
}


class LegacyClause(str, Enum):
    """A legacy free-form `/nw-devops` decision-question marker, gone post-migration.

    ABSENCE is the desired end state (C7/G-1): the migrated `/nw-devops` derives
    observability from the outcome KPIs, so the free-form deployment-target /
    orchestrator / CI-platform decision-question prose is removed/reconciled. The
    gate FAILs when this marker is absent → the AT asserts FAIL. Present today →
    gate PASSes → the AT (expecting FAIL-on-absence) is active-RED.
    """

    FREE_FORM_DECISION_QUESTIONS = "legacy:free-form-decision-questions"


# The legacy phrase grep-verified PRESENT at HEAD (so the gate PASSes → the AT,
# which expects FAIL-on-absence, is active-RED today). DELIVER removes/reconciles
# the devops.md:18-90 free-form decision-question block (C7/G-1).
LEGACY_MARKER: dict[LegacyClause, str] = {
    LegacyClause.FREE_FORM_DECISION_QUESTIONS: ("What is the deployment target?"),
}

SURFACE_BY_LEGACY: dict[LegacyClause, NormativeSurface] = {
    LegacyClause.FREE_FORM_DECISION_QUESTIONS: NormativeSurface.DEVOPS_COMMAND,
}


class FloorClause(str, Enum):
    """A migrated marker that MUST be present post-migration (C7 non-regression).

    The non-regression witness folded into slice-03: after the legacy free-form
    decision-question prose is removed, DEVOPS on an instrumenting feature must
    still reach a KPI-traced gate-OUT. The KPI→telemetry-map marker's PRESENCE is
    that witness. TODAY it is ABSENT (the migration has not run) → the gate FAILs
    → the floor AT (expecting PASS) is active-RED, and goes green exactly when the
    same DELIVER migration that lands slice-01/02 also makes slice-03's removal
    safe. The floor clause reuses the slice-01 KPI→telemetry marker (single SSOT
    phrase) so the non-regression witness is the very behaviour slice-01 introduces.
    """

    KPI_TRACED_OBSERVABILITY = "floor:kpi-traced-observability-preserved"


# The floor marker reuses the slice-01 KPI→telemetry-map phrase (SSOT — one
# discriminating phrase, two roles: slice-01 PRESENCE driver + slice-03
# non-regression witness). PRESENT post-migration ⇒ DEVOPS still instruments.
FLOOR_MARKER: dict[FloorClause, str] = {
    FloorClause.KPI_TRACED_OBSERVABILITY: PRESENCE_MARKER[
        PresenceClause.KPI_TELEMETRY_MAP
    ],
}

SURFACE_BY_FLOOR: dict[FloorClause, NormativeSurface] = {
    FloorClause.KPI_TRACED_OBSERVABILITY: NormativeSurface.PLATFORM_ARCHITECT_AGENT,
}


class DeadMechanism(str, Enum):
    """The two ways the gate mechanism cannot run → INDETERMINATE (security-seam
    degrade-LOUD analogue, AT-6 guardrail; KPI-4)."""

    ASSET_ABSENT = "asset-absent"  # the referenced surface does not exist on disk
    ASSET_UNDECODABLE = "asset-undecodable"  # the surface exists but is not UTF-8
