"""Domain types for slice-01 -- the U1 carpaccio PreToolUse intercept.

slice-01 of F-DES-ATDD-PURE-HOOK-GATES (U1 / Mikado T-E). Every domain noun in
the Gherkin is expressed once here as a typed enum or NewType; step bodies and
the composition service consume these typed parameters (Mandate-12 criterion 1).

slice-01 builds the `PreToolUse` intercept that blocks an atdd_pure
`A_GREEN_ATS` crafter dispatch when the carpaccio gate rejects the slice, when
the marker set is incomplete, when an earlier slice is unshipped, or when the
handler itself raises -- without the orchestrating LLM choosing to run the gate.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)


class HookVerdict(str, Enum):
    """The user-observable verdict of the U1 PreToolUse intercept.

    ALLOWED -- the dispatch falls through to the existing allow path (exit 0,
               no decision JSON on stdout).
    BLOCKED -- the intercept emitted a `{"decision": "block"}` body and a
               non-zero `decision.exit_code`.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class DispatchShape(str, Enum):
    """The marker-set shape of a PreToolUse dispatch the U1 intercept sees.

    CLASSIC          -- no `DES-MODE:atdd_pure` marker; classic path unchanged.
    ATDD_PURE_VALID  -- `DES-MODE:atdd_pure` + valid phase + valid slice.
    PHASE_MISSING    -- `DES-MODE:atdd_pure` present, `DES-PHASE` absent.
    SLICE_MISSING    -- `DES-MODE:atdd_pure` present, `DES-SLICE` absent.
    """

    CLASSIC = "classic"
    ATDD_PURE_VALID = "atdd_pure_valid"
    PHASE_MISSING = "phase_missing"
    SLICE_MISSING = "slice_missing"


class CarpaccioOutcome(str, Enum):
    """The carpaccio CLI verdict the U1 intercept surfaces.

    CLEARED  -- carpaccio CLI exit 0; the slice is allowed.
    REJECTED -- carpaccio CLI non-zero exit; the slice is blocked.
    """

    CLEARED = "cleared"
    REJECTED = "rejected"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

DISPATCH_SHAPE_BY_PHRASE: dict[str, DispatchShape] = {
    "a classic dispatch": DispatchShape.CLASSIC,
    "a valid atdd_pure A_GREEN_ATS dispatch": DispatchShape.ATDD_PURE_VALID,
    "an atdd_pure dispatch missing its phase marker": DispatchShape.PHASE_MISSING,
    "an atdd_pure dispatch missing its slice marker": DispatchShape.SLICE_MISSING,
}

VERDICT_BY_PHRASE: dict[str, HookVerdict] = {
    "allowed": HookVerdict.ALLOWED,
    "blocked": HookVerdict.BLOCKED,
}

CARPACCIO_OUTCOME_BY_PHRASE: dict[str, CarpaccioOutcome] = {
    "clears": CarpaccioOutcome.CLEARED,
    "rejects": CarpaccioOutcome.REJECTED,
}
