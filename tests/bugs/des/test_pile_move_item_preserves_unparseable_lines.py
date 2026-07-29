"""Closing one pile item must not destroy the rest of the pile file.

``move_item`` rebuilt the pile from the PARSED items only, so every line the
grammar does not recognise -- header comments, prose-format pending rows,
rows using a variant field name -- was silently deleted on the first closure.
Measured on the real techdebt.md: 302 lines -> 49, 253 destroyed, including
nine pending rows.
"""

from pathlib import Path

from des.domain.refactor.pile import move_item, parse_pile_report


_PARSEABLE = '- [ ] {id}: paradigm=object-oriented defect="d" proposed_solution="s"'

_UNPARSEABLE_PROSE = """- [ ] prose-row-the-grammar-cannot-see
  - paradigm: object-oriented
  - what: filed in the multi-line format
  - why: the analysis is the artifact and cannot be regenerated
"""


def _pile_text() -> str:
    return (
        "# NOTE: a header comment the maintainer wrote\n"
        "# spanning two lines\n"
        "\n"
        + _PARSEABLE.format(id="drained-item")
        + "\n"
        + _PARSEABLE.format(id="surviving-item")
        + "\n"
        '- [ ] variant-field-name-row: paradigm=object-oriented debt="uses debt= not defect="\n'
        + _UNPARSEABLE_PROSE
    )


def test_closing_an_item_leaves_every_other_line_byte_identical(
    tmp_path: Path,
) -> None:
    pile = tmp_path / "techdebt.md"
    paid = tmp_path / "done.md"
    pile.write_text(_pile_text(), encoding="utf-8")
    before = pile.read_text(encoding="utf-8").splitlines()

    move_item(pile, paid, "drained-item")

    after = pile.read_text(encoding="utf-8").splitlines()
    expected = [line for line in before if not line.startswith("- [ ] drained-item:")]
    assert after == expected


def test_closing_an_item_does_not_drop_pending_rows_the_parser_cannot_read(
    tmp_path: Path,
) -> None:
    pile = tmp_path / "techdebt.md"
    paid = tmp_path / "done.md"
    pile.write_text(_pile_text(), encoding="utf-8")
    invisible = {"variant-field-name-row", "prose-row-the-grammar-cannot-see"}
    assert invisible.isdisjoint(
        {item.item_id for item in parse_pile_report(pile).items}
    ), "fixture precondition: these rows must be invisible to the parser"

    move_item(pile, paid, "drained-item")

    survived = pile.read_text(encoding="utf-8")
    for item_id in invisible:
        assert item_id in survived


def test_the_closed_item_still_reaches_the_paid_ledger(tmp_path: Path) -> None:
    pile = tmp_path / "techdebt.md"
    paid = tmp_path / "done.md"
    pile.write_text(_pile_text(), encoding="utf-8")

    move_item(pile, paid, "drained-item")

    assert "drained-item" not in pile.read_text(encoding="utf-8")
    assert "- [x] drained-item:" in paid.read_text(encoding="utf-8")
