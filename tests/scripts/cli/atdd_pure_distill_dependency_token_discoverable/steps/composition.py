"""Composition root: read the ``nw-distill`` skill FAMILY (or a fabricated
fixture) and extract the token-locus text an acceptance-designer would see.

No production driving port exists for "is this documented" -- these are prose
files, not executable code (same posture as the row-1 sibling suite and as
AT-d in ``tests/des/unit/cli/test_carpaccio_ceiling_7_and_coupled_affordance.py``
for the ``@coupled`` affordance). This composition root reads the real repo /
installed family files directly.

Two discipline points beyond a bare substring match:

1. **Locus-scoped, not file-scoped.** The exact family file that gains the
   pointer is DESIGN's decision (feature-delta D-3: core ``nw-distill`` or a
   composed module). So we scan the whole family for the token, then extract a
   window AROUND the first occurrence and assert the flip + the nw-discuss
   cross-link sit NEAR the token -- discoverability means the pointer travels
   WITH the token, not that both merely appear somewhere in the family.

2. **Cross-link, not copy (D-4 SSOT/DRY).** The locus must NAME nw-discuss's
   own vocabulary reference (``nw-discuss`` + ``Slice Plan annotation
   vocabulary``). A restated copy that omits the pointer is rejected -- that is
   the copy that drifts the next time row 1's grammar is amended.

Anti-pattern detectors (``demands_justification_on_empty`` /
``reads_silence_as_serial``) are negation-aware: a correct edit that CONTRASTS
the flipped default against the old "assume serial" guess ("parallel-safe, NOT
assume serial") must not be mistaken for the family actually asserting it.

Both source and installed copies are checked -- an agent reads the INSTALLED
copy at runtime. An absent installed family reports ``tree_present=False``
(fresh clone / CI, not a defect) instead of raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .domain_types import FabricatedFamily, FamilyTree


_DEPENDENCY_TOKEN_RE = re.compile(r"depends-on\s*\{slice-id\}", re.IGNORECASE)

# The flipped default in plain language: silence/empty is parallel-safe.
_SILENCE_RE = re.compile(
    r"\b("
    r"silence"
    r"|empty(?:\s+annotation)?(?:\s+cell)?"
    r"|nothing\s+declared"
    r"|no\s+(?:declared|explicit)?\s*(?:annotation|dependency)"
    r")\b",
    re.IGNORECASE,
)
_PARALLEL_SAFE_RE = re.compile(
    r"parallel[- ]safe|parallel\s+by\s+default", re.IGNORECASE
)

# The cross-link pointer to nw-discuss's SSOT vocabulary section (D-4).
_DISCUSS_NAME_RE = re.compile(r"nw-discuss", re.IGNORECASE)
_VOCAB_REFERENCE_RE = re.compile(
    r"Slice\s+Plan\s+annotation\s+vocabulary", re.IGNORECASE
)

# Anti-pattern A -- the un-flipped default: an empty Annotation OWES a
# Justification. Deliberately does NOT match the correct phrasing
# ("empty Annotation cell IS parallel-safe by default ... a DECLARED
# depends-on owes a Justification ... silence never needs one").
_EMPTY_NEEDS_JUSTIFICATION_RE = re.compile(
    r"empty\s+annotation(?:\s+cell)?\s+"
    r"(?:requires?|needs?|owes?|must\s+(?:carry|have|provide|include))\s+"
    r"(?:a\s+|an\s+|its\s+|the\s+)?(?:non-empty\s+)?justification",
    re.IGNORECASE,
)

# Anti-pattern B -- silence read as "assume serial".
_ASSUME_SERIAL_RE = re.compile(
    r"assume[ds]?\s+serial"
    r"|serial\s+by\s+default"
    r"|(?:silence|empty|nothing\s+declared)\s+"
    r"(?:means?|reads?|implies|=)\s*.{0,25}serial",
    re.IGNORECASE,
)

# A negator immediately preceding an anti-pattern flips its polarity: the family
# CONTRASTING the flipped default against the old guess is not the family
# asserting it.
_NEGATOR_RE = re.compile(
    r"\b(?:not|never|no\s+longer|isn't|is\s+not|rather\s+than|instead\s+of|"
    r"retire[sd]?|retiring|to\s+retire)\b",
    re.IGNORECASE,
)

_LOCUS_RADIUS = 700  # chars each side of the token -- "near the token"


@dataclass(frozen=True)
class FamilyRead:
    family_text: str  # every family file concatenated -- whole-family checks
    locus_text: str  # window around the first token occurrence ("" if absent)
    token_found: bool
    tree_present: bool


def _repo_root() -> Path:
    # steps/composition.py -> steps -> atdd_pure_distill_dependency_token_discoverable
    # -> cli -> scripts -> tests -> repo root
    return Path(__file__).resolve().parents[5]


def _family_files(tree: FamilyTree) -> list[Path]:
    base = (
        _repo_root() / "nWave" / "skills"
        if tree is FamilyTree.SOURCE
        else Path.home() / ".claude" / "skills"
    )
    return sorted(base.glob("nw-distill*/SKILL.md"))


def _extract_locus(text: str) -> str:
    m = _DEPENDENCY_TOKEN_RE.search(text)
    if not m:
        return ""
    return text[max(0, m.start() - _LOCUS_RADIUS) : m.end() + _LOCUS_RADIUS]


def documents_dependency_token(text: str) -> bool:
    return bool(_DEPENDENCY_TOKEN_RE.search(text))


def states_default_flip(text: str) -> bool:
    return bool(_SILENCE_RE.search(text)) and bool(_PARALLEL_SAFE_RE.search(text))


def references_discuss_vocabulary(text: str) -> bool:
    return bool(_DISCUSS_NAME_RE.search(text)) and bool(
        _VOCAB_REFERENCE_RE.search(text)
    )


def _has_unnegated(pattern: re.Pattern[str], text: str) -> bool:
    for m in pattern.finditer(text):
        preceding = text[max(0, m.start() - 40) : m.start()]
        if not _NEGATOR_RE.search(preceding):
            return True
    return False


def demands_justification_on_empty(text: str) -> bool:
    return _has_unnegated(_EMPTY_NEEDS_JUSTIFICATION_RE, text)


def reads_silence_as_serial(text: str) -> bool:
    return _has_unnegated(_ASSUME_SERIAL_RE, text)


_FABRICATED: dict[FabricatedFamily, str] = {
    FabricatedFamily.RESTATED_NO_CROSSLINK: (
        "## 3-source induction map\n\n"
        "When DISTILL originates a Slice Plan, annotate an ordering dependency "
        "with `depends-on {slice-id}`. An empty Annotation cell is "
        "parallel-safe by default; a declared dependency owes a one-line "
        "Justification.\n"
        # DELIBERATELY no `nw-discuss` / no `Slice Plan annotation vocabulary`
        # pointer -- an independently-worded copy that will drift (D-4).
    ),
    FabricatedFamily.BARE_TOKEN_NO_FLIP: (
        "## 3-source induction map\n\n"
        "Annotate an ordering dependency with `depends-on {slice-id}`. See "
        "nw-discuss SKILL.md's Slice Plan annotation vocabulary (reference) for "
        "the canonical token list.\n"
        # token + pointer present, but the default-flip is NOT stated.
    ),
    FabricatedFamily.EMPTY_NEEDS_JUSTIFICATION: (
        "## 3-source induction map\n\n"
        "Use `depends-on {slice-id}` for ordering. An empty Annotation cell "
        "needs a Justification too -- every row must state its reason. See "
        "nw-discuss SKILL.md's Slice Plan annotation vocabulary (reference).\n"
        # the un-flipped default resurrected: silence made to owe a Justification.
    ),
    FabricatedFamily.ASSUME_SERIAL: (
        "## 3-source induction map\n\n"
        "Use `depends-on {slice-id}` for ordering. Silence means assume serial "
        "by row order. See nw-discuss SKILL.md's Slice Plan annotation "
        "vocabulary (reference).\n"
    ),
}


class DistillDependencyDiscoverabilityComposition:
    """Resolves the ``nw-distill`` skill family (or a fabricated fixture) to its
    token-locus text and whole-family text."""

    def read_family(self, tree: FamilyTree) -> FamilyRead:
        files = _family_files(tree)
        if not files:
            return FamilyRead(
                family_text="",
                locus_text="",
                token_found=False,
                tree_present=False,
            )
        parts: list[str] = []
        locus = ""
        for path in files:
            text = path.read_text(encoding="utf-8")
            parts.append(text)
            if not locus:
                locus = _extract_locus(text)
        return FamilyRead(
            family_text="\n".join(parts),
            locus_text=locus,
            token_found=bool(locus),
            tree_present=True,
        )

    def read_fabricated(self, fixture: FabricatedFamily) -> FamilyRead:
        """Run the fabricated fixture's FULL text through the SAME locus
        extraction a real family read uses -- proves the negative scenarios
        exercise the real extraction boundary, not a pre-extracted string."""
        text = _FABRICATED[fixture]
        return FamilyRead(
            family_text=text,
            locus_text=_extract_locus(text),
            token_found=bool(_DEPENDENCY_TOKEN_RE.search(text)),
            tree_present=True,
        )
