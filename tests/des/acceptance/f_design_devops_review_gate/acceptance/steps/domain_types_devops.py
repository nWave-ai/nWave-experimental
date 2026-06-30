"""Typed domain vocabulary for the f-design-devops-review-gate slice-02 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once as a typed enum, so each composition method consumes a
typed parameter (no raw ``str`` where an enum exists). The DSL emerges from these
enums, not from decorator proliferation.

slice-02 REUSES the slice-01 vocabulary VERBATIM for the verdict / boundary
nouns -- ``ReviewerVerdict``, ``GateOutcome``, ``WaveBoundary`` are imported from
``domain_types`` (the SSOT-not-duplication proof extends to the test types too:
the SAME enums range over the DEVOPS wave). slice-02 ADDS only the one noun
slice-01 did not need: the wave-active floor discriminant the live SubagentStop
dispatch keys on (AT-9 / AT-A8 literal-lift seam).

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through the composition-root resolution seam, the REAL ``des`` CLI
subprocess, and the REAL ``SubagentStopService.validate`` composition root
(Mandate-13 driving-port-only).
"""

from __future__ import annotations

from enum import Enum

# Re-export the slice-01 vocabulary VERBATIM (SSOT, no duplication): the same
# verdict / boundary nouns range over the DEVOPS wave.
from .domain_types import GateOutcome, ReviewerVerdict, WaveBoundary


__all__ = [
    "GateOutcome",
    "ReviewerVerdict",
    "WaveBoundary",
    "WaveFloor",
]


class WaveFloor(Enum):
    """The active wave the SubagentStop dispatch keys on (the literal-lift seam).

    The live ``SubagentStopService.validate`` resolves the gate-out stack off the
    ACTIVE wave read from the ``.nwave/wave-active/active.json`` floor
    (subagent_stop_service.py:305-307). Today the dispatch hardcodes
    ``wave_state.wave == "discuss"`` (line 307) + ``resolve_stack("discuss", ...)``
    (line 311); the lift this feature requires reads the active wave instead.

    * ``DEVOPS`` -- a platform-architect returning a DEVOPS output (AT-9): the
      lifted dispatch must resolve the DEVOPS gate-out stack and fire the review
      veto. RED at HEAD: the "discuss" literal means a devops floor never
      dispatches -> the return passes un-gated.
    * ``DISCUSS`` -- the existing wave (AT-A8 regression pin): the lift must NOT
      change the DISCUSS behavior -- a discuss return still dispatches the SAME
      discuss gate-out stack and vetoes identically.

    Both ``.value`` members are in the closed ``WAVE_VOCABULARY``
    (des.domain.wave_active) -- the floor accepts them at construction.
    """

    DEVOPS = "devops"
    DISCUSS = "discuss"
