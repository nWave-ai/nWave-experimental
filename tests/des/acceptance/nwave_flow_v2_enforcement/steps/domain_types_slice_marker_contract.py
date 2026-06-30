"""Typed domain vocabulary for the fix-wave-dispatch-marker-contract ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the
slice-01 / slice-02 / slice-03 Gherkin names is expressed once here as a typed
enum. Test-local (Mandate-13); ``GateDecision`` re-declared per-feature
(slice-04 / 07 / 07b / 07c / 07d precedent -- a test-local observable surface,
never a production import).
"""

from __future__ import annotations

from enum import Enum


class WaveUnderTest(Enum):
    """The waves whose command templates ship a DES-WAVE-only entering dispatch.

    The veto (`pre_tool_use_service.py:146`) fires for EVERY active wave; the
    fix must be wave-generic (RCA E7). slice-01 exercises ``design`` (AT-1a) and
    ``discuss`` (AT-1b -- the gate-IN fall-through path). The enum values are the
    floor-record wave names + the literal carried by ``<!-- DES-WAVE: <wave> -->``.
    """

    DESIGN = "design"
    DISCUSS = "discuss"


class GateDecision(Enum):
    """The observable hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"


class EntryMarkerContract(Enum):
    """The two marker shapes an in-wave dispatch may carry, by entry legitimacy.

    DES_WAVE_ONLY -- exactly what the shipped DISCUSS/DESIGN/DEVOPS/DISTILL
      command templates emit for an ENTERING dispatch: ``<!-- DES-WAVE: <wave> -->``
      alone, no `_DES_MARKER_KEY` token (so ``has_des_markers=False``). The
      legitimate entry shape the gate must RECOGNIZE (slice-01 / slice-02).
    MARKERLESS_CHILD -- a genuinely markerless in-wave child: no DES markers at
      all and NOT a wave entry (``wave_entering=False``). The bypass the S2 veto
      must STILL DENY loud (slice-01 AT-1c / slice-03 AT-3a).
    """

    DES_WAVE_ONLY = "a DES-WAVE-only entering dispatch"
    MARKERLESS_CHILD = "a genuinely markerless in-wave child"
