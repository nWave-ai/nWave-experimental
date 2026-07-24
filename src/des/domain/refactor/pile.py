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


if TYPE_CHECKING:
    from pathlib import Path

#: The PileItem schema version -- the CONTRACT the future finder swarm
#: (``des find``) must emit against (Open Question 3).
SCHEMA_VERSION = 1

_PENDING_HEADER = "# Tech debt pile"
_PAID_HEADER = "# Paid tech debt"

# One pending-item line: `- [ ] <id>: paradigm=<p> defect="..." proposed_solution="..."`
# -- byte-for-byte the shape the DISTILL composition fixture seeds.
_ITEM_LINE_RE = re.compile(
    r"^- \[ \] (?P<item_id>\S+): paradigm=(?P<paradigm>\S+) "
    r'defect="(?P<defect>[^"]*)" proposed_solution="(?P<proposed_solution>[^"]*)"$'
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
    """

    items: tuple[PileItem, ...]
    skipped_lines: tuple[str, ...]
    unreadable: PileUnreadable | None = None


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
    for raw_line in pile_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ITEM_LINE_RE.match(stripped)
        if match is None:
            skipped.append(stripped)
            continue
        items.append(
            PileItem(
                item_id=match.group("item_id"),
                defect=match.group("defect"),
                proposed_solution=match.group("proposed_solution"),
                paradigm=match.group("paradigm"),
            )
        )
    return PileParseReport(items=tuple(items), skipped_lines=tuple(skipped))


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
    """
    items = parse_pile(pile_path)
    moved = next((item for item in items if item.item_id == item_id), None)
    remaining = tuple(item for item in items if item.item_id != item_id)
    _write_pending(pile_path, remaining)
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


def _write_pending(pile_path: Path, items: tuple[PileItem, ...]) -> None:
    lines = [_PENDING_HEADER, ""]
    lines.extend(_render_line("[ ]", item) for item in items)
    pile_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    return (
        f"- {checkbox} {item.item_id}: paradigm={item.paradigm} "
        f'defect="{item.defect}" proposed_solution="{item.proposed_solution}"'
    )
