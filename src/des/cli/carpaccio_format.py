"""Shared carpaccio format predicates -- the single SSOT (ADR-001).

The carpaccio slice gate (``carpaccio_slice_gate.py``) and the designer-facing
pre-check (``carpaccio_precheck.py``) both read these format predicates. Keeping
them in ONE place is the hard anti-drift constraint of ADR-001: a divergent
second checker would pass at authoring time and reject mid-spine -- the exact
friction the pre-check removes.

This module is pure-function: it reads the filesystem, raises ``GateError`` on a
violation, and mutates nothing. It is stdlib-only (no ``import yaml`` -- the DES
bundle scan forbids it in bundled ``des`` modules), FLAT under ``src/des/cli/``,
and glob-shipped with the rest of ``des.cli``.

The import direction is one-directional: ``carpaccio_slice_gate -> carpaccio_format``
(and ``carpaccio_precheck -> carpaccio_format``), NEVER the reverse, to avoid a
circular import. The gate RETAINS its assertion-5 record-presence review logic, ``main()``,
and ``_emit``; those depend on the shared helpers ``_at_review_rejection`` and
``_slice_scenarios`` which therefore live here (peer-review LOW, 2026-05-29:
both helpers cross the moved/retained boundary so they MOVE into this module and
the gate imports them).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.application.feature_at_files import (
    EXCLUDED_SEARCH_DIRS,
    _legacy_acceptance_dir,
)
from des.application.feature_at_files import (
    feature_tag_files as _feature_tag_files,
)
from des.cli.pytest_bdd_detection import module_level_scenarios_call
from des.cli.verify_red_green import _content_sha as _red_seal_content_sha
from des.cli.verify_red_green import _seal_path as _red_green_seal_path
from des.domain.lane_profile import LANE_PROFILES, AtRequirement, LaneProfile
from des.domain.slice_id_trailer import SLICE_TAG_RE
from des.domain.telemetry_paths import LedgerFamily, ledger_path
from des.ports.test_runner_port import AT_KIND_SUFFIX_MAP as _AT_DISCOVERY_SUFFIX_RUNNER


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal


# ``_legacy_acceptance_dir`` and ``_feature_tag_files`` are re-exported from the
# application layer (AD-05 layering fix) for ``carpaccio_precheck`` /
# ``carpaccio_slice_gate``; ``__all__`` marks them as intentional re-exports so
# autoflake does not drop the otherwise-internally-unused legacy resolver.
# ``read_feature_files`` is the public ``.feature``-reader shared by
# ``carpaccio_slice_gate`` / ``carpaccio_precheck`` / ``verify_commit_trailers``
# / ``at_review_verdict`` -- a function used by four modules is a declared part
# of this module's surface, never a smuggled cross-module private.
__all__ = [
    "FEATURE_END_SEALED_MARKER",
    "_feature_tag_files",
    "_legacy_acceptance_dir",
    "is_slice_coupled",
    "mark_feature_end_sealed",
    "mark_slice_status_shipped",
    "native_regression_at_discovery",
    "read_feature_files",
]


# Default carpaccio slice-size ceiling when .nwave/config.yaml omits it.
# Raised 7 -> 15 (Ale, 2026-08-01): the escape valve (@coupled + ADR-028 D2
# justification) already proved itself the correct call on cohesive slices --
# D80 used it three times in one session (up to 20 ATs) once negative/symmetric
# oracles became mandatory (S5/S6, this same session) made hitting a low
# ceiling routine rather than exceptional. Raising the default cuts the
# round-trip-to-justify tax for the now-common case without removing the
# ceiling itself -- an unbounded slice is still a real smell worth a gate.
# Originally ratified 7 (Ale, 2026-07-05, F-CARPACCIO-CEILING-7-AND-COUPLED-
# SURFACE) -- still the ONE canonical locus; .nwave/config.yaml MUST agree
# (never a diverging project override) and no docstring/example elsewhere
# may hardcode a second, independently-stale copy of this literal.
_DEFAULT_SLICE_MAX = 15

_SLICE_PLAN_HEADING_RE = re.compile(
    r"^#{2,4}\s+Wave:\s+DISCUSS\s+/\s+\[REF\]\s+Slice Plan\s*$"
)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s")
_SLICE_ID_RE = re.compile(
    r"^slice-\d+(?:[a-z])?$"
)  # canonical + letter-suffix (friction #10)
# The tag extractor MUST accept the SAME grammar the validator above accepts
# (sister Tsunami Q-31, 2026-06-26): a `slice-05b` id is validator-VALID, but the
# old `@(slice-\d+)\b` failed to extract `@slice-05b` (the `\b` between `\d` and a
# letter is no boundary -> the whole match fails) -> the gate emitted a SILENT
# `no-scenarios-for-slice` on a valid id. The `(?:[a-z])?` mirrors the validator so
# the two grammars agree; `@slice-01` (digit-only) is unaffected.
#
# Imported from the domain SSOT (fix-slice-id-grammar-drift-ssot) -- this WAS
# the reference fix (friction #10); it is now folded back onto the one grammar
# home so no second copy can drift again.
_SLICE_TAG_RE = SLICE_TAG_RE
_COUPLED_TAG_RE = re.compile(r"@coupled\b")
_WALKING_SKELETON_RE = re.compile(r"@walking-skeleton|@walking_skeleton")
_ANNOTATION_ESCAPE_RE = re.compile(
    r"@coupled|@walking-skeleton|@walking_skeleton|@infrastructure|@prefactoring"
)
_PREFACTORING_TAG_RE = re.compile(r"@prefactoring\b")

#: The `[REF] Slice Plan` Annotation-cell token that names the regression-test
#: file backing a `pytest-regression` bugfix slice (bug #94's mechanical-seal
#: route). Public (no leading underscore): the ONE shared locus every consumer
#: of the `@regression-test-file:<path>` grammar imports -- the G-DISTILL-EXIT
#: hook (`subagent_stop_handler._mechanical_seal_cleared_slices`) and the
#: `des next` loop projection (`deliver_loop_projection._project_pending_slice`)
#: both resolve this token to the SAME regex, never a second, independently
#: drifting copy (fix-des-next-blind-to-sealed-red, ZERO-DEFECTS dedup).
REGRESSION_TEST_FILE_ANNOTATION_RE = re.compile(r"@regression-test-file:(\S+)")


class GateError(Exception):
    """A gate verdict carrying a non-zero exit code and a JSON payload.

    Raised by the parse/assertion helpers and caught by ``main`` so each
    failure path emits exactly one single-line JSON object before exiting.
    """

    def __init__(self, exit_code: int, payload: dict[str, object]) -> None:
        super().__init__(payload.get("error", payload.get("event", "gate error")))
        self.exit_code = exit_code
        self.payload = payload


#: The canonical Slice Plan table columns, in order -- the ONE locus every
#: caller needing the canonical header MUST derive from (M1: never a copied
#: literal). This is the parser's own header expectation: :func:`_build_slice_rows`
#: resolves each canonical field from the cell the HEADER NAMES (falling back to
#: the legacy positional read only when the header names none of these columns),
#: while :func:`slice_plan_header_deviation` compares the header ROW TEXT against
#: this constant to catch a drift the read alone cannot report (extra/missing/
#: reordered columns) -- see `feature_delta_doctor._slice_plan_header_gaps`, the
#: `malformed-slice-plan-header` gap emitter that consumes both.
SLICE_PLAN_CANONICAL_COLUMNS: tuple[str, ...] = (
    "Slice",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)

#: The canonical columns bound to names, unpacked FROM the SSOT tuple above --
#: never a second list of column names. An arity/order change to
#: `SLICE_PLAN_CANONICAL_COLUMNS` breaks this unpack LOUDLY at import time,
#: which is the intended failure mode.
(
    _SLICE_COLUMN,
    _VALUE_STATEMENT_COLUMN,
    _STATUS_COLUMN,
    _ANNOTATION_COLUMN,
    _JUSTIFICATION_COLUMN,
) = SLICE_PLAN_CANONICAL_COLUMNS

#: Header-cell separators collapsed before matching a header cell against the
#: canonical column names: `slice_id`, `slice-id`, `Slice  Id` all normalise to
#: the same key, so the snake_case/kebab-case spellings already shipped in this
#: repo's feature-deltas resolve to the same canonical column as `Slice`.
_HEADER_CELL_SEPARATOR_RE = re.compile(r"[\s_\-]+")


def _normalized_header_cell(cell: str) -> str:
    """Case-insensitive, whitespace/underscore/hyphen-normalised header cell."""
    return _HEADER_CELL_SEPARATOR_RE.sub(" ", cell.strip().lower()).strip()


#: Extra accepted spellings per canonical column, keyed BY the canonical name
#: (never a parallel column list). Only spellings actually shipped in this
#: repo's Slice Plan tables: `slice_id` / `slice-id` for the id column.
_SLICE_PLAN_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    _SLICE_COLUMN: ("slice id",),
}

#: normalised header cell -> canonical column name.
_CANONICAL_COLUMN_BY_HEADER_CELL: dict[str, str] = {
    key: column
    for column in SLICE_PLAN_CANONICAL_COLUMNS
    for key in (
        _normalized_header_cell(column),
        *_SLICE_PLAN_COLUMN_ALIASES.get(column, ()),
    )
}


def canonical_slice_plan_header() -> str:
    """The canonical Slice Plan header ROW, rendered from
    :data:`SLICE_PLAN_CANONICAL_COLUMNS` -- the copy-pasteable EXPECTED header a
    rejection shows the author (M1: derived, never a hand-written literal)."""
    return "| " + " | ".join(SLICE_PLAN_CANONICAL_COLUMNS) + " |"


def _resolve_header_columns(header_line: str) -> dict[str, int]:
    """Map each canonical column NAMED by ``header_line`` to its cell index.

    A canonical column the header does not name is simply absent from the
    mapping (the caller reads it as ``''``); a non-canonical extra column
    ("Class", "ADD + REMOVE") contributes no entry and therefore shifts
    nothing. An empty mapping means the header names no canonical column at
    all -- the caller's signal to fall back to the legacy positional read.
    """
    resolved: dict[str, int] = {}
    for index, cell in enumerate(_split_table_cells(header_line)):
        column = _CANONICAL_COLUMN_BY_HEADER_CELL.get(_normalized_header_cell(cell))
        if column is not None and column not in resolved:
            resolved[column] = index
    return resolved


@dataclass(frozen=True)
class SlicePlanRow:
    """One parsed row of the ``[REF] Slice Plan`` table."""

    slice_id: str
    value_statement: str
    status: str
    annotation: str
    justification: str


@dataclass(frozen=True)
class SlicePlan:
    """The parsed ``[REF] Slice Plan`` table -- ordered slice rows.

    ``header_line`` carries the table's header ROW verbatim (stripped) so a
    downstream assertion can tell "the column is ABSENT from the header" from
    "the cell is present but empty" -- two failure modes with two different
    repairs (add a column vs write the prose). Defaults to ``''`` for callers
    that build a plan directly from rows (tests, fixtures): an empty header
    line means "header unknown", never "column missing".
    """

    rows: tuple[SlicePlanRow, ...]
    header_line: str = ""

    def row_for(self, slice_id: str) -> SlicePlanRow | None:
        for row in self.rows:
            if row.slice_id == slice_id:
                return row
        return None


def is_slice_coupled(plan: SlicePlan, slice_id: str) -> bool:
    """Whether ``slice_id``'s OWN Slice-Plan row carries the ``@coupled``
    annotation -- the SAME predicate the carpaccio entry gate already trusts
    (``_COUPLED_TAG_RE.search(row.annotation)``, e.g. ``carpaccio_format.py:
    890, 1047``), exported here so a second gate (the E3 examine-verdict
    commit gate) can consult it without re-deriving the regex (RCA Branch B --
    fix-coupled-slice-examine-deferred-to-feature-end).

    Fail-closed to ``False`` when the row is absent -- an entering slice with
    no Slice-Plan row is never granted the ``@coupled`` observability
    exemption.
    """
    row = plan.row_for(slice_id)
    if row is None:
        return False
    return bool(_COUPLED_TAG_RE.search(row.annotation))


# ---------------------------------------------------------------------------
# .feature binding resolution (F-04)
# ---------------------------------------------------------------------------
#
# The ``@feature-{id}`` resolver (``_feature_tag_files``) moved to the
# application layer (AD-05 layering fix): a filesystem walk over a feature's
# ``.feature`` files is application logic the application layer must own WITHOUT
# importing back down into the CLI. It is imported at the top of this module
# under its legacy ``_feature_tag_files`` name (re-export) so existing
# ``carpaccio_format`` importers (``carpaccio_slice_gate``, ``carpaccio_precheck``)
# and this module's own ``check_carpaccio`` call-site resolve it unchanged.


# ---------------------------------------------------------------------------
# Config read (stdlib-only, F-11)
# ---------------------------------------------------------------------------


# Provenance labels `_resolve_slice_max` returns alongside the ceiling value
# (GDP-3/GDP-6, fix-carpaccio-ceiling-provenance): a bare integer in a
# rejection message hides WHICH source produced it -- a gitignored repo
# override silently lowering the framework default is invisible without this.
_SLICE_MAX_SOURCE_REPO_CONFIG: Literal["repo-config"] = "repo-config"
_SLICE_MAX_SOURCE_FRAMEWORK_DEFAULT: Literal["framework-default"] = "framework-default"


def _config_slice_max(repo: Path) -> int:
    """Read ``atdd_pure.carpaccio_slice_max`` from ``.nwave/config.yaml``.

    F-11: as a shipped ``des.cli`` module the gate MUST be stdlib-only -- the
    DES bundle scan (`tests/build/.../milestone-2-des-bundle.feature`) forbids
    ``import yaml`` in any bundled ``des`` module. ``.nwave/config.yaml`` carries
    the single ``atdd_pure.carpaccio_slice_max`` integer under a two-level
    block-mapping; a stdlib line-scan reads it without a YAML dependency,
    preserving the prior semantics (default + positive-int guard) exactly.

    Thin wrapper over :func:`_resolve_slice_max` -- kept for existing callers
    (``carpaccio_precheck``, unit tests) that only need the value, not its
    provenance.
    """
    return _resolve_slice_max(repo)[0]


def _resolve_slice_max(
    repo: Path,
) -> tuple[int, Literal["repo-config", "framework-default"]]:
    """Resolve the effective carpaccio ceiling AND its provenance.

    Same read semantics as :func:`_config_slice_max` (default + positive-int
    guard), but also reports WHICH source produced the value: ``"repo-config"``
    when ``.nwave/config.yaml`` exists and parses to a positive int, else
    ``"framework-default"`` (:data:`_DEFAULT_SLICE_MAX`). Callers that need to
    declare provenance in a user-facing message (the ``CARPACCIO_SLICE_TOO_LARGE``
    rejection) use this instead of the bare-int :func:`_config_slice_max`.
    """
    config_path = repo / ".nwave" / "config.yaml"
    if not config_path.is_file():
        return _DEFAULT_SLICE_MAX, _SLICE_MAX_SOURCE_FRAMEWORK_DEFAULT
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_SLICE_MAX, _SLICE_MAX_SOURCE_FRAMEWORK_DEFAULT
    value = _scan_atdd_pure_int(text, "carpaccio_slice_max")
    if isinstance(value, int) and value > 0:
        return value, _SLICE_MAX_SOURCE_REPO_CONFIG
    return _DEFAULT_SLICE_MAX, _SLICE_MAX_SOURCE_FRAMEWORK_DEFAULT


def _slice_max_provenance_clause(
    slice_max: int, source: Literal["repo-config", "framework-default"]
) -> str:
    """Render the ceiling's provenance for a user-facing rejection message.

    ``"repo-config"`` names BOTH the literal ``.nwave/config.yaml`` (the
    override's source) AND the framework default, so the operator sees the
    override lowered/raised it. ``"framework-default"`` positively labels the
    ceiling as the framework default and never mentions ``.nwave/config.yaml``
    (the negative AT guards against mislabeling the default as a repo
    override).
    """
    if source == _SLICE_MAX_SOURCE_REPO_CONFIG:
        return (
            f"from repo .nwave/config.yaml; framework default is {_DEFAULT_SLICE_MAX}"
        )
    return "framework default"


def _scan_atdd_pure_int(text: str, key: str) -> int | None:
    """Stdlib scan for an integer ``atdd_pure.<key>`` value in a YAML config.

    Reads the two-level block-mapping shape ``.nwave/config.yaml`` carries::

        atdd_pure:
          carpaccio_slice_max: <N>

    Returns the integer when the nested key is found under the ``atdd_pure:``
    top-level block, or None when absent / non-integer. Deliberately narrow:
    it parses exactly the one config shape the gate needs, not arbitrary YAML.
    """
    in_atdd_pure = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            in_atdd_pure = stripped.rstrip(":") == "atdd_pure" and stripped.endswith(
                ":"
            )
            continue
        if not in_atdd_pure or ":" not in stripped:
            continue
        name, _, value_text = stripped.partition(":")
        if name.strip() != key:
            continue
        try:
            return int(value_text.split("#", 1)[0].strip())
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Slice-plan table parsing (ADR-028 D2-bis)
# ---------------------------------------------------------------------------


# A GFM-escaped pipe (``\|``) is literal cell text, NOT a column boundary.
# ``_UNESCAPED_PIPE_RE`` matches a ``|`` only when it is not preceded by a
# backslash, so a row is split on real boundaries while ``\|`` survives inside a
# cell; ``_split_table_cells`` then un-escapes the survivor back to ``|``.
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")


def _split_table_cells(line: str) -> list[str]:
    """Split a GFM table row into trimmed cells, dropping the outer pipes.

    GFM-escaped pipes (``\\|``) are treated as literal text: the split is on
    un-escaped ``|`` only, and each cell un-escapes ``\\|`` back to ``|`` so the
    value statement keeps the literal pipe the author wrote.
    """
    stripped = line.strip()
    # Drop the single outer boundary pipe on each side (GFM table fence), then
    # split on un-escaped interior pipes so an in-cell ``\|`` is not a boundary.
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [
        cell.strip().replace("\\|", "|") for cell in _UNESCAPED_PIPE_RE.split(stripped)
    ]


def parse_slice_plan_rows(feature_delta_text: str) -> list[SlicePlanRow]:
    """Tolerant parse of the ``[REF] Slice Plan`` table into slice rows.

    The single shared slice-plan parser (C10): the carpaccio CLI entry gate and
    the subagent-stop hook both delegate here so the entry gate and the exit
    gate agree on the SAME parse of the SAME plan. Tolerant of three GFM-naive
    defects the two former copies disagreed on:

    * heading depth -- the section heading matches at H2 through H4;
    * escaped pipes -- a GFM ``\\|`` inside a cell is literal, not a boundary;
    * column layout -- the slice-id is the cell matching ``slice-NN`` and every
      other canonical field is read from the cell its HEADER NAMES, so a
      canonical column the header omits reads ``''`` and a non-canonical extra
      column shifts nothing. A 4-column plan without ``Status`` and a 6-column
      plan with a leading ``Class`` both parse correctly. Only a header naming
      NO canonical column at all falls back to the legacy positional read (and
      says so, loudly, on stderr).

    Raises ``GateError`` exit 1 when the section heading is absent, exit 2 when
    the table is malformed (no data rows, no row carrying a ``slice-NN`` id,
    duplicate slice id).
    """
    return _parse_slice_plan_table(feature_delta_text)[1]


def _parse_slice_plan_table(
    feature_delta_text: str,
) -> tuple[str, list[SlicePlanRow]]:
    """The shared parse -- the header ROW (verbatim, stripped) and the rows.

    One locus for both public entry points: :func:`parse_slice_plan_rows`
    keeps its rows-only signature (the hook's contract) while
    :func:`parse_slice_plan` also boxes the header, which is what lets a
    downstream rejection name a MISSING COLUMN instead of blaming the prose.
    """
    lines = feature_delta_text.splitlines()
    heading_index = next(
        (i for i, line in enumerate(lines) if _SLICE_PLAN_HEADING_RE.match(line)),
        None,
    )
    if heading_index is None:
        raise GateError(
            1,
            {
                "event": "SlicePlanSectionMissing",
                "error": "feature-delta has no '[REF] Slice Plan' section",
            },
        )
    table_rows = _collect_table_rows(lines, heading_index + 1)
    if len(table_rows) < 2:
        raise _malformed_table("the slice-plan table has no data rows")
    header_line = table_rows[0].strip()
    return header_line, _build_slice_rows(table_rows[2:], header_line)


def parse_slice_plan(feature_delta_text: str) -> SlicePlan:
    """Parse the ``[REF] Slice Plan`` table out of a feature-delta.

    Thin wrapper over the shared tolerant :func:`_parse_slice_plan_table` that
    boxes the rows -- and the header row they were resolved against -- into a
    :class:`SlicePlan`.
    """
    header_line, rows = _parse_slice_plan_table(feature_delta_text)
    return SlicePlan(rows=tuple(rows), header_line=header_line)


def _collect_table_rows(lines: list[str], start: int) -> list[str]:
    """Collect the contiguous GFM table block after the section heading.

    Truncation-aware (fix-carpaccio-names-malformed-table-line, GDP-3): a
    non-pipe line that interrupts the table body is the table's natural end
    ONLY when nothing but prose/a new section follows it. When a further
    pipe-delimited row exists below the interruption -- before the next
    markdown heading closes the section -- the interruption truncated the
    table body instead of ending it, and every row below was about to be
    silently dropped. That case raises :func:`_malformed_table` naming the
    stop line and cause, instead of letting the downstream entering-slice
    lookup mis-report the dropped row as genuinely absent. A well-formed
    table (no interruption, or an interruption with no further row before
    the next heading) parses byte-identically to before this fix.
    """
    rows: list[str] = []
    started = False
    for offset, line in enumerate(lines[start:]):
        if _TABLE_ROW_RE.match(line):
            started = True
            rows.append(line)
            continue
        if started:
            interruption_index = start + offset
            if _further_table_row_before_next_heading(lines, interruption_index):
                raise _malformed_table(
                    "the slice-plan table body was truncated at line "
                    f"{interruption_index + 1} -- that line is not a "
                    "pipe-delimited table row, so the row-per-line scan "
                    "stopped there and every declared slice row below it "
                    "was never read"
                )
            break
    return rows


def _further_table_row_before_next_heading(lines: list[str], from_index: int) -> bool:
    """True when a pipe-delimited table row appears at/after ``from_index``
    before the next markdown heading (or before the lines run out).

    Bounds the truncation check to the CURRENT section: a later, unrelated
    table under a later heading (e.g. a "Reuse Analysis" table further down
    the same feature-delta) must never be mistaken for a truncated slice-plan
    table -- the scan gives up the moment a new heading closes the section.
    """
    for line in lines[from_index:]:
        if _MARKDOWN_HEADING_RE.match(line):
            return False
        if _TABLE_ROW_RE.match(line):
            return True
    return False


def _build_slice_rows(
    data_rows: list[str], header_line: str = ""
) -> list[SlicePlanRow]:
    """Build slice rows from the table data rows, header-driven (exit 2).

    Header-driven: the slice-id is still the first cell matching ``slice-NN``
    (the row anchor), and every OTHER canonical field is read from the cell
    ``header_line`` NAMES for it. A canonical column the header omits reads
    ``''``; a non-canonical extra column ("Class", "ADD + REMOVE") is ignored
    and shifts nothing. Reading by offset from the slice-id cell was the defect
    this replaces: on a 4-column plan without ``Status`` the ``@coupled`` tag
    landed in ``status`` and the justification prose in ``annotation``.

    Legacy fallback: when ``header_line`` names NO canonical column at all (or
    no header was threaded in), the positional read is used -- already-shipped
    plans with a wholly non-canonical header keep parsing exactly as before.
    That fallback is announced on stderr, never taken silently.
    """
    columns = _resolve_header_columns(header_line)
    if not columns:
        _warn_positional_fallback(header_line)
    rows: list[SlicePlanRow] = []
    seen: set[str] = set()
    for raw in data_rows:
        cells = _split_table_cells(raw)
        slice_index = next(
            (i for i, cell in enumerate(cells) if _SLICE_ID_RE.match(cell)),
            None,
        )
        if slice_index is None:
            raise _malformed_table(
                f"slice-plan row has no 'slice-NN' identifier cell: {raw!r}"
            )
        slice_id = cells[slice_index]
        if slice_id in seen:
            raise _malformed_table(f"duplicate slice id in slice plan: {slice_id!r}")
        seen.add(slice_id)
        rows.append(_slice_plan_row(slice_id, cells, columns, slice_index))
    if not rows:
        raise _malformed_table("the slice-plan table has no slice rows")
    return rows


def _slice_plan_row(
    slice_id: str,
    cells: list[str],
    columns: dict[str, int],
    slice_index: int,
) -> SlicePlanRow:
    """One row's canonical fields, resolved by header name (or, when the header
    named no canonical column, by the legacy offset from the slice-id cell)."""
    if not columns:
        return SlicePlanRow(
            slice_id=slice_id,
            value_statement=_cell_at(cells, slice_index + 1),
            status=_cell_at(cells, slice_index + 2),
            annotation=_cell_at(cells, slice_index + 3),
            justification=_cell_at(cells, slice_index + 4),
        )
    return SlicePlanRow(
        slice_id=slice_id,
        value_statement=_column_cell(cells, columns, _VALUE_STATEMENT_COLUMN),
        status=_column_cell(cells, columns, _STATUS_COLUMN),
        annotation=_column_cell(cells, columns, _ANNOTATION_COLUMN),
        justification=_column_cell(cells, columns, _JUSTIFICATION_COLUMN),
    )


def _warn_positional_fallback(header_line: str) -> None:
    """Announce the legacy positional read on stderr (GDP-6: degrade LOUD).

    Emitted on stderr as one JSON line so it can never be mistaken for the
    gate's own stdout verdict, while still being observable to an operator and
    greppable by a log scan.
    """
    print(
        json.dumps(
            {
                "event": "SlicePlanHeaderNamesNoCanonicalColumn",
                "what": (
                    "the Slice Plan header names no canonical column "
                    f"(header: {header_line!r}); every cell was read by "
                    "POSITION from the slice-id cell"
                ),
                "why": (
                    "a positional read attributes cells by offset, so a table "
                    "whose columns differ from "
                    f"{canonical_slice_plan_header()} silently yields the "
                    "wrong value for status / annotation / justification"
                ),
                "how": (
                    "rewrite the Slice Plan header to "
                    f"{canonical_slice_plan_header()}, then re-run "
                    "`des feature-delta-doctor <feature-delta.md>` to confirm "
                    "the malformed-slice-plan-header gap is cleared"
                ),
            }
        ),
        file=sys.stderr,
    )


def _column_cell(cells: list[str], columns: dict[str, int], column: str) -> str:
    """The cell the header names for ``column``; ``''`` when the header omits
    that canonical column or the row is short of it."""
    index = columns.get(column)
    return "" if index is None else _cell_at(cells, index)


def _cell_at(cells: list[str], index: int) -> str:
    """Return ``cells[index]`` or the empty string when the column is absent."""
    return cells[index] if index < len(cells) else ""


def slice_plan_header_deviation(feature_delta_text: str) -> str | None:
    """Return the raw Slice Plan header row (stripped, verbatim) when it
    deviates from :data:`SLICE_PLAN_CANONICAL_COLUMNS`; ``None`` when the
    section/header row is absent, or when the header IS canonical.

    Compares header-row TEXT CELLS against the canonical schema (not merely
    column count): catches an extra column, a missing column, and reordered
    columns alike (fix-delta-doctor-validates-slice-plan-columns). Complements
    ``_build_slice_rows``, which now RESOLVES each field by header name and so
    reads a deviating table correctly, but still cannot tell the author their
    header deviates; this function only DETECTS the drift, it never rejects
    the parse.

    Consumed by ``feature_delta_doctor._slice_plan_header_gaps`` (M1: one
    locus, :data:`SLICE_PLAN_CANONICAL_COLUMNS` is the only place the
    canonical column names live).
    """
    lines = feature_delta_text.splitlines()
    heading_index = next(
        (i for i, line in enumerate(lines) if _SLICE_PLAN_HEADING_RE.match(line)),
        None,
    )
    if heading_index is None:
        return None
    table_rows = _collect_table_rows(lines, heading_index + 1)
    if not table_rows:
        return None
    header_line = table_rows[0]
    if tuple(_split_table_cells(header_line)) == SLICE_PLAN_CANONICAL_COLUMNS:
        return None
    return header_line.strip()


#: EDC-7/LSC-6 closed vocabulary for the Slice Plan ``Status`` column -- the
#: ONE exported locus every consumer of the closed status set imports (M1:
#: never a copied literal). ``mark_slice_status_shipped``'s own
#: ``.strip().lower() != "pending"`` comparison is the exact tolerance this
#: vocabulary's membership check mirrors: case-insensitive, whitespace-
#: stripped, no more and no less.
SLICE_PLAN_CANONICAL_STATUS_TOKENS: tuple[str, ...] = (
    "pending",
    "in-flight",
    "shipped",
)


def _normalized_status_token(status: str) -> str:
    """Case-insensitive, whitespace-stripped Status-cell token -- EXACTLY as
    tolerant as :func:`mark_slice_status_shipped`'s own ``.strip().lower()``
    comparison (no more, no less)."""
    return status.strip().lower()


@dataclass(frozen=True)
class SliceStatusDeviation:
    """One Slice Plan Status-cell finding outside the closed EDC-7/LSC-6
    vocabulary, or the GDP-8 third state naming why the statuses could not be
    read at all.

    ``state`` is one of ``"non-canonical"`` (a row's own Status cell is
    outside the closed vocabulary) or ``"could-not-verify"`` (the table
    exists but could not be parsed into rows at all -- ``detail`` names why).
    ``slice_id``/``status`` are populated only for the ``"non-canonical"``
    state.
    """

    state: str
    detail: str
    slice_id: str = ""
    status: str = ""


def slice_plan_status_deviations(feature_delta_text: str) -> list[SliceStatusDeviation]:
    """Every Slice Plan Status-cell deviation from the closed EDC-7/LSC-6
    vocabulary (:data:`SLICE_PLAN_CANONICAL_STATUS_TOKENS`), or the GDP-8
    third state when the table exists but cannot be parsed into rows at all.

    Returns ``[]`` when: the ``[REF] Slice Plan`` section is absent (already
    reported elsewhere, by ``missing-locked-section``), or the header names
    no ``Status`` column at all (already reported elsewhere, by
    ``malformed-slice-plan-header`` -- every cell then reads ``''`` and
    re-flagging it here would double-count one root cause under two gap
    ids).

    Never raises: any ``GateError`` the shared parse machinery raises while
    reading the table is caught and turned into the ``"could-not-verify"``
    state (GDP-6 -- silently reporting zero status deviations there would be
    a silent-wrong).

    Consumed by ``feature_delta_doctor._slice_plan_status_gaps`` (M1: one
    locus, detection here / rendering there -- mirrors
    :func:`slice_plan_header_deviation` / ``_slice_plan_header_gaps``).
    """
    lines = feature_delta_text.splitlines()
    heading_index = next(
        (i for i, line in enumerate(lines) if _SLICE_PLAN_HEADING_RE.match(line)),
        None,
    )
    if heading_index is None:
        return []
    try:
        table_rows = _collect_table_rows(lines, heading_index + 1)
    except GateError as exc:
        return [
            SliceStatusDeviation(
                state="could-not-verify",
                detail=str(exc.payload.get("error", exc)),
            )
        ]
    if not table_rows:
        return []
    header_line = table_rows[0]
    columns = _resolve_header_columns(header_line)
    if _STATUS_COLUMN not in columns:
        return []
    try:
        rows = _build_slice_rows(table_rows[2:], header_line)
    except GateError as exc:
        return [
            SliceStatusDeviation(
                state="could-not-verify",
                detail=str(exc.payload.get("error", exc)),
            )
        ]
    canonical = frozenset(SLICE_PLAN_CANONICAL_STATUS_TOKENS)
    return [
        SliceStatusDeviation(
            state="non-canonical",
            detail="",
            slice_id=row.slice_id,
            status=row.status,
        )
        for row in rows
        if _normalized_status_token(row.status) not in canonical
    ]


# ---------------------------------------------------------------------------
# Slice-plan table WRITE (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED)
# ---------------------------------------------------------------------------
#
# Mechanical, pure text-surgery counterparts to the parse-only machinery
# above. Neither function performs any I/O -- both take the feature-delta's
# text and return either the rewritten text or ``None`` (a no-op: nothing to
# change, or the input is not safely rewritable). The CALLER (``commit_slice
# .py`` / ``feature_end.py``, both hexagonal adapters that already own
# filesystem I/O) is responsible for reading/writing the file and for
# catching any unexpected exception -- this module's own promise stays
# "reads nothing, mutates nothing" at the FILESYSTEM level; these functions
# only transform an in-memory string.


def _replace_table_cell(line: str, cell_index: int, new_value: str) -> str | None:
    """Replace the ``cell_index``-th GFM cell's content in one table ``line``.

    Locates the un-escaped pipe boundaries (the SAME ``_UNESCAPED_PIPE_RE``
    scan :func:`_split_table_cells` uses) and rewrites ONLY the target
    cell's span to `` {new_value} `` (single-space padding, matching this
    repo's own Slice Plan authoring convention), leaving every other cell's
    original text -- including whatever whitespace/escaping the author
    used -- untouched. Returns ``None`` when ``cell_index`` is out of range
    for this row (fewer pipe boundaries than the requested cell needs)
    instead of guessing.
    """
    leading_ws = line[: len(line) - len(line.lstrip())]
    trailing_ws = line[len(line.rstrip()) :]
    stripped = line.strip()
    positions = [m.start() for m in _UNESCAPED_PIPE_RE.finditer(stripped)]
    if cell_index + 1 >= len(positions):
        return None
    start = positions[cell_index] + 1
    end = positions[cell_index + 1]
    new_stripped = f"{stripped[:start]} {new_value} {stripped[end:]}"
    return f"{leading_ws}{new_stripped}{trailing_ws}"


def mark_slice_status_shipped(feature_delta_text: str, slice_id: str) -> str | None:
    """Mechanically flip ``slice_id``'s Slice-Plan ``Status`` cell to ``shipped``.

    Pure text transform, idempotent and degrade-quiet-to-``None`` (the
    caller decides whether/how to report the no-op): returns the rewritten
    text on a genuine ``pending`` -> ``shipped`` flip, or ``None`` when NO
    rewrite happened -- any of: the ``[REF] Slice Plan`` section is absent,
    the table is malformed (the SAME ``GateError`` :func:`parse_slice_plan`
    raises), ``slice_id`` has no row, or the row's ``Status`` is anything
    OTHER than the literal ``pending`` (already ``shipped``, or a
    hand-authored value like ``blocked``/``in-progress`` this mechanical
    sync must NEVER clobber -- GDP-6, never invent a diagnosis for an
    unexpected value, just decline to touch it).

    F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED: this is the producing-tool
    side of the fix -- ``des commit-slice`` calls this right after a
    genuine ``SliceCommitVerified`` ledger append so the human-readable
    Slice Plan table never drifts from the ledger it is supposed to
    summarize.
    """
    try:
        plan = parse_slice_plan(feature_delta_text)
    except GateError:
        return None
    row = plan.row_for(slice_id)
    if row is None or row.status.strip().lower() != "pending":
        return None

    lines = feature_delta_text.splitlines()
    heading_index = next(
        (i for i, ln in enumerate(lines) if _SLICE_PLAN_HEADING_RE.match(ln)),
        None,
    )
    if heading_index is None:
        return None

    data_rows_seen = 0
    for i in range(heading_index + 1, len(lines)):
        line = lines[i]
        if not _TABLE_ROW_RE.match(line):
            if data_rows_seen >= 2:
                break
            continue
        data_rows_seen += 1
        if data_rows_seen <= 2:
            # Row 1 = header, row 2 = the `|---|---|` separator.
            continue
        cells = _split_table_cells(line)
        slice_index = next(
            (j for j, cell in enumerate(cells) if _SLICE_ID_RE.match(cell)), None
        )
        if slice_index is None or cells[slice_index] != slice_id:
            continue
        new_line = _replace_table_cell(line, slice_index + 2, "shipped")
        if new_line is None:
            return None
        lines[i] = new_line
        rewritten = "\n".join(lines)
        if feature_delta_text.endswith("\n"):
            rewritten += "\n"
        return rewritten
    return None


#: The mechanical feature-end-sealed marker, appended once by
#: :func:`mark_feature_end_sealed` -- the SAME `<!-- DES-... -->` HTML-comment
#: marker grammar this repo already uses (``des_enforcement_policy.py``,
#: ``marker_completeness_policy.py``, ``validator.py``), so a Slice Plan
#: reader (human or tool) sees a feature-end attestation the same way it
#: already recognizes other DES markers.
FEATURE_END_SEALED_MARKER = "<!-- DES-FEATURE-END: sealed -->"


def mark_feature_end_sealed(feature_delta_text: str) -> str | None:
    """Append the feature-end-sealed marker once. Pure text transform.

    Idempotent: returns ``None`` when the marker is ALREADY present (no
    rewrite), else the text with :data:`FEATURE_END_SEALED_MARKER`
    appended on its own line at the end of the file (a blank line first,
    unless the file already ends in one). Never requires a Slice Plan
    section -- a feature-delta with no Slice Plan still gets sealed.
    """
    if FEATURE_END_SEALED_MARKER in feature_delta_text:
        return None
    text = feature_delta_text
    if not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"
    return text + FEATURE_END_SEALED_MARKER + "\n"


def _malformed_table(detail: str) -> GateError:
    return GateError(
        2,
        {
            "event": "MalformedInput",
            "cause": "the slice-plan table",
            "error": detail,
        },
    )


def _malformed_feature_tag(detail: str) -> GateError:
    return GateError(
        2,
        {
            "event": "MalformedInput",
            "cause": "a .feature slice tag",
            "error": detail,
        },
    )


def _malformed_regression_file(detail: str) -> GateError:
    return GateError(
        2,
        {
            "event": "MalformedInput",
            "cause": "the pytest regression-test file",
            "error": detail,
        },
    )


def _malformed_pytest_bdd_bound_file(
    regression_test_file: Path, scenarios_call: ast.Call
) -> GateError:
    """Bug #64 (twin of #29/#42): ``--at-kind pytest-regression`` was blind to
    a module-level ``pytest_bdd.scenarios(<literal>)`` binding and misreported
    it as ``zero test_* functions`` -- a false "your file is broken/empty"
    that sends the maintainer chasing a non-existent authoring mistake.
    ``scenarios_call`` is only ever handed a call whose first positional
    argument is a string literal (guarded by
    :func:`des.cli.pytest_bdd_detection.module_level_scenarios_call`)."""
    first_arg = scenarios_call.args[0]
    assert isinstance(first_arg, ast.Constant)  # guarded by the caller
    feature_literal = first_arg.value
    assert isinstance(feature_literal, str)  # guarded by the caller
    return _malformed_regression_file(
        f"{regression_test_file} is gherkin/pytest-bdd-bound, not a plain "
        f"pytest-regression file: it carries a module-level "
        f"scenarios({feature_literal!r}) binding, so pytest-bdd registers "
        "its tests dynamically at collection time and no literal test_* "
        "function exists to count. Re-run with --at-kind gherkin instead of "
        "--at-kind pytest-regression."
    )


# ---------------------------------------------------------------------------
# pytest-regression AT-discovery mode (ADR-001, fix-pre-push-hook-dual-
# installer-collision) -- the pytest-native mirror of "one Gherkin Scenario
# = one AT", for a bugfix's plain-pytest regression test file.
# ---------------------------------------------------------------------------


def count_pytest_regression_ats(regression_test_file: Path) -> int:
    """AT count for ``at_kind="pytest-regression"`` -- ``len`` of
    :func:`pytest_regression_at_names` (ADR-001, this feature).

    See that function for the CLOSED counting rules and the raised
    ``GateError``s; this wrapper adds nothing but the count, and stays the
    published surface its existing callers import.
    """
    return len(pytest_regression_at_names(regression_test_file))


def pytest_regression_at_names(regression_test_file: Path) -> list[str]:
    """The module-level AT NAMES for ``at_kind="pytest-regression"``.

    AST-collects module-level (never class-nested) ``def test_*`` / ``async
    def test_*`` function definitions in ``regression_test_file`` -- the
    pytest-native mirror of "one Gherkin ``Scenario:`` = one AT". Names, not
    just a count, because the RED-seal delta path
    (:func:`_red_seal_net_new_at_names`) must INTERSECT this AT universe with
    the seal's failing set; the count is :func:`count_pytest_regression_ats`.
    Three exclusions are CLOSED (ADR-001):

    * a ``class TestFoo: def test_bar(self): ...`` is NOT counted (the walk
      is over ``tree.body`` only, never recursed into a class body);
    * a ``@pytest.mark.parametrize``-decorated ``def test_*`` counts as
      exactly ONE AT regardless of parameter-set count (mirrors Gherkin
      ``Scenario Outline:`` collapsing its ``Examples`` rows to one parsed
      ``Scenario``);
    * a ``test_*``-named function decorated ``@pytest.fixture`` / ``@fixture``
      is excluded via a decorator-list check before counting.

    Raises ``GateError`` exit 2 (``MalformedInput``, ``cause="the pytest
    regression-test file"``) when the file cannot be read, cannot be parsed,
    or has zero module-level ``test_*`` functions -- never a silently-zero
    AT count.
    """
    try:
        source = regression_test_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise _malformed_regression_file(
            f"cannot read {regression_test_file}: {exc}"
        ) from exc
    try:
        tree = ast.parse(source, filename=str(regression_test_file))
    except SyntaxError as exc:
        raise _malformed_regression_file(
            f"cannot parse {regression_test_file}: {exc}"
        ) from exc
    scenarios_call = module_level_scenarios_call(tree)
    if scenarios_call is not None:
        raise _malformed_pytest_bdd_bound_file(regression_test_file, scenarios_call)
    names = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
        and not _has_fixture_decorator(node)
    ]
    if not names:
        raise _malformed_regression_file(
            f"zero test_* functions found at module level in {regression_test_file}"
        )
    return names


def _predecessor_attested_at_total(
    repo: Path, feature_id: str, entering_slice: str
) -> int:
    """Sum of ``at_ids`` counts already attested to OTHER slices of this
    feature in the AT-completion ledger (fix-carpaccio-shared-file-overcount).

    Reads ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` -- the SAME ledger
    ``carpaccio_slice_gate._latest_verdict_record`` reads for the entering
    slice's OWN record -- but here scans for every OTHER ``slice_id`` (a
    predecessor that already shares this ``regression_test_file``), keeping
    only the LATEST ``ATReviewVerdict`` record per predecessor slice (a
    re-review supersedes an earlier one) and summing each one's ``at_ids``
    length. A predecessor slice's ``at_ids`` are generic ``AT-N`` labels
    local to that slice's own review, not globally-unique test names, so
    COUNTS are summed per distinct ``slice_id`` -- never a cross-slice set
    union, which would silently collide identical labels from different
    slices.

    Degrades honestly: an absent/unreadable ledger, or any malformed line,
    contributes 0 for that line -- never raises. The caller's own fallback
    (whole-file count when the ledger is entirely absent) is what keeps this
    honest, per GDP-7 (filesystem-only, no git).
    """
    at_ledger_path = ledger_path(repo, LedgerFamily.ATDD_PURE, feature_id)
    if not at_ledger_path.is_file():
        return 0
    latest_by_slice: dict[str, object] = {}
    try:
        lines = at_ledger_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") != "ATReviewVerdict":
            continue
        slice_id = record.get("slice_id")
        if not isinstance(slice_id, str) or slice_id == entering_slice:
            continue
        latest_by_slice[slice_id] = record.get("at_ids")
    total = 0
    for at_ids in latest_by_slice.values():
        if isinstance(at_ids, list):
            total += len(at_ids)
    return total


def _red_seal_is_fresh(repo: Path, regression_test_file: Path) -> bool:
    """True iff a ``RedObserved`` seal (P0.2, ``verify-red-green
    --record-red``) is on record for ``regression_test_file`` AND its recorded
    ``content_sha256`` matches the file's CURRENT bytes AND it witnessed >=1
    failing test.

    The single extracted locus for the content-bound freshness FACT
    (fix-readiness-gate-at-kind-blind-scenario-tags) -- pulled out of
    :func:`_red_seal_net_new_at_names` so a second caller needing ONLY the
    boolean freshness predicate (never the AT-name delta) reuses this instead
    of hand-rolling a second staleness rule. Mirrors
    ``carpaccio_slice_gate._red_seal_fresh``'s semantics exactly (same
    content-sha + witnessed-failure contract, over RESOLVED paths so the
    slug/hash can never diverge from the producer, which also resolves both).
    Degrades ``False`` -- never a silent pass -- on every malformed, absent,
    outside-repo, or stale input.
    """
    try:
        seal = _red_green_seal_path(repo.resolve(), regression_test_file.resolve())
    except ValueError:
        return False  # regression file outside the repo -- no resolvable slug
    if not seal.is_file():
        return False
    try:
        record = json.loads(seal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, dict):
        return False
    outcomes = record.get("outcomes")
    if not isinstance(outcomes, dict) or "fail" not in outcomes.values():
        return False
    try:
        current_sha = _red_seal_content_sha(regression_test_file)
    except OSError:
        return False
    return record.get("content_sha256") == current_sha


def _red_seal_net_new_at_names(
    repo: Path, regression_test_file: Path
) -> set[str] | None:
    """The file's ATs that this slice is INTRODUCING, per its fresh RED seal.

    The property-side answer (GDP-8) to "how many ATs does this slice add to
    a file it SHARES with earlier work". ``des verify-red-green --record-red``
    seals, at ``.nwave/telemetry/red-green/{slug}.json``, one outcome per test
    id: the ATs the entering slice is introducing FAIL (they witness behavior
    that does not exist yet) while every already-delivered test PASSES. So the
    failing set IS the slice's delta -- observed, not designated, and read
    from the filesystem alone (GDP-7: no git, no external tool).

    Junit ids are ``{classname}::{name}``; the name is reduced to its function
    identifier (a ``@parametrize`` id suffix ``[...]`` is dropped, mirroring
    :func:`pytest_regression_at_names`' one-AT-per-parametrized-function rule)
    and INTERSECTED by the caller with that AST universe -- so a class-nested
    or fixture-decorated test in the seal can never inflate the delta.

    Returns ``None`` -- never a count the caller might trust -- on every
    degraded input: seal absent, unreadable, malformed, outside the repo, or
    content-STALE. Staleness is the load-bearing one (GDP-6, fail-closed):
    the seal is bound to ``content_sha256``, so tests appended after RED was
    recorded leave the seal no longer describing the file, and the caller
    falls back to the whole-file charge rather than letting the additions ride
    in unseen. The freshness half of this check now delegates to
    :func:`_red_seal_is_fresh` (the single extracted locus for that fact).
    """
    if not _red_seal_is_fresh(repo, regression_test_file):
        return None
    try:
        seal = _red_green_seal_path(repo, regression_test_file)
    except ValueError:
        return None  # regression file outside the repo -- no resolvable slug
    try:
        record = json.loads(seal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    outcomes = record.get("outcomes")
    if not isinstance(outcomes, dict):
        return None
    failing = {
        str(test_id).rsplit("::", 1)[-1].split("[", 1)[0]
        for test_id, outcome in outcomes.items()
        if outcome == "fail"
    }
    return failing or None


def count_net_new_pytest_regression_ats(
    regression_test_file: Path,
    *,
    repo: Path | None = None,
    feature_id: str | None = None,
    entering_slice: str | None = None,
) -> int:
    """Net-new AT count for the ENTERING slice (fix-carpaccio-shared-file-
    overcount, recurring friction #53).

    The single locus BOTH carpaccio call sites use for a ``regression_test_
    file`` that is SHARED across slices: ``check_carpaccio``'s assertion-1
    size gate (this module) and ``carpaccio_slice_gate._check_verdict_record``'s
    assertion-5 AT-set check. Both previously called
    :func:`count_pytest_regression_ats` directly and consumed the file's
    WHOLE total unconditionally -- a slice adding 1 AT to a file already
    carrying a predecessor's 10 attested ATs was over-counted to 11.

    Two sources answer "net-new", consulted STRONGEST-FIRST.

    1. The fresh RED seal (:func:`_red_seal_net_new_at_names`) -- the file's
       ATs that FAIL pre-implementation, intersected with the module-level AT
       universe. This is the PROPERTY (which ATs is this slice introducing),
       and it is the only one of the two that can see tests left by ANOTHER
       feature or by a bugfix.
    2. Otherwise the whole-file AST count MINUS the ``at_ids`` already
       attested to other slices of THIS feature in the AT-completion ledger
       (:func:`_predecessor_attested_at_total`). Clamped at 0 -- a net-new
       count cannot be negative even if ledger data is unexpectedly stale.

    Source 2 alone was the defect (defects.md: ``carpaccio-pytest-route-
    counts-whole-file-not-slice-delta``): its ledger is FEATURE-SCOPED and its
    verdict records carry no file path, so tests a PRIOR feature or bugfix
    left in a shared file subtract nothing and are charged to the entering
    slice. Measured: 5 inherited + 3 added = 8, rejected against the ceiling
    of 7. That made the gate PENALISE reuse of an existing test file and
    REWARD spawning new ones -- inverting the reuse-first discipline DESIGN
    enforces upstream.

    The seal-derived count needs no upper clamp: it is an INTERSECTION with
    the file's own AT universe, so a stray or renamed seal id cannot charge
    more than the file holds. It is taken only when non-empty, so a seal whose
    failing tests all fall outside that universe (class-nested, say) degrades
    to source 2 rather than reporting a free 0.

    Degrades honestly to the WHOLE-FILE count (today's behavior, never
    silently permissive) when ``repo``, ``feature_id``, or ``entering_slice``
    is omitted, and to source 2 when the seal is absent/stale/unusable.
    """
    names = pytest_regression_at_names(regression_test_file)
    total = len(names)
    if repo is None:
        return total
    seal_names = _red_seal_net_new_at_names(repo, regression_test_file)
    if seal_names is not None:
        net_new = len(set(names) & seal_names)
        if net_new:
            return net_new
    if feature_id is None or entering_slice is None:
        return total
    predecessor_total = _predecessor_attested_at_total(repo, feature_id, entering_slice)
    return max(total - predecessor_total, 0)


def pytest_regression_content_hash(regression_test_file: Path) -> str:
    """Content-seal for ``at_kind="pytest-regression"`` (ADR-001, this feature).

    SHA-256 over ``regression_test_file``'s raw source text -- the pytest-
    regression mirror of ``_at_content_hash``'s sorted-scenario-body hash:
    same anti-staleness guarantee (any post-approval edit changes the hash),
    different substrate (one file's full source, not scenario bodies).
    """
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise _malformed_regression_file(
            f"cannot read {regression_test_file}: {exc}"
        ) from exc
    return hashlib.sha256(source).hexdigest()


# ---------------------------------------------------------------------------
# native-regression AT-discovery mode (fix-rust-regression-at-kind-wiring) --
# resolves (at_ids, content_hash) through the unified AT-discovery port
# facet-pair (``des.ports.test_runner_port.RunnerAdapter.discover_ats``)
# instead of a per-language hand-rolled scanner. The runner is resolved from
# the regression file's OWN suffix -- mirrors ``verify_slice_commit_
# completeness._routes_through_runner_port``'s suffix-keyed decision -- NEVER
# an operator-declared per-language flag. ``_AT_DISCOVERY_SUFFIX_RUNNER`` is
# an IMPORT of the ``des.ports.test_runner_port.AT_KIND_SUFFIX_MAP`` SSOT
# (ADR-AAD-001 DA-5) -- not an independently-defined literal.
# ---------------------------------------------------------------------------


def _no_at_detector_for_language(regression_test_file: Path, detail: str) -> GateError:
    return GateError(
        2,
        {
            "event": "MalformedInput",
            "cause": "the regression-test file",
            "error": f"no AT detector for this language -- {detail}",
            "how": (
                f"{regression_test_file} has no wired AT-discovery facet; "
                f"recognized suffixes: {sorted(_AT_DISCOVERY_SUFFIX_RUNNER)!r}"
            ),
        },
    )


def native_regression_at_discovery(regression_test_file: Path) -> tuple[list[str], str]:
    """Derive ``(at_ids, at_content_hash)`` for ``at_kind="native-regression"``.

    Resolves the at-discovery runner from ``regression_test_file``'s suffix,
    seeds the runner registry, and dispatches through ``RunnerAdapter.
    discover_ats`` -- the SAME unified port facet-pair
    ``discover_pytest_ats``/``discover_cargo_ats`` register under
    (fix-rust-regression-at-kind-wiring). An unrecognized suffix, or a
    ``RunnerAdapterUnavailable`` degrade from the facet itself (unreadable/
    malformed/zero-AT file), raises ``GateError`` exit 2 naming "no AT
    detector for this language" -- degrade-LOUD, never a silent pytest
    fallback on a non-Python target.
    """
    from des.adapters.driven.runner.runner_registry import seed_runner_registry
    from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable

    runner_name = _AT_DISCOVERY_SUFFIX_RUNNER.get(regression_test_file.suffix)
    if runner_name is None:
        raise _no_at_detector_for_language(
            regression_test_file,
            f"unrecognized suffix {regression_test_file.suffix!r}",
        )
    seed_runner_registry()
    adapter = RunnerAdapter(name=runner_name)
    try:
        discovery = adapter.discover_ats(
            regression_test_file.parent, regression_test_file
        )
    except RunnerAdapterUnavailable as exc:
        raise _no_at_detector_for_language(
            regression_test_file,
            f"the {runner_name!r} at-discovery facet refused: {exc}",
        ) from exc
    return list(discovery.at_ids), discovery.content_hash


def _has_fixture_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _decorator_name(dec) in ("fixture", "pytest.fixture")
        for dec in node.decorator_list
    )


def _decorator_name(dec: ast.expr) -> str:
    """Dotted name of a decorator expression, e.g. ``@pytest.fixture(...)`` -> 'pytest.fixture'."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


# ---------------------------------------------------------------------------
# .feature scenario parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One parsed ``.feature`` scenario: its slice tags + its normalized body."""

    slice_tags: tuple[str, ...]
    has_coupled_tag: bool
    normalized_body: str


def read_feature_files(repo: Path, feature_id: str) -> list[str]:
    """Read every ``.feature`` file self-identifying with ``feature_id``."""
    return [
        path.read_text(encoding="utf-8", errors="replace")
        for path in _feature_tag_files(repo, feature_id)
    ]


def parse_scenarios(feature_texts: list[str]) -> list[Scenario]:
    """Parse every ``Scenario`` block across the slice's ``.feature`` files."""
    scenarios: list[Scenario] = []
    for text in feature_texts:
        scenarios.extend(_parse_scenarios_in_text(text))
    return scenarios


def _parse_scenarios_in_text(text: str) -> list[Scenario]:
    lines = text.splitlines()
    scenarios: list[Scenario] = []
    pending_tags: list[str] = []
    block: list[str] | None = None
    block_tags: list[str] = []

    def flush() -> None:
        if block is not None:
            scenarios.append(_make_scenario(block_tags, block))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@"):
            pending_tags.append(stripped)
            continue
        if stripped.startswith("Scenario:") or stripped.startswith("Scenario Outline:"):
            flush()
            block = []
            block_tags = list(pending_tags)
            pending_tags = []
            continue
        if stripped.startswith("Feature:"):
            pending_tags = []
            continue
        if block is not None:
            block.append(line)
    flush()
    return scenarios


def _make_scenario(tag_lines: list[str], body_lines: list[str]) -> Scenario:
    tag_text = " ".join(tag_lines)
    slice_tags = tuple(_SLICE_TAG_RE.findall(tag_text))
    has_coupled = bool(_COUPLED_TAG_RE.search(tag_text))
    normalized = _normalize_body(body_lines)
    return Scenario(
        slice_tags=slice_tags,
        has_coupled_tag=has_coupled,
        normalized_body=normalized,
    )


def _normalize_body(body_lines: list[str]) -> str:
    """Normalize a scenario body: strip per line, drop blanks, lowercase.

    Tag lines are already excluded by the parser. Per ADR-029 D5 Hole-fix:
    a pure re-tag does not churn the hash, any Given/When/Then edit does.
    """
    cleaned = [line.strip().lower() for line in body_lines if line.strip()]
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Carpaccio assertions 1-4 (ADR-028 D2-bis)
# ---------------------------------------------------------------------------


def check_carpaccio(
    plan: SlicePlan,
    scenarios: list[Scenario],
    entering_slice: str,
    slice_max: int,
    at_kind: Literal["gherkin", "pytest-regression", "native-regression"] = "gherkin",
    regression_test_file: Path | None = None,
    *,
    repo: Path | None = None,
    feature_id: str | None = None,
    slice_max_source: Literal["repo-config", "framework-default"] = (
        "framework-default"
    ),
) -> dict[str, object] | None:
    """Run carpaccio assertions 1-4 (+ mixed-mode guard). Raises ``GateError``.

    ``repo`` + ``feature_id`` (fix-feature-tag-files-workspace-layout,
    keyword-only, optional): when both are given, a ``no-scenarios-for-slice``
    rejection is enriched with WHAT was searched (the ``@feature-{feature_id}``
    tag), WHERE (the roots walked), and HOW to fix it -- see
    :func:`_no_scenarios_rejection`. When either is omitted, the plain
    :func:`_at_review_rejection` fires unchanged (byte-identical legacy path).

    ``slice_max_source`` (keyword-only, fix-carpaccio-ceiling-provenance):
    declares WHERE ``slice_max`` came from (``"repo-config"`` |
    ``"framework-default"``, see :func:`_resolve_slice_max`) so the
    ``CARPACCIO_SLICE_TOO_LARGE`` rejection can name its provenance. Defaults
    to ``"framework-default"`` for callers that pass a bare ``slice_max``
    without resolving provenance (byte-identical message for those callers'
    intended default-ceiling case).

    ``at_kind="gherkin"`` (default) preserves byte-identical behavior for
    every existing caller. ``at_kind="pytest-regression"`` (ADR-001,
    fix-pre-push-hook-dual-installer-collision) swaps assertion 2's
    Gherkin-coverage check + the Gherkin-scenario AT count for an AST-counted
    ``test_*``-function AT count read from ``regression_test_file``;
    assertions 1/3/4 are REUSED UNCHANGED -- only the AT-count source differs.

    Raises ``ValueError`` (a programming-contract violation, never a
    ``GateError``) when ``at_kind="pytest-regression"`` is passed with
    ``regression_test_file=None`` -- only the CLI's own arg-parsing can
    mis-wire this combination; it never reflects a malformed feature-delta.

    Returns a non-None dict only to surface the ``CoupledSliceAccepted``
    event when an over-N coupled slice with a justification is accepted
    (gherkin mode only -- a pytest-regression AT carries no ``@coupled``-tag
    vocabulary, so the escape never applies in that mode).
    """
    if (
        at_kind in ("pytest-regression", "native-regression")
        and regression_test_file is None
    ):
        raise ValueError(
            f"check_carpaccio: at_kind={at_kind!r} requires regression_test_file"
        )
    if at_kind in ("pytest-regression", "native-regression") and _slice_scenarios(
        scenarios, entering_slice
    ):
        # A selected regression file may coexist with Gherkin scenarios owned
        # by other slices, but never with a second AT-discovery route for the
        # slice entering delivery.
        raise GateError(
            2,
            {
                "event": "MalformedInput",
                "cause": "mixed AT-discovery mode",
                "error": (
                    f"at_kind={at_kind!r} but entering slice {entering_slice!r} "
                    "also owns .feature scenarios; select one AT-discovery mode "
                    "for that slice"
                ),
            },
        )
    entering_row = plan.row_for(entering_slice)
    if entering_row is None:
        raise GateError(
            44,
            {
                "event": "CARPACCIO_SLICE_TOO_LARGE",
                "error": (
                    f"entering slice {entering_slice!r} has no row in the slice plan"
                ),
                "instruction": (
                    "add a slice-plan row for the entering slice, or re-slice"
                ),
            },
        )
    if at_kind == "pytest-regression":
        assert regression_test_file is not None  # guarded above
        at_count = count_net_new_pytest_regression_ats(
            regression_test_file,
            repo=repo,
            feature_id=feature_id,
            entering_slice=entering_slice,
        )
        _check_walking_skeleton_first(plan)
        _check_value_annotation(plan)
        all_coupled = bool(_COUPLED_TAG_RE.search(entering_row.annotation))
        return _check_slice_size_count(
            plan,
            entering_slice,
            slice_max,
            at_count,
            all_coupled=all_coupled,
            slice_max_source=slice_max_source,
        )
    if at_kind == "native-regression":
        assert regression_test_file is not None  # guarded above
        at_ids, _content_hash = native_regression_at_discovery(regression_test_file)
        _check_walking_skeleton_first(plan)
        _check_value_annotation(plan)
        all_coupled = bool(_COUPLED_TAG_RE.search(entering_row.annotation))
        return _check_slice_size_count(
            plan,
            entering_slice,
            slice_max,
            len(at_ids),
            all_coupled=all_coupled,
            slice_max_source=slice_max_source,
        )
    _check_total_coverage(plan, scenarios)
    _check_walking_skeleton_first(plan)
    _check_value_annotation(plan)
    if not _slice_scenarios(scenarios, entering_slice):
        profile = _lane_profile_for_slice(plan, entering_slice)
        if profile is not None and profile.at_requirement is AtRequirement.EXEMPT:
            return {
                "event": "LaneAtExemptionAccepted",
                "slice_id": entering_slice,
                "lane": profile.lane_id,
            }
        if repo is not None and feature_id is not None:
            raise _no_scenarios_rejection(repo, feature_id, entering_slice)
        raise _at_review_rejection("no-scenarios-for-slice", entering_slice)
    return _check_slice_size(
        plan, scenarios, entering_slice, slice_max, slice_max_source=slice_max_source
    )


def _lane_profile_for_slice(plan: SlicePlan, slice_id: str) -> LaneProfile | None:
    """Resolve a Slice-Plan row's Annotation cell to a `LANE_PROFILES` entry.

    The single shared consulting mechanism (D11/D12, green-to-green-seal-
    design.md): both `check_carpaccio`'s no-scenarios-for-slice branch (here)
    and `check_at_review` (`carpaccio_slice_gate.py`) resolve the SAME lane
    profile through this ONE helper, so the AT-exemption never diverges
    between the two consulting loci. Returns ``None`` when the row is absent
    or carries no `@prefactoring` annotation -- the negative path (an
    unannotated 0-AT slice) then falls through to the existing rejection,
    byte-identical to today.
    """
    row = plan.row_for(slice_id)
    if row is None or not _PREFACTORING_TAG_RE.search(row.annotation):
        return None
    return LANE_PROFILES.get("prefactoring")


def _slice_scenarios(scenarios: list[Scenario], slice_id: str) -> list[Scenario]:
    return [s for s in scenarios if slice_id in s.slice_tags]


def _check_total_coverage(plan: SlicePlan, scenarios: list[Scenario]) -> None:
    """Assertion 2: every authored scenario carries exactly one @slice-NN tag."""
    plan_ids = {row.slice_id for row in plan.rows}
    for scenario in scenarios:
        tag_count = len(scenario.slice_tags)
        if tag_count == 0:
            raise GateError(
                44,
                {
                    "event": "CARPACCIO_SLICE_TOO_LARGE",
                    "error": (
                        "an authored scenario carries no @slice-NN tag "
                        "(incremental total-coverage violation)"
                    ),
                    "instruction": (
                        "tag every authored scenario with exactly one @slice-NN"
                    ),
                },
            )
        if tag_count > 1:
            raise GateError(
                44,
                {
                    "event": "CARPACCIO_SLICE_TOO_LARGE",
                    "error": (
                        "an authored scenario carries multiple @slice-NN tags "
                        f"({sorted(scenario.slice_tags)})"
                    ),
                    "instruction": "give each scenario exactly one @slice-NN tag",
                },
            )
        tag = scenario.slice_tags[0]
        if tag not in plan_ids:
            raise _malformed_feature_tag(
                f"a .feature scenario carries @{tag} with no matching slice-plan row"
            )


def _check_walking_skeleton_first(plan: SlicePlan) -> None:
    """Assertion 3: a @walking-skeleton slice must be the first plan row,
    OR preceded ONLY by @prefactoring prerequisite rows (any count, N>=0).

    The shape is `prefactoring* -> walking-skeleton -> later behavioral
    slices`: zero or more @prefactoring rows immediately before the walking
    skeleton are a recognized, behavior-preserving prerequisite (e.g. an
    extract-interface refactor the walking skeleton must drive against) --
    not an ad-hoc reordering, and NOT capped at one row. Any prefix row that
    is NOT @prefactoring still rejects, naming the FIRST such offending row
    rather than the old generic "not ordered first" text.
    """
    ws_index = next(
        (
            i
            for i, row in enumerate(plan.rows)
            if _WALKING_SKELETON_RE.search(row.annotation)
        ),
        None,
    )
    if ws_index is None or ws_index == 0:
        return
    prefix = plan.rows[:ws_index]
    non_prefactoring = [
        row for row in prefix if not _PREFACTORING_TAG_RE.search(row.annotation)
    ]
    if non_prefactoring:
        offending = non_prefactoring[0]
        raise GateError(
            44,
            {
                "event": "CARPACCIO_SLICE_TOO_LARGE",
                "error": (
                    f"slice {offending.slice_id} precedes the @walking-skeleton "
                    "row but is neither the walking skeleton nor a recognized "
                    "@prefactoring prerequisite"
                ),
                "instruction": (
                    "order the @walking-skeleton slice first in the plan, or "
                    "tag the prerequisite row @prefactoring with a "
                    "justification via `des feature-delta-doctor "
                    "<feature-delta.md>`"
                ),
            },
        )


