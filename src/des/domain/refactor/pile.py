"""Pile domain -- parses/renders techdebt.md <-> paidtechdebt.md; PileItem values.

CREATE_NEW (des-refactor-fixer-swarm slice-01). No existing markdown-checklist
pile-drain reader/writer exists (confirmed absent: ``BACKLOG.md``-adjacent
tooling is a different format/purpose -- Jira sync, not drain-and-move).

``schema_version`` is carried now (Open Question 3, feature-delta) so the future
``des find`` finder swarm has a stable contract to emit against from day one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from des.domain.refactor.discovery_method import (
    RecognizedDiscoveryMethod,
    select_discovery_method,
)


if TYPE_CHECKING:
    from pathlib import Path

#: The PileItem schema version -- the CONTRACT the future finder swarm
#: (``des find``) must emit against (Open Question 3).
SCHEMA_VERSION = 1

_PAID_HEADER = "# Paid tech debt"

# One pending-item line: `- [ ] <id>: paradigm=<p> defect="..." proposed_solution="..."`
# with an OPTIONAL trailing ` discovered_by=<token>`
# -- byte-for-byte the shape the DISTILL composition fixture seeds.
#
# The trailing field is optional and can never be made mandatory here: 223
# pending rows of the pre-field shape sit in the real ``defects.md``, and a
# required group would turn every one of them into a ``skipped_line`` at once
# -- the drain would report an empty pile and exit 0, which is
# ``fix-drain-single-item-silent-noop`` all over again. A row that declares
# nothing is not silent, though: it parses as ``UNATTRIBUTED`` AND its id
# reaches ``PileParseReport.unattributed_item_ids``.
_ITEM_LINE_RE = re.compile(
    r"^- \[ \] (?P<item_id>\S+): paradigm=(?P<paradigm>\S+) "
    r'defect="(?P<defect>[^"]*)" proposed_solution="(?P<proposed_solution>[^"]*)"'
    r"(?: discovered_by=(?P<discovered_by>\S+))?$"
)


@dataclass(frozen=True)
class PileItem:
    """One pending tech-debt/friction item -- the pile's unit of work.

    ``paradigm`` is the declared FP/OOP lens (slice-05 consumes this to refuse
    a mismatched dispatch; slice-01 only carries the field).
    """

    item_id: str
    defect: str
    proposed_solution: str
    paradigm: str
    discovered_by: str = RecognizedDiscoveryMethod.UNATTRIBUTED.value
    schema_version: int = SCHEMA_VERSION


class PileUnreadable(Enum):
    """WHY a ``--pile`` path could not be READ as a pile file at all.

    A pile that was never read is a categorically different outcome from a
    pile that WAS read and holds zero pending items -- "I could not start, so
    I never looked" vs "I looked and there was nothing to do". Each member's
    value is the WHY phrase a reporter renders for a maintainer.

    All three collapse to the same ``Path.is_file() is False``, which is why
    they are classified rather than tested for one at a time: a fix that only
    recognised a missing file would still read a ``--pile`` aimed at a
    directory as an empty pile.
    """

    NO_SUCH_FILE = "no file exists at that path"
    NO_SUCH_DIRECTORY = "its parent directory does not exist"
    IS_A_DIRECTORY = "that path is a directory, not a pile file"


@dataclass(frozen=True)
class PileParseReport:
    """Parsed pending items, any non-blank non-header lines that failed the
    item grammar, and whether the pile could be read at all -- the three
    outcomes a reporter must be able to tell apart.

    ``unreadable`` is ``None``, and only ``None``, when the pile file WAS
    read. Folding an unreadable path into the same empty value a real, empty,
    parsed pile produces is what let ``des refactor`` tell a maintainer who
    mistyped ``--pile`` that their pile was empty, and exit 0
    (fix-drain-single-item-silent-noop).

    ``unattributed_item_ids`` names the parsed items that declared NO
    ``discovered_by=`` channel. It is the same third-state discipline applied
    to attribution: a consumer computing yield-per-discovery-method sums the
    items it can bucket, and without this aggregate the rows it cannot bucket
    are invisible -- coverage would read 100% of whatever happened to be
    countable (GDP-8 arity corollary: the third state must reach the
    AGGREGATE, not merely the record).

    ``unrecognized_discovery`` names the items whose declared channel is not a
    member of the closed set, paired with the offending token. It REPORTS and
    does not refuse: unlike ``paradigm=``, which decides which RPP lens the
    fixer dispatches and so must block a wrong value before dispatch,
    ``discovered_by=`` is provenance -- it changes nothing about the fix.
    Refusing to drain a real defect because its provenance tag is misspelled
    would put the enforcement cost on the operator for zero correctness gain
    (GDP-5) and would decide on the DESIGNATION rather than the property
    (GDP-8). The item keeps its raw token verbatim rather than being
    normalised to ``unattributed``, because a typo is evidence of what the
    author meant and silently rewriting it destroys that.
    """

    items: tuple[PileItem, ...]
    skipped_lines: tuple[str, ...]
    unreadable: PileUnreadable | None = None
    unattributed_item_ids: tuple[str, ...] = ()
    unrecognized_discovery: tuple[tuple[str, str], ...] = ()


def classify_unreadable_pile(pile_path: Path) -> PileUnreadable | None:
    """Why ``pile_path`` cannot be read as a pile file, or ``None`` when it
    can -- named once here so the distinction survives parsing instead of
    being destroyed at it."""
    if pile_path.is_file():
        return None
    if pile_path.is_dir():
        return PileUnreadable.IS_A_DIRECTORY
    if not pile_path.parent.is_dir():
        return PileUnreadable.NO_SUCH_DIRECTORY
    return PileUnreadable.NO_SUCH_FILE


def parse_pile_report(pile_path: Path) -> PileParseReport:
    """Parse a ``techdebt.md``-shaped pile file, reporting the parsed items,
    any non-blank content line that did not match the item grammar (a real
    parse-miss, never silently dropped from observability), and -- when the
    path could not be read as a pile file at all -- WHY, so a caller can
    refuse instead of reporting a finding about a pile it never opened.
    """
    unreadable = classify_unreadable_pile(pile_path)
    if unreadable is not None:
        return PileParseReport(items=(), skipped_lines=(), unreadable=unreadable)
    items: list[PileItem] = []
    skipped: list[str] = []
    unattributed: list[str] = []
    unrecognized: list[tuple[str, str]] = []
    for raw_line in pile_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ITEM_LINE_RE.match(stripped)
        if match is None:
            skipped.append(stripped)
            continue
        declared_channel = match.group("discovered_by")
        if declared_channel is None:
            declared_channel = RecognizedDiscoveryMethod.UNATTRIBUTED.value
            unattributed.append(match.group("item_id"))
        elif not select_discovery_method(declared_channel).accepted:
            unrecognized.append((match.group("item_id"), declared_channel))
        items.append(
            PileItem(
                item_id=match.group("item_id"),
                defect=match.group("defect"),
                proposed_solution=match.group("proposed_solution"),
                paradigm=match.group("paradigm"),
                discovered_by=declared_channel,
            )
        )
    return PileParseReport(
        items=tuple(items),
        skipped_lines=tuple(skipped),
        unattributed_item_ids=tuple(unattributed),
        unrecognized_discovery=tuple(unrecognized),
    )


def parse_pile(pile_path: Path) -> tuple[PileItem, ...]:
    """Parse the pending ITEMS out of a ``techdebt.md``-shaped pile file.

    Items only. An absent pile file yields zero items here, which is NOT the
    same observable outcome as an empty one: a caller that must tell "read,
    and there was nothing pending" apart from "could not be read at all"
    calls ``parse_pile_report`` and consults ``PileParseReport.unreadable``.
    Collapsing the two -- and calling that collapse legitimate -- is what let
    a mistyped ``--pile`` be reported to a maintainer as an empty pile, with
    a success exit (fix-drain-single-item-silent-noop).
    """
    return parse_pile_report(pile_path).items


def move_item(pile_path: Path, paid_path: Path, item_id: str) -> None:
    """Move ``item_id`` out of the pending pile and into the paid ledger.

    Atomic-observable: both writes happen in this one call, so a caller never
    observes the item missing from both files or present in both at once.

    Line-surgical, exactly like ``annotate_item_escalated``: the ONE matching
    pending line is dropped and every other line is written back
    byte-identical. Re-RENDERING the pile from the PARSED items instead
    deletes everything the grammar cannot read -- header comments,
    prose-format pending rows, rows using a variant field name -- and those
    are the pile's irreplaceable content, not decoration. Measured on the real
    ``techdebt.md`` before this was fixed: one closure took it from 302 lines
    to 49, destroying nine pending rows.
    """
    if not pile_path.is_file():
        return
    moved = next(
        (item for item in parse_pile(pile_path) if item.item_id == item_id), None
    )
    item_prefix_re = re.compile(rf"^- \[ \] {re.escape(item_id)}:")
    lines = pile_path.read_text(encoding="utf-8").splitlines()
    remaining = [line for line in lines if not item_prefix_re.match(line)]
    pile_path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    if moved is not None:
        _append_paid(paid_path, moved)


def annotate_item_escalated(pile_path: Path, item_id: str) -> None:
    """Rewrite ``item_id``'s pending line in place to carry an ``escalated``
    marker, keeping the item in the pending pile (``techdebt.md``) -- never
    moved to ``paidtechdebt.md`` (D9, AT-8). Item-specific: only the one
    matching line is touched, every sibling line is left byte-identical --
    the escalation signal must never be a pile-wide side effect.
    """
    if not pile_path.is_file():
        return
    item_prefix_re = re.compile(rf"^- \[ \] {re.escape(item_id)}:")
    lines = pile_path.read_text(encoding="utf-8").splitlines()
    updated_lines = [
        f"{line} [escalated]"
        if item_prefix_re.match(line) and "escalated" not in line.lower()
        else line
        for line in lines
    ]
    pile_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def _append_paid(paid_path: Path, item: PileItem) -> None:
    existing = (
        paid_path.read_text(encoding="utf-8")
        if paid_path.is_file()
        else f"{_PAID_HEADER}\n"
    )
    if not existing.endswith("\n"):
        existing += "\n"
    paid_path.write_text(existing + _render_line("[x]", item) + "\n", encoding="utf-8")


def _render_line(checkbox: str, item: PileItem) -> str:
    """Render one item back to the row grammar.

    ``discovered_by=`` is rendered ALWAYS, including when it is
    ``unattributed``: a closed row that quietly dropped the marker would put
    the ledger back where it started -- prose with no extractable channel --
    and the denominator this field exists to create is over the CLOSED rows
    just as much as the pending ones.
    """
    return (
        f"- {checkbox} {item.item_id}: paradigm={item.paradigm} "
        f'defect="{item.defect}" proposed_solution="{item.proposed_solution}" '
        f"discovered_by={item.discovered_by}"
    )
