"""Domain types for the discuss-epic-mode slice-06 dogfood acceptance slice.

Slice-06 value: the flow-v2 wave-migrations follow-on list (today living only in
conversation / flow-design ``§13 CHANGE-SET master``) becomes a validated,
repeatable epic-delta -- the first real epic-mode run. The deliverable is the REAL
artifact at the production repository path
``docs/epic/flow-v2-wave-migrations/epic-delta.md``, AUTHORED at DELIVER by the
Luna PO agent following the epic-mode procedure (slice-02 authoring prose +
slice-04 escalation + slice-05 maintenance, all exercised against it).

There is NO ``src/des`` surface for slice-06 -- the producer is the LLM-mediated
``--epic`` authoring procedure (PROSE). DESIGN pins the dogfood completeness
contract (feature-delta "slice-06 dogfood completeness contract") + the EDC-5/6
DC-2 deferral + EDC-8 gate-OUT as the AT-citable specification of what the produced
artifact MUST satisfy. The slice-01 validator (gate-OUT, EDC-8) is the only
mechanical ``src/des`` seam these ATs drive.

Every domain noun in the Gherkin is expressed once here as a typed enum or NewType
(Mandate-12 criterion 1). Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the sibling epic-mode suites speak of "the maintainer runs
the epic-mode authoring / oversized-detection / maintenance"; this suite speaks of
"the flow-v2 wave-migrations epic-delta" and "the §13 change-set follow-on items"
-- the dogfood vocabulary. The domain nouns differ, so the step phrases never
collide across files.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic identifier. For slice-06 the dogfood epic is fixed:
# "flow-v2-wave-migrations".
EpicId = NewType("EpicId", str)


class DogfoodVerdict(str, Enum):
    """Maintainer-observable verdict of the slice-06 dogfood gate-OUT (EDC-8).

    The first real epic-mode run ends with the slice-01 ``--require-feature-plan
    --format=json`` keystone gate on the REAL produced artifact. This suite reads
    ONLY the ``accepted`` token of that closed set -- the gate-OUT contract for an
    epic-mode run is verdict ``accepted`` (exit 0).

    ACCEPTED            -- token ``accepted``: the REAL flow-v2-wave-migrations
                           epic-delta is a structurally well-formed Feature Plan;
                           the dogfood run cleared the keystone gate.
    NOT_ACCEPTED        -- the gate-OUT returned any non-``accepted`` verdict token
                           (or exit != 0): the produced epic-delta did NOT clear the
                           keystone gate.
    EPIC_DELTA_ABSENT   -- the production-path epic-delta does not exist: the
                           epic-mode run has not produced it. On the current tip the
                           dogfood run has not happened, so every slice-06
                           invocation lands here -- the active-RED
                           missing-functionality signal, NOT a real verdict.
    """

    ACCEPTED = "accepted"
    NOT_ACCEPTED = "not_accepted"
    EPIC_DELTA_ABSENT = "epic_delta_absent"


class Section13Item(str, Enum):
    """The closed 7-item coverage universe of the flow-v2 §13 follow-on list.

    DESIGN slice-06 dogfood completeness contract (feature-delta) pins the coverage
    universe of the flow-design ``§13 CHANGE-SET master`` conversational follow-on
    list as exactly these 7 items. The dogfood's HONESTY is that every item maps to
    >= 1 Feature Plan row in the produced epic-delta -- OR is a row-merge documented
    in that row's Justification (merge-if-identical-except-scale taste test). This
    is content-faithfulness as a closed-set semantic coverage assertion, NOT a
    brittle byte-pin of the §13 prose: the source list can be re-worded; the
    contract is that all 7 categories of change are represented.

    DESIGN_WAVE_MIGRATION   -- (1) the /nw-design wave migration to flow-v2.
    DEVOPS_WAVE_MIGRATION    -- (2) the /nw-devops wave migration to flow-v2.
    DISTILL_WAVE_MIGRATION   -- (3) the /nw-distill wave migration to flow-v2.
    DELIVER_WAVE_MIGRATION   -- (4) the /nw-deliver wave migration to flow-v2.
    DECLARATIVE_GATE_COMPOSITION
                             -- (5) the declarative wave->gate composition
                                extraction (flow-design §15.A).
    MANIFEST_GATE_G_TRACK    -- (6) the manifest + gate-G (design<->AT coherence)
                                track.
    SELF_ATTEST_VERDICT_LAYER
                             -- (7) the self-attest verdict layer.
    """

    DESIGN_WAVE_MIGRATION = "design_wave_migration"
    DEVOPS_WAVE_MIGRATION = "devops_wave_migration"
    DISTILL_WAVE_MIGRATION = "distill_wave_migration"
    DELIVER_WAVE_MIGRATION = "deliver_wave_migration"
    DECLARATIVE_GATE_COMPOSITION = "declarative_gate_composition"
    MANIFEST_GATE_G_TRACK = "manifest_gate_g_track"
    SELF_ATTEST_VERDICT_LAYER = "self_attest_verdict_layer"


# Per-item recognition keywords. An item is COVERED when at least one of its
# keyword phrases appears (case-insensitive) in any Feature Plan row's text (the
# Feature name + Value statement + Justification cells), OR when the item is named
# in the produced artifact's documented-exclusions set. Kept module-level so step +
# service bodies stay delegations, never inline logic (Mandate-12 criterion 3).
SECTION_13_ITEM_KEYWORDS: dict[Section13Item, tuple[str, ...]] = {
    Section13Item.DESIGN_WAVE_MIGRATION: ("design-wave", "design wave", "/nw-design"),
    Section13Item.DEVOPS_WAVE_MIGRATION: ("devops-wave", "devops wave", "/nw-devops"),
    Section13Item.DISTILL_WAVE_MIGRATION: (
        "distill-wave",
        "distill wave",
        "/nw-distill",
    ),
    Section13Item.DELIVER_WAVE_MIGRATION: (
        "deliver-wave",
        "deliver wave",
        "/nw-deliver",
    ),
    Section13Item.DECLARATIVE_GATE_COMPOSITION: (
        "declarative",
        "wave->gate",
        "wave→gate",
        "§15.a",
        "gate composition",
    ),
    Section13Item.MANIFEST_GATE_G_TRACK: ("manifest", "gate-g", "gate g", "coherence"),
    Section13Item.SELF_ATTEST_VERDICT_LAYER: (
        "self-attest",
        "self attest",
        "attestation",
    ),
}


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

DOGFOOD_EPIC_ID: EpicId = EpicId("flow-v2-wave-migrations")