def _check_value_annotation(plan: SlicePlan) -> None:
    """Assertion 4: an annotated escape row must record a justification.

    Two failure modes, two repairs (GDP-3/GDP-4) -- conflating them is the
    defect this split fixes:

    * the ``Justification`` COLUMN is absent from the header -> no prose can
      ever be recorded, so the rejection names the missing column, shows the
      header FOUND against the canonical header EXPECTED, and routes the
      repair to the producing tool (``des feature-delta-doctor``);
    * the column is present and the CELL is empty -> the author's repair
      really is to write the prose, so the content-directed rejection stands.
    """
    for row in plan.rows:
        if _ANNOTATION_ESCAPE_RE.search(row.annotation) and not row.justification:
            raise _missing_justification_error(plan, row)


def _missing_justification_error(plan: SlicePlan, row: SlicePlanRow) -> GateError:
    """The rejection for an annotated escape row with no justification --
    missing-COLUMN diagnosis when the header omits ``Justification``, else the
    content-directed diagnosis for a present-but-empty cell."""
    if not _justification_column_absent(plan):
        return GateError(
            44,
            {
                "event": "CARPACCIO_SLICE_TOO_LARGE",
                "error": (
                    f"slice {row.slice_id} carries annotation "
                    f"{row.annotation!r} but records no justification"
                ),
                "instruction": "record a justification for the annotated slice",
            },
        )
    canonical_header = canonical_slice_plan_header()
    return GateError(
        44,
        {
            "event": "CARPACCIO_SLICE_TOO_LARGE",
            "error": (
                f"the Slice Plan table has no '{_JUSTIFICATION_COLUMN}' column, "
                f"so slice {row.slice_id}'s annotation {row.annotation!r} has "
                f"nowhere to record its justification -- header FOUND: "
                f"{plan.header_line} -- header EXPECTED: {canonical_header}"
            ),
            "instruction": (
                f"add the missing '{_JUSTIFICATION_COLUMN}' column: rewrite the "
                f"Slice Plan header to {canonical_header} and give every row a "
                "matching cell, then re-run `des feature-delta-doctor "
                "<feature-delta.md>` to confirm the malformed-slice-plan-header "
                "gap is cleared"
            ),
        },
    )


