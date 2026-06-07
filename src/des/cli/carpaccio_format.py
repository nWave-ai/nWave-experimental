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
circular import. The gate RETAINS its assertion-5 HMAC review logic, ``main()``,
and ``_emit``; those depend on the shared helpers ``_at_review_rejection`` and
``_slice_scenarios`` which therefore live here (peer-review LOW, 2026-05-29:
both helpers cross the moved/retained boundary so they MOVE into this module and
the gate imports them).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.application.feature_at_files import (
    _legacy_acceptance_dir,
)
from des.application.feature_at_files import (
    feature_tag_files as _feature_tag_files,
)


if TYPE_CHECKING:
    from pathlib import Path


# ``_legacy_acceptance_dir`` and ``_feature_tag_files`` are re-exported from the
# application layer (AD-05 layering fix) for ``carpaccio_precheck`` /
# ``carpaccio_slice_gate``; ``__all__`` marks them as intentional re-exports so
# autoflake does not drop the otherwise-internally-unused legacy resolver.
__all__ = [
    "_feature_tag_files",
    "_legacy_acceptance_dir",
]


# Default carpaccio slice-size ceiling when .nwave/config.yaml omits it.
_DEFAULT_SLICE_MAX = 3

_SLICE_PLAN_HEADING_RE = re.compile(
    r"^##\s+Wave:\s+DISCUSS\s+/\s+\[REF\]\s+Slice Plan\s*$"
)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SLICE_ID_RE = re.compile(
    r"^slice-\d+(?:[a-z])?$"
)  # canonical + letter-suffix (friction #10)
_SLICE_TAG_RE = re.compile(r"@(slice-\d+)\b")
_COUPLED_TAG_RE = re.compile(r"@coupled\b")
_WALKING_SKELETON_RE = re.compile(r"@walking-skeleton|@walking_skeleton")
_ANNOTATION_ESCAPE_RE = re.compile(
    r"@coupled|@walking-skeleton|@walking_skeleton|@infrastructure"
)


class GateError(Exception):
    """A gate verdict carrying a non-zero exit code and a JSON payload.

    Raised by the parse/assertion helpers and caught by ``main`` so each
    failure path emits exactly one single-line JSON object before exiting.
    """

    def __init__(self, exit_code: int, payload: dict[str, object]) -> None:
        super().__init__(payload.get("error", payload.get("event", "gate error")))
        self.exit_code = exit_code
        self.payload = payload


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
    """The parsed ``[REF] Slice Plan`` table -- ordered slice rows."""

    rows: tuple[SlicePlanRow, ...]

    def row_for(self, slice_id: str) -> SlicePlanRow | None:
        for row in self.rows:
            if row.slice_id == slice_id:
                return row
        return None


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


def _config_slice_max(repo: Path) -> int:
    """Read ``atdd_pure.carpaccio_slice_max`` from ``.nwave/config.yaml``.

    F-11: as a shipped ``des.cli`` module the gate MUST be stdlib-only -- the
    DES bundle scan (`tests/build/.../milestone-2-des-bundle.feature`) forbids
    ``import yaml`` in any bundled ``des`` module. ``.nwave/config.yaml`` carries
    the single ``atdd_pure.carpaccio_slice_max`` integer under a two-level
    block-mapping; a stdlib line-scan reads it without a YAML dependency,
    preserving the prior semantics (default + positive-int guard) exactly.
    """
    config_path = repo / ".nwave" / "config.yaml"
    if not config_path.is_file():
        return _DEFAULT_SLICE_MAX
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_SLICE_MAX
    value = _scan_atdd_pure_int(text, "carpaccio_slice_max")
    if isinstance(value, int) and value > 0:
        return value
    return _DEFAULT_SLICE_MAX


def _scan_atdd_pure_int(text: str, key: str) -> int | None:
    """Stdlib scan for an integer ``atdd_pure.<key>`` value in a YAML config.

    Reads the two-level block-mapping shape ``.nwave/config.yaml`` carries::

        atdd_pure:
          carpaccio_slice_max: 3

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


def _split_table_cells(line: str) -> list[str]:
    """Split a GFM table row into trimmed cells, dropping the outer pipes."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_slice_plan(feature_delta_text: str) -> SlicePlan:
    """Parse the ``[REF] Slice Plan`` table out of a feature-delta.

    Raises ``GateError`` exit 1 when the section heading is absent, exit 2
    when the table is malformed (wrong column count, bad slice identifier,
    duplicate slice id).
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
    return _build_slice_plan(table_rows[2:])


def _collect_table_rows(lines: list[str], start: int) -> list[str]:
    """Collect the contiguous GFM table block after the section heading."""
    rows: list[str] = []
    started = False
    for line in lines[start:]:
        if _TABLE_ROW_RE.match(line):
            started = True
            rows.append(line)
            continue
        if started:
            break
    return rows


def _build_slice_plan(data_rows: list[str]) -> SlicePlan:
    """Validate + build slice rows from the table data rows (exit 2 on error)."""
    rows: list[SlicePlanRow] = []
    seen: set[str] = set()
    for raw in data_rows:
        cells = _split_table_cells(raw)
        if len(cells) != 5:
            raise _malformed_table(
                f"slice-plan row must have 5 columns, found {len(cells)}: {raw!r}"
            )
        slice_id = cells[0]
        if not _SLICE_ID_RE.match(slice_id):
            raise _malformed_table(
                f"slice-plan row identifier must match 'slice-NN': {slice_id!r}"
            )
        if slice_id in seen:
            raise _malformed_table(f"duplicate slice id in slice plan: {slice_id!r}")
        seen.add(slice_id)
        rows.append(
            SlicePlanRow(
                slice_id=slice_id,
                value_statement=cells[1],
                status=cells[2],
                annotation=cells[3],
                justification=cells[4],
            )
        )
    if not rows:
        raise _malformed_table("the slice-plan table has no slice rows")
    return SlicePlan(rows=tuple(rows))


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


# ---------------------------------------------------------------------------
# .feature scenario parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One parsed ``.feature`` scenario: its slice tags + its normalized body."""

    slice_tags: tuple[str, ...]
    has_coupled_tag: bool
    normalized_body: str


