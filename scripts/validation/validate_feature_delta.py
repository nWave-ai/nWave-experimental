"""validate_feature_delta — schema validator for lean feature-delta.md (C14).

Dev/CI-only validator (NOT shipped to end users). Two validation modes:

- **Plain mode** (no flag) — enforces D2 schema-typed section headings: every
  `## Wave: <NAME> / [<TYPE>] <Section>` heading must declare a TYPE token in
  {REF, WHY, HOW}. Non-Wave `##` headings are out of scope.
- **`--require-slice-plan` mode** (slice-06, ADR-028 D2 / D2-bis, ADR-029 D3) —
  additionally asserts the `## Wave: DISCUSS / [REF] Slice Plan` section is
  present and its table carries the five required columns in fixed order. Used
  by the Product Owner at DISCUSS authoring time so a missing or malformed
  slice plan is caught before the feature-delta flows downstream.

CLI contract:
- Plain mode (AC-5.c): exit 0 on a well-formed lean feature-delta.md;
  exit non-zero with an explicit list of malformed headings otherwise.
- `--require-slice-plan --format=json` mode: emit a single JSON object to
  stdout carrying a stable `"verdict"` field whose value is exactly one of the
  closed token set {accepted, missing-slice-plan, malformed-slice-plan,
  malformed-wave-heading}; exit 0 on `accepted`, non-zero on any rejection.

Architecture:
- Pure functional core (`validate_feature_delta_content`,
  `validate_slice_plan_content`) — no I/O.
- Thin CLI shell (`main`) — reads file, calls pure functions, prints, returns
  exit code.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Domain types — pure data carriers
# ---------------------------------------------------------------------------

#: Tokens accepted in the `[<TYPE>]` slot of a Wave heading per D2.
ALLOWED_TYPE_TOKENS: frozenset[str] = frozenset({"REF", "WHY", "HOW"})

#: The five required slice-plan columns, in the D2 fixed order (ADR-028 D2 L137:
#: "Five columns, fixed order"). A re-order violates the fixed-order contract.
SLICE_PLAN_COLUMNS: tuple[str, ...] = (
    "Slice",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)

#: The closed `verdict` token set emitted under --require-slice-plan
#: --format=json. Each token is a STRUCTURED contract — the AT reads the token,
#: never a free-text stdout substring.
VERDICT_ACCEPTED = "accepted"
VERDICT_MISSING_SLICE_PLAN = "missing-slice-plan"
VERDICT_MALFORMED_SLICE_PLAN = "malformed-slice-plan"
VERDICT_MALFORMED_WAVE_HEADING = "malformed-wave-heading"

#: The canonical Reuse Analysis heading (DDD-8 / R1 normative SSOT). Skill
#: template at `nWave/skills/nw-design/SKILL.md` must emit this exact string.
REUSE_ANALYSIS_HEADING = "## Reuse Analysis"

#: The five required Reuse Analysis columns in canonical order (DDD-8 / R1
#: normative SSOT). The skill template must emit these exact column names.
REUSE_ANALYSIS_COLUMNS: tuple[str, ...] = (
    "Existing Component",
    "File",
    "Overlap",
    "Decision",
    "Justification",
)

#: The closed `verdict` token set emitted under --require-reuse-analysis
#: --format=json (DDD-2). Slice-01 shipped the two walking-skeleton verdicts
#: (structurally-accepted, missing-reuse-analysis); slice-02 closes the set
#: with malformed-reuse-analysis (DDD-3/DDD-7/DDD-11), unjustified-create-new
#: (DDD-3), and the two exemption verdicts (methodology-exempt, no-overlap-
#: declared, DDD-9). The full set is the gate's contract; an off-set token
#: would prove the classifier drifted off contract.
VERDICT_STRUCTURALLY_ACCEPTED = "structurally-accepted"
VERDICT_MISSING_REUSE_ANALYSIS = "missing-reuse-analysis"
VERDICT_MALFORMED_REUSE_ANALYSIS = "malformed-reuse-analysis"
VERDICT_UNJUSTIFIED_CREATE_NEW = "unjustified-create-new"
VERDICT_METHODOLOGY_EXEMPT = "methodology-exempt"
VERDICT_NO_OVERLAP_DECLARED = "no-overlap-declared"

#: The two canonical Decision tokens accepted in a Reuse Analysis row (DDD-7).
#: Any other normalized token is `malformed-reuse-analysis`.
_REUSE_DECISION_TOKENS: frozenset[str] = frozenset({"EXTEND", "CREATE_NEW"})

#: Exemption-marker line patterns (DDD-9). A line directly under the canonical
#: `## Reuse Analysis` heading matching one of these is a first-class accepted
#: verdict the gate classifies itself.
_REUSE_MARKER_METHODOLOGY_EXEMPT_RE = re.compile(
    r"^Reuse-Analysis:\s*methodology-exempt\s*$"
)
_REUSE_MARKER_NO_OVERLAP_RE = re.compile(r"^Reuse-Analysis:\s*no-overlap\s*$")

#: Collapse every run of whitespace to a single `_` (DDD-7 normalization step).
_WHITESPACE_RUN_RE = re.compile(r"\s+")

#: Match a Wave-prefixed `##` heading. Captures (wave_name, type_token, tail).
#: Anchored on the schema separator ` / ` so non-conforming headings still
#: parse but flag a violation.
_WAVE_HEADING_RE = re.compile(
    r"^##\s+Wave:\s+(?P<wave>[A-Za-z0-9_\- ]+?)\s*/\s*"
    r"\[(?P<type>[^\]]+)\]\s+(?P<section>.+?)\s*$"
)

#: Match any heading that starts with `## Wave:` — used to detect Wave headings
#: that are malformed AND lack the schema separator entirely.
_WAVE_PREFIX_RE = re.compile(r"^##\s+Wave:\s")

#: Match the canonical slice-plan section heading (ADR-028 D2 L133).
_SLICE_PLAN_HEADING_RE = re.compile(
    r"^##\s+Wave:\s+DISCUSS\s*/\s*\[REF\]\s+Slice\s+Plan\s*$"
)

#: Match the canonical Reuse Analysis heading (DDD-8). Exact-form match;
#: variant headings (wrong level, prefix, suffix) are not accepted.
_REUSE_ANALYSIS_HEADING_RE = re.compile(r"^##\s+Reuse\s+Analysis\s*$")

#: Match any `##` markdown heading (level-2 only, not `###` or deeper).
_H2_RE = re.compile(r"^##\s+(?!#)(?P<text>.+?)\s*$")


class Offender(NamedTuple):
    """A heading that violates the D2 schema."""

    line: int
    heading: str
    reason: str


class ValidationResult(NamedTuple):
    """Outcome of validating one feature-delta.md."""

    is_valid: bool
    offenders: list[Offender]
    wave_section_count: int


class SlicePlanResult(NamedTuple):
    """Outcome of the --require-slice-plan structural slice-plan check.

    `verdict` is one of the closed token set; `detail` is a human-readable
    diagnostic naming the cause (for the JSON payload + plain-text rendering).
    """

    verdict: str
    detail: str


class ReuseAnalysisResult(NamedTuple):
    """Outcome of the --require-reuse-analysis structural Reuse Analysis check.

    `verdict` is one of the closed token set (DDD-2); `detail` is a
    human-readable diagnostic naming the cause (for the JSON payload +
    plain-text rendering). Mirrors `SlicePlanResult` shape per DDD-2.
    """

    verdict: str
    detail: str


# ---------------------------------------------------------------------------
# Pure core — heading-form validation
# ---------------------------------------------------------------------------


def _classify_wave_heading(line_no: int, raw_text: str) -> Offender | None:
    """Validate one Wave heading. Pure.

    Args:
        line_no: 1-based line number for diagnostics.
        raw_text: stripped heading line, including the leading `## `.

    Returns:
        None if the heading conforms to the schema; an Offender otherwise.
    """
    match = _WAVE_HEADING_RE.match(raw_text)
    if match is None:
        return Offender(
            line=line_no,
            heading=raw_text,
            reason=(
                "missing schema prefix; expected "
                "'## Wave: <NAME> / [REF|WHY|HOW] <Section>'"
            ),
        )
    type_token = match.group("type")
    if type_token not in ALLOWED_TYPE_TOKENS:
        return Offender(
            line=line_no,
            heading=raw_text,
            reason=(
                f"invalid type token '[{type_token}]'; "
                f"expected one of {sorted(ALLOWED_TYPE_TOKENS)}"
            ),
        )
    return None


def validate_feature_delta_content(content: str) -> ValidationResult:
    """Validate a feature-delta.md document body. Pure function.

    Walks each line; for every `## Wave:` heading delegates to
    `_classify_wave_heading`. Other H2 headings are ignored (meta sections
    such as `## Expansions requested` are out-of-scope per scope of D2).

    Args:
        content: file body (UTF-8 text).

    Returns:
        ValidationResult with `is_valid` true iff no offenders were found.
    """
    offenders: list[Offender] = []
    wave_count = 0

    for idx, line in enumerate(content.splitlines(), start=1):
        if not _WAVE_PREFIX_RE.match(line):
            continue
        wave_count += 1
        offender = _classify_wave_heading(idx, line.rstrip())
        if offender is not None:
            offenders.append(offender)

    return ValidationResult(
        is_valid=not offenders,
        offenders=offenders,
        wave_section_count=wave_count,
    )


# ---------------------------------------------------------------------------
# Pure core — slice-plan structural validation (slice-06)
# ---------------------------------------------------------------------------


def _parse_table_cells(row: str) -> list[str]:
    """Split a GFM table row into its trimmed cell values. Pure.

    A GFM row is `| a | b | c |`; the leading and trailing pipes produce empty
    edge fields which are dropped.
    """
    parts = [cell.strip() for cell in row.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_separator_row(row: str) -> bool:
    """True if `row` is a GFM table separator (`|---|---|`)."""
    cells = _parse_table_cells(row)
    return bool(cells) and all(
        set(cell) <= {"-", ":"} and "-" in cell for cell in cells
    )


def _slice_plan_table_rows(content: str) -> list[str] | None:
    """Extract the slice-plan table's raw rows. Pure.

    Locates the single `## Wave: DISCUSS / [REF] Slice Plan` heading and
    collects the first GFM table beneath it — non-blank lines starting with
    `|`, taken until the first blank line or next `##` heading.

    Returns:
        The list of raw table rows (header, separator, then slice rows), or
        None when the slice-plan heading is absent.
    """
    lines = content.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if _SLICE_PLAN_HEADING_RE.match(line.rstrip()):
            start = idx + 1
            break
    if start is None:
        return None

    rows: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if not stripped:
            if rows:
                break
            continue
        if stripped.startswith("|"):
            rows.append(stripped)
        elif rows:
            break
    return rows


def validate_slice_plan_content(content: str) -> SlicePlanResult:
    """Structurally validate the slice-plan section. Pure function.

    Runs the heading-form check first (a malformed wave heading anywhere is
    reported as `malformed-wave-heading` regardless of slice-plan shape), then
    the slice-plan structural check:

    - section absent                        -> missing-slice-plan
    - table column header not the D2 fixed   -> malformed-slice-plan
      five columns (wrong count or reordered)
    - header + separator but zero slice rows -> malformed-slice-plan
    - well-formed five-column table, >=1 row -> accepted

    Args:
        content: feature-delta.md body (UTF-8 text).

    Returns:
        SlicePlanResult carrying the closed-set verdict token + a diagnostic.
    """
    heading_result = validate_feature_delta_content(content)
    if not heading_result.is_valid:
        first = heading_result.offenders[0]
        return SlicePlanResult(
            verdict=VERDICT_MALFORMED_WAVE_HEADING,
            detail=(
                f"malformed wave heading at line {first.line}: "
                f"{first.heading} - {first.reason}"
            ),
        )

    rows = _slice_plan_table_rows(content)
    if rows is None:
        return SlicePlanResult(
            verdict=VERDICT_MISSING_SLICE_PLAN,
            detail=(
                "no '## Wave: DISCUSS / [REF] Slice Plan' section found (ADR-028 D2)"
            ),
        )

    header_cells = _parse_table_cells(rows[0]) if rows else []
    if tuple(header_cells) != SLICE_PLAN_COLUMNS:
        return SlicePlanResult(
            verdict=VERDICT_MALFORMED_SLICE_PLAN,
            detail=(
                f"slice-plan table columns {header_cells} do not match the "
                f"D2 fixed five-column header {list(SLICE_PLAN_COLUMNS)}"
            ),
        )

    slice_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    if not slice_rows:
        return SlicePlanResult(
            verdict=VERDICT_MALFORMED_SLICE_PLAN,
            detail="slice-plan table has its header but zero slice rows",
        )

    return SlicePlanResult(
        verdict=VERDICT_ACCEPTED,
        detail=f"slice plan is well formed; {len(slice_rows)} slice rows",
    )


# ---------------------------------------------------------------------------
# Pure core — Reuse Analysis structural validation (slice-01)
# ---------------------------------------------------------------------------


def _reuse_analysis_heading_indices(content: str) -> list[int]:
    """Return the line indices of every canonical `## Reuse Analysis` heading.

    Pure. A second occurrence is the DDD-11 duplicate-heading violation.
    """
    return [
        idx
        for idx, line in enumerate(content.splitlines())
        if _REUSE_ANALYSIS_HEADING_RE.match(line.rstrip())
    ]


def _reuse_analysis_table_rows(content: str) -> list[str] | None:
    """Extract the Reuse Analysis table's raw rows. Pure.

    Locates the canonical `## Reuse Analysis` heading and collects the first
    GFM table beneath it — non-blank lines starting with `|`, taken until the
    first blank line or next `##` heading.

    Returns:
        The list of raw table rows (header, separator, then component rows),
        or None when the Reuse Analysis heading is absent.
    """
    indices = _reuse_analysis_heading_indices(content)
    if not indices:
        return None
    lines = content.splitlines()
    start = indices[0] + 1

    rows: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if not stripped:
            if rows:
                break
            continue
        if stripped.startswith("|"):
            rows.append(stripped)
        elif rows:
            break
    return rows


def _reuse_section_body_lines(content: str) -> list[str]:
    """Return the non-blank, non-`|` lines under the first Reuse Analysis
    heading until the next `##` heading. Pure.

    These are the candidate exemption-marker lines (DDD-9). The body stops at
    the first table line, the first blank-after-content boundary, or the next
    `##` heading.
    """
    indices = _reuse_analysis_heading_indices(content)
    if not indices:
        return []
    lines = content.splitlines()
    body: list[str] = []
    for line in lines[indices[0] + 1 :]:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if stripped.startswith("|"):
            break
        if stripped:
            body.append(stripped)
    return body


def _normalise_decision_token(raw_cell: str) -> str:
    """Normalise a Decision cell per DDD-7. Pure.

    strip `**bold**` markers (DDD-11) -> strip whitespace -> upper-case ->
    collapse every run of internal whitespace to a single `_`. Returns the
    normalised token; an empty cell normalises to the empty string.
    """
    unbolded = raw_cell.strip()
    if unbolded.startswith("**") and unbolded.endswith("**") and len(unbolded) >= 4:
        unbolded = unbolded[2:-2]
    return _WHITESPACE_RUN_RE.sub("_", unbolded.strip().upper())


def _classify_component_row(
    row_no: int, cells: list[str]
) -> ReuseAnalysisResult | None:
    """Classify a single component row. Pure.

    Returns a rejection verdict on the first defect found, or None when the
    row is well formed (Decision in {EXTEND, CREATE_NEW}, with non-empty
    Justification on CREATE_NEW).
    """
    if len(cells) < len(REUSE_ANALYSIS_COLUMNS):
        return ReuseAnalysisResult(
            verdict=VERDICT_MALFORMED_REUSE_ANALYSIS,
            detail=(
                f"row {row_no} has {len(cells)} cells; expected "
                f"{len(REUSE_ANALYSIS_COLUMNS)} ({list(REUSE_ANALYSIS_COLUMNS)})"
            ),
        )
    decision = _normalise_decision_token(cells[3])
    if decision not in _REUSE_DECISION_TOKENS:
        return ReuseAnalysisResult(
            verdict=VERDICT_MALFORMED_REUSE_ANALYSIS,
            detail=(
                f"row {row_no} Decision {cells[3]!r} does not normalise into "
                f"{sorted(_REUSE_DECISION_TOKENS)} (DDD-7)"
            ),
        )
    if decision == "CREATE_NEW" and not cells[4].strip():
        return ReuseAnalysisResult(
            verdict=VERDICT_UNJUSTIFIED_CREATE_NEW,
            detail=(f"row {row_no} is CREATE_NEW with an empty Justification (DDD-3)"),
        )
    return None


def _classify_exemption_marker(content: str) -> ReuseAnalysisResult | None:
    """Detect a DDD-9 exemption marker under the canonical heading. Pure.

    Returns the methodology-exempt or no-overlap-declared verdict when the
    corresponding marker is present; None otherwise.
    """
    for line in _reuse_section_body_lines(content):
        if _REUSE_MARKER_METHODOLOGY_EXEMPT_RE.match(line):
            return ReuseAnalysisResult(
                verdict=VERDICT_METHODOLOGY_EXEMPT,
                detail="Reuse-Analysis: methodology-exempt marker present (DDD-9)",
            )
        if _REUSE_MARKER_NO_OVERLAP_RE.match(line):
            return ReuseAnalysisResult(
                verdict=VERDICT_NO_OVERLAP_DECLARED,
                detail="Reuse-Analysis: no-overlap marker present (DDD-9)",
            )
    return None


def validate_reuse_analysis_content(content: str) -> ReuseAnalysisResult:
    """Structurally validate the Reuse Analysis section. Pure function.

    Closes the DDD-2 verdict set:

    - no `## Reuse Analysis` heading + no exemption marker -> missing-reuse-
      analysis;
    - exemption marker under the heading -> methodology-exempt /
      no-overlap-declared (DDD-9, accepted);
    - duplicate `## Reuse Analysis` heading -> malformed-reuse-analysis
      (DDD-11);
    - table column header not the canonical five columns -> malformed-reuse-
      analysis (DDD-8);
    - any component row with Decision not in {EXTEND, CREATE_NEW} after DDD-7
      normalization -> malformed-reuse-analysis;
    - any CREATE_NEW row with an empty Justification -> unjustified-create-new
      (DDD-3);
    - all component rows well formed -> structurally-accepted (DDD-3 — NOT a
      claim that reuse-first was honoured; only that the table is well
      formed).

    Args:
        content: feature-delta.md body (UTF-8 text).

    Returns:
        ReuseAnalysisResult carrying the closed-set verdict token + a
        diagnostic.
    """
    heading_indices = _reuse_analysis_heading_indices(content)
    if len(heading_indices) > 1:
        return ReuseAnalysisResult(
            verdict=VERDICT_MALFORMED_REUSE_ANALYSIS,
            detail=(
                f"duplicate '## Reuse Analysis' heading at lines "
                f"{[idx + 1 for idx in heading_indices]} (DDD-11)"
            ),
        )

    marker_result = _classify_exemption_marker(content)
    if marker_result is not None:
        return marker_result

    rows = _reuse_analysis_table_rows(content)
    if rows is None:
        return ReuseAnalysisResult(
            verdict=VERDICT_MISSING_REUSE_ANALYSIS,
            detail=(
                "no '## Reuse Analysis' section found "
                "(DDD-8 / nw-design SKILL.md step 5)"
            ),
        )

    header_cells = _parse_table_cells(rows[0]) if rows else []
    if tuple(header_cells) != REUSE_ANALYSIS_COLUMNS:
        return ReuseAnalysisResult(
            verdict=VERDICT_MALFORMED_REUSE_ANALYSIS,
            detail=(
                f"Reuse Analysis table columns {header_cells} do not match the "
                f"canonical five-column header {list(REUSE_ANALYSIS_COLUMNS)} "
                f"(DDD-8)"
            ),
        )

    component_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    if not component_rows:
        return ReuseAnalysisResult(
            verdict=VERDICT_MISSING_REUSE_ANALYSIS,
            detail="Reuse Analysis section has its header but zero component rows",
        )

    for row_no, row in enumerate(component_rows, start=1):
        rejection = _classify_component_row(row_no, _parse_table_cells(row))
        if rejection is not None:
            return rejection

    return ReuseAnalysisResult(
        verdict=VERDICT_STRUCTURALLY_ACCEPTED,
        detail=(
            f"Reuse Analysis is structurally accepted; "
            f"{len(component_rows)} component rows"
        ),
    )


# ---------------------------------------------------------------------------
# Thin CLI shell — only side effect boundary
# ---------------------------------------------------------------------------


def _format_success(result: ValidationResult) -> str:
    return f"Feature delta is valid. {result.wave_section_count} wave sections checked."


def _format_failure(result: ValidationResult) -> str:
    lines = [f"Feature delta has {len(result.offenders)} malformed headings:"]
    for offender in result.offenders:
        lines.append(f"  line {offender.line}: {offender.heading} - {offender.reason}")
    return "\n".join(lines)


def validate_feature_delta(file_path: Path) -> ValidationResult:
    """Read `file_path` and validate its content. Thin I/O wrapper.

    Args:
        file_path: Path to a feature-delta.md file.

    Returns:
        ValidationResult.
    """
    content = file_path.read_text(encoding="utf-8")
    return validate_feature_delta_content(content)


_USAGE = (
    "usage: validate_feature_delta.py "
    "[--require-slice-plan] [--require-reuse-analysis] [--format=json] "
    "<path-to-feature-delta.md>"
)


class _ParsedArgs(NamedTuple):
    """Parsed CLI arguments."""

    path: str
    require_slice_plan: bool
    require_reuse_analysis: bool
    json_format: bool


def _parse_args(args: list[str]) -> _ParsedArgs | None:
    """Parse the CLI argument list. Returns None on malformed invocation.

    Accepts the optional flags `--require-slice-plan`, `--require-reuse-analysis`,
    and `--format=json` in any order, plus exactly one positional path
    argument. The plain-mode contract (a lone path argument) is preserved.
    """
    require_slice_plan = False
    require_reuse_analysis = False
    json_format = False
    positionals: list[str] = []
    for arg in args:
        if arg == "--require-slice-plan":
            require_slice_plan = True
        elif arg == "--require-reuse-analysis":
            require_reuse_analysis = True
        elif arg == "--format=json":
            json_format = True
        elif arg.startswith("-"):
            return None
        else:
            positionals.append(arg)
    if len(positionals) != 1:
        return None
    return _ParsedArgs(
        path=positionals[0],
        require_slice_plan=require_slice_plan,
        require_reuse_analysis=require_reuse_analysis,
        json_format=json_format,
    )


def _run_plain(target: Path) -> int:
    """Run the heading-form-only check. Plain-text output, exit 0/1."""
    result = validate_feature_delta(target)
    if result.is_valid:
        print(_format_success(result))
        return 0
    print(_format_failure(result))
    return 1


def _run_require_slice_plan(target: Path, json_format: bool) -> int:
    """Run the structural slice-plan check (slice-06).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on `accepted`, 1 on rejection.
    """
    content = target.read_text(encoding="utf-8")
    result = validate_slice_plan_content(content)
    if json_format:
        print(json.dumps({"verdict": result.verdict, "detail": result.detail}))
    else:
        print(f"{result.verdict}: {result.detail}")
    return 0 if result.verdict == VERDICT_ACCEPTED else 1


def _run_require_reuse_analysis(target: Path, json_format: bool) -> int:
    """Run the structural Reuse Analysis check (F-DESIGN-REUSE-FIRST-GATE).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on `structurally-accepted`,
    1 on rejection. Mirrors `_run_require_slice_plan` per DDD-1.
    """
    content = target.read_text(encoding="utf-8")
    result = validate_reuse_analysis_content(content)
    if json_format:
        print(json.dumps({"verdict": result.verdict, "detail": result.detail}))
    else:
        print(f"{result.verdict}: {result.detail}")
    return 0 if result.verdict == VERDICT_STRUCTURALLY_ACCEPTED else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `validate_feature_delta.py [flags] <path-to-feature-delta.md>`.

    Args:
        argv: optional argument list (defaults to `sys.argv[1:]`).

    Returns:
        0 on success, 1 on any malformed heading / malformed slice plan /
        malformed reuse analysis / I/O error.
    """
    args = sys.argv[1:] if argv is None else argv
    parsed = _parse_args(args)
    if parsed is None:
        print(_USAGE, file=sys.stderr)
        return 1

    target = Path(parsed.path)
    if not target.is_file():
        print(f"error: {target} is not a file", file=sys.stderr)
        return 1

    if parsed.require_slice_plan:
        return _run_require_slice_plan(target, parsed.json_format)
    if parsed.require_reuse_analysis:
        return _run_require_reuse_analysis(target, parsed.json_format)
    return _run_plain(target)


if __name__ == "__main__":
    raise SystemExit(main())
