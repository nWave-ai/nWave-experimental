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
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.application.feature_at_files import (
    EXCLUDED_SEARCH_DIRS,
    _legacy_acceptance_dir,
)
from des.application.feature_at_files import (
    feature_tag_files as _feature_tag_files,
)
from des.domain.lane_profile import LANE_PROFILES, AtRequirement, LaneProfile


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal


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
    r"^#{2,4}\s+Wave:\s+DISCUSS\s+/\s+\[REF\]\s+Slice Plan\s*$"
)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SLICE_ID_RE = re.compile(
    r"^slice-\d+(?:[a-z])?$"
)  # canonical + letter-suffix (friction #10)
# The tag extractor MUST accept the SAME grammar the validator above accepts
# (sister Tsunami Q-31, 2026-06-26): a `slice-05b` id is validator-VALID, but the
# old `@(slice-\d+)\b` failed to extract `@slice-05b` (the `\b` between `\d` and a
# letter is no boundary -> the whole match fails) -> the gate emitted a SILENT
# `no-scenarios-for-slice` on a valid id. The `(?:[a-z])?` mirrors the validator so
# the two grammars agree; `@slice-01` (digit-only) is unaffected.
_SLICE_TAG_RE = re.compile(r"@(slice-\d+(?:[a-z])?)\b")
_COUPLED_TAG_RE = re.compile(r"@coupled\b")
_WALKING_SKELETON_RE = re.compile(r"@walking-skeleton|@walking_skeleton")
_ANNOTATION_ESCAPE_RE = re.compile(
    r"@coupled|@walking-skeleton|@walking_skeleton|@infrastructure|@prefactoring"
)
_PREFACTORING_TAG_RE = re.compile(r"@prefactoring\b")


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
    * column count -- the slice-id is the cell matching ``slice-NN`` and the
      value is the next cell, with any further columns (status, annotation,
      justification) read positionally and extras ignored. A 3-column plan and
      a 5-column plan both parse.

    Raises ``GateError`` exit 1 when the section heading is absent, exit 2 when
    the table is malformed (no data rows, no row carrying a ``slice-NN`` id,
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
    return _build_slice_rows(table_rows[2:])


def parse_slice_plan(feature_delta_text: str) -> SlicePlan:
    """Parse the ``[REF] Slice Plan`` table out of a feature-delta.

    Thin wrapper over the shared tolerant :func:`parse_slice_plan_rows` that
    boxes the rows into a :class:`SlicePlan`.
    """
    return SlicePlan(rows=tuple(parse_slice_plan_rows(feature_delta_text)))


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


def _build_slice_rows(data_rows: list[str]) -> list[SlicePlanRow]:
    """Build slice rows from the table data rows, column-count-tolerant (exit 2).

    Column-tolerant: the slice-id is the first cell matching ``slice-NN`` and
    the value / status / annotation / justification are read positionally from
    the cells that follow it; any cell beyond the fifth is ignored, and a
    3-column plan simply leaves annotation + justification empty. This unifies
    the former 3-column (hook) and 5-column (CLI) contracts into one parse.
    """
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
        rows.append(
            SlicePlanRow(
                slice_id=slice_id,
                value_statement=_cell_at(cells, slice_index + 1),
                status=_cell_at(cells, slice_index + 2),
                annotation=_cell_at(cells, slice_index + 3),
                justification=_cell_at(cells, slice_index + 4),
            )
        )
    if not rows:
        raise _malformed_table("the slice-plan table has no slice rows")
    return rows


def _cell_at(cells: list[str], index: int) -> str:
    """Return ``cells[index]`` or the empty string when the column is absent."""
    return cells[index] if index < len(cells) else ""


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


# ---------------------------------------------------------------------------
# pytest-regression AT-discovery mode (ADR-001, fix-pre-push-hook-dual-
# installer-collision) -- the pytest-native mirror of "one Gherkin Scenario
# = one AT", for a bugfix's plain-pytest regression test file.
# ---------------------------------------------------------------------------


def count_pytest_regression_ats(regression_test_file: Path) -> int:
    """AT count for ``at_kind="pytest-regression"`` (ADR-001, this feature).

    AST-counts module-level (never class-nested) ``def test_*`` / ``async def
    test_*`` function definitions in ``regression_test_file`` -- the pytest-
    native mirror of "one Gherkin ``Scenario:`` = one AT". Three exclusions
    are CLOSED (ADR-001):

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
    count = sum(
        1
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
        and not _has_fixture_decorator(node)
    )
    if count == 0:
        raise _malformed_regression_file(
            f"zero test_* functions found at module level in {regression_test_file}"
        )
    return count


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
    at_kind: Literal["gherkin", "pytest-regression"] = "gherkin",
    regression_test_file: Path | None = None,
    *,
    repo: Path | None = None,
    feature_id: str | None = None,
) -> dict[str, object] | None:
    """Run carpaccio assertions 1-4 (+ mixed-mode guard). Raises ``GateError``.

    ``repo`` + ``feature_id`` (fix-feature-tag-files-workspace-layout,
    keyword-only, optional): when both are given, a ``no-scenarios-for-slice``
    rejection is enriched with WHAT was searched (the ``@feature-{feature_id}``
    tag), WHERE (the roots walked), and HOW to fix it -- see
    :func:`_no_scenarios_rejection`. When either is omitted, the plain
    :func:`_at_review_rejection` fires unchanged (byte-identical legacy path).

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
    if at_kind == "pytest-regression" and regression_test_file is None:
        raise ValueError(
            "check_carpaccio: at_kind='pytest-regression' requires regression_test_file"
        )
    if at_kind == "pytest-regression" and scenarios:
        # Mixed-mode guard (ADR-001 HIGH-3): the caller always parses
        # `scenarios` from `_feature_tag_files(repo, feature_id)`, so a
        # non-empty list here IS "the feature owns .feature files" -- the two
        # AT-discovery modes are mutually exclusive by enforcement, never a
        # silent precedence rule.
        raise GateError(
            2,
            {
                "event": "MalformedInput",
                "cause": "mixed AT-discovery mode",
                "error": (
                    "at_kind='pytest-regression' but the feature also owns "
                    ".feature scenarios; the two AT-discovery modes are "
                    "mutually exclusive"
                ),
            },
        )
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
    if at_kind == "pytest-regression":
        assert regression_test_file is not None  # guarded above
        at_count = count_pytest_regression_ats(regression_test_file)
        _check_walking_skeleton_first(plan)
        _check_value_annotation(plan)
        return _check_slice_size_count(
            plan, entering_slice, slice_max, at_count, all_coupled=False
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
    return _check_slice_size(plan, scenarios, entering_slice, slice_max)


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
    """Assertion 1 (gherkin mode): slice size <= N unless a coupled-AT-group
    escape applies.

    The only size escape (ADR-028 D2) is a coupled AT group: every scenario
    in the slice carries a ``@coupled`` tag AND the plan row records a
    coupling justification. A plain ``@walking-skeleton`` / ``@infrastructure``
    annotation does NOT lift the size ceiling -- it governs ordering and the
    value-annotation check, not slice size.
    """
    slice_scenarios = _slice_scenarios(scenarios, entering_slice)
    at_count = len(slice_scenarios)
    all_coupled = bool(slice_scenarios) and all(
        s.has_coupled_tag for s in slice_scenarios
    )
    return _check_slice_size_count(
        plan, entering_slice, slice_max, at_count, all_coupled
    )


def _check_slice_size_count(
    plan: SlicePlan,
    entering_slice: str,
    slice_max: int,
    at_count: int,
    all_coupled: bool,
) -> dict[str, object] | None:
    """Assertion 1 core: slice size <= N unless a coupled-AT-group escape applies.

    Shared by both ``at_kind`` modes (ADR-001, fix-pre-push-hook-dual-
    installer-collision): gherkin mode (``_check_slice_size``) computes
    ``at_count`` / ``all_coupled`` from ``.feature`` scenarios;
    pytest-regression mode (``check_carpaccio``) passes the AST-counted AT
    count and ``all_coupled=False`` -- no ``@coupled``-tag vocabulary exists
    for a plain pytest regression file in this ADR's scope.
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
                f"{wanted_tag!r} with a scenario tagged @{slice_id}."
            ),
            "searched_tag": wanted_tag,
            "searched_roots": searched_roots,
            "instruction": (
                f"add/author a '.feature' file tagged {wanted_tag!r} with a "
                f"scenario tagged @{slice_id}"
            ),
        },
    )