def _justification_column_absent(plan: SlicePlan) -> bool:
    """Whether the plan's header row names no ``Justification`` column.

    ``False`` when the header is unknown (a plan built directly from rows):
    an unknown header is never reported as a missing column -- fail-safe onto
    the content-directed rejection, which is the pre-existing behaviour.
    """
    if not plan.header_line:
        return False
    return _JUSTIFICATION_COLUMN not in _resolve_header_columns(plan.header_line)


def _check_slice_size(
    plan: SlicePlan,
    scenarios: list[Scenario],
    entering_slice: str,
    slice_max: int,
    *,
    slice_max_source: Literal["repo-config", "framework-default"] = (
        "framework-default"
    ),
) -> dict[str, object] | None:
    """Assertion 1 (gherkin mode): slice size <= N unless a coupled-AT-group
    escape applies.

    The only size escape (ADR-028 D2) is a coupled AT group: the entering
    slice's own Slice-Plan row carries a ``@coupled`` annotation AND records a
    coupling justification (fix-carpaccio-coupled-gherkin-reads-row) -- the
    ROW is authoritative, mirroring the pytest-regression branch
    (``check_carpaccio``, ``_COUPLED_TAG_RE.search(entering_row.annotation)``),
    since the CARPACCIO_SLICE_TOO_LARGE rejection instructs the operator to
    annotate the row regardless of ``at_kind``. Per-scenario ``@coupled`` tags
    remain an optional mirror -- honored too, but never required. A plain
    ``@walking-skeleton`` / ``@infrastructure`` annotation does NOT lift the
    size ceiling -- it governs ordering and the value-annotation check, not
    slice size.
    """
    slice_scenarios = _slice_scenarios(scenarios, entering_slice)
    at_count = len(slice_scenarios)
    row = plan.row_for(entering_slice)
    row_coupled = bool(row is not None and _COUPLED_TAG_RE.search(row.annotation))
    scenarios_coupled = bool(slice_scenarios) and all(
        s.has_coupled_tag for s in slice_scenarios
    )
    all_coupled = row_coupled or scenarios_coupled
    return _check_slice_size_count(
        plan,
        entering_slice,
        slice_max,
        at_count,
        all_coupled,
        slice_max_source=slice_max_source,
    )


