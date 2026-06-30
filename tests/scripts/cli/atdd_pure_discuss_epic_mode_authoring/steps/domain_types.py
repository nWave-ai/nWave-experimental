"""Domain types for the discuss-epic-mode slice-02 acceptance slice.

Slice-02 value: a maintainer runs ``/nw-discuss --epic <id>`` and gets a
*validated* epic-delta (epic-JTBD + Feature Plan + keystone designation +
dependency order) instead of cutting features by hand. The "code" of this slice
is SKILL / COMMAND text (DESIGN slice-02/04/05 text contracts) -- there is NO
``src/des`` surface. DESIGN pins the epic-delta contract (EDC) as the AT-citable
specification of what the ``--epic`` authoring procedure MUST produce.

Every domain noun in the Gherkin is expressed once here as a typed enum or
NewType (Mandate-12 criterion 1). Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the slice-01 sibling suite
(``tests/scripts/cli/atdd_pure_validate_feature_delta_feature_plan``) speaks
"the feature-plan check on the epic-delta" -- a CLI validation act. This suite
speaks "the maintainer runs the epic-mode authoring on the epic" -- the
``--epic`` authoring act -- and "the produced epic-delta". The domain nouns
differ, so the step phrases never collide.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic identifier (e.g. "flow-v2-wave-migrations").
EpicId = NewType("EpicId", str)


class EpicDeltaContract(str, Enum):
    """The EDC structural contracts the ``--epic`` authoring procedure produces.

    DESIGN slice-02/04/05 text contracts pin the EDC as a numbered, closed,
    citable set. The slice-02 ATs observe these on the PRODUCED epic-delta
    artifact at its production path ``docs/epic/{id}/epic-delta.md``. The
    slice-01 validator does NOT enforce keystone count, dependency order, or the
    JIT invariant (DC-2 defers their mechanical validation) -- so the slice-02
    ATs pin them as an executable specification of the authoring procedure's
    output, observed on the artifact.

    EDC_SHAPE        -- EDC-1..EDC-7 together: the produced epic-delta exists at
                        ``docs/epic/{id}/epic-delta.md`` (EDC-1), opens with the
                        ``# Epic Delta: {id}`` title (EDC-2), carries the
                        epic-JTBD section (EDC-3), the Feature Plan under the R1
                        heading with the five fixed columns (EDC-4), exactly ONE
                        ``@walking-skeleton`` keystone row (EDC-5), backward-only
                        dependency order = row order (EDC-6), and Status tokens
                        from the R2 closed set with authored rows ``pending``
                        (EDC-7). The structural happy path -- slice-02 AT-1, the
                        walking skeleton.
    EDC_GATE_OUT     -- EDC-8: the produced epic-delta exit-validates -- the real
                        slice-01 CLI ``des validate-feature-delta
                        --require-feature-plan --format=json`` returns the
                        ``accepted`` verdict, exit 0 (slice-02 AT-2, the mechanical
                        seam: an EDC-conformant artifact clears the keystone gate).
    EDC_JIT          -- EDC-9: the ``--epic`` run produces ONLY the epic-delta --
                        zero ``docs/feature/{id}/`` feature workspaces exist for
                        any planned feature (slice-02 AT-3: the fractal-JIT
                        invariant, never N feature-deltas upfront).
    """

    EDC_SHAPE = "edc_shape"
    EDC_GATE_OUT = "edc_gate_out"
    EDC_JIT = "edc_jit"


class EpicDeltaVerdict(str, Enum):
    """Maintainer-observable verdict of the slice-01 gate-OUT validation.

    The ``--epic`` run ends with the slice-01 ``--require-feature-plan
    --format=json`` gate (EDC-8). This suite reads ONLY the ``accepted`` token of
    that closed set -- the gate-OUT contract for an epic-mode run is verdict
    ``accepted`` (exit 0). Any other token, or no token, is a gate-OUT failure.

    ACCEPTED                 -- token ``accepted``: the produced epic-delta is a
                                structurally well-formed Feature Plan; the
                                epic-mode run may proceed to feature pickup.
    NOT_ACCEPTED             -- the gate-OUT returned any non-``accepted`` verdict
                                token (or exit != 0): the produced epic-delta did
                                NOT clear the keystone gate.
    EPIC_DELTA_ABSENT        -- the production-path epic-delta does not exist: the
                                ``--epic`` authoring procedure has not produced it.
                                On the current tip the procedure is undefined, so
                                every slice-02 invocation lands here -- the
                                active-RED missing-functionality signal, NOT a
                                real verdict.
    """

    ACCEPTED = "accepted"
    NOT_ACCEPTED = "not_accepted"
    EPIC_DELTA_ABSENT = "epic_delta_absent"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

EPIC_DELTA_CONTRACT_BY_PHRASE: dict[str, EpicDeltaContract] = {
    "the EDC structural shape": EpicDeltaContract.EDC_SHAPE,
    "the gate-OUT validation": EpicDeltaContract.EDC_GATE_OUT,
    "the fractal-JIT invariant": EpicDeltaContract.EDC_JIT,
}
