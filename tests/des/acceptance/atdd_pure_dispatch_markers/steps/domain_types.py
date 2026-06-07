"""Domain types for hg-slice-00 -- the atdd_pure dispatch marker recognition slice.

hg-slice-00 of F-DES-ATDD-PURE-HOOK-GATES (U0 -- ADR-030 D8). A DES hook can
only intercept a dispatch it can RECOGNISE. The recognition substrate is the
three-marker set every atdd_pure crafter dispatch carries:

  <!-- DES-MODE  : atdd_pure   -->   the mode discriminator
  <!-- DES-PHASE : A_GREEN_ATS -->   the atdd_pure phase (ATDDPurePhase member)
  <!-- DES-SLICE : slice-01    -->   the carpaccio slice id (anchored slice-\\d+)

Every domain noun used in the Gherkin is expressed once here as a typed enum or
NewType (Mandate-12 criterion 1). Step bodies and the composition service
consume these typed parameters -- no raw `str` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A carpaccio slice identifier as carried by a DES-SLICE marker (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class MarkerPresence(str, Enum):
    """The shape a single DES marker takes in the dispatch prompt.

    The recognition test drives each of the three markers (mode / phase / slice)
    with one of these literal Gherkin tokens. The composition root maps the
    token to a concrete marker line (or to no line at all, for ABSENT).
    """

    ABSENT = "absent"
    ORCHESTRATOR = "orchestrator"  # mode marker only -- a classic dispatch
    ATDD_PURE = "atdd_pure"  # mode marker -- the canonical atdd_pure value
    ATDD_PURE_DASHED = "atdd-pure"  # mode marker -- cosmetically-off, normalises
    A_GREEN_ATS = "A_GREEN_ATS"  # phase marker -- a valid ATDDPurePhase member
    A_GREEN_ATS_LOWER = "a_green_ats"  # phase marker -- case-off, normalises
    G_COMMIT = "G_COMMIT"  # phase marker -- a valid ATDDPurePhase member
    NOT_A_PHASE = "NOT_A_PHASE"  # phase marker -- out-of-vocabulary, defective
    SLICE_01 = "slice-01"  # slice marker -- well-formed, anchored slice-\\d+
    SLICE_12 = "slice-12"  # slice marker -- well-formed
    SLICE_03 = "slice-03"  # slice marker -- well-formed
    SLICE_MALFORMED_NODASH = "slice1"  # slice marker -- no dash, anchor fails
    SLICE_MALFORMED_TAIL = "slice-3-->"  # slice marker -- garbled tail, anchor fails


class DispatchRecognition(str, Enum):
    """The user-observable recognition verdict for a whole marker set.

    ABSENT    -- no DES-MODE:atdd_pure marker -> a classic dispatch; a hook
                 falls through to the unchanged classic path (U1/U2 do not fire).
    VALID     -- DES-MODE:atdd_pure present AND DES-PHASE is an ATDDPurePhase
                 member AND DES-SLICE matches the anchored slice-\\d+ shape.
                 A hook may fire its atdd_pure branch on this dispatch.
    DEFECTIVE -- DES-MODE:atdd_pure present BUT a remaining marker is absent,
                 malformed, or carries an out-of-vocabulary value. Recognised
                 AS defective (M3/M14) -- never silently mistaken for a classic
                 dispatch, never silently dropped to None.
    """

    ABSENT = "absent"
    VALID = "valid"
    DEFECTIVE = "defective"


# Gherkin-phrase / token -> typed-value lookups. Module-level dicts keep every
# step body a single typed lookup plus a single composition call (Mandate-12
# criterion 3: no control flow in step bodies).

MARKER_PRESENCE_BY_TOKEN: dict[str, MarkerPresence] = {
    m.value: m for m in MarkerPresence
}

RECOGNITION_BY_TOKEN: dict[str, DispatchRecognition] = {
    r.value: r for r in DispatchRecognition
}
