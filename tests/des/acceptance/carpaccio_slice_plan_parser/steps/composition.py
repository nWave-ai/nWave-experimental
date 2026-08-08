"""Composition root for the carpaccio slice-plan parser slice (C10).

Wires the public production slice-plan parser against hermetic feature-delta text:

  ENTRY_GATE -- ``des.cli.carpaccio_format.parse_slice_plan(text)`` (text-driven;
        the CLI carpaccio entry gate's parser). Strict at HEAD: H2-only heading,
        raw-`|` split, requires exactly 5 columns.
This composition drives the parser through its real public entry point, the same
surface the carpaccio gate invokes.

Layer 3 (module-port acceptance): the driving port is the public parser entry point.
Example-only, no PBT machinery (Mandate 9/11). The parser is pure-read (no
state mutation), so the observable is the extracted slice-id set / the parse
outcome -- not a state delta.

Business logic lives here as the single source of truth; step bodies delegate to
``ParserComposition`` methods and never inline parse logic (Mandate-15
criterion 3).

Regression contract: AC-1/2/3 FAIL at HEAD -- the CLI entry-gate parser rejects
the 3-column plan (``MalformedInput`` "must have 5 columns"), miscounts the
escaped pipe, and reports the H3 plan section missing. AC-4 is a live-green
preservation guard.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from .domain_types import FeatureId, ParseOutcome, ParserUnderTest, SliceId


@dataclass(frozen=True)
class ParseResult:
    """The observable result of one real parser reading a slice plan.

    ``outcome`` is the coarse observable (parsed / rejected / section-missing).
    ``slice_ids`` is the ordered slice-id set extracted (empty unless PARSED).
    ``value_for`` maps each parsed slice-id to its extracted value statement.
    """

    outcome: ParseOutcome
    slice_ids: tuple[SliceId, ...]
    value_for: dict[SliceId, str]


class ParserComposition:
    """Production-wired access to the public slice-plan parser."""

    def __init__(self, repo_dir: Path) -> None:
        self._repo = repo_dir
        self._delta_text: str | None = None

    # --- delta authoring (preconditions, never the expected output) ---------

    def write_feature_delta(self, feature_id: FeatureId, delta_text: str) -> None:
        """Write the crafted feature-delta under the hermetic tmp_path repo."""
        self._delta_text = delta_text
        delta_path = self._repo / "docs" / "feature" / feature_id / "feature-delta.md"
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        delta_path.write_text(delta_text, encoding="utf-8")

    def parse_with(self, parser: ParserUnderTest) -> ParseResult:
        """Drive the named public parser over the supplied delta."""
        assert parser is ParserUnderTest.ENTRY_GATE
        carpaccio_format = importlib.import_module("des.cli.carpaccio_format")
        assert self._delta_text is not None
        try:
            plan = carpaccio_format.parse_slice_plan(self._delta_text)
        except carpaccio_format.GateError as exc:
            return _classify_gate_error(exc)
        slice_ids = tuple(SliceId(row.slice_id) for row in plan.rows)
        value_for = {SliceId(row.slice_id): row.value_statement for row in plan.rows}
        return ParseResult(ParseOutcome.PARSED, slice_ids, value_for)


def _classify_gate_error(exc: object) -> ParseResult:
    """Map a carpaccio_format.GateError payload to a coarse ParseOutcome."""
    payload = getattr(exc, "payload", {})
    event = payload.get("event") if isinstance(payload, dict) else None
    if event == "SlicePlanSectionMissing":
        return ParseResult(ParseOutcome.SECTION_MISSING, (), {})
    return ParseResult(ParseOutcome.REJECTED_COLUMNS, (), {})
