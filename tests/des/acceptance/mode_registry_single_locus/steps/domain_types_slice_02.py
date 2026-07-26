"""Domain types for mode-registry-single-locus slice-02 (the SSOT-via-Types-Services-DSL mandate, criterion 1).

Every domain noun the slice-02 Gherkin uses is expressed ONCE here as a typed
concept; composition methods consume these types (criterion 2). Step modules
coerce Gherkin phrases to these types via the *_BY_PHRASE lookup tables.

Sentinel discipline: every value the working registry is EDITED to is a
sentinel that appears NOWHERE in the shipped assets — its presence in a
projected region therefore proves the projection READ the registry (never a
baked constant), and the retired inline value's absence proves the hand-written
copy is gone. That edit-then-observe round trip IS the slice-02 wiring witness
(Slice Plan: "registry edit -> re-render -> region content equals seam output").

Phase-shape sentinel placement (post-review amendment 2026-06-11, the
feature-end TEST_DESIGN_DECISION): the `deliver_phase_shape` sentinel targets
the CLASSIC (non-default) flavor ONLY. Under a LEGAL single-key registry the
DEFAULT flavor's phase shape must stay runtime-canonical — the slice-05
Layer-C agreement leg cross-checks exactly the default flavor against
`CANONICAL_PHASES`, so an atdd_pure phase-shape sentinel and the AT-03
accepted baseline are mutually exclusive. Registry read-through for the
phase-shape field is proven via the classic row instead; the generalization
to atdd_pure is sound because docgen renders every flavor through the ONE
`resolve_mode_descriptor` code path (per-flavor data, single renderer).
"""

from __future__ import annotations

from enum import Enum

from .domain_types_slice_01 import (  # shared slice-01 vocabulary (S1-safe reuse)
    ATDD_PURE_CRAFTER_DISCIPLINE,
    CRAFTER_AGENT,
    SHIPPED_FLAVORS,
    SkillName,
    WorkflowFlavor,
)


__all__ = [
    "ATDD_DESCRIPTOR_SENTINEL",
    "CRAFTER_AGENT",
    "DESCRIPTOR_SENTINEL_BY_FLAVOR",
    "DRIFT_BY_PHRASE",
    "EDITED_CRAFTER_SKILL",
    "INLINE_ROW_MARKER",
    "RETIRED_INLINE_SKILL",
    "SHIPPED_FLAVORS",
    "ProjectionDrift",
    "RegionId",
    "SkillName",
    "WorkflowFlavor",
]


# --- Generated regions (the projection's observable surface) -----------------


class RegionId(Enum):
    """A GENERATED region a docgen projection owns inside an asset.

    Marker grammar per the DESIGN SSOT (analysis §2.3.2):
    ``<!-- GENERATED:<region-id> START ... -->`` body
    ``<!-- GENERATED:<region-id> END -->``.
    """

    SKILL_LOAD_SET = "skill-load-set"
    MODE_DESCRIPTOR = "mode-descriptor"


# --- The retired inline row (AT-01 retirement oracle) ------------------------

# The skill the nw-software-crafter.md:74 inline table directs today. After the
# working registry is edited to the sentinel below and re-rendered, NO line of
# the crafter spec may still pair this name with the inline row's CONDITIONAL
# marker — any such line is the surviving hand-written copy.
RETIRED_INLINE_SKILL: SkillName = ATDD_PURE_CRAFTER_DISCIPLINE

# The word that uniquely marks the :74 inline table row (verified against the
# shipped spec: the only line pairing the skill name with this marker).
INLINE_ROW_MARKER = "CONDITIONAL"


# --- Registry-edit sentinels (appear nowhere in the shipped assets) ----------

EDITED_CRAFTER_SKILL = SkillName("nw-conditional-skill-authored-by-at-01")

ATDD_DESCRIPTOR_SENTINEL = "registry-authored atdd-pure descriptor sentinel 7f3a"

#: The descriptor sentinel each SHIPPED flavor carries. The assertion iterates
#: this map, never a hand-written tuple: "every declared mode" is a population
#: the registry defines, so a flavor leaving the product must not leave behind
#: an expectation nothing plants.
DESCRIPTOR_SENTINEL_BY_FLAVOR: dict[WorkflowFlavor, str] = {
    WorkflowFlavor.ATDD_PURE: ATDD_DESCRIPTOR_SENTINEL,
}


# --- Projection drifts (AT-03 named sad paths) --------------------------------


class ProjectionDrift(Enum):
    """A way a projected working copy can silently fall behind its registry.

    Each member is one explicitly named sad path (example-based per the
    layered-discipline sad-path rule, Mandate 11)."""

    REGISTRY_EDITED_WITHOUT_RERENDER = "registry_edited_without_rerender"
    REGION_HAND_EDITED = "region_hand_edited"


DRIFT_BY_PHRASE: dict[str, ProjectionDrift] = {
    "the registry's crafter skills are edited": (
        ProjectionDrift.REGISTRY_EDITED_WITHOUT_RERENDER
    ),
    "the generated skill-load region is hand-edited": (
        ProjectionDrift.REGION_HAND_EDITED
    ),
}
