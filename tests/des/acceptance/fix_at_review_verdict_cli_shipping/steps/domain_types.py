"""Domain types for the fix-at-review-verdict-cli-shipping acceptance suite.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed
once here as a typed enum / NewType / frozen dataclass. Composition service
methods (composition.py) consume these typed parameters; step bodies coerce
the Gherkin literal to the typed value and pass it straight through.

Domain nouns:
  - ReviewOutcome   -- the reviewer's decision (APPROVED writes a verdict;
                       NEEDS_REVISION writes nothing).
  - GateDecision    -- whether the carpaccio gate cleared or refused a slice.
  - FeatureId / SliceId -- identity of the reviewed work unit.
  - RecorderModule  -- the canonical recorder-module stem the install ships.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


FeatureId = NewType("FeatureId", str)
SliceId = NewType("SliceId", str)


class ReviewOutcome(Enum):
    """The acceptance-designer reviewer's decision on a slice's AT set."""

    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"


class GateDecision(Enum):
    """Whether the carpaccio DISTILL->DELIVER gate admitted the slice."""

    CLEARED = "cleared"
    REFUSED = "refused"


class RecorderModule(Enum):
    """A canonical recorder-module stem the install ships from the source tree.

    The single member this feature is about is the AT-review verdict recorder;
    a representative sibling recorder is included so the "no other shipped
    recorder is dropped" assertion has a concrete witness.
    """

    AT_REVIEW_VERDICT = "at_review_verdict"
    CARPACCIO_SLICE_GATE = "carpaccio_slice_gate"
