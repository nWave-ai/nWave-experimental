"""Domain types for mode-registry-single-locus slice-01 (the SSOT-via-Types-Services-DSL mandate, criterion 1).

Every domain noun the slice-01 Gherkin uses is expressed ONCE here as a typed
concept; composition methods consume these types (criterion 2), never raw
strings where a domain type exists. Step modules coerce Gherkin phrases to
these types via the *_BY_PHRASE lookup tables.

The byte-equivalence witness (feature-delta DISTILL open item, pinned by
slice-01): `EXPECTED_ATDD_PURE_CRAFTER_SKILLS` is the EXACT conditional-skill
set the `nw-software-crafter.md:74` inline table carries today. The AT asserts
the registry answer set-equals this constant — that equality IS the
"dispatch behaviour byte-identical" witness; the inline table is then safe to
retire as a duplicate of the registry row.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# --- Agents and skills -------------------------------------------------------

AgentName = NewType("AgentName", str)
SkillName = NewType("SkillName", str)

CRAFTER_AGENT = AgentName("nw-software-crafter")

ATDD_PURE_CRAFTER_DISCIPLINE = SkillName("nw-crafter-discipline-atdd-pure")

# The byte-equivalence witness: the set the agent spec's inline table declares
# today (nw-software-crafter.md:74 — "CONDITIONAL: load only when workflow.mode
# == atdd_pure"). One skill, exactly.
EXPECTED_ATDD_PURE_CRAFTER_SKILLS: frozenset[str] = frozenset(
    {ATDD_PURE_CRAFTER_DISCIPLINE}
)


# --- Workflow flavors (the mode 4-tuple's identity) ---------------------------


class WorkflowFlavor(Enum):
    """A shipped workflow flavor — one registry file under `nWave/flavors/`."""

    ATDD_PURE = "atdd_pure"
    # CLASSIC is retained ONLY as a fixture identity: slices that author their
    # own registry in tmp_path still need a second flavor id to author, and a
    # retired name is the honest one to use. It is NOT shipped -- see
    # SHIPPED_FLAVORS, which is what any assertion about the real registry must
    # iterate. Conflating "a name the fixtures can use" with "a mode the product
    # ships" is what made this feature fail after the removal.
    CLASSIC = "classic"


#: The flavors the product actually SHIPS. One mode, one registry file.
SHIPPED_FLAVORS: tuple[WorkflowFlavor, ...] = (WorkflowFlavor.ATDD_PURE,)


FLAVOR_BY_PHRASE: dict[str, WorkflowFlavor] = {
    "atdd_pure": WorkflowFlavor.ATDD_PURE,
    "classic": WorkflowFlavor.CLASSIC,
}


# --- Registry declaration defects (AT-03 named sad paths) ---------------------


class RegistryDefect(Enum):
    """A way a flavor's crafter `skill_load_set` entry can fail to be a
    proper declaration. Each member is one explicitly named sad path
    (example-based per the layered-discipline sad-path rule)."""

    CONDITIONAL_NOT_A_LIST = "conditional_not_a_list"
    CRAFTER_ROW_MISSING = "crafter_row_missing"


DEFECT_BY_PHRASE: dict[str, RegistryDefect] = {
    "written as one bare word instead of a list": (
        RegistryDefect.CONDITIONAL_NOT_A_LIST
    ),
    "missing from the flavor entirely": RegistryDefect.CRAFTER_ROW_MISSING,
}

# The flavor_id the AT-03 tmp_path registry fixture is authored under.
AUTHORED_DEFECTIVE_FLAVOR_ID = "defective"
