"""Typed domain vocabulary for f-deliver-wave-migration ATs (Mandate-12 c1).

Every domain noun the Gherkin uses is expressed once here as an enum / typed
constant. The composition root consumes these typed parameters (Mandate-12 c2 —
no raw `str` where an enum exists); step bodies pass them through (c3).

The driving surface is the REAL `des skill-normative-gate` dispatcher subcommand
(Layer-3 subprocess, Mandate-13). f-deliver's deliverable is normative PROSE —
the crafter-matches-design contract language migrated into
`nWave/agents/nw-software-crafter.md` + `nWave/agents/nw-functional-software-crafter.md`
+ `nWave/tasks/nw/deliver.md` + the crafter skill `nWave/skills/nw-tdd-methodology/SKILL.md`.
The DESIGN Code-Design is explicit (`feature-delta.md:721-730`): **zero new
`src/des` module, zero new GateVerdict, zero new parser** — prose + filesystem
only. The mechanical ConformanceDiff (public-surface AST diff) is
**DESIGNED-NOT-BUILT** and OWNED by feature 6 (`f-coherence-and-attestation`,
the `CodeFactPort AstAdapter`; DESIGN OB-1 → option (b)/(c), `feature-delta.md:573`).
THESE ATs DO NOT build or test a conformance engine. They drive `des
skill-normative-gate` over the shipped DELIVER prose and assert that the prose
CONTRACT *declares* the discipline.

The gate is the mechanical witness over that prose: a clause registers a
DISCRIMINATING marker (≥2 whitespace-normalized tokens) an asset MUST carry; the
gate reports PASS (marker present, exit 0), FAIL (marker absent, exit 1), or
INDETERMINATE (asset/marker unreadable, exit 4). Empirically confirmed against
the real dispatcher (`src/des/cli/skill_normative_gate.py`,
`src/des/domain/gate_outcome.py:68`).

Two induction directions encode this feature's two correspondence classes:

  • PRESENCE clauses (slice-01/02 + the slice-03 FLOOR): the f-deliver
    crafter-matches-design markers (bundle-consume + implement-matching, the
    public-surface ConformanceDiff PASS, the private-refactor-freedom guardrail,
    the undeclared/missing-public-symbol FAIL→redo, the K5 DESIGN-DEFECT bump, the
    INDETERMINATE degrade-LOUD, the language-agnostic per-language AST seam). These
    are ABSENT from the shipped prose TODAY (not yet migrated), so the gate returns
    FAIL and the AT — which expects PASS — is active-RED. When DELIVER migrates the
    prose, the gate returns PASS and the AT goes green.

  • ABSENCE clause (slice-03): the legacy "implement minimum code that turns all
    ATs from RED to GREEN" wording (C9/G-1) that frames implementation purely as
    AT-satisfaction with NO bundle-consume / matches-design-conformance step — it
    exists TODAY and MUST be reconciled away post-migration. Absence is the desired
    end state → the gate returns FAIL (marker absent) → the AT asserts FAIL. Present
    today → gate PASSes → the AT (expecting FAIL) is active-RED. DELIVER reconciles
    the prose → FAIL → green.

The INDETERMINATE guardrail (AT-6) is also witnessed directly: a clause is
registered against an UNREADABLE asset so the gate degrades LOUD to INDETERMINATE
(exit 4) by construction — the §17 "mechanism could not run ⇒ degrade-LOUD, never
a silent pass" row (KPI-4).

Real-Surface Binding (Mandate-13 protocol-driver contract): every marker below is
a multi-word DISCRIMINATING phrase (never a bare common token), authored against
the REAL shipped surfaces. The ATs read those real files via the real gate
subprocess — never a fabricated oracle.

Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared driving-surface seam
for this feature is the `des skill-normative-gate` mechanical witness over the
crafter prose. The OB-1 crafter-matches-design SEAM + the OB-2 K5 named-contradiction
witness + the C7/C8 language-agnostic AST seam are DESIGN-declared PROSE seams
(`feature-delta.md:573-718` OB-1/OB-2; `:627-637` the seam table); AT-5 and AT-7
each name THAT exact seam (a discriminating marker) and witness it through the
real gate. No seam is left dormant.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


# tests/des/acceptance/deliver_wave_migration/deliver_wave_migration_steps/domain_types.py
#   parents[0]=deliver_wave_migration_steps [1]=deliver_wave_migration
#   [2]=acceptance [3]=des [4]=tests [5]=nWave-dev
REPO_ROOT = Path(__file__).resolve().parents[5]
NW_SOFTWARE_CRAFTER_AGENT = REPO_ROOT / "nWave" / "agents" / "nw-software-crafter.md"
NW_FUNCTIONAL_SOFTWARE_CRAFTER_AGENT = (
    REPO_ROOT / "nWave" / "agents" / "nw-functional-software-crafter.md"
)
NW_DELIVER_COMMAND = REPO_ROOT / "nWave" / "tasks" / "nw" / "deliver.md"
NW_TDD_METHODOLOGY_SKILL = (
    REPO_ROOT / "nWave" / "skills" / "nw-tdd-methodology-cycle" / "SKILL.md"
)


class Verdict(str, Enum):
    """The closed gate verdict the dispatcher emits (reuses GateVerdict exit codes)."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# Exit-code contract — empirically confirmed against the real `des
