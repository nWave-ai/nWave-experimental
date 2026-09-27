"""The ONE `<document>#<heading>` rule a DESIGN `authority_locator` obeys.

The rule lives here as DATA -- an ordered table of clauses, each a sentence
paired with the predicate that decides it -- because it has TWO consumers and
they must never disagree:

* :func:`is_design_authority_locator` is what the decoder
  (``des.adapters.driven.task_invocation.model_envelope.decode_model_run``) and
  the restored-handover guard (``des.application.handover.design_facts_defect``)
  ask before a locator may become ``DesignFacts``;
* :func:`design_authority_locator_description` is the human statement the
  solution architect READS at its own authoring surface, projected there as a
  GENERATED region.

Both read the same table, so a prose-only edit cannot change what is enforced
and a rule-only edit cannot leave the published text unchanged.  Measured
before this module existed: an architect answering ``authority_locator`` with a
traversal or a prose sentence ended the whole design turn ``Indeterminate /
ModelEnvelopeUnavailable / DesignFactsUnsafeLocator`` for a grammar stated in no
surface the role reads -- the turn was paid for, refused, and taught nothing.

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


#: The refusal a locator outside this grammar produces.  Named in the published
#: statement so the architect can recognise the terminal it is being taught to
#: avoid, and spelled ONCE so the word in the prose is the word in the terminal.
UNSAFE_LOCATOR_REFUSAL = "DesignFactsUnsafeLocator"


def _document(locator: str) -> str:
    return locator.partition("#")[0]


def _heading(locator: str) -> str:
    return locator.partition("#")[2]


#: The grammar, ordered, one clause per shape it refuses.  Each row is the
#: sentence the architect reads AND the predicate the decoder runs; there is no
#: third spelling of either anywhere.
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

#: The one admission beside the clauses: an EMPTY locator is not ill-formed, it
#: is the statement that no configured DESIGN-document destination has assigned
#: this value a section identity yet.  The provider schema therefore keeps a
#: patternless ``{"type": "string"}`` for the field: a pattern would make the
#: honest empty answer unrepresentable.
EMPTY_LOCATOR_ADMISSION = (
    "The EMPTY string is admissible and is the honest answer while no configured "
    "DESIGN-document destination has assigned this value a section identity; the "
    "constructor, never the turn, fills one in later."
)


def is_design_authority_locator(locator: str) -> bool:
    """Whether ``locator`` may become a bound ``DesignFacts.authority_locator``.

    Empty is admitted (see :data:`EMPTY_LOCATOR_ADMISSION`); anything else must
    satisfy EVERY clause of :data:`LOCATOR_CLAUSES`.
    """
    return not locator or all(holds(locator) for _, holds in LOCATOR_CLAUSES)


def design_authority_locator_description() -> str:
    """The same table, as the sentence the architect reads while authoring.

    Derived from :data:`LOCATOR_CLAUSES` rather than written beside it, so the
    published statement cannot drift from the rule that refuses the turn.
    """
    return "\n".join(
        (
            "`authority_locator` is a DESIGN section locator, "
            "`<document>#<heading>`, admissible only when:",
            *(f"- {clause}" for clause, _ in LOCATOR_CLAUSES),
            "",
            EMPTY_LOCATOR_ADMISSION,
            "",
            f"Any other answer -- a traversal such as `../outside/DESIGN.md#Slice 1`, "
            f"a prose sentence naming the section, a second `#` or a line break "
            f"inside the heading -- is refused as `{UNSAFE_LOCATOR_REFUSAL}`, and the "
            "whole design turn ends Indeterminate with nothing bound.",
        )
    )
