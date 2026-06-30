"""Domain types for the discuss-epic-mode slice-07 caveman slice.

Slice-07 value: agents executing the discuss wave receive the caveman reasoning
MANDATE (verdict-first, tables, depth via ``rigor``) and ALL new epic-mode text is
verified caveman-native -- zero retroactive compression (pilot: 8-10% ceiling on
mature skills, Ale-ratified 2026-06-10).

The "code" of this slice is SKILL / COMMAND / AGENT text (D-caveman clause (b): the
reasoning mandate inserted into the discuss execution surfaces) + a caveman-native
AUDIT of the new epic-mode sections slices 02/04/05/06 already landed. There is NO
``src/des`` surface. The driving surface is the REAL ``nWave/`` files, observed
read-only (Layer 3 FS acceptance) -- mirroring slice-06's dogfood read-only model
over the real repository path, one wave-surface up.

Every domain noun in the Gherkin is expressed once here as a typed enum or NewType
(Mandate-12 criterion 1). Step bodies + the composition service consume these typed
parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the sibling epic-mode suites speak of the ``--epic``
authoring act, the Phase 1.5 escalation, the status-flip maintenance, and the
dogfood run. This suite speaks "the discuss surface carries the caveman reasoning
mandate" and "the new epic-mode section is authored caveman-native" -- distinct
domain nouns (the reasoning mandate, the house style), so the phrases never collide.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A discuss execution surface = a real ``nWave/`` file an agent executing the
# discuss wave reads. The mandate clause (D-caveman (b)) lands in the execution
# surfaces: the discuss SKILL (the methodology the agent loads) and the
# nw-product-owner agent spec (the agent that EXECUTES the discuss wave). The
# discuss TASK is the command-dispatch surface.
SurfacePath = NewType("SurfacePath", str)


class DiscussSurface(str, Enum):
    """The discuss execution surfaces the caveman reasoning mandate must reach.

    D-caveman clause (b): "agents executing the discuss wave receive the caveman
    reasoning MANDATE". The mandate must be present where the executing agent reads
    its instructions:

    SKILL    -- ``nWave/skills/nw-discuss/SKILL.md``: the discuss methodology the
                executing agent loads. The mandate's home (mirrors nw-distill
                SKILL.md:37 ``## Reasoning mandate (D-caveman ...)``).
    AGENT    -- ``nWave/agents/nw-product-owner.md``: Luna, the agent that EXECUTES
                the discuss wave. The mandate must reach the executing agent's spec
                (the "dispatch text" the slice-07 row + DoD-7 name).
    """

    SKILL = "nWave/skills/nw-discuss/SKILL.md"
    AGENT = "nWave/agents/nw-product-owner.md"


class MandatePresence(str, Enum):
    """Maintainer-observable verdict of the caveman-reasoning-mandate audit.

    The mandate is PRESENT on a surface when the surface carries the caveman
    reasoning instruction: verdict-first + tables-over-prose + depth-via-``rigor``
    (the three load-bearing clauses, mirroring nw-distill SKILL.md:37 +
    nw-agent-builder.md:112-114). A surface missing any clause is ABSENT.

    PRESENT -- the surface carries all three mandate clauses. The GREEN target.
    ABSENT  -- the surface does not carry the caveman reasoning mandate. On the
               current tip EVERY discuss surface lands here (grep verified
               2026-06-11: zero ``caveman`` / ``reasoning mandate`` hits in
               SKILL.md / discuss.md / nw-product-owner.md) -- the active-RED
               missing-functionality signal, NOT a real verdict.
    """

    PRESENT = "present"
    ABSENT = "absent"


class NativeStyleVerdict(str, Enum):
    """Verdict of the caveman-native house-style audit on a NEW epic-mode section.

    D-caveman clause (a'): ALL NEW epic-mode text is authored caveman-native --
    declarative, tables, no narrative padding. The MECHANICAL pins (this suite):
      - table-density: the section carries GFM tables (the caveman house style
        favours tables over prose);
      - narrative-padding absence: the section is free of narrative-padding markers
        (hedge/filler connectives that signal prose-bloat -- "in order to",
        "it is worth noting", "as we can see", "needless to say", ...).
    The QUALITATIVE "reads dry + domain-coherent" judgment is NOT mechanical -- it is
    routed to the Sentinel review of this slice (the LSC-4 prose-owned-split
    precedent). This enum is the mechanical verdict only.

    NATIVE      -- the section carries tables AND zero narrative-padding markers. The
                   landed slice-02/04/05/06 epic-mode sections are NATIVE today
                   (authored caveman-native by instruction) -- so this leg is a
                   WITNESS, not a RED (slice-03 WITNESS_GREEN precedent).
    NOT_NATIVE  -- the section carries narrative padding or lacks tabular structure.
    """

    NATIVE = "native"
    NOT_NATIVE = "not_native"


class CompressionVerdict(str, Enum):
    """Verdict of the zero-retroactive-compression invariant (state-delta inverse).

    D-caveman re-scope (Ale 2026-06-10): retroactive compression of mature skills is
    SUPERSEDED (pilot ceiling 8-10%). The slice-07 ATs must NOT require any existing
    text to shrink. The inverse pin: the pre-existing discuss content present BEFORE
    the mandate insertion is PRESERVED -- the mandate is an ADDITION, never a removal
    of existing sections.

    PRESERVED  -- every pre-existing discuss section heading still present after the
                  mandate insertion (state-delta: existing content unchanged, mandate
                  appended). The contract slice-07 must hold.
    SHRUNK     -- a pre-existing section was removed/compressed by the slice. A
                  D-caveman re-scope violation (retro-compression is out of scope).
    """

    PRESERVED = "preserved"
    SHRUNK = "shrunk"


# The three load-bearing mandate clauses (mirrors nw-distill SKILL.md:37 +
# nw-agent-builder.md:112-114). A surface carries the mandate iff ALL THREE appear.
# Module-level so the composition's presence check stays a single membership test,
# no control flow in the service body (Mandate-12 criterion 3).
MANDATE_CLAUSE_MARKERS: tuple[str, ...] = (
    "verdict-first",  # state the conclusion before the rationale
    "table",  # tables over prose
    "rigor",  # depth comes from the rigor profile, not padding
)

# Narrative-padding markers -- hedge / filler connectives that signal prose-bloat.
# A caveman-native section carries ZERO of these (the mechanical house-style pin).
# Mirrors the nw-agent-builder-reviewer mechanical caveman house-style check.
NARRATIVE_PADDING_MARKERS: tuple[str, ...] = (
    "in order to",
    "it is worth noting",
    "as we can see",
    "needless to say",
    "it should be noted",
    "at the end of the day",
    "for all intents and purposes",
)

# The NEW epic-mode section headings slices 02/04/05/06 landed in SKILL.md -- the
# caveman-native audit scope (clause a'). These sections must be NATIVE.
NEW_EPIC_MODE_SECTION_HEADINGS: tuple[str, ...] = (
    "## Epic Mode (`--epic`)",
    "### Epic-delta contract (EDC",
    "### Epic-delta maintenance (LSC",
)

# A pre-existing SKILL.md section heading that MUST survive the mandate insertion
# (zero-retroactive-compression witness -- the mandate ADDS, never removes). Chosen
# as a stable structural anchor present long before this feature.
PRESERVED_SECTION_HEADING: str = "## Overview"