# skill-normative-gate` dispatcher (`src/des/domain/gate_outcome.py:68`):
# PASS→0, FAIL→1, INDETERMINATE→4. The §17 five-verdict GateVerdict SSOT is
# REUSED unchanged (DESIGN C6: no sixth verdict; `feature-delta.md:788`).
EXIT_BY_VERDICT: dict[Verdict, int] = {
    Verdict.PASS: 0,
    Verdict.FAIL: 1,
    Verdict.INDETERMINATE: 4,
}


class NormativeSurface(str, Enum):
    """A shipped prose surface f-deliver migrates (resolves to a real .md asset)."""

    SOFTWARE_CRAFTER_AGENT = "nw-software-crafter"
    FUNCTIONAL_SOFTWARE_CRAFTER_AGENT = "nw-functional-software-crafter"
    DELIVER_COMMAND = "nw-deliver"
    TDD_METHODOLOGY_SKILL = "nw-tdd-methodology"


# Resolve a surface to its real shipped asset path (explicit asset per clause).
ASSET_BY_SURFACE: dict[NormativeSurface, Path] = {
    NormativeSurface.SOFTWARE_CRAFTER_AGENT: NW_SOFTWARE_CRAFTER_AGENT,
    NormativeSurface.FUNCTIONAL_SOFTWARE_CRAFTER_AGENT: (
        NW_FUNCTIONAL_SOFTWARE_CRAFTER_AGENT
    ),
    NormativeSurface.DELIVER_COMMAND: NW_DELIVER_COMMAND,
    NormativeSurface.TDD_METHODOLOGY_SKILL: NW_TDD_METHODOLOGY_SKILL,
}


class PresenceClause(str, Enum):
    """A f-deliver crafter-matches-design marker the migrated prose MUST carry
    (absent today).

    Each value pairs a stable clause-id (the verdict line names it) with a
    discriminating marker phrase asserted PRESENT in the real shipped surface.
    The clause-id maps 1:1 onto a FINAL-slice-plan AT
    (`feature-delta.md:880-889`).
    """

    # slice-01 (walking skeleton) — bundle-consume + matches-design PASS + private freedom
    BUNDLE_CONSUME_IMPLEMENT_MATCHING = (
        "deliver:bundle-consume-implement-matching"  # AT-1
    )
    MATCHES_DESIGN_PUBLIC_SURFACE = (
        "deliver:matches-design-public-surface-conforms"  # AT-2
    )
    PRIVATE_REFACTOR_FREEDOM = (
        "deliver:private-refactor-extract-method-not-flagged"  # AT-3
    )
    # slice-02 — divergence FAIL→redo + K5 bump + INDETERMINATE degrade + language-agnostic seam
    UNDECLARED_PUBLIC_SYMBOL_REDO = (
        "deliver:undeclared-or-missing-public-symbol-redo"  # AT-4
    )
    DESIGN_DEFECT_BUMP = "deliver:design-defect-bump-to-design-human-disposes"  # AT-5
    MATCHES_DESIGN_INDETERMINATE_LOUD = (
        "deliver:matches-design-indeterminate-degrade-loud"  # AT-6
    )
    LANGUAGE_AGNOSTIC_AST_SEAM = (
        "deliver:language-agnostic-public-surface-ast-seam"  # AT-7
    )


# The discriminating marker each presence clause registers. Multi-word phrases the
# DELIVER migration must introduce verbatim into the prose (whitespace-normalized
# substring match — the gate requires ≥2 tokens). Grep-verified ABSENT from the
# shipped surfaces at HEAD (so the gate FAILs → the AT is active-RED today).
PRESENCE_MARKER: dict[PresenceClause, str] = {
    PresenceClause.BUNDLE_CONSUME_IMPLEMENT_MATCHING: (
        "the crafter consumes the bundle the AT set the code-design contract and "
        "the architecture and implements matching the declared structure"
    ),
    PresenceClause.MATCHES_DESIGN_PUBLIC_SURFACE: (
        "the crafter-matches-design gate compares the implementation public "
        "surface against the design declared public contract"
    ),
    PresenceClause.PRIVATE_REFACTOR_FREEDOM: (
        "a new private symbol or Extract-Method refactor below the public boundary "
        "is never flagged as a conformance violation"
    ),
    PresenceClause.UNDECLARED_PUBLIC_SYMBOL_REDO: (
        "an undeclared public symbol or a missing declared one fails the gate at "
        "gate-OUT and is routed to redo in-wave"
    ),
    PresenceClause.DESIGN_DEFECT_BUMP: (
        "a named contract self-contradiction routes a recorded DESIGN-DEFECT bump "
        "to DESIGN that the human disposes instead of being patched in place"
    ),
    PresenceClause.MATCHES_DESIGN_INDETERMINATE_LOUD: (
        "the crafter-matches-design mechanism that cannot run degrades LOUD as "
        "INDETERMINATE never a silent pass"
    ),
    PresenceClause.LANGUAGE_AGNOSTIC_AST_SEAM: (
        "the public-surface inspection is resolved behind a per-language AST port "
        "reusing the CodeFactPort adapter family"
    ),
}

