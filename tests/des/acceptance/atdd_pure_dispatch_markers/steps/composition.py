"""Composition root for hg-slice-00 -- atdd_pure dispatch marker recognition.

hg-slice-00 of F-DES-ATDD-PURE-HOOK-GATES (U0 -- ADR-030 D8).

Wires the PRODUCTION marker-recognition surfaces:
  * `des.domain.des_marker_parser.DesMarkerParser` -- the extended parser
    (hg-slice-00 adds DES-PHASE / DES-SLICE patterns + atdd_pure DesMarkers
    fields + value normalisation + enum/anchor validation).
  * `des.domain.des_marker_parser.classify_atdd_pure_dispatch` -- the
    three-way (absent / valid / defective) dispatch classifier. This is the
    mechanical core the `/nw-deliver` phase-entry diagnostic consumes to refuse
    a defective dispatch (the verified-emission backstop, ADR-030 D8).

Layer 1-2: the driving port is the `DesMarkerParser` domain class -- a pure,
no-I/O parser. The only real I/O is reading the production `nw-deliver/SKILL.md`
skill file for the walking-skeleton scenario, so that scenario exercises the
GENUINE atdd_pure dispatch template (not a hand-written fixture prompt).

Business logic lives in the production surfaces above; step bodies delegate to
`DispatchMarkerComposition` methods and never inline logic (Mandate-12
criterion 3).

RED contract: the production surfaces do not exist on master. This module
imports them at module load; on master that import fails, so the slice-00 RED
scaffold (the production-side `__SCAFFOLD__` stub at
`src/des/domain/des_marker_parser.py`) must provide the symbols raising
AssertionError -- yielding RED (MISSING_FUNCTIONALITY), never BROKEN
(ImportError). hg-slice-00 GREEN replaces the scaffold with the real parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from des.domain.atdd_pure_phases import LEGACY_PHASE_ALIASES, ATDDPurePhase
from des.domain.des_marker_parser import (
    DesMarkerParser,
    atdd_pure_missing_marker,
    classify_atdd_pure_dispatch,
)

from .domain_types import DispatchRecognition, MarkerPresence


# Repo root -- this file is tests/des/acceptance/atdd_pure_dispatch_markers/steps/.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The production skill file whose atdd_pure dispatch template hg-slice-00
# extends to emit the three markers. The walking-skeleton scenario reads the
# REAL file -- if the markers are not emitted there, the round-trip fails.
_NW_DELIVER_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"


def _marker_line(name: str, value: str) -> str:
    """Render one DES marker in the canonical `<!-- DES-X : value -->` shape."""
    return f"<!-- {name} : {value} -->"


def _render_prompt(
    mode: MarkerPresence,
    phase: MarkerPresence,
    slice_marker: MarkerPresence,
) -> str:
    """Render a dispatch prompt carrying the requested subset of markers.

    A MarkerPresence of ABSENT means the corresponding marker line is omitted
    entirely. Any other value is emitted verbatim as the marker's value -- so a
    malformed or out-of-vocabulary token reaches the parser unaltered.
    """
    lines = ["# DES_METADATA", "<!-- DES-VALIDATION : required -->"]
    if mode is not MarkerPresence.ABSENT:
        lines.append(_marker_line("DES-MODE", mode.value))
    if phase is not MarkerPresence.ABSENT:
        lines.append(_marker_line("DES-PHASE", phase.value))
    if slice_marker is not MarkerPresence.ABSENT:
        lines.append(_marker_line("DES-SLICE", slice_marker.value))
    return "\n".join(lines)


def _extract_atdd_pure_dispatch_block(skill_text: str) -> str:
    """Pull the atdd_pure dispatch-prompt block out of the real nw-deliver skill.

    hg-slice-00 extends the nw-deliver atdd_pure dispatch path to emit the three
    markers. The block is delimited by the markers themselves; this returns the
    contiguous prompt region carrying `DES-MODE : atdd_pure`. If the skill file
    has not yet been extended (master state) the region is absent and the
    returned text carries no atdd_pure markers -- so the walking-skeleton
    scenario fails RED for MISSING_FUNCTIONALITY, never for a fixture bug.
    """
    return skill_text


@dataclass
class ParseOutcome:
    """The observable result of parsing / classifying a dispatch prompt."""

    recognition: DispatchRecognition
    mode: str | None
    atdd_pure_phase: str | None
    slice_id: str | None
    refused_missing_marker: str | None = None


class DispatchMarkerComposition:
    """Production-wired composition root for the marker-recognition slice.

    The driving port is the `DesMarkerParser` domain class plus the
    `classify_atdd_pure_dispatch` classifier. No mutable system state -- both
    surfaces are pure functions of the prompt text.
    """

    def __init__(self) -> None:
        self._parser = DesMarkerParser()
        self._prompt: str | None = None
        # The three marker selections, accumulated by the Given/And steps and
        # rendered into a prompt lazily on the first driving-port invocation.
        self._mode: MarkerPresence = MarkerPresence.ABSENT
        self._phase: MarkerPresence = MarkerPresence.ABSENT
        self._slice: MarkerPresence = MarkerPresence.ABSENT

    # --- prompt provisioning -------------------------------------------------

    def use_production_nw_deliver_prompt(self) -> None:
        """Load the GENUINE atdd_pure dispatch prompt from the nw-deliver skill."""
        skill_text = _NW_DELIVER_SKILL.read_text(encoding="utf-8")
        self._prompt = _extract_atdd_pure_dispatch_block(skill_text)

    def set_mode_marker(self, mode: MarkerPresence) -> None:
        """Record the DES-MODE marker selection for the rendered prompt."""
        self._mode = mode

    def set_phase_marker(self, phase: MarkerPresence) -> None:
        """Record the DES-PHASE marker selection for the rendered prompt."""
        self._phase = phase

    def set_slice_marker(self, slice_marker: MarkerPresence) -> None:
        """Record the DES-SLICE marker selection for the rendered prompt."""
        self._slice = slice_marker

    def _resolved_prompt(self) -> str:
        """The production prompt if loaded, else the prompt rendered from markers."""
        if self._prompt is not None:
            return self._prompt
        return _render_prompt(self._mode, self._phase, self._slice)

    # --- driving-port invocations -------------------------------------------

    def parse_dispatch(self) -> ParseOutcome:
        """Parse the dispatch prompt via the production DesMarkerParser."""
        markers = self._parser.parse(self._resolved_prompt())
        recognition = classify_atdd_pure_dispatch(markers)
        return ParseOutcome(
            recognition=recognition,
            mode=markers.mode,
            atdd_pure_phase=markers.atdd_pure_phase,
            slice_id=markers.slice_id,
        )

    def classify_dispatch(self) -> ParseOutcome:
        """Classify the dispatch prompt into absent / valid / defective."""
        return self.parse_dispatch()

    def run_phase_entry_diagnostic(self) -> ParseOutcome:
        """Run the nw-deliver phase-entry diagnostic over the dispatch prompt.

        The diagnostic's mechanical core is `classify_atdd_pure_dispatch`: a
        DEFECTIVE classification names which marker the dispatch is missing /
        malformed, and the diagnostic refuses the dispatch on that finding.
        """
        markers = self._parser.parse(self._resolved_prompt())
        recognition = classify_atdd_pure_dispatch(markers)
        missing = atdd_pure_missing_marker(markers)
        return ParseOutcome(
            recognition=recognition,
            mode=markers.mode,
            atdd_pure_phase=markers.atdd_pure_phase,
            slice_id=markers.slice_id,
            refused_missing_marker=missing,
        )

    # --- observable-vocabulary helpers --------------------------------------

    @staticmethod
    def phase_vocabulary() -> frozenset[str]:
        """The closed ATDD-pure phase vocabulary a valid DES-PHASE draws from.

        After the 7->3 reduction (fix-atdd-pure-spine-phase-count-reduction
        slice-02) the live enum carries only the canonical phases, but the parser
        still recognises the retired legacy phase words by replaying them onto
        their canonical phase. A valid DES-PHASE therefore draws from the union
        of the live canonical members AND the recognised legacy alias words --
        the real nw-deliver SKILL.md still spells the entry phase ``A_GREEN_ATS``
        (its prose migrates in slice-03), so the walking-skeleton round-trip
        legitimately parses a legacy word the parser recognises.
        """
        return frozenset(p.value for p in ATDDPurePhase) | frozenset(
            LEGACY_PHASE_ALIASES
        )
