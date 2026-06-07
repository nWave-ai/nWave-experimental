"""Domain types for the fix-carpaccio-distill-authoring-ergonomics AT set.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

The feature has two driving ports, both real Layer-3 subprocesses:
  * `des carpaccio-slice-gate`  -- the existing enforcing entry GATE (slices
    01/02), invoked via the `des` dispatcher subcommand (it is a gate).
  * `python -m des.cli.carpaccio_precheck`  -- the NEW read-only advisory
    pre-check (slice 03), a NON-GATE designer tool invoked MODULE-DIRECT (not a
    `des` dispatcher subcommand -- the dispatcher registry is parity-pinned to
    the gate catalog, so a non-gate tool cannot be a subcommand; deferred to
    F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "demo-feature").
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class GateVerdict(str, Enum):
    """User-observable verdict of one carpaccio-slice-gate invocation.

    Maps onto the gate CLI exit-code contract (ADR-028 D2-bis + ADR-029 D5).

    CLEARED            -- exit 0: the slice is cleared to enter implementation.
    SLICE_PLAN_MISSING -- exit 1: the feature-delta or slice-plan section absent.
    MALFORMED_INPUT    -- exit 2: malformed slice-plan table OR an orphan tag.
    SLICE_TOO_LARGE    -- exit 44 CARPACCIO_SLICE_TOO_LARGE: oversized / coverage /
                          ordering / missing-justification violation.
    AT_REVIEW_REJECTED -- exit 45 AT_REVIEW_NOT_APPROVED: assertion 5 failed.
    """

    CLEARED = "cleared"  # exit 0
    SLICE_PLAN_MISSING = "slice_plan_missing"  # exit 1
    MALFORMED_INPUT = "malformed_input"  # exit 2
    SLICE_TOO_LARGE = "slice_too_large"  # exit 44
    AT_REVIEW_REJECTED = "at_review_rejected"  # exit 45


class HumanVerdictClass(str, Enum):
    """The PASS/FAIL/DEGRADED class of the gate's human-readable summary line.

    The gate emits a single human-readable verdict line on stderr (via
    ``human_surface.print_human_summary``). Under subprocess capture stderr is
    not a TTY, so the line is plain text prefixed by one of the three markers.

    PASS_CLASS     -- the line begins with the success marker (cleared).
    FAIL_CLASS     -- the line begins with the refusal marker (refused).
    DEGRADED_CLASS -- the line begins with the soft/partial marker (advisory).
    """

    PASS_CLASS = "PASS"
    FAIL_CLASS = "FAIL"
    DEGRADED_CLASS = "DEGRADED"


class SlicePlanShape(str, Enum):
    """The shape of the entering slice the gate fixture provisions.

    COUPLED_OVER_CEILING_JUSTIFIED -- more ATs than the ceiling, every scenario
        carries @coupled, the plan row records a justification -> the coupled-
        AT-group escape applies -> CoupledSliceAccepted, exit 0.
    VALID_IN_SIZE -- a well-formed five-column plan; the entering slice's AT
        count is within the ceiling -> SliceCleared, exit 0.
    OVER_CEILING_UNCOUPLED -- more ATs than the ceiling, no @coupled escape ->
        CARPACCIO_SLICE_TOO_LARGE, exit 44.
    """

    COUPLED_OVER_CEILING_JUSTIFIED = "coupled_over_ceiling_justified"
    VALID_IN_SIZE = "valid_in_size"
    OVER_CEILING_UNCOUPLED = "over_ceiling_uncoupled"


class PrecheckFeatureShape(str, Enum):
    """The shape of the feature the pre-check fixture provisions (slice-03).

    MISSING_BINDING_TAG -- the feature's .feature files carry no file-level
        ``@feature-{id}`` binding tag and live outside the legacy directory, so
        the gate would later resolve zero scenarios (the no-scenarios-for-slice
        precursor). The pre-check must surface this UPFRONT.
    OVER_CEILING_PAIR -- two over-ceiling slices: one WITHOUT the coupled escape
        (the pre-check flags it) and one WITH the coupled escape satisfied (the
        pre-check reports it as cleared by the escape) -- distinguishes the two.
    MULTIPLE_DEFECTS -- a feature carrying THREE distinct format defects at once
        (missing binding tag + a slice-tag mismatch + an over-ceiling slice). The
        pre-check must report ALL THREE in one pass, never fail-fast.
    """

    MISSING_BINDING_TAG = "missing_binding_tag"
    OVER_CEILING_PAIR = "over_ceiling_pair"
    MULTIPLE_DEFECTS = "multiple_defects"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts
# lets each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

SLICE_PLAN_SHAPE_BY_PHRASE: dict[str, SlicePlanShape] = {
    "an over-ceiling slice that is fully coupled with a recorded justification": (
        SlicePlanShape.COUPLED_OVER_CEILING_JUSTIFIED
    ),
    "a well-formed in-size slice plan": SlicePlanShape.VALID_IN_SIZE,
    "an over-ceiling slice that is not coupled": (
        SlicePlanShape.OVER_CEILING_UNCOUPLED
    ),
}

# Keys are the substring captured by the {precheck_phrase} parser placeholder
# (the text AFTER "the feature's scenario files carry " / "the feature carries ").
PRECHECK_FEATURE_SHAPE_BY_PHRASE: dict[str, PrecheckFeatureShape] = {
    "no feature-binding tag": PrecheckFeatureShape.MISSING_BINDING_TAG,
    "an over-ceiling slice without the coupled escape": (
        PrecheckFeatureShape.OVER_CEILING_PAIR
    ),
    "a missing feature-binding tag, a slice-tag mismatch, and an over-ceiling slice": (
        PrecheckFeatureShape.MULTIPLE_DEFECTS
    ),
}
