"""Typed domain vocabulary for the nwave-flow-v2-enforcement slice-07d ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-07d
Gherkin names is expressed once here as a typed enum. Test-local (Mandate-13);
``GateDecision`` re-declared per-slice (slice-04/07/07b/07c precedent).
"""

from __future__ import annotations

from enum import Enum


class WaveDeclarationShape(Enum):
    """The unusable wave-declaration shapes an ad-hoc dispatch may carry (AT-3).

    Both shapes MUST leave the fallback inert: no arm, no record, no gate
    interference (K2 / S1). The enum values are the Gherkin example-row
    literals.
    """

    ABSENT = "no wave declaration"
    """The dispatch carries no wave declaration at all."""

    OUT_OF_VOCAB = "an unknown wave declaration"
    """The dispatch declares a wave outside the closed vocabulary -- treated
    as absent (validated at the use site, never armed)."""


class GateDecision(Enum):
    """The observable hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"
