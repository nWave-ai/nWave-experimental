"""Domain types for the distill-dependency-token-discoverable acceptance slice.

`docs/feature/parallel-by-default-distill-slicing/feature-delta.md` slice-02
(Mandate-12 criterion 1). Every domain noun used in the Gherkin is expressed
once here as a typed enum; step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.

Sibling precedent (EXTEND): the row-1 suite
``tests/scripts/cli/atdd_pure_slice_dependency_annotation_discoverable/`` proved
the SAME discoverability shape at the DISCUSS authoring surfaces (nw-discuss
SKILL.md / nw-product-owner agent). This slice moves the target to the DISTILL
authoring surface -- the ``nw-distill`` skill FAMILY (core + composed modules) --
and adds the SSOT/DRY cross-link obligation (D-4): the family must POINT at
nw-discuss's vocabulary reference, not restate it.
"""

from __future__ import annotations

from enum import Enum


class FamilyTree(str, Enum):
    """One of the two locations the ``nw-distill`` skill family is read from.

    An acceptance-designer at runtime reads the INSTALLED copy
    (``~/.claude/skills``); the SOURCE tree is the authored copy. Both are
    exercised -- an installed tree that is absent (fresh clone / CI) is
    SKIPPED, not failed.
    """

    SOURCE = "source"
    INSTALLED = "installed"


class FabricatedFamily(str, Enum):
    """Synthetic family-file texts used ONLY by the negative scenarios --
    each constructs the exact "documented in the wrong way" shape a real bad
    edit to the ``nw-distill`` family could produce, proving each detector is
    not testing-theater."""

    # token + flip present, but NO pointer to nw-discuss -- an independently
    # worded copy that will silently drift the next time row 1's grammar is
    # amended (D-4 SSOT/DRY violation).
    RESTATED_NO_CROSSLINK = "restated_no_crosslink"
    # token + pointer present, but the default-flip is NOT stated in plain
    # language (charter obs 1).
    BARE_TOKEN_NO_FLIP = "bare_token_no_flip"
    # the un-flipped default resurrected: an empty Annotation is made to OWE a
    # Justification (charter obs 3 -- keeps the pre-row-1 default alive).
    EMPTY_NEEDS_JUSTIFICATION = "empty_needs_justification"
    # silence read as "assume serial" (charter obs 3 -- the exact guess row 1
    # exists to retire).
    ASSUME_SERIAL = "assume_serial"


FAMILY_TREE_BY_PHRASE: dict[str, FamilyTree] = {
    "nw-distill family (source)": FamilyTree.SOURCE,
    "nw-distill family (installed)": FamilyTree.INSTALLED,
}
