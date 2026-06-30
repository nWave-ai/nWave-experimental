"""Domain types for the algebra-projections-enforced slice-02 acceptance slice.

DISCUSS WD-3(b)/WD-5 + DESIGN DD-A4 (revised by ADR-002) + ADR-001 D2 / ADR-002 D1
(Mandate-12 criterion 1). Every domain noun used in the slice-02 Gherkin is
expressed once here as a typed enum or NewType. Step bodies and the composition
services consume these typed parameters — no raw ``str`` where a domain enum
exists, no control flow in step bodies.

ONE driving surface this slice, two compositions over it (ADR-002): direction (b)
completeness lives at the DELIVER-entry gate ``des verify-deliver-entry-contract``,
NOT on the standalone ``validate-feature-delta --require-registry-sections`` flag.
Both slice-02 compositions therefore drive the REAL DELIVER-entry gate:
  * the direction-(b) completeness oracle (a missing mandatory locked section is a
    FAIL; an empty-body section is not) — the ``MandatoryDeltaShape`` enum below;
  * the byte-stable DELIVER-entry migration regression-witness — the
    ``DeliverEntryShape`` enum below.
Both observe the §17 ``FreezeVerdict`` (the gate's GateVerdict envelope).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A wave id (retained for the shared Gherkin "for the discuss wave" phrasing; the
# DELIVER-entry gate does not take a wave argument, so the slice-02 direction-(b)
# scenarios no longer pass one — kept for any cross-slice reuse).
WaveId = NewType("WaveId", str)


# =============================================================================
# The §17 freeze verdict — the single observable of the DELIVER-entry gate
# =============================================================================


class FreezeVerdict(str, Enum):
    """User-observable verdict of one DELIVER-entry contract-freeze invocation.

    The REAL ``des verify-deliver-entry-contract`` gate emits a §17 GateVerdict in
    its ``--format=json`` envelope (``verdict`` field). Every slice-02 scenario
    (both the direction-(b) completeness oracle and the byte-stable witness) reads
    this structured token; these three are the only verdicts slice-02 exercises.

    PASS         -- token ``pass``: the contract is structurally complete and is
                    frozen.
    FAIL         -- token ``fail``: a structural deficiency (here, a missing locked
                    section) refuses the freeze.
    INDETERMINATE -- token ``indeterminate``: degrade-LOUD on an unreadable
                    contract (not exercised by this slice, named for completeness of
                    the closed set).
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


#: The §17 verdict tokens slice-02 maps. Shared by BOTH compositions: the
#: direction-(b) completeness oracle and the byte-stable migration witness read the
#: SAME envelope (ADR-002: one surface, two compositions).
FREEZE_VERDICT_TOKEN: dict[str, FreezeVerdict] = {
    "pass": FreezeVerdict.PASS,
    "fail": FreezeVerdict.FAIL,
    "indeterminate": FreezeVerdict.INDETERMINATE,
}


#: The four locked sections the DELIVER-entry FAIL diagnostic NAMES verbatim
#: (verify_deliver_entry_contract.py:193-200). This is BOTH the byte-stability
#: oracle (the witness asserts all four are named) AND the universe the
#: direction-(b) completeness oracle draws its omitted/empty target from. Sourced
#: from ``_DELIVER_LOCKED_CONTRACT`` (the real contract the gate reads), NOT
#: fabricated.
DELIVER_ENTRY_LOCKED_SECTIONS: tuple[str, ...] = (
    "Architecture & Contract Tests",
    "ADR Refs",
    "Reuse Analysis",
    "Slice Plan",
)


# =============================================================================
# Direction (b): mandatory locked-section completeness — DELIVER-entry surface
# =============================================================================


class MandatoryDeltaShape(str, Enum):
    """The shape of the DELIVER-entry contract presented to the completeness oracle.

    Direction (b) — "every mandatory section is PRESENT" — is realised at the
    DELIVER-entry gate against the four LOCKED sections (ADR-002 D1). Both shapes
    drive the REAL ``verify-deliver-entry-contract`` gate.

    OMITS_ONE_LOCKED  -- the contract carries a valid slice plan + an authored AT
                         module but OMITS exactly one of the four locked sections
                         (a real ``_DELIVER_LOCKED_CONTRACT`` id). The gate FAILs,
                         the diagnostic naming the omitted section so the maintainer
                         knows what to author (WD-3 direction (b)). The walking
                         skeleton.
    ONE_SECTION_EMPTY -- the contract carries the heading of every locked section
                         (so presence is satisfied) with one section's BODY left
                         honestly empty, plus a valid slice plan + an authored AT
                         module. Presence is heading-based
                         (validate_feature_delta.py:574), so an empty-body section
                         is NOT a missing-mandatory failure — the contract still
                         FREEZES (PASS). The structural analogue of WD-5 at the
                         DELIVER-entry surface (the only honest analogue this gate
                         carries — it has zero greenfield-degradable sections).
    """

    OMITS_ONE_LOCKED = "omits_one_locked"
    ONE_SECTION_EMPTY = "one_section_empty"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts lets
# each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

# Keyed by the Gherkin phrase that follows "a DELIVER-entry contract " in each Given
# line of the direction-(b) completeness feature.
MANDATORY_DELTA_SHAPE_BY_PHRASE: dict[str, MandatoryDeltaShape] = {
    "omitting a mandatory locked section": MandatoryDeltaShape.OMITS_ONE_LOCKED,
    "carrying every locked section heading with one section left honestly empty": (
        MandatoryDeltaShape.ONE_SECTION_EMPTY
    ),
}


# =============================================================================
# Byte-stable DELIVER-entry migration: regression-witness
# =============================================================================


class DeliverEntryShape(str, Enum):
    """The structural shape of the DELIVER-entry contract presented to the gate.

    MISSING_LOCKED_SECTION -- the feature-delta carries a valid slice plan + an
                              authored AT module, but OMITS at least one of the
                              four locked sections (Architecture & Contract Tests /
                              ADR Refs / Reuse Analysis / Slice Plan). The gate
                              REFUSES, naming the four locked sections — the
                              behaviour that MUST stay byte-stable through the
                              registry migration.
    COMPLETE               -- the feature-delta carries all four locked sections, a
                              valid five-column slice plan, and a ``.feature`` AT
                              module backing the planned slice. The gate FREEZES
                              (PASS) — the byte-stable happy path.
    """

    MISSING_LOCKED_SECTION = "missing_locked_section"
    COMPLETE = "complete"


DELIVER_ENTRY_SHAPE_BY_PHRASE: dict[str, DeliverEntryShape] = {
    "missing one of its locked sections": DeliverEntryShape.MISSING_LOCKED_SECTION,
    "that carries every locked section and a valid slice plan backed by an "
    "authored slice": DeliverEntryShape.COMPLETE,
}