def _check_slice_size_count(
    plan: SlicePlan,
    entering_slice: str,
    slice_max: int,
    at_count: int,
    all_coupled: bool,
    *,
    slice_max_source: Literal["repo-config", "framework-default"] = (
        "framework-default"
    ),
) -> dict[str, object] | None:
    """Assertion 1 core: slice size <= N unless a coupled-AT-group escape applies.

    Shared by both ``at_kind`` modes (ADR-001, fix-pre-push-hook-dual-
    installer-collision; ``all_coupled`` derivation fixed under
    fix-carpaccio-pytest-coupled-escape): gherkin mode (``_check_slice_size``)
    computes ``at_count`` / ``all_coupled`` from ``.feature`` scenarios'
    ``@coupled`` tags; pytest-regression mode (``check_carpaccio``) passes the
    AST-counted AT count and derives ``all_coupled`` from the entering slice's
    own Slice-Plan row Annotation cell (``_COUPLED_TAG_RE.search(row.annotation)``)
    -- the same ``@coupled``-tag vocabulary, read from the row instead of from
    scenario tags, since a plain pytest regression file carries no per-test tags.

    ``slice_max_source`` (fix-carpaccio-ceiling-provenance, GDP-3/GDP-6):
    declares WHERE ``slice_max`` came from so the ``CARPACCIO_SLICE_TOO_LARGE``
    rejection names its provenance instead of a bare, source-less integer.
    """
    if at_count <= slice_max:
        return None
    row = plan.row_for(entering_slice)
    assert row is not None  # guaranteed by check_carpaccio precondition
    if all_coupled and row.justification:
        return {
            "event": "CoupledSliceAccepted",
            "slice_id": entering_slice,
            "at_count": at_count,
        }
    provenance_clause = _slice_max_provenance_clause(slice_max, slice_max_source)
    raise GateError(
        44,
        {
            "event": "CARPACCIO_SLICE_TOO_LARGE",
            "slice_id": entering_slice,
            "at_count": at_count,
            "slice_max": slice_max,
            "slice_max_source": slice_max_source,
            "error": (
                f"slice {entering_slice} has {at_count} ATs, exceeding the "
                f"carpaccio ceiling of {slice_max} ({provenance_clause})"
            ),
            "instruction": (
                "a cohesive over-ceiling slice is LEGITIMATE, not a violation: "
                "if the AT group cannot be decomposed without breaking the "
                "single end-to-end vertical it proves, annotate the slice-plan "
                "row @coupled with a recorded justification (ADR-028 D2) -- "
                "this is the DESIGNED escape path, not a workaround. Otherwise "
                f"re-slice into thinner end-to-end verticals each within the "
                f"ceiling of {slice_max} ({provenance_clause}). A slice that is "
                "over-ceiling AND not cleanly re-sliceable warrants deep-review "
                "+ refactor at FEATURE scope, not a per-slice patch. "
                "@walking-skeleton / @infrastructure annotations govern "
                "ordering, not this size escape -- only @coupled + "
                "justification lifts the ceiling"
            ),
        },
    )


