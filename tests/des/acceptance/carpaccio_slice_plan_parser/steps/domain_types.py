"""Domain types for the carpaccio slice-plan parser-unification acceptance slice.

C10 of consolidation-for-wider-beta-testing (Mandate-15 criterion 1). Every
domain noun used in the Gherkin is expressed once here as a typed enum or
NewType; step bodies and the composition service consume these typed parameters
-- no raw `str` where a domain enum exists.

The slice consolidates two divergent slice-plan parsers into ONE tolerant
`parse_slice_plan_rows(text)` in carpaccio_format, to which the CLI entry gate
(`carpaccio_format.parse_slice_plan`) and the subagent-stop hook parser
(`subagent_stop_handler._parse_slice_plan_rows`) both delegate.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-carpaccio-slice-plan-parser-unify").
FeatureId = NewType("FeatureId", str)

# A canonical slice identifier matching `slice-\d+` (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class ParserUnderTest(Enum):
    """The two real parser entry points the slice consolidates.

    ENTRY_GATE -- the CLI carpaccio entry gate parser
        (``des.cli.carpaccio_format.parse_slice_plan``), text-driven.
    EXIT_HOOK  -- the subagent-stop hook parser
        (``des.adapters.drivers.hooks.subagent_stop_handler._parse_slice_plan_rows``),
        feature-delta-file-driven.
    """

    ENTRY_GATE = "entry-gate"
    EXIT_HOOK = "exit-hook"


class HeadingLevel(Enum):
    """The markdown heading depth the slice-plan section sits under.

    H2 is the format the shipped feature-deltas use; H3 is the GFM-naive defect
    case (both real parsers report the section missing at HEAD).
    """

    H2 = 2
    H3 = 3


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
