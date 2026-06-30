"""Domain types for the algebra-projections-enforced slice-03 acceptance slice.

DISCUSS slice-03 + DESIGN Point 4 (the 8 induced distill ref_sections),
Reuse Analysis row `distill.yaml` (Mandate-12 criterion 1). Every domain noun
used in the Gherkin is expressed once here as a typed enum or NewType. Step
bodies and the composition service consume these typed parameters — no raw
``str`` where a domain enum exists, no control flow in step bodies.

slice-03 reuses the slice-01 ``RegistrySectionVerdict`` + ``VERDICT_TOKEN``
closed-token contract verbatim (same driving port, same JSON envelope). The
slice-specific data is the DISTILL ``DeltaShape`` set and the
distill-wave section composition.
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-01 verdict contract verbatim — the driving port + JSON envelope
# are identical (SSOT: the slice-01 closed token set). slice-03 adds no new token.
from .domain_types import VERDICT_TOKEN, RegistrySectionVerdict, WaveId


__all__ = [
    "DISTILL_DECLARED_SECTIONS",
    "DISTILL_DELTA_SHAPE_BY_PHRASE",
    "DISTILL_VERDICT_BY_PHRASE",
    "PLAINLY_UNDECLARED_DISTILL_SECTION",
    "VERDICT_TOKEN",
    "DistillDeltaShape",
    "RegistrySectionVerdict",
    "WaveId",
]


# The 8 sections the distill wave's output_contract MUST declare (DESIGN Point 4,
# induced from schemas/feature-delta-tier1-sections.yaml DISTILL required_sections
# [7] + the Wave-Decision Reconciliation reconciliation addition, mirroring the
# discuss.yaml output_contract pattern). The all-declared happy-path feature-delta
# carries EXACTLY these; DELIVER adds them to distill.yaml to turn the AT GREEN.
DISTILL_DECLARED_SECTIONS: tuple[str, ...] = (
    "Wave-Decision Reconciliation",
    "Scenario List with Tags",
    "WS Strategy",
    "Adapter Coverage Table",
    "Scaffolds",
    "Test Placement",
    "Driving Adapter Coverage",
    "Pre-requisites",
)

# A section id in NEITHER the distill output_contract (post-DELIVER) NOR any
# tier1 distill required_section — a plainly-undeclared DISTILL section. The
# undeclared-section REJECT must NAME this id (A2). At HEAD the empty distill
# contract names the FIRST section instead, so the naming assertion RED-fails.
PLAINLY_UNDECLARED_DISTILL_SECTION = "Totally Bogus Distill Section"


class DistillDeltaShape(str, Enum):
    """The shape of the DISTILL feature-delta presented to the registry-section check.

    ALL_DISTILL_DECLARED  -- the feature-delta carries EXACTLY the 8 sections the
                             distill wave declares (the happy path / walking
                             skeleton). With distill.yaml's output_contract present
                             the check ACCEPTS; at HEAD (empty contract) it
                             REJECTS the first section -> active-RED.
    UNDECLARED_DISTILL_SECTION -- the 8 declared sections PLUS one plainly-
                             undeclared section. With the contract present the
                             check REJECTS, naming the bogus section; at HEAD it
                             names the FIRST declared section instead -> the
                             naming assertion RED-fails.
    SINGLE_DISTILL_DECLARED -- the feature-delta carries ONLY one distill-declared
                             section ("Scenario List with Tags"). With the contract
                             present this single declared section is ACCEPTED; at
                             HEAD (empty contract = pass-everything hole inverted)
                             it is REJECTED as undeclared -> active-RED. The
                             discriminator that the contract block is the source.
    """

    ALL_DISTILL_DECLARED = "all_distill_declared"
    UNDECLARED_DISTILL_SECTION = "undeclared_distill_section"
    SINGLE_DISTILL_DECLARED = "single_distill_declared"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: step bodies stay
# a single typed lookup + a single composition call, no branching business logic).

DISTILL_DELTA_SHAPE_BY_PHRASE: dict[str, DistillDeltaShape] = {
    "whose [REF] sections are exactly the distill wave's declared sections": (
        DistillDeltaShape.ALL_DISTILL_DECLARED
    ),
    "carrying a [REF] section the distill wave does not declare": (
        DistillDeltaShape.UNDECLARED_DISTILL_SECTION
    ),
    "carrying only a single distill-declared section": (
        DistillDeltaShape.SINGLE_DISTILL_DECLARED
    ),
}

DISTILL_VERDICT_BY_PHRASE: dict[str, RegistrySectionVerdict] = {
    "accepts the feature-delta": RegistrySectionVerdict.ACCEPTED,
    "rejects the feature-delta for an undeclared section": (
        RegistrySectionVerdict.UNDECLARED_SECTION
    ),
}
