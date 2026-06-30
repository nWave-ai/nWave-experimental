"""Domain types for the fix-readiness-gate-reuse-first-invariant ATs.

Mandate-12 criterion 1 (SSOT + Zero Duplication via Types + Services + DSL):
every domain noun used in the Gherkin is expressed once here as a typed enum
or NewType. Step bodies and the ReadinessReuseComposition service consume
these typed parameters -- no raw `str` where a domain enum exists.

The feature EXTENDS `src/des/cli/verify_readiness_pre_dispatch.py` with a 6th
invariant `reuse_first_or_design_skip`. A feature that SKIPS the optional
DESIGN wave must not reach its first crafter dispatch carrying NO reuse-first
analysis: the readiness gate REFUSES a feature-delta carrying neither a
`## Reuse Analysis` section nor a `## Wave: DESIGN / [REF] Design Skipped`
witness. The 6th invariant is satisfied iff EITHER a valid Reuse Analysis is
present OR the DESIGN-skip witness is present.

The driving port (Mandate-13, S2 driving-port-only) is the public
`des verify-readiness-pre-dispatch` CLI subcommand (Layer 3 subprocess).
The composition NEVER imports the gate module directly.
"""

from __future__ import annotations

from enum import Enum


# A feature identifier (the `--feature-id` the readiness gate is invoked with).
# Kept as a closed enum so step bodies + composition methods stay typed; each
# value names the workspace shape the AT arms.
class ReadinessVerdict(str, Enum):
    """The public readiness gate verdict -- one of two terminal shapes.

    CLEARED -- every first-dispatch invariant satisfied; dispatch proceeds.
    REFUSED -- at least one first-dispatch invariant failed; the combined
               diagnostic lists every failure.
    """

    CLEARED = "cleared"
    REFUSED = "refused"


class InvariantStatus(str, Enum):
    """The status of a single first-dispatch invariant within the diagnostic.

    SATISFIED -- the invariant holds for this workspace.
    FAILED    -- the invariant does not hold; remediation accompanies the entry.
    """

    SATISFIED = "satisfied"
    FAILED = "failed"


class FirstDispatchInvariantId(str, Enum):
    """The first-dispatch invariants the readiness gate verifies.

    The first five are the pre-existing cascade (friction #57). REUSE_FIRST is
    the net-new 6th invariant this feature adds -- additive to the same
    single-invocation aggregate (friction #57 single-JSON-line contract
    preserved). The id literal MUST match the gate's `_INV_REUSE_FIRST`
    constant value `reuse_first_or_design_skip`.
    """

    SLICE_PLAN_SECTION = "slice_plan_section"
    SCENARIO_SLICE_TAGS = "scenario_slice_tags"
    AT_REVIEW_VERDICT = "at_review_verdict"
    GATE_OUTPUT_PRODUCEABLE = "gate_output_produceable"
    PRE_COMMIT_SCOPE = "pre_commit_scope"
    REUSE_FIRST = "reuse_first_or_design_skip"


# The five PRE-EXISTING invariants -- the slice-01 contract asserts these stay
# unchanged when the additive 6th invariant lands.
PRE_EXISTING_INVARIANTS: tuple[FirstDispatchInvariantId, ...] = (
    FirstDispatchInvariantId.SLICE_PLAN_SECTION,
    FirstDispatchInvariantId.SCENARIO_SLICE_TAGS,
    FirstDispatchInvariantId.AT_REVIEW_VERDICT,
    FirstDispatchInvariantId.GATE_OUTPUT_PRODUCEABLE,
    FirstDispatchInvariantId.PRE_COMMIT_SCOPE,
)


class ReuseAnalysisShape(str, Enum):
    """The Reuse Analysis section shape the AT arms into the feature-delta.

    Drives the `validate_reuse_analysis_content` verdict the 6th invariant
    consumes (verdict -> present/absent mapping fixed in DESIGN Code-Design).

    ABSENT             -- no `## Reuse Analysis` section at all
                          (validator verdict: missing-reuse-analysis -> ABSENT,
                          falls through to the witness leg).
    VALID              -- a well-formed five-column Reuse Analysis table with an
                          EXTEND row (validator verdict: structurally-accepted
                          -> PRESENT, reuse leg satisfied).
    METHODOLOGY_EXEMPT -- an explicit `Reuse-Analysis: methodology-exempt`
                          marker (validator verdict: methodology-exempt ->
                          PRESENT).
    MALFORMED          -- a present-but-broken table (wrong columns / bad
                          Decision token) (validator verdict:
                          malformed-reuse-analysis -> ABSENT/refuse, does NOT
                          clear the leg as if absent-then-witnessed).
    UNJUSTIFIED_CREATE_NEW -- a CREATE_NEW row with an empty Justification
                          (validator verdict: unjustified-create-new ->
                          ABSENT/refuse; the precise anti-pattern reuse-first
                          exists to stop).
    NO_OVERLAP_DECLARED -- an explicit `Reuse-Analysis: no-overlap` marker
                          (validator verdict: no-overlap-declared -> PRESENT,
                          the 3rd accepted PRESENT verdict per DDD-9).
    """

    ABSENT = "absent"
    VALID = "valid"
    METHODOLOGY_EXEMPT = "methodology_exempt"
    MALFORMED = "malformed"
    UNJUSTIFIED_CREATE_NEW = "unjustified_create_new"
    NO_OVERLAP_DECLARED = "no_overlap_declared"


class DesignSkipWitness(str, Enum):
    """The `## Wave: DESIGN / [REF] Design Skipped` witness shape (O-1 opt-a).

    ABSENT          -- no witness heading present.
    WITH_RATIONALE  -- witness heading present with a non-empty rationale body
                       (a valid witness -> the witness leg is satisfied).
    EMPTY_RATIONALE -- witness heading present but no rationale body (a bare
                       heading is NOT a valid witness -> witness ABSENT, the
                       gate degrades with a diagnostic that the rationale is
                       empty).
    """

    ABSENT = "absent"
    WITH_RATIONALE = "with_rationale"
    EMPTY_RATIONALE = "empty_rationale"


# Gherkin-phrase -> typed-value lookups. Module-scoped so each step body stays a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

REUSE_SHAPE_BY_PHRASE: dict[str, ReuseAnalysisShape] = {
    "no Reuse Analysis": ReuseAnalysisShape.ABSENT,
    "a valid Reuse Analysis": ReuseAnalysisShape.VALID,
    "a methodology-exempt Reuse Analysis marker": ReuseAnalysisShape.METHODOLOGY_EXEMPT,
    "a malformed Reuse Analysis": ReuseAnalysisShape.MALFORMED,
    "an unjustified create-new Reuse Analysis": (
        ReuseAnalysisShape.UNJUSTIFIED_CREATE_NEW
    ),
    "a no-overlap-declared Reuse Analysis marker": (
        ReuseAnalysisShape.NO_OVERLAP_DECLARED
    ),
}

WITNESS_BY_PHRASE: dict[str, DesignSkipWitness] = {
    "no Design Skipped witness": DesignSkipWitness.ABSENT,
    "a Design Skipped witness with a rationale": DesignSkipWitness.WITH_RATIONALE,
    "a Design Skipped witness with an empty rationale": (
        DesignSkipWitness.EMPTY_RATIONALE
    ),
}

VERDICT_BY_PHRASE: dict[str, ReadinessVerdict] = {
    "refuses": ReadinessVerdict.REFUSED,
    "clears": ReadinessVerdict.CLEARED,
}
