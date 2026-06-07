"""Domain types for slice-02 -- the WS-floor NOT_APPLICABLE applicability path.

slice-02 of fix-feature-end-ws-gate-applicability (the un-gameable divergence
pair + the usage guard). Every domain noun in the slice-02 Gherkin is expressed
once here as a typed enum or NewType; step bodies and the composition service
consume these typed parameters (Mandate-12 criterion 1 -- the domain types
module exists with typed enums for every domain noun used in Gherkin).

The behaviour this slice specifies (verified from the ratified DESIGN at HEAD,
``feature-delta.md`` DDD-3/DDD-4): the walking-skeleton floor returns
``GateVerdict.NOT_APPLICABLE`` (exit 0) for a feature that genuinely ships no
installable walking-skeleton artifact -- but ONLY on a POSITIVE, EXPLICIT,
JUSTIFIED declaration (``walking_skeleton_applicable: false`` + a non-empty
``not_applicable_rationale``), AND the gate MECHANICALLY cross-checks
installability (probing ``pyproject.toml`` / ``setup.py`` / ``setup.cfg`` as a
direct child of the resolved ``feature_root``) so a feature CANNOT lie. An
installable feature carrying the SAME declaration is a LIE and FAILS (exit 1).
A declaration with an empty/missing rationale is a USAGE error (exit 2).

None of that branch exists at HEAD -- the gate has no
``walking_skeleton_applicable`` parse, no ``_detect_installable`` probe, and no
NOT_APPLICABLE producer -- so the slice-02 ATs RED-fail for the right reason
(MISSING_FUNCTIONALITY).
"""

from __future__ import annotations

from enum import Enum


class FeatureShape(str, Enum):
    """The shape of the staged feature whose WS-floor applicability is decided.

    slice-03 supersession (2026-06-05): the two installability divergence-pair
    shapes (NON_INSTALLABLE_DECLARED_NOT_APPLICABLE / INSTALLABLE_DECLARED_NOT_
    APPLICABLE) were RETIRED with the scenarios they fed -- the installability
    cross-check is now delta-aware and specified by
    slice-03-delta-aware-installability.feature on real git work-trees. Only the
    orthogonal justification guard remains here.

    DECLARED_NOT_APPLICABLE_NO_RATIONALE
        -- a feature declaring ``walking_skeleton_applicable: false`` with an
           empty/missing rationale. The declaration is unjustified -> USAGE error
           (exit 2), refusing the declaration rather than silently passing. The
           rationale guard runs BEFORE any installability probe, so it is
           unaffected by delta-awareness.
    """

    DECLARED_NOT_APPLICABLE_NO_RATIONALE = "declared_not_applicable_no_rationale"


class FloorVerdict(str, Enum):
    """The operator-observable verdict of one walking-skeleton-floor run.

    NOT_APPLICABLE -- the floor recognised the feature ships no installable
                      walking-skeleton artifact and certified past it (exit 0).
    FAIL           -- the floor refused: the feature is installable yet declared
                      not-applicable (a lie the gate caught mechanically; exit 1).
    USAGE_ERROR    -- the declaration was malformed (unjustified -- empty/missing
                      rationale); the floor refused the declaration (exit 2).
    """

    NOT_APPLICABLE = "not_applicable"
    FAIL = "fail"
    USAGE_ERROR = "usage_error"


class ReasonMarker(str, Enum):
    """A substring that identifies WHICH reason a floor verdict reports.

    NOT_APPLICABLE_VERDICT
        -- the verdict token the gate emits in its stdout JSON when it honours a
           justified non-applicable declaration (``GateVerdict.NOT_APPLICABLE``,
           ``gate_outcome.py:30``).
    FAIL_VERDICT
        -- the verdict token the gate emits when it refuses (``GateVerdict.FAIL``,
           ``gate_outcome.py:29``).
    INSTALLABLE_CONTRADICTION
        -- a token of the diagnostic naming the detected-installability
           contradiction when an installable feature lies (DESIGN DDD-3 line 428).
    UNJUSTIFIED_RATIONALE
        -- a token of the usage error naming the missing/empty rationale when the
           declaration is unjustified (DESIGN DDD-4 line 509).
    """

    NOT_APPLICABLE_VERDICT = "not_applicable"
    FAIL_VERDICT = "fail"
    INSTALLABLE_CONTRADICTION = "installable"
    UNJUSTIFIED_RATIONALE = "rationale"


__all__ = ["FeatureShape", "FloorVerdict", "ReasonMarker"]
