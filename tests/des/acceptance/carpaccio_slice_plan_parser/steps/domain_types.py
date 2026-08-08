"""Domain types for the carpaccio slice-plan parser acceptance slice.

C10 of consolidation-for-wider-beta-testing (Mandate-15 criterion 1). Every
domain noun used in the Gherkin is expressed once here as a typed enum or
NewType; step bodies and the composition service consume these typed parameters
-- no raw `str` where a domain enum exists.

The slice exercises the public CLI entry-gate parser
(`carpaccio_format.parse_slice_plan`).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-carpaccio-slice-plan-parser-unify").
FeatureId = NewType("FeatureId", str)

# A canonical slice identifier matching `slice-\d+` (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class ParserUnderTest(Enum):
    """The public parser entry point exercised by this slice."""

    ENTRY_GATE = "entry-gate"


class ParseOutcome(Enum):
    """The observable outcome of a parser reading a slice plan.

    PARSED          -- the parser returned slice rows.
    REJECTED_COLUMNS -- the parser refused on a column-count mismatch
                        (the CLI ``MalformedInput`` "must have 5 columns" path).
    SECTION_MISSING -- the parser reported the slice-plan section absent
                        (the H2-only-heading defect path).
    """

    PARSED = "parsed"
    REJECTED_COLUMNS = "rejected-columns"
    SECTION_MISSING = "section-missing"
