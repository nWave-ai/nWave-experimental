"""Composition root for the discuss-epic-mode slice-07 caveman slice.

Slice-07 value: agents executing the discuss wave receive the caveman reasoning
MANDATE (verdict-first, tables, depth via ``rigor``) and ALL new epic-mode text is
verified caveman-native -- zero retroactive compression.

Honest mechanical-vs-prompt boundary (the central slice-07 decision)
====================================================================
The caveman reasoning mandate is METHODOLOGY/AGENT text -- prose an executing
discuss-wave agent reads. The QUALITATIVE judgment "this prose reads dry +
domain-coherent" is NOT mechanically testable; it is routed to the Sentinel review
of this slice (the LSC-4 prose-owned-split precedent). What IS mechanically pinnable
-- and what this suite pins -- are three STRUCTURAL contracts over the REAL
``nWave/`` files, observed read-only (Layer 3 FS acceptance, the slice-06 dogfood
read-only model one wave-surface up):

  1. Mandate presence (clause b): the discuss execution surfaces (SKILL + the
     nw-product-owner agent that EXECUTES the discuss wave) carry the three
     load-bearing mandate clauses (verdict-first / tables / depth-via-rigor).
     ACTIVE-RED today -- grep verified 2026-06-11: ZERO ``caveman`` /
     ``reasoning mandate`` hits in any discuss surface.

  2. Caveman-native style (clause a'): the NEW epic-mode sections slices
     02/04/05/06 landed in SKILL.md are NATIVE -- they carry GFM tables AND zero
     narrative-padding markers. WITNESS today -- the text was authored caveman-native
     by instruction (slice-03 WITNESS_GREEN precedent; the honest verdict is judged
     empirically in the fail-for-the-right-reason gate, not assumed).

  3. Zero retroactive compression (re-scope inverse): the mandate insertion is an
     ADDITION -- a pre-existing SKILL.md section (``## Overview``) survives. This is
     the state-delta inverse of the SUPERSEDED retro-compression target (pilot
     ceiling 8-10%, Ale 2026-06-10): the ATs must NOT require any existing text to
     shrink. PRESERVED today (the section exists) and must STAY preserved at GREEN.

What stays PROMPT-SURFACE (deliberately NOT an AT):
  - The exact wording / tone of the mandate prose and the epic-mode sections. A
    byte-pin of authored prose is the presence-watcher anti-pattern. The mechanical
    pins are STRUCTURAL (clause-marker presence, table presence, padding-marker
    absence, section preservation) -- the qualitative read goes to Sentinel.

S2 driving-port-only: this composition imports ZERO ``src/des`` production code.
The driving surface is the REAL ``nWave/`` files read read-only; there is no
``src/des`` seam for a methodology/prose slice (mirrors slice-04/05: prose contract,
no validator gate). S2 = PASS by construction.

S3 dormant-seam reconciliation: slice-07 declares ZERO net-new ``src/des`` seams
(mandate-only re-scope; the deliverable is prose). No net-new seam can ship dormant
-- S3 = PASS by construction.

Layer 3 (FS acceptance): the only real driven adapter is the filesystem (read-only
reads of the real ``nWave/`` files). No PBT machinery (Mandate 9/11) -- the audit is
a finite, enumerable closed contract over the discuss surfaces + the closed set of
new epic-mode section headings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    MANDATE_CLAUSE_MARKERS,
    NARRATIVE_PADDING_MARKERS,
    NEW_EPIC_MODE_SECTION_HEADINGS,
    PRESERVED_SECTION_HEADING,
    CompressionVerdict,
    DiscussSurface,
    MandatePresence,
    NativeStyleVerdict,
)


def real_repo_root() -> Path:
    """Locate the real repository root from this module's path.

    ``tests/scripts/cli/atdd_pure_discuss_epic_mode_caveman/steps/composition.py``
    -> five ``parents`` up is the repo root (the slice-06 dogfood precedent). The
    slice-07 driving surface is the REAL ``nWave/`` files: the deliverable is the
    mandate inserted into the real discuss surfaces, not a synthetic fixture.
    """
    return Path(__file__).resolve().parents[5]


def _section_body(content: str, heading: str) -> str:
    """Return the body of a markdown section (heading -> next same-or-higher heading).

    A section runs from its heading line to (but not including) the next heading at
    the same or higher level. Pure string slicing, module-level so the composition
    observation stays a single call + assertion in the step body (Mandate-12
    criterion 3).
    """
    lines = content.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith(heading)),
        None,
    )
    if start is None:
        return ""
    level = len(heading) - len(heading.lstrip("#"))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("#")
            and (len(lines[i]) - len(lines[i].lstrip("#"))) <= level
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _carries_mandate(content: str) -> bool:
    """True iff the surface carries ALL THREE load-bearing mandate clauses.

    Caveman reasoning mandate = verdict-first + tables-over-prose + depth-via-rigor
    (mirrors nw-distill SKILL.md:37 + nw-agent-builder.md:112-114). A surface carries
    the mandate only when all three markers appear -- a single ``all(...)`` over the
    closed marker set, no branching.
    """
    lowered = content.lower()
    return all(marker in lowered for marker in MANDATE_CLAUSE_MARKERS)


def _is_native(section: str) -> bool:
    """True iff a section is caveman-native: tabular/bold-lead structure AND no padding.

    Mechanical house-style pins (the nw-agent-builder mechanical check, verbatim
    nw-agent-builder.md:163: "tables and compact one-line bold-lead lists"). A native
    section favours structured density over prose -- it carries EITHER a GFM table
    (``|--- ...``) OR a compact bold-lead list (``- **Lead** -- ...``) -- AND is free
    of narrative-padding markers. Requiring a table ALONE is too narrow: the house
    style explicitly blesses the bold-lead-list form (empirically, the Epic-delta
    maintenance LSC section is a bold-lead list, not a table).
    """
    lowered = section.lower()
    has_table = "|---" in section or "| --" in section or "|--" in section
    has_bold_lead = "- **" in section
    structured = has_table or has_bold_lead
    no_padding = not any(p in lowered for p in NARRATIVE_PADDING_MARKERS)
    return structured and no_padding


@dataclass
class CavemanComposition:
    """Composition root for the slice-07 caveman-mandate + native-audit slice.

    Drives the REAL ``nWave/`` discuss surfaces read-only. ``root`` defaults to the
    real repository root (the deliverable is the mandate in the real surfaces); a
    test MAY override ``root`` to a tmp_path tree for the GREEN-path probe (write a
    conformant surface into an isolated tree, point the composition at it). The
    production observation is always over ``real_repo_root()``.
    """

    root: Path

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else real_repo_root()

    # --- reads ---------------------------------------------------------------

    def _read(self, surface: DiscussSurface) -> str:
        path = self.root / surface.value
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # --- clause 1: mandate presence (ACTIVE-RED today) -----------------------

    def observe_mandate_presence(self, surface: DiscussSurface) -> MandatePresence:
        """Observe whether a discuss execution surface carries the caveman mandate.

        On the current tip every surface reads ABSENT (the mandate is undefined in
        any discuss surface) -- the active-RED missing-functionality signal. At GREEN
        the mandate is authored into SKILL.md + nw-product-owner.md.
        """
        content = self._read(surface)
        return (
            MandatePresence.PRESENT
            if _carries_mandate(content)
            else MandatePresence.ABSENT
        )

    # --- clause 2: caveman-native style of the NEW epic-mode text (WITNESS) ---

    def observe_native_style(self) -> NativeStyleVerdict:
        """Audit the NEW epic-mode sections (slices 02/04/05/06) for native style.

        NATIVE iff EVERY new epic-mode section carries a GFM table AND zero
        narrative-padding markers. WITNESS today (the sections were authored
        caveman-native by instruction). A single ``all(...)`` over the closed
        heading set, no branching.
        """
        content = self._read(DiscussSurface.SKILL)
        return (
            NativeStyleVerdict.NATIVE
            if all(
                _is_native(_section_body(content, heading))
                for heading in NEW_EPIC_MODE_SECTION_HEADINGS
            )
            else NativeStyleVerdict.NOT_NATIVE
        )

    # --- clause 3: zero retroactive compression (state-delta inverse) --------

    def observe_compression(self) -> CompressionVerdict:
        """Observe the zero-retroactive-compression invariant.

        PRESERVED iff a pre-existing SKILL.md section (``## Overview``) still exists
        -- the mandate insertion is an ADDITION, never a removal of existing content.
        The state-delta inverse of the SUPERSEDED retro-compression target.
        """
        content = self._read(DiscussSurface.SKILL)
        return (
            CompressionVerdict.PRESERVED
            if PRESERVED_SECTION_HEADING in content
            else CompressionVerdict.SHRUNK
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        Slice-07 mutates no repository state -- the ATs are read-only observations of
        the real ``nWave/`` files. The zero-retroactive-compression invariant is the
        observable: the pre-existing ``## Overview`` section is PRESERVED across the
        mandate insertion (the mandate ADDS, never removes).
        """
        return {
            "skill.preserved_section.present": self.observe_compression()
            == CompressionVerdict.PRESERVED,
        }
