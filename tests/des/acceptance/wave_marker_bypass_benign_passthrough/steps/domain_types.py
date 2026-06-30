"""Typed domain vocabulary for the fix-wave-marker-bypass-benign-passthrough
slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists) and the DSL emerges from
the type system rather than from decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through the composition-root driving port (Mandate-13).
"""

from __future__ import annotations

from enum import Enum


class FloorState(Enum):
    """Whether a wave-active floor is armed under the (isolated) project root.

    The floor is the SHARED CWD state the regression conflated with
    "in-the-wave". Every scenario injects this state EXPLICITLY into a clean
    tmp root (Fix-2 test-isolation): the hook's decision is asserted against a
    CONTROLLED floor, never the developer's live working-tree floor.
    """

    DESIGN_ARMED = "design-armed"  # a `design` wave floor is armed (COMMAND prov.)
    NO_FLOOR = "no-floor"  # NoWaveActive -- the S1 floor, nothing armed


class DispatchShape(Enum):
    """The marker shape a checked dispatch carries (pure prompt content).

    The discriminant the corrected guard keys on. ``FULLY_MARKERLESS`` is the
    benign passthrough (zero DES markers, no DES-WAVE); the partial shapes carry
    wave context but MISS DES-VALIDATION -- a positively-identified bypass.
    """

    FULLY_MARKERLESS = "fully-markerless"  # zero DES markers, no DES-WAVE -> ALLOW
    PARTIAL_MARKERS = "partial-markers"  # DES-PROJECT-ID + DES-STEP-ID, no -VALIDATION
    DES_WAVE_ONLY = "des-wave-only"  # only <!-- DES-WAVE: design --> -> partial ctx
    FULL_DES_VALIDATION = "full-des-validation"  # carries DES-VALIDATION (is_des_task)
    # --- slice-03 (ADR-001 Amendment 1) marker-form shapes -------------------
    # The required marker carried in the PLAIN-LINE spelling `DES-VALIDATION:
    # required` (NOT the HTML-comment form). has_des_markers=True (matches
    # _DES_MARKER_KEY) but is_des_task=False (the HTML-comment pattern does not
    # match) -> a legitimate complete dispatch the slice-01 guard wrongly
    # false-positive-BLOCKs; the refined `carries_des_validation` recognizes it.
    PLAIN_LINE_DES_VALIDATION = "plain-line-des-validation"
    # Partial markers carrying NEITHER DES-VALIDATION form (no HTML-comment, no
    # plain-line) -- a genuine wave-bypass that must STILL be blocked (K1).
    NEITHER_VALIDATION_FORM = "neither-validation-form"


class GateDecision(Enum):
    """The observable PreToolUse decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"
