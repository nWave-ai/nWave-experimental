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


@dataclass(frozen=True)
class PileParseReport:
    """Parsed pending items plus any non-blank, non-header lines that failed
    the item grammar -- the observability need that distinguishes a
    genuinely empty pile from one whose only content couldn't be parsed."""

    items: tuple[PileItem, ...]
    skipped_lines: tuple[str, ...]


def parse_pile_report(pile_path: Path) -> PileParseReport:
    """Parse a ``techdebt.md``-shaped pile file, reporting both the parsed
    items and any non-blank content line that did not match the item
    grammar (a real parse-miss, never silently dropped from observability).
    """
    if not pile_path.is_file():
        return PileParseReport(items=(), skipped_lines=())
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
    """Parse the pending items out of a ``techdebt.md``-shaped pile file.

    A genuinely absent pile file parses as zero pending items (a fresh pile
    has no file yet) -- never an error, since an absent pile is a legitimate
    "nothing to drain" state, the same observable outcome as an empty one.
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
