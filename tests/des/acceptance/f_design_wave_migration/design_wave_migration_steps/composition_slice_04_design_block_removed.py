"""Composition root for f-design-wave-migration slice-04 Gherkin ATs.

Driving surface (Mandate-13 prose-surface case): the filesystem read of the REAL
shipped skill files via the shared ``_skill_source`` helper (read_distill +
read_deliver — reused, NOT duplicated). slice-04 is a removal-only consolidation:
the DESIGN-absence-keyed BLOCK / hard MANDATORY-read is reconciled away across the
WHOLE removal surface (AT-8), verified by ABSENCE + NON-REGRESSION so the
never-blocks invariant C1 holds end-to-end.

THE FOUR LOCI AT-8 SCANS (DESIGN §Removal map R-1..R-4; ADR-DWM-001):
  R-4  nw-distill  1st matrix ("warn vs block")          BLOCK -> WARN/advisory
                   + EXCEPT DESIGN carve-out dropped.
  R-3  nw-distill  2nd matrix ("Missing Upstream")        BLOCK -> proceed/advisory
                   + EXCEPT DESIGN carve-out dropped (byte-twin, one matrix over).
  R-1  nw-deliver  DESIGN read declass from MANDATORY -> read-if-present.
  R-2  nw-deliver  READING ENFORCEMENT brief.md drops the hard-require conjunct.

DISCRIMINATING, NOT TAUTOLOGY (both halves, so a no-op deletion that also strips
the advisory cannot false-green): ABSENCE — the BLOCK/MANDATORY token is gone
from EACH locus's OWN window; PRESENCE — an advisory / read-if-present replacement
is present in the SAME window (reconciled, not merely deleted).

GREEN-not-active-RED: format conversion of PASSING behaviour — all four loci are
already reconciled in the shipped skills. Each oracle stays GENUINE
(mutation-verified): re-inserting BLOCK into a matrix row, or MANDATORY into the
deliver DESIGN step, reds the scenario.

Mirrors the original ``test_slice04_design_block_removed.py`` AT-8 assertions,
folding each matrix's row + carve-out witness into one scenario per matrix
(carpaccio ceiling <=5 — 4 load-bearing scenarios, no coverage lost).
"""

from __future__ import annotations

from .._skill_source import read_deliver, read_distill
from .domain_types_design_wave_migration import DesignMatrix


# nw-deliver R-1 anchor: the DESIGN reading step in §Prior Wave Reading.
_R1_DESIGN_STEP = "**DESIGN**"
# nw-deliver R-2 anchor: the READING ENFORCEMENT block.
_R2_ENFORCEMENT = "**READING ENFORCEMENT**"