def _read_feature_files(repo: Path, feature_id: str) -> list[str]:
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
) -> dict[str, object] | None:
    """Run carpaccio assertions 1-4. Raises ``GateError`` on a violation.

    Returns a non-None dict only to surface the ``CoupledSliceAccepted``
    event when an over-N coupled slice with a justification is accepted.
    """
    if plan.row_for(entering_slice) is None:
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
    _check_total_coverage(plan, scenarios)
    if not _slice_scenarios(scenarios, entering_slice):
        raise _at_review_rejection("no-scenarios-for-slice", entering_slice)
    _check_walking_skeleton_first(plan)
    _check_value_annotation(plan)
    return _check_slice_size(plan, scenarios, entering_slice, slice_max)


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
    """Assertion 3: a @walking-skeleton slice must be the first plan row."""
    ws_index = next(
        (
            i
            for i, row in enumerate(plan.rows)
            if _WALKING_SKELETON_RE.search(row.annotation)
        ),
        None,
    )
    if ws_index is not None and ws_index != 0:
        raise GateError(
            44,
            {
                "event": "CARPACCIO_SLICE_TOO_LARGE",
                "error": (
                    "the @walking-skeleton slice is not ordered first "
                    f"(found at row {ws_index + 1})"
                ),
                "instruction": "order the @walking-skeleton slice first in the plan",
            },
        )


def _check_value_annotation(plan: SlicePlan) -> None:
    """Assertion 4: an annotated escape row must record a justification."""
    for row in plan.rows:
        if _ANNOTATION_ESCAPE_RE.search(row.annotation) and not row.justification:
            raise GateError(
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


def _check_slice_size(
    plan: SlicePlan,
    scenarios: list[Scenario],
    entering_slice: str,
    slice_max: int,
) -> dict[str, object] | None:
    """Assertion 1: slice size <= N unless a coupled-AT-group escape applies.

    The only size escape (ADR-028 D2) is a coupled AT group: every scenario
    in the slice carries a ``@coupled`` tag AND the plan row records a
    coupling justification. A plain ``@walking-skeleton`` / ``@infrastructure``
    annotation does NOT lift the size ceiling -- it governs ordering and the
    value-annotation check, not slice size.
    """
    slice_scenarios = _slice_scenarios(scenarios, entering_slice)
    at_count = len(slice_scenarios)
    if at_count <= slice_max:
        return None
    row = plan.row_for(entering_slice)
    assert row is not None  # guaranteed by check_carpaccio precondition
    all_coupled = bool(slice_scenarios) and all(
        s.has_coupled_tag for s in slice_scenarios
    )
    if all_coupled and row.justification:
        return {
            "event": "CoupledSliceAccepted",
            "slice_id": entering_slice,
            "at_count": at_count,
        }
    raise GateError(
        44,
        {
            "event": "CARPACCIO_SLICE_TOO_LARGE",
            "slice_id": entering_slice,
            "at_count": at_count,
            "slice_max": slice_max,
            "error": (
                f"slice {entering_slice} has {at_count} ATs, exceeding the "
                f"carpaccio ceiling of {slice_max}"
            ),
            "instruction": (
                "re-slice into thinner end-to-end verticals each within the "
                f"ceiling of {slice_max}, or annotate the slice as @coupled / "
                "@walking-skeleton / @infrastructure with a recorded justification"
            ),
        },
    )


# ---------------------------------------------------------------------------
# Shared AT-review helper (crosses the moved/retained boundary -- ADR-001)
# ---------------------------------------------------------------------------


def _at_review_rejection(reason: str, slice_id: str) -> GateError:
    return GateError(
        45,
        {
            "event": "ATReviewGateRejected",
            "slice_id": slice_id,
            "reason": reason,
            "error": f"AT-review gate rejected slice {slice_id}: {reason}",
        },
    )
