"""A pile row must be able to DECLARE how the defect was discovered, and the
absence of that declaration must be observable rather than silent.

DEFECT (Mikado D01, ``docs/mikado/2026-07-28-des-machine-anatomy.md`` row 65).
``defects.md`` (221 rows) and ``done.md`` (239 rows) record WHAT was found and
never HOW it was found. The pile grammar
(``des.domain.refactor.pile._ITEM_LINE_RE``) has no field for it, so the only
attribution that exists is prose buried inside ``defect="..."``. Measured on
the real files 2026-07-28: ~14/212 rows (6.6%) name a discoverer at all, and a
keyword count is not a substitute -- 109/212 rows contain the word "gate", but
in nearly all of them the gate is the SUBJECT of the defect (a broken gate),
not the finder. Counting those as captures would invert the finding.

WHY IT MATTERS: the yield of a verification method (does an adversarial review
find more than a systematic audit? does a gate that fires pay for itself?) is
a ratio whose DENOMINATOR is "defects found by that method". Without a
declared discovery channel the denominator does not exist, so every
per-method value question answers NO_EVIDENCE. This is
``data:consumer-known-before-produced`` applied to our own process.

DESIGN, and the two refusals it must produce:

1. The declared token is checked against a CLOSED set, exactly like the
   already-ratified ``paradigm=`` precedent
   (``des.domain.refactor.paradigm_select.RecognizedParadigm`` /
   ``select_paradigm_lens``). The closed set is DERIVED from the discovery
   channels actually attested in the two real pile files, not invented; an
   unrecognised token is REFUSED with WHAT/WHY/HOW rather than absorbed as
   free text, because a field that accepts anything is prose with an equals
   sign in it.

2. A row that declares nothing is NOT silently attributed. It parses (the 223
   pending rows on disk predate the field and must keep draining), it carries
   the EXPLICIT ``unattributed`` member rather than an empty string or
   ``None``, and its ``item_id`` reaches the parse report's aggregate --
   GDP-8's arity corollary: the third state ("could not attribute") must be
   visible to the consumer, never collapsed into the positive or the negative.

WHAT THESE ATs DELIBERATELY DO NOT PIN: they do not require the field on
existing rows, and they do not assert any operator-facing coverage report.
Backfilling attribution onto 460 historical rows is a separate, larger job;
this slice makes the channel DECLARABLE and its absence COUNTABLE.

DRIVING SURFACE: the pile grammar is parsed from a file on disk, so every AT
here writes a real pile file and reads it back through the same
``parse_pile_report`` the drain CLI calls -- never by constructing a
``PileItem`` by hand, which would test the dataclass instead of the grammar.
The one CLI-level AT asserts the operator-facing grammar message, which is the
only place ``des refactor`` teaches the row shape before an operator hits the
wall (GDP-2/GDP-3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from des.domain.refactor.discovery_method import (
    RecognizedDiscoveryMethod,
    select_discovery_method,
)
from des.domain.refactor.pile import parse_pile_report


if TYPE_CHECKING:
    from pathlib import Path


#: A row in TODAY's shape -- no ``discovered_by`` field at all. 223 rows of
#: this exact shape are pending in the real ``defects.md`` right now, which is
#: why the field can only ever be OPTIONAL in the grammar.
_LEGACY_ROW = '- [ ] {id}: paradigm=object-oriented defect="d" proposed_solution="s"'

#: The same row, declaring its discovery channel.
_ATTRIBUTED_ROW = (
    '- [ ] {id}: paradigm=object-oriented defect="d" proposed_solution="s" '
    "discovered_by={method}"
)


def _write_pile(tmp_path: Path, *rows: str) -> Path:
    pile = tmp_path / "techdebt.md"
    pile.write_text("# Tech debt\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return pile


@pytest.mark.parametrize("method", list(RecognizedDiscoveryMethod))
def test_a_row_declaring_a_recognized_discovery_method_carries_it_onto_the_parsed_item(
    tmp_path: Path, method: RecognizedDiscoveryMethod
) -> None:
    """GIVEN a pile row that declares a discovery channel from the closed set
    WHEN the pile is parsed
    THEN the parsed item carries that exact token.

    Parametrized over the WHOLE enum rather than one sampled member: the point
    of a closed set is that every member is reachable through the grammar, and
    a member the regex cannot match is a member that exists only in the docs.
    """
    pile = _write_pile(tmp_path, _ATTRIBUTED_ROW.format(id="TD-1", method=method.value))

    report = parse_pile_report(pile)

    assert [item.item_id for item in report.items] == ["TD-1"], (
        f"the row declaring discovered_by={method.value} did not parse as an "
        f"item at all; skipped_lines={report.skipped_lines}"
    )
    assert report.items[0].discovered_by == method.value


def test_a_row_without_discovered_by_is_never_silently_attributed(
    tmp_path: Path,
) -> None:
    """GIVEN a legacy pile row that declares no discovery channel
    WHEN the pile is parsed
    THEN the item carries the EXPLICIT ``unattributed`` member, AND its id
    reaches the report's unattributed aggregate.

    Both halves are load-bearing and neither implies the other. A default that
    is merely a sentinel value on the item is still silent to a consumer that
    iterates items and sums by channel -- the unattributed rows would simply
    not appear in any bucket, and the coverage ratio would read 100%. The
    aggregate is what makes the denominator visible (GDP-8 arity corollary:
    the third state must reach the AGGREGATE, not just the record).
    """
    pile = _write_pile(tmp_path, _LEGACY_ROW.format(id="TD-legacy"))

    report = parse_pile_report(pile)

    assert report.items[0].discovered_by == RecognizedDiscoveryMethod.UNATTRIBUTED.value
    assert report.unattributed_item_ids == ("TD-legacy",), (
        "a row that declared no discovery channel did not reach the parse "
        "report's unattributed aggregate, so a consumer counting yield per "
        "method cannot see the rows it is missing"
    )


def test_the_unattributed_aggregate_never_names_a_row_that_did_declare_a_channel(
    tmp_path: Path,
) -> None:
    """GIVEN a pile holding one attributed row and one legacy row
    WHEN the pile is parsed
    THEN only the legacy row's id appears in the unattributed aggregate.

    The inverse failure of the previous AT, and the one that actually bites:
    an aggregate that over-reports (every row, or every row whose token it
    failed to recognise) would make the coverage ratio read 0% forever and be
    just as useless as one that under-reports.
    """
    pile = _write_pile(
        tmp_path,
        _ATTRIBUTED_ROW.format(id="TD-attributed", method="systematic-audit"),
        _LEGACY_ROW.format(id="TD-legacy"),
    )

    report = parse_pile_report(pile)

    assert report.unattributed_item_ids == ("TD-legacy",)


def test_a_legacy_row_without_the_field_is_not_dropped_from_the_parsed_items(
    tmp_path: Path,
) -> None:
    """GIVEN a pile of rows in the pre-field shape
    WHEN the pile is parsed
    THEN every row still parses as an item and none is reported as a
    parse-miss.

    The regression this guards is catastrophic and cheap to cause: making
    ``discovered_by`` a REQUIRED group in the item regex would turn all 223
    pending rows of the real ``defects.md`` into ``skipped_lines`` at once --
    the drain would report an empty pile and exit 0, which is the exact
    failure mode ``fix-drain-single-item-silent-noop`` already cost this repo
    once.
    """
    pile = _write_pile(
        tmp_path, *(_LEGACY_ROW.format(id=f"TD-{n}") for n in range(1, 4))
    )

    report = parse_pile_report(pile)

    assert [item.item_id for item in report.items] == ["TD-1", "TD-2", "TD-3"]
    assert report.skipped_lines == ()


def test_a_row_declaring_an_unrecognized_channel_is_reported_and_not_refused(
    tmp_path: Path,
) -> None:
    """GIVEN a pile row whose declared channel is not in the closed set
    WHEN the pile is parsed
    THEN the item still parses and keeps its raw token, and the report names
    the item together with the offending token.

    Deliberately NOT a refusal, and the asymmetry with ``paradigm=`` is the
    whole point. ``paradigm=`` decides which RPP lens the fixer dispatches, so
    a wrong value must block BEFORE dispatch. ``discovered_by=`` is provenance
    and changes nothing about the fix -- blocking a real defect's repair over
    a misspelled provenance tag would charge the operator for zero correctness
    gain (GDP-5) and would decide on the designation rather than the property
    (GDP-8). The raw token survives verbatim rather than being normalised to
    ``unattributed``: a typo is evidence of what the author meant.
    """
    pile = _write_pile(tmp_path, _ATTRIBUTED_ROW.format(id="TD-typo", method="audit"))

    report = parse_pile_report(pile)

    assert [item.item_id for item in report.items] == ["TD-typo"]
    assert report.items[0].discovered_by == "audit"
    assert report.unrecognized_discovery == (("TD-typo", "audit"),)
    assert report.unattributed_item_ids == (), (
        "an unrecognized channel is a DIFFERENT fact from an absent one; "
        "folding it into the unattributed bucket loses the distinction "
        "between 'nobody declared' and 'the declaration is wrong'"
    )


def test_select_discovery_method_rejects_a_token_outside_the_closed_set() -> None:
    """GIVEN a declared discovery token that is not a member of the closed set
    WHEN the token is selected
    THEN selection refuses, and the refusal NAMES both the offending token and
    the accepted set.

    A near-miss is the realistic input, not a garbage word: an author who
    writes ``discovered_by=audit`` instead of ``systematic-audit`` must be told
    which token to use, not merely that theirs is wrong (the standing
    WHAT/WHY/HOW mandate; GDP-3).
    """
    selection = select_discovery_method("audit")

    assert selection.accepted is False
    assert selection.method is None
    assert selection.reason is not None
    assert "audit" in selection.reason
    assert RecognizedDiscoveryMethod.SYSTEMATIC_AUDIT.value in selection.reason


def test_select_discovery_method_rejects_an_absent_declaration_rather_than_guessing(
    tmp_path: Path,
) -> None:
    """GIVEN an empty declared token
    WHEN the token is selected
    THEN selection refuses instead of quietly resolving to ``unattributed``.

    ``unattributed`` is a DECLARABLE answer ("I looked and cannot say"), not a
    fallback the machine reaches for on the author's behalf. Letting the empty
    string resolve to it would make "nobody declared" and "the author declared
    they could not tell" the same datum, which is precisely the collapse this
    field exists to undo.
    """
    selection = select_discovery_method("")

    assert selection.accepted is False
    assert selection.method is None


def test_the_operator_facing_grammar_message_names_discovered_by() -> None:
    """GIVEN the grammar shape ``des refactor`` prints when a pile is
    unparseable
    WHEN it is read
    THEN it teaches the ``discovered_by`` field and shows it in the example.

    A schema field nothing surfaces at the authoring point is a field nobody
    fills in. This message is the only place the row shape is taught inside
    the tool itself (GDP-2: proactive affordance at the authoring surface),
    so a field absent from it is catalogued but not wired.
    """
    from des.cli.refactor import _GRAMMAR_EXAMPLE, _GRAMMAR_SHAPE

    assert "discovered_by=" in _GRAMMAR_SHAPE
    assert "discovered_by=" in _GRAMMAR_EXAMPLE
