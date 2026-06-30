"""Domain types for mode-registry-single-locus slice-03 (the SSOT-via-Types-Services-DSL mandate, criterion 1).

Every domain noun the slice-03 Gherkin uses is expressed ONCE here as a typed
concept; composition methods consume these types (criterion 2). Step modules
coerce Gherkin phrases to these types via the *_BY_PHRASE lookup tables.

Sentinel discipline (slice-02 precedent): every value the working catalog is
EDITED to is a sentinel that appears NOWHERE in the shipped assets — its
presence in a guide's frontmatter afterwards proves the projection READ the
catalog (never baked frontmatter). The two probed guides are the 2026-06-10
hotfix victims: the execute guide's description and the distill guide's
argument hint — the exact desync class this slice makes non-representable.

Anchor discipline: each edit keys off a shipped substring verified UNIQUE in
its file and contained in a single physical line of the catalog's folded
scalar, so a plain text replacement is deterministic on the byte-copied
working assets.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


__all__ = [
    "DESYNC_BY_PHRASE",
    "DISTILL_HINT_ANCHOR",
    "DISTILL_HINT_SENTINEL",
    "EXECUTE_DESCRIPTION_ANCHOR",
    "EXECUTE_DESCRIPTION_SENTINEL",
    "HAND_EDIT_SENTINEL",
    "CommandGuide",
    "CommandName",
    "GuideDesync",
    "ProjectedField",
]


CommandName = NewType("CommandName", str)


class CommandGuide(Enum):
    """A command guide file under nWave/tasks/nw/ probed by this slice.

    Both members are the 2026-06-10 hotfix desync victims (Slice Plan
    slice-03: "execute description, distill argument_hint").
    """

    EXECUTE = "execute"
    DISTILL = "distill"

    @property
    def filename(self) -> str:
        return f"{self.value}.md"


class ProjectedField(Enum):
    """A frontmatter field the catalog projects into a command guide."""

    DESCRIPTION = "description"
    ARGUMENT_HINT = "argument-hint"


# --- Anchors (shipped substrings, verified unique per file) -------------------

# Catalog execute description, line 553 (single physical line of the folded
# scalar); appears once in the catalog and once in execute.md.
EXECUTE_DESCRIPTION_ANCHOR = "Dispatches one unit"

# Catalog distill argument_hint (single physical line); appears once in the
# catalog. The hint flag evolved (--accept-pilot-scope-extension demoted to a
# body-only cohort override; the primary distill hint is now --test-framework).
DISTILL_HINT_ANCHOR = "--test-framework=[cucumber|specflow|pytest-bdd]"


# --- Catalog-edit sentinels (appear nowhere in the shipped assets) ------------

EXECUTE_DESCRIPTION_SENTINEL = "catalog-authored execute description sentinel 9b1d"
DISTILL_HINT_SENTINEL = "--sentinel-hint-authored-by-slice-03-at-01-3e7d"

# The hand-edit desync value planted directly in a guide's frontmatter
# (AT-02 second vector — the projection must refuse it, never serve it).
HAND_EDIT_SENTINEL = "hand-edited guide description — not what the catalog says"


# --- Guide desyncs (AT-02 named sad paths) ------------------------------------


class GuideDesync(Enum):
    """A way a command guide can silently fall behind its catalog.

    Each member is one explicitly named sad path (example-based per the
    layered-discipline sad-path rule, Mandate 11) — together they ARE the
    2026-06-10 hotfix desync class."""

    CATALOG_EDITED_WITHOUT_REPROJECTION = "catalog_edited_without_reprojection"
    GUIDE_HAND_EDITED = "guide_hand_edited"


DESYNC_BY_PHRASE: dict[str, GuideDesync] = {
    "the catalog re-describes the execute command": (
        GuideDesync.CATALOG_EDITED_WITHOUT_REPROJECTION
    ),
    "the execute guide's projected description is hand-edited": (
        GuideDesync.GUIDE_HAND_EDITED
    ),
}
