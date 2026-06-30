"""Composition root for f-design-wave-migration slice-01 Gherkin ATs.

Driving surface (Mandate-13 driving-port-only, prose-surface case): the
filesystem read of the REAL shipped ``nw-distill`` skill via the shared
``_skill_source.read_distill`` helper (reused from the original plain-pytest
suite — NOT duplicated). The DESIGN-skip soft-gate (row 7b) is
LLM-reads-markdown-prose behaviour with no runtime code path, so the
deterministic, git-free, cross-OS observable is that the canonical shipped skill
carries row 7b's prose, asserted on DISCRIMINATING multi-word phrases windowed
around the ``[REF] Code-Design`` anchor (so the assertion validates row 7b's OWN
prose, not an incidental mention elsewhere).

GREEN-not-active-RED: this is a format conversion of PASSING behaviour — row 7b
already ships in nw-distill. Each oracle stays GENUINE: removing the asserted
phrase from row 7b's window reds the scenario (mutation-verified).

Mirrors the original ``test_slice01_design_skip_advisory.py`` assertions verbatim
(AT-1 / AT-2 / AT-5), one composition method per Gherkin step.
"""

from __future__ import annotations

from .._skill_source import read_distill
from .domain_types_design_wave_migration import (
    DESIGN_SECTION_HEADING,
    NW_DESIGN_WAVE,
)


class DesignSkipAdvisoryComposition:
    """SUT = the shipped nw-distill skill, driven through a filesystem read."""

    def __init__(self) -> None:
        self._distill: str = ""

    # --- Given / When ------------------------------------------------------

    def when_the_shipped_distill_skill_is_read(self) -> None:
        """Drive the port: read the REAL shipped nw-distill skill from disk."""
        self._distill = read_distill()

    # --- helpers (window scoping, no business logic) -----------------------

    def _row_7b_window(self) -> str:
        """Prose window around row 7b's DESIGN-section reference (±600 chars).

        Row 7b is the ONLY place in nw-distill that keys an advisory off the
        feature-delta's [REF] Code-Design presence; anchoring on that heading
        scopes the assertions to row 7b's own prose.
        """
        idx = self._distill.find(DESIGN_SECTION_HEADING)
        if idx == -1:
            return ""
        return self._distill[max(0, idx - 600) : idx + 600]

    # --- Then --------------------------------------------------------------

    def then_design_absent_trigger_exists(self) -> None:
        """AT-1: row 7b keys an advisory off the absence of the feature-delta's
        [REF] Code-Design section (brief §2 DESIGN-absent trigger + §3a Observe)."""
        assert DESIGN_SECTION_HEADING in self._distill, (
            "nw-distill must carry row 7b: a §Prior Wave Reading sub-step that keys "
            "the DESIGN-absent advisory off the feature-delta's [REF] Code-Design "
            "section presence (brief §2 DESIGN-absent trigger + §3a Observe)"
        )

    def then_advisory_proposes_nw_design(self) -> None:
        """AT-1: when DESIGN is absent, row 7b PROPOSEs /nw-design as the remedy
        (brief §3a Branch: 'NAME the evidence ... PROPOSE /nw-design')."""
        window = self._row_7b_window()
        assert NW_DESIGN_WAVE in window, (
            "row 7b must PROPOSE /nw-design as the remedy when the DESIGN section "
            "is absent (brief §3a: 'PROPOSE /nw-design')"
        )

    def then_advisory_branches_absent_vs_present_silent(self) -> None:
        """AT-2: row 7b's OWN conditional language — absent => advisory, present
        => silent (brief §2; §3a Branch). A DESIGN-present feature gets no
        advisory. Keys on row 7b's branch prose, NOT slice-04's matrix phrase."""
        window = self._row_7b_window().lower()
        assert "absent" in window and "present" in window, (
            "row 7b must express BOTH branches — absent => advisory, present => "
            "silent — so a DESIGN-present feature gets no advisory (AT-2)"
        )
        assert "silent" in window, (
            "row 7b's DESIGN-present branch must be silent (brief §2 "
            "'Present -> silent') — the advisory is conditional on ABSENCE"
        )

    def then_advisory_never_blocks(self) -> None:
        """AT-5: row 7b's Proceed step continues to DISTILL on ANY answer — the
        advisory never blocks (brief §3a step 3; C1 never-blocks invariant)."""
        window = self._row_7b_window()
        assert "continue to DISTILL" in window or "on any answer" in window.lower(), (
            "row 7b must PROCEED to DISTILL on ANY answer (never blocks) — "
            "brief §3a Proceed step, AT-5 / C1 never-blocks invariant"
        )
