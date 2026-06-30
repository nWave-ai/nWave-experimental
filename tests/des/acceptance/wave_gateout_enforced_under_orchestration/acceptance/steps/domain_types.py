"""Domain types for wave-gateout-enforced-under-orchestration slice-01 (Mandate-12).

Typed enums for every Gherkin domain noun the slice-01 scenarios speak. The step
methods consume these typed parameters; no raw ``str`` literal where a domain enum
exists. The DSL emerges from the typed concepts -- the composition root's methods
take ``ReviewState`` / ``WaveClosure`` rather than free strings.
"""

from __future__ import annotations

from enum import Enum


class ReviewState(Enum):
    """The recorded-review precondition the orchestration return is gated against.

    NONE     -- no DESIGN review verdict recorded (the un-reviewed deliverable).
    APPROVED -- an artefact-current approved verdict recorded through the REAL
                producer CLI (the architect's reviewer said "no objection").
    STALE    -- an approved verdict recorded through the REAL producer CLI, then
                the sealed feature-delta CHANGED so the verdict's content seal no
                longer matches the current artefact (an APPROVED-then-edited race
                -- the un-gameable seal property, slice-05). ReviewVerdictGate
                reads the hash drift as INDETERMINATE("stale-artefact") -> veto,
                never silent-allow.
    """

    NONE = "none"
    APPROVED = "approved"
    STALE = "stale"


class MarkerShape(Enum):
    """The DES-marker subset an Agent()-dispatched return carries (slice-06).

    The fail-closed boundary discriminant. A DES-WAVE-bearing return that the
    wave-only resolver cannot resolve must degrade LOUD (refuse), NOT fall through
    to the genuine-non-DES passthrough-allow.

    GOVERNED_WAVE   -- a DES-WAVE in WAVE_VOCABULARY + a DES-PROJECT-ID: the
                       resolvable wave-only shape (reaches the gate-out).
    OUT_OF_VOCAB    -- a DES-WAVE whose value is NOT in WAVE_VOCABULARY + a
                       DES-PROJECT-ID: a DES return the resolver cannot map to a
                       governed wave. DESIGN DDD-6 wants this REFUSED (degrade-LOUD),
                       distinct from a genuine non-DES return. RED at HEAD:
                       _resolve_wave_only_context returns None -> silent passthrough.
    NO_PROJECT_ID   -- a DES-WAVE in WAVE_VOCABULARY but NO DES-PROJECT-ID: a DES
                       return missing the project id the gate-out needs. DESIGN
                       wants this REFUSED. RED at HEAD: `not project_id` -> None ->
                       silent passthrough.
    NON_DES         -- NO DES-WAVE marker at all (a genuinely non-DES agent return).
                       The EXISTING passthrough-allow MUST stay byte-stable
                       (regression-lock, green-on-keystone).
    """

    GOVERNED_WAVE = "governed-wave"
    OUT_OF_VOCAB = "out-of-vocab"
    NO_PROJECT_ID = "no-project-id"
    NON_DES = "non-des"


class WaveClosure(Enum):
    """The observable wave-boundary decision on the orchestration return.

    ALLOWED -- the return may close the wave (hook allows; exit 0).
    REFUSED -- the return is blocked (hook blocks; exit 2). Absence of a review
               reads as REFUSED -- a refusal, never a silent pass (degrade-LOUD).
    """

    ALLOWED = "allowed"
    REFUSED = "refused"


class Wave(Enum):
    """The governed wave whose gate-out veto the orchestration return must reach.

    The wave-only reachability route delivered by slice-01 is wave-PARAMETRIC
    (DDD-8): the SAME ``_resolve_des_context`` ADD-branch + ``validate`` wave-only
    guard serve every wave in ``_REVIEW_GATE_OUT_WAVES = {discuss, design, devops}``
    (subagent_stop_service.py:52). slice-02/03/04 are regression-locks proving the
    keystone route already covers all four RCA blast-radius gate-outs -- they are
    GREEN on the current committed code, NOT active-RED scaffolds.

    DESIGN -- the keystone wave (slice-01); ``verify-design-review`` veto.
    DEVOPS -- slice-02; ``verify-devops-review`` veto (the SAME ReviewVerdictGate
              core, only the wave name changes -- the SSOT-reuse proof).
    DISCUSS -- slice-03/04; a TWO-row gate-out stack
               ``[validate-feature-delta, verify-discuss-review]``: the structural
               row (slice-03) + the PO-review-verdict row (slice-04).
    """

    DESIGN = "design"
    DEVOPS = "devops"
    DISCUSS = "discuss"


class DiscussGateRow(Enum):
    """The row of the DISCUSS two-row gate-out stack a scenario targets.

    The DISCUSS gate-out stack is the readable 2-row list
    ``[validate-feature-delta, verify-discuss-review]`` (halt-at-first-veto): the
    structural row runs FIRST, the PO-review row runs ONLY after it passes.

    STRUCTURAL -- ``validate-feature-delta`` -> ``DiscussGateOut.evaluate`` over the
                  feature-delta slice-plan content (slice-03). A malformed /
                  non-value-bearing slice plan -> SLICE_PLAN_REJECTED veto; a
                  well-formed value-bearing one -> PASS (not blocked structurally).
    PO_REVIEW  -- ``verify-discuss-review`` -> ``DiscussReviewGate.evaluate`` over the
                  recorded PO-review verdict (slice-04). Reached only with a
                  value-bearing slice plan; an absent verdict -> INDETERMINATE veto.
    """

    STRUCTURAL = "structural"
    PO_REVIEW = "po-review"
