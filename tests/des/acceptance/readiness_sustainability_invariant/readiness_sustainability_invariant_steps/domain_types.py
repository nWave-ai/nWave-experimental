"""Domain types for the readiness SUSTAINABILITY-invariant (invariant 7) ATs.

Mandate-12 criterion 1 (SSOT + Zero Duplication via Types): every domain noun
used in the Gherkin is expressed once here as a typed enum. Step bodies and the
ReadinessSustainabilityComposition service consume these typed parameters -- no
raw `str` where a domain enum exists.

The wiring under test EXTENDS `src/des/cli/verify_readiness_pre_dispatch.py` with
a 7th invariant `sustainability` mirroring the existing 6th `reuse_first_or_design_skip`.
Invariant 6 already calls `validate_reuse_analysis_content`; invariant 7 calls
`validate_sustainability_content` (the slice-03 pure-core function) on the
feature-delta, FAILING readiness when the `## Test Reuse & Consolidation Analysis`
section is declared-but-missing/malformed.

Driving port (Mandate-13, S2 driving-port-only): the public
`des verify-readiness-pre-dispatch` CLI subcommand (Layer 3 subprocess). The
composition NEVER imports the gate module directly.

S1 step-text uniqueness: every Gherkin literal in this feature is
sustainability/invariant-7-specific and DISTINCT from the
`readiness_reuse_invariant` package literals AND from the sustainable-test-suite
slice-01..05 literals (those drive `validate-feature-delta` directly; these drive
the readiness aggregate and speak of "the readiness gate" + "the sustainability
readiness dimension").
"""

from __future__ import annotations

from enum import Enum


class ReadinessVerdict(str, Enum):
    """The public readiness gate verdict -- one of two terminal shapes.

    CLEARED -- every readiness invariant satisfied; dispatch proceeds.
    REFUSED -- at least one readiness invariant failed; the combined diagnostic
               lists every failure.
    """

    CLEARED = "cleared"
    REFUSED = "refused"


class InvariantStatus(str, Enum):
    """The status of a single readiness invariant within the diagnostic."""

    SATISFIED = "satisfied"
    FAILED = "failed"


class ReadinessInvariantId(str, Enum):
    """The readiness invariants the gate verifies.

    The first five are the pre-existing cascade (friction #57 + the reuse-first
    slice). SUSTAINABILITY is a net-new invariant the gate-wiring step adds --
    additive to the same single-invocation aggregate (the friction #57
    single-JSON-line contract preserved). The id literal the gate emits is
    EXPECTED to be `sustainability`; the typed projection tolerates its absence
    at HEAD (active-RED: the 7th invariant does not yet exist).

    NOTE (fix-readiness-carpaccio-disagree): this enum used to also carry an
    `AT_REVIEW_VERDICT = "at_review_verdict"` member -- unused by any step or
    assertion in this AT scope (grep-confirmed inert), removed alongside the
    gate's own deletion of that invariant so the mirror carries no orphan id.
    """

    SLICE_PLAN_SECTION = "slice_plan_section"
    SCENARIO_SLICE_TAGS = "scenario_slice_tags"
    GATE_OUTPUT_PRODUCEABLE = "gate_output_produceable"
    PRE_COMMIT_SCOPE = "pre_commit_scope"
    REUSE_FIRST = "reuse_first_or_design_skip"
    SUSTAINABILITY = "sustainability"


class SustainabilitySectionShape(str, Enum):
    """The `## Test Reuse & Consolidation Analysis` section shape the AT arms.

    Drives the `validate_sustainability_content` verdict the 7th invariant
    consumes (the slice-03 pure-core function; verdict -> satisfied/failed
    mapping mirrors invariant 6's reuse-leg).

    WELL_FORMED        -- a well-formed five-column table with a valid Decision
                          row (validator verdict: structurally-accepted ->
                          satisfied).
    METHODOLOGY_EXEMPT -- a `Test-Reuse-Analysis: methodology-exempt` marker
                          (validator verdict: methodology-exempt -> satisfied).
    ABSENT             -- no `## Test Reuse & Consolidation Analysis` section
                          (validator verdict: missing-sustainability-section ->
                          failed). The DECLARED-BUT-MISSING must-block case.
    MALFORMED          -- a present-but-broken table (wrong columns) (validator
                          verdict: malformed-sustainability-section -> failed).
    """

    WELL_FORMED = "well_formed"
    METHODOLOGY_EXEMPT = "methodology_exempt"
    ABSENT = "absent"
    MALFORMED = "malformed"


# Gherkin-phrase -> typed-value lookups. Module-scoped so each step body stays a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

SUSTAINABILITY_SHAPE_BY_PHRASE: dict[str, SustainabilitySectionShape] = {
    "a well-formed sustainability section": SustainabilitySectionShape.WELL_FORMED,
    "a methodology-exempt sustainability marker": (
        SustainabilitySectionShape.METHODOLOGY_EXEMPT
    ),
    "no sustainability section": SustainabilitySectionShape.ABSENT,
    "a malformed sustainability section": SustainabilitySectionShape.MALFORMED,
}