# ---------------------------------------------------------------------------
# Shared AT-review helper (crosses the moved/retained boundary -- ADR-001)
# ---------------------------------------------------------------------------


def _at_review_rejection(reason: str, slice_id: str) -> GateError:
    """Self-describing ``ATReviewGateRejected`` (GDP-3/GDP-4, fix-carpaccio-
    at-review-rejection-self-explains): every-failure-explains-what-why-how --
    WHAT (``reason``) and WHY are unchanged; this adds the missing HOW,
    naming the two producing tools that clear assertion 5 (mirrors
    ``carpaccio_slice_gate._MECHANICAL_OR_VERDICT_HOW``, which OVERWRITES
    this ``how`` with the fuller pytest-regression wording via
    ``_with_mechanical_remedy`` -- this default covers every OTHER caller,
    principally the plain Gherkin path that today reaches this function
    unwrapped).
    """
    how = (
        "satisfy assertion 5 by EITHER (a) minting an APPROVED "
        "ATReviewVerdict: `des record-at-review-verdict --feature-id "
        f"<feature-id> --slice-id {slice_id} --verdict APPROVED "
        "--reviewer-agent-id <reviewer-id>`, OR (b) the mechanical pair "
        "(pytest-regression mode only): `des verify-red-green --record-red "
        "--test-file <regression-test-file>` AND `des verify-negative-at "
        "--test-file <regression-test-file> --all-critical`."
    )
    return GateError(
        45,
        {
            "event": "ATReviewGateRejected",
            "slice_id": slice_id,
            "reason": reason,
            "error": f"AT-review gate rejected slice {slice_id}: {reason}",
            "how": how,
        },
    )


