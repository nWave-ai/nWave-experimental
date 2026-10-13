"""The ONE `<document>#<heading>` rule a DESIGN `authority_locator` obeys.

The ordered clauses are shared by restored-handover validation and the published
description of persisted section identities. The DESIGN constructor assigns
the configured locator; it is not part of the architect's response manifest.

The PATH half of the grammar is NOT respelled here: it is
``des.domain.architecture_brief_resolver``'s, whose own header already declares
it the sole owner of the repository-relative whole-file shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.architecture_brief_resolver import (
    is_repository_relative_whole_file_locator,
)


if TYPE_CHECKING:
    from collections.abc import Callable


def _document(locator: str) -> str:
    return locator.partition("#")[0]


def _heading(locator: str) -> str:
    return locator.partition("#")[2]


#: Ordered clauses for persisted DESIGN section locators.
LOCATOR_CLAUSES: tuple[tuple[str, Callable[[str], bool]], ...] = (
    (
        "it carries exactly one `#`, separating the document from the heading",
        lambda locator: locator.count("#") == 1,
    ),
    (
        "the text before the `#` is a repository-relative whole-file path: no "
        "leading `/`, no `.` or `..` segment, and never a URL or prose",
        lambda locator: is_repository_relative_whole_file_locator(_document(locator)),
    ),
    (
        "the heading after the `#` is not empty",
        lambda locator: bool(_heading(locator)),
    ),
    (
        "the heading contains no further `#`",
        lambda locator: "#" not in _heading(locator),
    ),
    (
        "the heading contains no line break, neither LF nor CR",
        lambda locator: "\n" not in _heading(locator) and "\r" not in _heading(locator),
    ),
)

#: An empty internal locator precedes configured section identity assignment.
EMPTY_LOCATOR_ADMISSION = (
    "The EMPTY string is admissible while no configured DESIGN-document "
    "destination has assigned this value a section identity; the constructor "
    "assigns the configured locator during publication."
)


def is_design_authority_locator(locator: str) -> bool:
    """Whether ``locator`` may become a bound ``DesignFacts.authority_locator``.

    Empty is admitted (see :data:`EMPTY_LOCATOR_ADMISSION`); anything else must
    satisfy EVERY clause of :data:`LOCATOR_CLAUSES`.
    """
    return not locator or all(holds(locator) for _, holds in LOCATOR_CLAUSES)


def design_authority_locator_description() -> str:
    """Publish the shared persisted-locator grammar from its clause table."""
    return "\n".join(
        (
            "`authority_locator` is a DESIGN section locator, "
            "`<document>#<heading>`, admissible only when:",
            *(f"- {clause}" for clause, _ in LOCATOR_CLAUSES),
            "",
            EMPTY_LOCATOR_ADMISSION,
            "",
            "Any other locator -- a traversal such as `../outside/DESIGN.md#Slice 1`, "
            "a prose sentence naming the section, a second `#` or a line break "
            "inside the heading -- is not a repository-relative DESIGN section "
            "identity. Restore the canonical handover or reconstruct complete "
            "DESIGN with `des design --replace-current --input -` before reuse.",
        )
    )