# Which surface each presence clause is asserted against. The crafter-agent +
# deliver-command carry the gate-IN/gate-OUT prose; the FP-crafter mirrors the
# matches-design posture; the TDD skill carries the GREEN/refactor discipline.
SURFACE_BY_PRESENCE: dict[PresenceClause, NormativeSurface] = {
    PresenceClause.BUNDLE_CONSUME_IMPLEMENT_MATCHING: (
        NormativeSurface.SOFTWARE_CRAFTER_AGENT
    ),
    PresenceClause.MATCHES_DESIGN_PUBLIC_SURFACE: NormativeSurface.DELIVER_COMMAND,
    PresenceClause.PRIVATE_REFACTOR_FREEDOM: (NormativeSurface.TDD_METHODOLOGY_SKILL),
    PresenceClause.UNDECLARED_PUBLIC_SYMBOL_REDO: NormativeSurface.DELIVER_COMMAND,
    PresenceClause.DESIGN_DEFECT_BUMP: NormativeSurface.DELIVER_COMMAND,
    PresenceClause.MATCHES_DESIGN_INDETERMINATE_LOUD: (
        NormativeSurface.DELIVER_COMMAND
    ),
    PresenceClause.LANGUAGE_AGNOSTIC_AST_SEAM: (
        NormativeSurface.FUNCTIONAL_SOFTWARE_CRAFTER_AGENT
    ),
}


class LegacyClause(str, Enum):
    """A legacy AT-satisfaction-only marker, gone/reconciled post-migration.

    ABSENCE is the desired end state (C9/G-1): the migrated crafter prose frames
    implementation as bundle-consume + matches-design (public-surface conformance),
    so the legacy "implement minimum code that turns all ATs from RED to GREEN"
    wording — which describes implementation purely as AT-satisfaction with NO
    design-contract conformance step — is reconciled. The gate FAILs when this
    marker is absent → the AT asserts FAIL. Present today → gate PASSes → the AT
    (expecting FAIL-on-absence) is active-RED.
    """

    AT_SATISFACTION_ONLY = "legacy:at-satisfaction-only-no-matches-design"


# The legacy phrase grep-verified PRESENT at HEAD (so the gate PASSes → the AT,
# which expects FAIL-on-absence, is active-RED today). DELIVER reconciles the
# nw-software-crafter.md A_GREEN_ATS step (`:104`) to add the bundle-consume +
# matches-design conformance step, removing the AT-satisfaction-only framing.
LEGACY_MARKER: dict[LegacyClause, str] = {
    LegacyClause.AT_SATISFACTION_ONLY: (
        "Implement the minimum production code that turns all ATs from RED to GREEN"
    ),
}

SURFACE_BY_LEGACY: dict[LegacyClause, NormativeSurface] = {
    LegacyClause.AT_SATISFACTION_ONLY: NormativeSurface.SOFTWARE_CRAFTER_AGENT,
}


class FloorClause(str, Enum):
    """A migrated marker that MUST be present post-migration (C9 non-regression).

    The non-regression witness folded into slice-03: after the legacy
    AT-satisfaction-only wording is reconciled, the crafter on a CONFORMING feature
    must still reach a matches-design gate-OUT PASS — the matches-design leg is
    PRESENT, not re-broken. The matches-design public-surface marker's PRESENCE is
    that witness. TODAY it is ABSENT (the migration has not run) → the gate FAILs →
    the floor AT (expecting PASS) is active-RED, and goes green exactly when the
    same DELIVER migration that lands slice-01/02 also makes slice-03's removal
    safe. The floor clause reuses the slice-01 matches-design marker (single SSOT
    phrase) so the non-regression witness is the very behaviour slice-01 introduces.
    """

    MATCHES_DESIGN_PRESERVED = "floor:matches-design-leg-preserved"


# The floor marker reuses the slice-01 matches-design-public-surface phrase (SSOT
# — one discriminating phrase, two roles: slice-01 PRESENCE driver + slice-03
# non-regression witness). PRESENT post-migration ⇒ DELIVER still conforms.
FLOOR_MARKER: dict[FloorClause, str] = {
    FloorClause.MATCHES_DESIGN_PRESERVED: PRESENCE_MARKER[
        PresenceClause.MATCHES_DESIGN_PUBLIC_SURFACE
    ],
}

SURFACE_BY_FLOOR: dict[FloorClause, NormativeSurface] = {
    FloorClause.MATCHES_DESIGN_PRESERVED: NormativeSurface.DELIVER_COMMAND,
}


class DeadMechanism(str, Enum):
    """The two ways the gate mechanism cannot run → INDETERMINATE (the
    matches-design degrade-LOUD analogue, AT-6 guardrail; KPI-4)."""

    ASSET_ABSENT = "asset-absent"  # the referenced surface does not exist on disk
    ASSET_UNDECODABLE = "asset-undecodable"  # the surface exists but is not UTF-8