class DesignBlockRemovedComposition:
    """SUT = the shipped nw-distill + nw-deliver skills, driven through
    filesystem reads. AT-8 owns the four removal loci exclusively."""

    def __init__(self) -> None:
        self._distill: str = ""
        self._deliver: str = ""

    # --- When --------------------------------------------------------------

    def when_the_shipped_distill_skill_is_read(self) -> None:
        """Drive the port: read the REAL shipped nw-distill skill from disk."""
        self._distill = read_distill()

    def when_the_shipped_deliver_skill_is_read(self) -> None:
        """Drive the port: read the REAL shipped nw-deliver skill from disk."""
        self._deliver = read_deliver()

    # --- helpers (window scoping, no business logic) -----------------------

    @staticmethod
    def _matrix_window(text: str, heading: str) -> str:
        """The body of a Graceful-Degradation matrix — heading to next top-level
        `## ` (or EOF) — so DESIGN-row assertions are scoped to THAT matrix only
        (the veto lives in TWO matrices; R-3/R-4 witnessed independently)."""
        start = text.find(heading)
        if start == -1:
            return ""
        body_start = start + len(heading)
        nxt = text.find("\n## ", body_start)
        return text[body_start:] if nxt == -1 else text[body_start:nxt]

    @staticmethod
    def _design_row(matrix_body: str) -> str:
        """The single table row in a matrix body that keys on a `design/` path."""
        for line in matrix_body.splitlines():
            if "design/" in line and "|" in line:
                return line
        return ""

    @staticmethod
    def _window(text: str, anchor: str, before: int = 80, after: int = 520) -> str:
        """Prose window around an anchor, scoping each assertion to the locus's
        OWN clause. Empty when the anchor is absent (caller asserts first)."""
        idx = text.find(anchor)
        if idx == -1:
            return ""
        return text[max(0, idx - before) : idx + len(anchor) + after]

    # --- Then: nw-distill matrices (R-4 / R-3 — row + carve-out) -----------

    def then_matrix_design_block_reconciled_to_advisory(
        self, matrix: DesignMatrix
    ) -> None:
        """AT-8 / R-4 + R-3: the named nw-distill Graceful-Degradation matrix's
        DESIGN row no longer carries the DESIGN-absence BLOCK veto — reconciled to
        an advisory that PROCEEDS (never blocks, C1). ABSENCE: 'BLOCK' gone from
        THAT row. PRESENCE: a WARN/advisory/proceed replacement in the same row.
        AND the matrix's 'EXCEPT ... BLOCK' DESIGN carve-out is dropped while the
        'warnings, not failures' degrade wording survives (the carve-out is the
        same veto in prose form, one clause below the row)."""
        heading = matrix.value
        body = self._matrix_window(self._distill, heading)
        assert body, (
            f"nw-distill must still carry the '{heading}' matrix (slice-04 "
            "reconciles its DESIGN row in-place; it does not delete the matrix — "
            "the DEVOPS/DISCUSS rows stay)"
        )
        row = self._design_row(body)
        assert row, (
            f"the '{heading}' matrix must still carry a `design/` row "
            "(reconciled in-place to advisory, not removed)"
        )
        # ABSENCE: the DESIGN-absence BLOCK veto is gone from this row.
        assert "BLOCK" not in row, (
            f"NOT reconciled: the '{heading}' matrix STILL BLOCKs on DESIGN "
            f"absence — surviving row: {row!r}. Per ADR-DWM-001 / C1 the DESIGN "
            "row must be declassed from BLOCK to advisory (WARN/proceed)."
        )
        # PRESENCE: the advisory/proceed replacement is actually there.
        lowered = row.lower()
        assert "warn" in lowered or "advisory" in lowered or "proceed" in lowered, (
            "reconciled to a BARE DELETION (advisory missing): the `design/` row "
            f"dropped BLOCK but carries no WARN/advisory/proceed replacement — "
            f"surviving row: {row!r}. The never-blocks behaviour must be PRESENT."
        )
        # Carve-out ABSENCE: the DESIGN-keyed "EXCEPT ... BLOCK" clause is gone.
        has_except_block = "EXCEPT" in body and "BLOCK" in body
        assert not has_except_block, (
            f"carve-out NOT dropped: the '{heading}' matrix's rationale clause "
            "STILL carries the 'EXCEPT ... (DESIGN for hexagonal boundary): BLOCK' "
            "exception — the DESIGN-absence veto in prose form, re-asserting the "
            "block one clause below the reconciled row (ADR-DWM-001: drop it)."
        )
        # Carve-out PRESENCE: the 'warnings, not failures' wording survives.
        assert "warnings" in body.lower(), (
            f"carve-out reconciled by BARE DELETION: the '{heading}' 'Missing "
            "artifacts -> warnings, not failures' clause was removed entirely "
            "instead of having only its DESIGN BLOCK exception dropped — the "
            "degrade-to-warning behaviour must remain PRESENT (ADR-DWM-001)."
        )

    # --- Then: nw-deliver DESIGN read declass (R-1) ------------------------

    def then_deliver_design_read_not_mandatory(self) -> None:
        """AT-8 / R-1: the nw-deliver DESIGN reading step — '**DESIGN**
        (structural context, MANDATORY): Read brief.md ...' — must drop the
        unconditional MANDATORY hard-require. ABSENCE: the step no longer marks
        the read MANDATORY. PRESENCE: a read-if-present / degrade replacement is
        in the SAME step (reconciled, not deleted)."""
        window = self._window(self._deliver, _R1_DESIGN_STEP)
        assert window, (
            "nw-deliver must still carry a DESIGN reading step in §Prior Wave "
            "Reading (slice-04 reconciles it to read-if-present, not delete — R-1)"
        )
        assert "MANDATORY" not in window, (
            "R-1 NOT reconciled: nw-deliver STILL marks the DESIGN read MANDATORY "
            f"— surviving DESIGN step window: {window!r}. Per ADR-FLOW-002 D2 "
            "(optional DESIGN) the read must be declassed to read-if-present."
        )
        lowered = window.lower()
        assert (
            "if present" in lowered
            or "read-if-present" in lowered
            or "if the feature ran design" in lowered
            or "degrade" in lowered
        ), (
            "R-1 reconciled to a BARE DELETION (conditional read missing): the "
            "DESIGN step dropped MANDATORY but carries no read-if-present / "
            f"degrade-loud replacement — surviving window: {window!r}. DELIVER "
            "must still READ the DESIGN artifact WHEN present; only ABSENT degrades."
        )

    # --- Then: nw-deliver READING ENFORCEMENT brief.md hard-require (R-2) ---

    def then_deliver_reading_enforcement_brief_not_hard_required(self) -> None:
        """AT-8 / R-2: the nw-deliver READING ENFORCEMENT block — 'You MUST read
        feature-delta.md ... AND docs/product/architecture/brief.md ...' — must
        drop the unconditional hard-require of the DESIGN artifact (brief.md).
        ABSENCE: brief.md is no longer a conjunct of the 'You MUST read ... AND'
        sentence. PRESENCE (non-regression): the surviving MUST-reads
        (feature-delta + .feature) stay hard-required."""
        window = self._window(self._deliver, _R2_ENFORCEMENT, before=20, after=620)
        assert window, (
            "nw-deliver must still carry the READING ENFORCEMENT block (slice-04 "
            "reconciles brief.md to read-if-present, not delete the enforcement "
            "of the feature-delta / .feature reads — R-2)"
        )
        # Bound the hard-require to its own sentence (first period) so we read
        # ONLY the MUST-read conjunction, not the trailing checklist prose.
        must_read_sentence = window
        must_idx = window.find("You MUST read")
        if must_idx != -1:
            tail = window[must_idx:]
            dot = tail.find(". ")
            must_read_sentence = tail if dot == -1 else tail[: dot + 1]
        brief_in_must_read = "You MUST read" in must_read_sentence and (
            "brief.md" in must_read_sentence
            or "architecture/brief" in must_read_sentence
        )
        assert not brief_in_must_read, (
            "R-2 NOT reconciled: the nw-deliver READING ENFORCEMENT block STILL "
            "hard-requires brief.md as a conjunct of the unconditional 'You MUST "
            "read ... AND docs/product/architecture/brief.md ...' sentence — "
            f"surviving MUST-read sentence: {must_read_sentence!r}. brief.md must "
            "move OUT of the hard-require conjunction to a read-if-present clause."
        )
        # PRESENCE (non-regression): the surviving MUST-reads stay enforced.
        assert "You MUST read" in window and (
            "feature-delta" in window or ".feature" in window
        ), (
            "R-2 reconciled by over-deletion: the READING ENFORCEMENT block no "
            "longer hard-requires the surviving MUST-reads (feature-delta / "
            f".feature) — surviving block: {window!r}. Only brief.md is in the "
            "R-2 removal surface; the feature-delta + .feature enforcement stays."
        )