def _no_scenarios_rejection(repo: Path, feature_id: str, slice_id: str) -> GateError:
    """Self-describing ``no-scenarios-for-slice`` rejection (fix-feature-tag-
    files-workspace-layout).

    Every-failure-explains-what-why-how (STANDING): the plain
    ``_at_review_rejection`` names only the reason code; on GENUINE absence of
    any matching ``.feature`` file this enriches the payload with WHAT was
    searched (the ``@feature-{feature_id}`` tag), WHERE it looked (the repo
    root, pruning ``EXCLUDED_SEARCH_DIRS``, plus the legacy acceptance dir),
    and HOW to fix it (add/author a matching, correctly-tagged ``.feature``).
    """
    wanted_tag = f"@feature-{feature_id}"
    legacy_dir = _legacy_acceptance_dir(repo, feature_id)
    pruned = ", ".join(sorted(EXCLUDED_SEARCH_DIRS))
    searched_roots = (
        f"repo root {repo} (walked recursively, pruning: {pruned}) and the "
        f"legacy acceptance dir {legacy_dir}"
    )
    pytest_regression_path = (
        "OR, if this slice's ATs are PYTEST tests rather than Gherkin scenarios "
        "-- a bugfix regression test, OR a feature's plain pytest acceptance "
        "tests, which are equally valid here -- enter via the mechanical-seal "
        "route: `--at-kind pytest-regression --regression-test-file <path>`. "
        "The flag is named for the bugfix case but is NOT limited to it: any "
        "pytest AT file sealed with `des verify-red-green --record-red` + "
        "`des verify-negative-at` clears this gate. NOTE: recording an "
        "ATReviewVerdict does NOT open this gate on its own -- the Gherkin scan "
        "above runs first, so a reviewer verdict is an attestation WITHIN the "
        "Gherkin route, not an alternative to it."
    )
    return GateError(
        45,
        {
            "event": "ATReviewGateRejected",
            "slice_id": slice_id,
            "reason": "no-scenarios-for-slice",
            "error": (
                f"AT-review gate rejected slice {slice_id}: no-scenarios-for-slice -- "
                f"searched for a '.feature' file tagged {wanted_tag!r} under "
                f"{searched_roots}, found none tagged with an @{slice_id} scenario. "
                f"To fix: add/author a '.feature' file carrying the file-level tag "
                f"{wanted_tag!r} with a scenario tagged @{slice_id}. "
                f"{pytest_regression_path}"
            ),
            "searched_tag": wanted_tag,
            "searched_roots": searched_roots,
            "instruction": (
                f"add/author a '.feature' file tagged {wanted_tag!r} with a "
                f"scenario tagged @{slice_id}. {pytest_regression_path}"
            ),
        },
    )
