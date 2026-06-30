"""Composition root for the carpaccio slice-plan parser-unification slice (C10).

Wires the TWO real production slice-plan parsers against a hermetic feature-delta
written under pytest ``tmp_path`` -- never this repo's own deltas:

  ENTRY_GATE -- ``des.cli.carpaccio_format.parse_slice_plan(text)`` (text-driven;
        the CLI carpaccio entry gate's parser). Strict at HEAD: H2-only heading,
        raw-`|` split, requires exactly 5 columns.
  EXIT_HOOK  -- ``des.adapters.drivers.hooks.subagent_stop_handler
        ._parse_slice_plan_rows(repo, feature_id)`` (feature-delta-file-driven;
        the subagent-stop hook's parser). Accepts >= 3 columns at HEAD.

The slice replaces both with ONE tolerant ``parse_slice_plan_rows(text)`` in
carpaccio_format to which both delegate. This composition drives the parsers
through their REAL public entry points -- the same surfaces the carpaccio gate
and the hook invoke -- so the ATs are honest regardless of the delegation detail.

Layer 3 (FS / module-port acceptance): the driving ports are the two parser
entry points; the only driven port is the real filesystem under ``tmp_path``.
Example-only, no PBT machinery (Mandate 9/11). The parsers are pure-read (no
state mutation), so the observable is the extracted slice-id set / the parse
outcome -- not a state delta.

Business logic lives here as the single source of truth; step bodies delegate to
``ParserComposition`` methods and never inline parse logic (Mandate-15
criterion 3).

HERMETICITY: the feature-delta lives entirely under ``tmp_path``; no
personal-hook home-directory path is read. The hook parser resolves
``repo / "docs" / "feature" / {feature_id} / "feature-delta.md"`` -- so the repo
root handed to it IS ``tmp_path``, and the delta is written at that exact path.

Regression contract: AC-1/2/3 FAIL at HEAD -- the CLI entry-gate parser rejects
the 3-column plan (``MalformedInput`` "must have 5 columns"), miscounts the
escaped pipe, and reports the H3 plan section missing -- while the fix makes
both parsers agree. AC-4 is a live-green preservation guard.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    FeatureId,
    ParseOutcome,
    ParserUnderTest,
    SliceId,
)


@dataclass(frozen=True)
class ParseResult:
    """The observable result of one real parser reading a slice plan.

    ``outcome`` is the coarse observable (parsed / rejected / section-missing).
    ``slice_ids`` is the ordered slice-id set extracted (empty unless PARSED).
    ``value_for`` maps each parsed slice-id to its extracted value statement
    (only the parsers that expose a value populate it; the hook exposes status
    rather than value, so it is left empty for the hook).
    """

    outcome: ParseOutcome
    slice_ids: tuple[SliceId, ...]
    value_for: dict[SliceId, str]


class ParserComposition:
    """Production-wired access to the two real slice-plan parsers."""

    def __init__(self, repo_dir: Path) -> None:
        self._repo = repo_dir
        self._feature_id: FeatureId | None = None
        self._delta_text: str | None = None

    # --- delta authoring (preconditions, never the expected output) ---------

    def write_feature_delta(self, feature_id: FeatureId, delta_text: str) -> None:
        """Write the crafted feature-delta to the hook-resolved path under tmp_path."""
        self._feature_id = feature_id
        self._delta_text = delta_text
        delta_path = self._repo / "docs" / "feature" / feature_id / "feature-delta.md"
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        delta_path.write_text(delta_text, encoding="utf-8")

    # --- driving the two real parsers ---------------------------------------

    def parse_with(self, parser: ParserUnderTest) -> ParseResult:
        """Drive the named real parser over the written delta, classifying outcome."""
        if parser is ParserUnderTest.ENTRY_GATE:
            return self._parse_entry_gate()
        return self._parse_exit_hook()

    def _parse_entry_gate(self) -> ParseResult:
        carpaccio_format = importlib.import_module("des.cli.carpaccio_format")
        assert self._delta_text is not None
        try:
            plan = carpaccio_format.parse_slice_plan(self._delta_text)
        except carpaccio_format.GateError as exc:
            return _classify_gate_error(exc)
        slice_ids = tuple(SliceId(row.slice_id) for row in plan.rows)
        value_for = {SliceId(row.slice_id): row.value_statement for row in plan.rows}
        return ParseResult(ParseOutcome.PARSED, slice_ids, value_for)

    def _parse_exit_hook(self) -> ParseResult:
        handler = importlib.import_module(
            "des.adapters.drivers.hooks.subagent_stop_handler"
        )
        assert self._feature_id is not None
        try:
            rows = handler._parse_slice_plan_rows(self._repo, self._feature_id)
        except handler._SlicePlanParseUnresolved:
            return ParseResult(ParseOutcome.SECTION_MISSING, (), {})
        slice_ids = tuple(SliceId(slice_id) for slice_id, _status in rows)
        return ParseResult(ParseOutcome.PARSED, slice_ids, {})


def _classify_gate_error(exc: object) -> ParseResult:
    """Map a carpaccio_format.GateError payload to a coarse ParseOutcome."""
    payload = getattr(exc, "payload", {})
    event = payload.get("event") if isinstance(payload, dict) else None
    if event == "SlicePlanSectionMissing":
        return ParseResult(ParseOutcome.SECTION_MISSING, (), {})
    return ParseResult(ParseOutcome.REJECTED_COLUMNS, (), {})
