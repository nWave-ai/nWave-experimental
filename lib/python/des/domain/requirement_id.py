"""Canonical requirement-identifier grammar for spec coverage.

Requirement IDs are domain identities, not loose text fragments.  The legacy
``R<n>`` form remains valid and the canonical vertically-sliced form is
``R-S<two digits>-<two digits>``.  Consumers use the same boundary-aware
helpers so a near identifier (for example ``prefix-R-S01-03`` or
``R-S01-03-suffix``) cannot be attributed to a different requirement.

This is pure, stdlib-only domain logic.  Both the CLI gate and application
attribution import it; application code must not depend on a CLI module.
"""

from __future__ import annotations

import re


#: The closed requirement-ID language.  Keep this fragment unanchored so
#: context-specific consumers can compose it without re-deriving the grammar.
REQUIREMENT_ID_PATTERN = r"(?:R\d+|R-S\d{2}-\d{2})"

#: A whole checklist-cell/list identifier.
REQUIREMENT_ID_RE = re.compile(rf"^{REQUIREMENT_ID_PATTERN}$")

#: An identifier embedded in marker text.  Hyphens are deliberately part of
#: the protected boundary: ``R-S01-03-suffix`` and ``prefix-R-S01-03`` must
#: not expose ``R-S01-03`` as a valid sub-token.
REQUIREMENT_ID_TOKEN_RE = re.compile(
    rf"(?<![A-Za-z0-9-])({REQUIREMENT_ID_PATTERN})(?![A-Za-z0-9-])"
)

#: A complete Gherkin/head-comment ``@covers-<requirement-id>`` tag.  The
#: post-identifier boundary shares the exact ID contract above.
COVERS_TAG_RE = re.compile(rf"@covers-({REQUIREMENT_ID_PATTERN})(?![A-Za-z0-9-])")


def is_requirement_id(value: str) -> bool:
    """Return whether ``value`` is one complete canonical requirement ID."""
    return REQUIREMENT_ID_RE.fullmatch(value) is not None


def requirement_ids_in(text: str) -> set[str]:
    """Return only exact canonical requirement IDs embedded in ``text``."""
    return set(REQUIREMENT_ID_TOKEN_RE.findall(text))
