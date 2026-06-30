"""Composition root for f-design-wave-migration slice-03 Gherkin ATs.

Driving surface (Mandate-13 prose-surface case): the filesystem read of the REAL
shipped nw-distill skill via the shared ``_skill_source.read_distill`` helper
(reused — NOT duplicated). The keystone deliverable is a REUSABLE PROSE PATTERN:
the named anchored block ``## Advisory-Skip-Gate Pattern (Tier-A)`` authored ONCE
that the 5 sibling wave-migrations EXTEND by anchor reference. The deterministic,
git-free, cross-OS observable is that the block exists, carries the five-slot
Tier-A closed-option ESC shape co-located in its own body, is a SINGLE authored
locus, and is REFERENCED by rows 7b/7c rather than re-inlined per trigger.

GREEN-not-active-RED: format conversion of PASSING behaviour — the pattern block
already ships. Each oracle stays GENUINE (mutation-verified): removing the anchor
heading, dropping a slot, or stripping the row references reds the scenario.

Mirrors the original ``test_slice03_reusable_pattern.py`` AT-7 assertions.
"""

from __future__ import annotations

from .._skill_source import read_distill
from .domain_types_design_wave_migration import FIVE_SLOTS, PATTERN_ANCHOR


class ReusablePatternComposition:
    """SUT = the shipped nw-distill skill, driven through a filesystem read."""

    def __init__(self) -> None:
        self._distill: str = ""

    # --- When --------------------------------------------------------------

    def when_the_shipped_distill_skill_is_read(self) -> None:
        """Drive the port: read the REAL shipped nw-distill skill from disk."""
        self._distill = read_distill()

    def _pattern_block(self) -> str:
        """The prose body of the `## Advisory-Skip-Gate Pattern (Tier-A)` block —
        from its heading to the next top-level `## ` heading (or EOF) — so the
        five-slot assertion is scoped to the pattern's OWN body."""
        start = self._distill.find(PATTERN_ANCHOR)
        if start == -1:
            return ""
        body_start = start + len(PATTERN_ANCHOR)
        nxt = self._distill.find("\n## ", body_start)
        return (
            self._distill[body_start:] if nxt == -1 else self._distill[body_start:nxt]
        )

    # --- Then --------------------------------------------------------------

    def then_pattern_block_is_a_citable_anchor(self) -> None:
        """AT-7 (1/3): nw-distill carries the named anchored block
        `## Advisory-Skip-Gate Pattern (Tier-A)` so a sibling wave-migration can
        grep-cite it as the SSOT anchor (DESIGN §:330, :350; KPI-4)."""
        assert PATTERN_ANCHOR in self._distill, (
            "nw-distill must carry the named anchored block "
            f"'{PATTERN_ANCHOR}' — the reusable Tier-A advisory-skip-gate pattern "
            "authored ONCE that the 5 sibling wave-migrations EXTEND by anchor "
            "reference (DESIGN §Reusable advisory-skip-gate pattern; KPI-4)"
        )

    def then_pattern_block_carries_five_tier_a_slots(self) -> None:
        """AT-7 (2/3): the pattern block carries the five-slot Tier-A
        closed-option ESC shape (NAME / RISK / PROPOSE / ASK / PROCEED) in its OWN
        body, so a sibling can reference the anchor and bind each slot to its
        wave (DESIGN §:351-359)."""
        block = self._pattern_block()
        assert block, (
            f"the '{PATTERN_ANCHOR}' block must exist with a body before its five "
            "slots can be asserted (AT-7)"
        )
        missing = [slot for slot in FIVE_SLOTS if slot not in block]
        assert not missing, (
            "the advisory-skip-gate pattern block must define all five Tier-A "
            f"closed-option slots {list(FIVE_SLOTS)} in its own body so a sibling "
            f"can bind each per wave — missing from the block: {missing} (AT-7)"
        )

    def then_pattern_is_single_locus_referenced_by_both_rows(self) -> None:
        """AT-7 (3/3): the shape is authored ONCE and rows 7b + 7c REFERENCE the
        anchor rather than re-inlining the five-slot shape — the pattern is SSOT,
        the per-trigger binding is delta (DESIGN §:330, :350, :361-362)."""
        # Single authored locus: the SSOT anchor heading is authored exactly once.
        count = self._distill.count(PATTERN_ANCHOR)
        assert count == 1, (
            f"the '{PATTERN_ANCHOR}' block must be authored EXACTLY once (SSOT "
            f"single locus) — found {count}; a sibling cites ONE anchor, the "
            "shape is never re-inlined per trigger (DESIGN §:330, :361, AT-7)"
        )
        # Both existing triggers REFERENCE the pattern name (the citable shape).
        citations = self._distill.count("Advisory-Skip-Gate Pattern (Tier-A)")
        assert citations >= 2, (
            "rows 7b (/nw-design) and 7c (/nw-discuss) must REFERENCE the "
            "'Advisory-Skip-Gate Pattern (Tier-A)' anchor (the shape authored "
            f"once + cited per trigger) — found {citations} mentions; expected the "
            "block heading PLUS >=1 reference so the shape is cited, not re-inlined "
            "(DESIGN §:350, :361-362, AT-7)"
        )
