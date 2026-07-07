"""validate_feature_delta — schema validator for lean feature-delta.md (C14).

A nWave runtime gate, dispatched as ``des validate-feature-delta`` (registered
in ``des.cli.__main__``). It ships in the DES bundle (under ``src/des/``) so it
runs on target machines as well as in dev/CI. Two validation modes:

- **Plain mode** (no flag) — enforces D2 schema-typed section headings: every
  `## Wave: <NAME> / [<TYPE>] <Section>` heading must declare a TYPE token in
  {REF, WHY, HOW}. Non-Wave `##` headings are out of scope.
- **`--require-slice-plan` mode** (slice-06, ADR-028 D2 / D2-bis, ADR-029 D3) —
  additionally asserts the `## Wave: DISCUSS / [REF] Slice Plan` section is
  present and its table carries the five required columns in fixed order. Used
  by the Product Owner at DISCUSS authoring time so a missing or malformed
  slice plan is caught before the feature-delta flows downstream.
- **`--require-feature-plan` mode** (discuss-epic-mode slice-01, R1) — the same
  structural check at epic granularity: asserts the
  `## Wave: DISCUSS / [REF] Feature Plan` section of an epic-delta is present and
  its table carries the five required columns (Feature, Value statement, Status,
  Annotation, Justification) in fixed order. Shares the generic plan core with
  the slice-plan mode via `_PlanSpec` (parametrizes (heading, columns, verdict
  tokens, nouns); never forks).

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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple, get_args

from des.domain.gate_outcome import GateVerdict
from des.domain.telemetry.documentation_density_event import WaveName


if TYPE_CHECKING:
    from des.domain.sustainability_metrics import GitDiffUnavailable, TestLocDelta


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

#: The five required Feature Plan columns, in the D2 fixed order reused verbatim
#: at feature granularity (discuss-epic-mode R1 — the Feature Plan grammar IS D2).
#: A dropped column or a re-order violates the fixed-order contract.
FEATURE_PLAN_COLUMNS: tuple[str, ...] = (
    "Feature",
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
#: slice-06 cohesion-MECC (nwave-flow-v2-enforcement): the structurally-certain
#: floor — a slice plan whose EVERY data row is annotated `@infrastructure`
#: carries no user-visible value and is vetoed. Non-zero exit flows through the
#: existing CLI shell (exit 0 iff `accepted`).
VERDICT_REJECTED_INFRA_ONLY = "rejected-infra-only"

#: The two NEW closed `verdict` tokens emitted under --require-feature-plan
#: --format=json (discuss-epic-mode slice-01). The verdict must name WHICH plan
#: contract failed; `accepted`, `malformed-wave-heading`, and
#: `rejected-infra-only` are REUSED verbatim across both plan modes. The
#: feature-plan-mode closed set (5) is: accepted · malformed-wave-heading ·
#: missing-feature-plan · malformed-feature-plan · rejected-infra-only.
VERDICT_MISSING_FEATURE_PLAN = "missing-feature-plan"
VERDICT_MALFORMED_FEATURE_PLAN = "malformed-feature-plan"

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

#: content-grounding verdict (F-fix-reuse-analysis-content-grounding, WS-9):
#: a well-formed row whose `Existing Component | File` citation is NOT
#: resolvable through the CodeFactPort chain (Tsunami-first, AST/textsearch
#: fallback, degrade-LOUD -- ADR-LA-001). Closes the phantom-citation gap: a
#: shape-only pass previously accepted a component name absent from its cited
#: file.
VERDICT_UNGROUNDED_REUSE_ANALYSIS = "ungrounded-reuse-analysis"

#: The two canonical Decision tokens accepted in a Reuse Analysis row (DDD-7).
#: Any other normalized token is `malformed-reuse-analysis`.
_REUSE_DECISION_TOKENS: frozenset[str] = frozenset({"EXTEND", "CREATE_NEW"})

#: The canonical Test Reuse & Consolidation Analysis heading (sustainable-test-suite
#: DDD-3, mirror of `## Reuse Analysis`). The DISTILL section author writes this exact
#: bare H2 heading; the slice-03 content gate parses the table beneath it.
SUSTAINABILITY_HEADING = "## Test Reuse & Consolidation Analysis"

#: The five required Test Reuse & Consolidation Analysis columns in canonical order
#: (sustainable-test-suite DDD-3, mirror of REUSE_ANALYSIS_COLUMNS). Byte-identical to
#: the slice-02/slice-03 step-side CANONICAL_SECTION_COLUMNS.
SUSTAINABILITY_COLUMNS: tuple[str, ...] = (
    "Existing Test/DSL-Step",
    "File",
    "Overlap",
    "Decision",
    "Justification",
)

#: The closed `verdict` token set emitted under --require-sustainability --format=json
#: (sustainable-test-suite DDD-2, git-free subset). Mirrors the Reuse Analysis closed
#: set widened with the sustainability decision vocabulary + the DDD-9 `no-new-tests`
#: sibling exemption. `blind-add-detected` is DELIBERATELY EXCLUDED — it is the
#: git-dependent cross-check leg (slice-04/05), not section-content (slice-03).
VERDICT_MISSING_SUSTAINABILITY = "missing-sustainability-section"
VERDICT_MALFORMED_SUSTAINABILITY = "malformed-sustainability-section"
VERDICT_NO_NEW_TESTS = "no-new-tests"
#: slice-04 (DDD-4): the git-dependent cross-check verdict slice-03 DEFERRED. Emitted by
#: the `--with-metrics` mode when a CONSOLIDATE/REUSE claim is contradicted by a net
#: test-LOC INCREASE in the real git diff (the `blind_add` leg returns `blind-add`).
VERDICT_BLIND_ADD_DETECTED = "blind-add-detected"
#: REUSED verbatim across both content gates (the token names the outcome class, not
#: the section kind): VERDICT_STRUCTURALLY_ACCEPTED, VERDICT_UNJUSTIFIED_CREATE_NEW,
#: VERDICT_METHODOLOGY_EXEMPT.

#: The four canonical Decision tokens accepted in a sustainability row (DDD-3, #3).
#: The Reuse Analysis EXTEND/CREATE_NEW set widened with REUSE/CONSOLIDATE. Any other
#: normalized token is `malformed-sustainability-section`.
_SUSTAINABILITY_DECISION_TOKENS: frozenset[str] = frozenset(
    {"REUSE", "EXTEND", "CONSOLIDATE", "CREATE_NEW"}
)

#: Exemption-marker line patterns (DDD-9) keyed to the sustainability section's own
#: `Test-Reuse-Analysis:` marker namespace. A line directly under the canonical heading
#: matching one of these is a first-class accepted verdict the gate classifies itself.
_SUSTAINABILITY_MARKER_METHODOLOGY_EXEMPT_RE = re.compile(
    r"^Test-Reuse-Analysis:\s*methodology-exempt\s*$"
)
_SUSTAINABILITY_MARKER_NO_NEW_TESTS_RE = re.compile(
    r"^Test-Reuse-Analysis:\s*no-new-tests\s*$"
)

#: Match the canonical Test Reuse & Consolidation Analysis heading (DDD-3). Exact-form
#: match; variant headings (wrong level, prefix, suffix) are not accepted.
_SUSTAINABILITY_HEADING_RE = re.compile(
    r"^##\s+Test\s+Reuse\s+&\s+Consolidation\s+Analysis\s*$"
)

#: Exemption-marker line patterns (DDD-9). A line directly under the canonical
#: `## Reuse Analysis` heading matching one of these is a first-class accepted
#: verdict the gate classifies itself.
_REUSE_MARKER_METHODOLOGY_EXEMPT_RE = re.compile(
    r"^Reuse-Analysis:\s*methodology-exempt\s*$"
)
_REUSE_MARKER_NO_OVERLAP_RE = re.compile(r"^Reuse-Analysis:\s*no-overlap\s*$")

#: Collapse every run of whitespace to a single `_` (DDD-7 normalization step).
_WHITESPACE_RUN_RE = re.compile(r"\s+")

#: Strip a single trailing parenthetical qualifier from a Decision cell (DDD-7
#: leniency): `CREATE_NEW (companion)` -> `CREATE_NEW`. The qualifier is a benign
#: human annotation; the substantive token is what the gate classifies.
_TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")

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

#: Match the canonical Feature Plan section heading (discuss-epic-mode R1 —
#: mirrors the slice-plan regex, D2 grammar reused verbatim).
_FEATURE_PLAN_HEADING_RE = re.compile(
    r"^##\s+Wave:\s+DISCUSS\s*/\s*\[REF\]\s+Feature\s+Plan\s*$"
)


def _exact_heading_regex(heading_literal: str) -> re.Pattern[str]:
    """Build an exact-form, whitespace-tolerant H2 heading regex from a
    canonical heading literal (e.g. ``"## Reuse Analysis"``). Pure.

    The SSOT-derivation half of the FR-11 fix: an independently hardcoded
    regex for the SAME heading text is exactly the drift class FR-11 traced
    (one grammar concept, two definitions). Deriving the regex from the
    literal means changing the constant automatically changes what the regex
    matches -- there is nowhere left for a second definition to hide.
    """
    words = heading_literal.removeprefix("##").split()
    return re.compile(
        r"^##\s+" + r"\s+".join(re.escape(word) for word in words) + r"\s*$"
    )


#: Match the canonical Reuse Analysis heading (DDD-8). Exact-form match;
#: variant headings (wrong level, prefix, suffix) are not accepted. Derived
#: from `REUSE_ANALYSIS_HEADING` (the SSOT constant) via `_exact_heading_regex`
#: -- not an independent hardcoded literal.
_REUSE_ANALYSIS_HEADING_RE = _exact_heading_regex(REUSE_ANALYSIS_HEADING)

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


class PlanValidationResult(NamedTuple):
    """Outcome of a structural plan check (slice plan OR feature plan).

    `verdict` is one of the closed token set; `detail` is a human-readable
    diagnostic naming the cause (for the JSON payload + plain-text rendering).
    Renamed from `SlicePlanResult` (discuss-epic-mode C2): one result type shared
    by both plan modes, with an honest name and an identical JSON shape.
    """

    verdict: str
    detail: str


#: Backward-compat alias — `SlicePlanResult` was a naming lie once two plan
#: kinds share the result type (discuss-epic-mode C2). The alias keeps every
#: existing importer/test green with zero call-site edits.
SlicePlanResult = PlanValidationResult


class _PlanSpec(NamedTuple):
    """The (heading, columns, diagnostic-nouns) parametrization for ONE plan
    kind — pure data. The generic plan core (`_validate_plan_content`) reads a
    frozen `_PlanSpec` so the slice-plan and feature-plan modes share one body
    while each renders its own headings, columns, verdict tokens, and diagnostic
    nouns (discuss-epic-mode slice-01 parametrization SHAPE).
    """

    heading_re: re.Pattern[str]  # exact-form H2 heading regex
    heading_literal: str  # exact heading text (missing-detail message)
    columns: tuple[str, ...]  # fixed-order five-column header contract
    verdict_missing: str  # closed token: section absent
    verdict_malformed: str  # closed token: bad header / zero rows
    contract_ref: str  # provenance citation in the missing-detail
    table_noun: str  # "slice-plan" | "feature-plan" (hyphenated)
    plan_noun: str  # "slice plan" | "feature plan" (spaced)
    row_noun: str  # "slice" | "feature"


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


#: The two plan-mode specs. Each binds the generic plan core to one plan kind's
#: headings, columns, verdict tokens, and diagnostic nouns. The slice-plan spec
#: renders every detail string byte-identically to the pre-parametrization code
#: (discuss-epic-mode C1 byte-identity contract T1-T6); the feature-plan spec
#: renders the feature-mode variants (its own heading literal + the R1 provenance
#: citation, the "feature-plan"/"feature plan"/"feature" nouns).
_SLICE_PLAN_SPEC = _PlanSpec(
    heading_re=_SLICE_PLAN_HEADING_RE,
    heading_literal="## Wave: DISCUSS / [REF] Slice Plan",
    columns=SLICE_PLAN_COLUMNS,
    verdict_missing=VERDICT_MISSING_SLICE_PLAN,
    verdict_malformed=VERDICT_MALFORMED_SLICE_PLAN,
    contract_ref="ADR-028 D2",
    table_noun="slice-plan",
    plan_noun="slice plan",
    row_noun="slice",
)
_FEATURE_PLAN_SPEC = _PlanSpec(
    heading_re=_FEATURE_PLAN_HEADING_RE,
    heading_literal="## Wave: DISCUSS / [REF] Feature Plan",
    columns=FEATURE_PLAN_COLUMNS,
    verdict_missing=VERDICT_MISSING_FEATURE_PLAN,
    verdict_malformed=VERDICT_MALFORMED_FEATURE_PLAN,
    contract_ref="discuss-epic-mode R1",
    table_noun="feature-plan",
    plan_noun="feature plan",
    row_noun="feature",
)


def _plan_table_rows(content: str, heading_re: re.Pattern[str]) -> list[str] | None:
    """Extract a plan table's raw rows beneath its heading. Pure.

    Locates the single heading matching `heading_re` and collects the first GFM
    table beneath it — non-blank lines starting with `|`, taken until the first
    blank line or next `##` heading. Generalized from `_slice_plan_table_rows`
    (discuss-epic-mode slice-01 H1: heading_re injected so both plan modes share
    the table walk).

    Returns:
        The list of raw table rows (header, separator, then data rows), or
        None when the plan heading is absent.
    """
    lines = content.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if heading_re.match(line.rstrip()):
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


def _classify_slice_cohesion(
    slice_rows: list[str], row_noun: str = "slice"
) -> PlanValidationResult | None:
    """Cohesion-MECC floor (slice-06; reused at feature granularity slice-03).
    Pure; result-not-raise.

    Vetoes the structurally-certain all-`@infrastructure` case: when EVERY data
    row's Annotation cell (column 4) normalises to `@infrastructure`, the plan
    carries no user-visible value and is rejected. Returns `None` (no objection)
    as soon as one row is value-bearing.

    The Annotation cell normalises via strip -> lowercase -> tolerate a leading
    `@`, so ` @Infrastructure ` and `@infrastructure` both match. An empty cell,
    `@walking-skeleton` / `@walking_skeleton`, or any unknown token counts as
    value-bearing (NOT infra).

    `row_noun` defaults to `"slice"` so the slice-mode detail stays
    byte-identical (C1 T5); the feature mode passes `"feature"`. The token
    `rejected-infra-only` is SHARED across both modes — it names the failure
    CLASS (no user-visible value), not the plan kind; the detail field's
    `{row_noun} rows` is the plan-kind disambiguator.

    Per §22.0, the MECC vetoes ONLY this structurally-certain case; it makes no
    semantic "is this really valueless" judgement (that stays reviewer-advisory).
    """
    infra_count = 0
    for row in slice_rows:
        cells = _parse_table_cells(row)
        annotation = cells[3] if len(cells) > 3 else ""
        normalised = annotation.strip().lower().lstrip("@")
        if normalised != "infrastructure":
            return None
        infra_count += 1
    # Defensive: zero rows ⇒ no-veto (an empty plan is NOT "all-infra"). The
    # current caller guards len(rows) >= 1, but this keeps the pure
    # function correct in isolation — without it, empty input would wrongly veto.
    if infra_count == 0:
        return None
    return PlanValidationResult(
        verdict=VERDICT_REJECTED_INFRA_ONLY,
        detail=(
            f"all {infra_count} {row_noun} rows are annotated @infrastructure; "
            f"an infrastructure-only plan carries no user-visible value (MECC)"
        ),
    )


def _validate_plan_content(content: str, spec: _PlanSpec) -> PlanValidationResult:
    """Structurally validate a plan section against `spec`. Pure function.

    The generic core shared by both plan modes. Runs the heading-form check
    first (a malformed wave heading anywhere is reported as
    `malformed-wave-heading` regardless of plan shape — spec-independent), then
    the plan structural check:

    - section absent                          -> spec.verdict_missing
    - table column header not the fixed five  -> spec.verdict_malformed
      columns (wrong count or reordered)
    - header + separator but zero data rows   -> spec.verdict_malformed
    - all-@infrastructure data rows           -> rejected-infra-only
    - well-formed five-column table, >=1 row  -> accepted

    Args:
        content: feature-delta.md / epic-delta.md body (UTF-8 text).
        spec:    the plan-kind parametrization.

    Returns:
        PlanValidationResult carrying the closed-set verdict token + diagnostic.
    """
    heading_result = validate_feature_delta_content(content)
    if not heading_result.is_valid:
        first = heading_result.offenders[0]
        return PlanValidationResult(
            verdict=VERDICT_MALFORMED_WAVE_HEADING,
            detail=(
                f"malformed wave heading at line {first.line}: "
                f"{first.heading} - {first.reason}"
            ),
        )

    rows = _plan_table_rows(content, spec.heading_re)
    if rows is None:
        return PlanValidationResult(
            verdict=spec.verdict_missing,
            detail=(f"no '{spec.heading_literal}' section found ({spec.contract_ref})"),
        )

    # DC-1 (discuss-epic-mode, Ale-ratified narrow MECC): Status tokens are NOT
    # validated here — the validator stays structurally narrow by design (mirror
    # of the slice-plan mode, which never validates Status cells). Status-token
    # rejection is the LSC/slice-05 contract (LSC-6), trivially promotable to a
    # closed verdict later if LSC enforcement proves insufficient.
    header_cells = _parse_table_cells(rows[0]) if rows else []
    if tuple(header_cells) != spec.columns:
        return PlanValidationResult(
            verdict=spec.verdict_malformed,
            detail=(
                f"{spec.table_noun} table columns {header_cells} do not match "
                f"the D2 fixed five-column header {list(spec.columns)}"
            ),
        )

    data_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    if not data_rows:
        return PlanValidationResult(
            verdict=spec.verdict_malformed,
            detail=(
                f"{spec.table_noun} table has its header but zero {spec.row_noun} rows"
            ),
        )

    cohesion_veto = _classify_slice_cohesion(data_rows, spec.row_noun)
    if cohesion_veto is not None:
        return cohesion_veto

    return PlanValidationResult(
        verdict=VERDICT_ACCEPTED,
        detail=f"{spec.plan_noun} is well formed; {len(data_rows)} {spec.row_noun} rows",
    )


def validate_slice_plan_content(content: str) -> PlanValidationResult:
    """Structurally validate the slice-plan section. Pure function.

    Spec-bound wrapper over `_validate_plan_content` — signature and every
    emitted `(verdict, detail)` byte UNCHANGED (discuss-epic-mode C1 byte-identity
    contract). The Guardrail-2 regression witness is the existing
    `--require-slice-plan` AT + unit suites staying green post-refactor.
    """
    return _validate_plan_content(content, _SLICE_PLAN_SPEC)


def validate_feature_plan_content(content: str) -> PlanValidationResult:
    """Structurally validate the Feature Plan section of an epic-delta. Pure.

    Spec-bound wrapper over `_validate_plan_content` for the feature-plan mode
    (discuss-epic-mode slice-01). Emits the feature-mode closed verdict set:
    `accepted · malformed-wave-heading · missing-feature-plan ·
    malformed-feature-plan · rejected-infra-only`.
    """
    return _validate_plan_content(content, _FEATURE_PLAN_SPEC)


# ---------------------------------------------------------------------------
# Pure core — locked-[REF]-section presence (f-deliver-entry-contract-freeze
# DDD-1 / CT-2b: the NEW section-presence check the DELIVER-entry gate composes)
# ---------------------------------------------------------------------------

#: The named locked feature-delta sections the DELIVER-entry contract-freeze gate
#: requires PRESENT (DDD-1 1b / CT-2b). Authored either as a `## Wave: <NAME> /
#: [REF] <Section>` heading (the three [REF] sections) or as the bare canonical
#: `## Reuse Analysis` heading (DDD-8). The source validator checks heading TYPE
#: tokens + the slice-plan table — NEITHER asserts these sections are PRESENT, so
#: this is genuinely-new GREEN work (review HIGH-2), not "verbatim reuse".
LOCKED_REF_SECTIONS: tuple[str, ...] = (
    "Architecture & Contract Tests",
    "ADR Refs",
    "Reuse Analysis",
    "Slice Plan",
)


def _present_section_set(content: str) -> set[str]:
    """The named sections a feature-delta carries (the presence universe). Pure.

    A section is PRESENT when a heading names it — either a
    `## Wave: <NAME> / [REF] <Section>` heading or the bare canonical
    `## Reuse Analysis` heading (DDD-8). Shared by `locked_sections_present` (the
    hard-coded-tuple presence check) and `missing_registry_sections` (the
    registry-backed sibling) so both read the SAME presence universe — the
    DELIVER-entry caller migration between them is byte-stable (DA-3).
    """
    sections = {
        match.group("section").strip()
        for line in content.splitlines()
        if (match := _WAVE_HEADING_RE.match(line.rstrip())) is not None
    }
    # The bare `## Reuse Analysis` heading is a first-class locked-section form
    # (DDD-8) — fold it into the present set when authored that way.
    sections |= {
        "Reuse Analysis"
        for line in content.splitlines()
        if _REUSE_ANALYSIS_HEADING_RE.match(line.rstrip()) is not None
    }
    return sections


def locked_sections_present(content: str) -> list[str]:
    """Return the locked sections that are ABSENT from a feature-delta. Pure.

    A locked section is PRESENT when a heading names it — either a
    `## Wave: <NAME> / [REF] <Section>` heading or the bare canonical
    `## Reuse Analysis` heading (DDD-8). The returned list is the missing-section
    names in `LOCKED_REF_SECTIONS` order; an empty list means every locked
    section is present.
    """
    sections = _present_section_set(content)
    return [name for name in LOCKED_REF_SECTIONS if name not in sections]


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
    # DDD-7 leniency (SUBSTANCE-AWARE, 2026-07-05): a trailing parenthetical
    # qualifier (`CREATE_NEW (companion)`, `EXTEND (in place)`) is tolerated ->
    # the bare substantive token is extracted. The qualifier belongs in the
    # Overlap/Justification cell, but rejecting the whole row on a benign
    # human annotation is a form-proxy breaking on an edge case; consult the
    # substance (the leading token), do not brittle-fail. A cell that does not
    # reduce to a canonical token (e.g. `MAYBE_REWRITE`) still fails.
    unbolded = _TRAILING_PARENTHETICAL_RE.sub("", unbolded.strip())
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


def _strip_inline_code(cell: str) -> str:
    """Strip one surrounding pair of `` ` `` markers from a table cell. Pure."""
    stripped = cell.strip()
    if stripped.startswith("`") and stripped.endswith("`") and len(stripped) >= 2:
        return stripped[1:-1]
    return stripped


def _component_citation_is_grounded(
    existing_component: str, file_cell: str, project_root: Path
) -> bool:
    """Resolve one `Existing Component | File` citation THROUGH the CodeFactPort.

    Re-derives the fact via `CodeFactChain` (Tsunami-first, AST fallback,
    textsearch floor -- ADR-LA-001), never a bespoke grep. `file_cell` is
    resolved relative to `project_root` (the same base `_ground_sut` uses for
    `sut:` citations, `scripts/cli/validate_component_manifest.py:34
    _REPO_ROOT`). Returns True iff the cited file exists AND the named symbol
    resolves as one of its atoms.
    """
    from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
    from des.ports.code_fact_port import (
        CAPABILITY_ATOMS_IN_FILE,
        CapabilityDescriptor,
    )

    symbol = _strip_inline_code(existing_component)
    file_path = project_root / _strip_inline_code(file_cell)
    if not symbol or not file_path.is_file():
        return False

    descriptor = CapabilityDescriptor(
        id=CAPABILITY_ATOMS_IN_FILE,
        stability="stable",
        contract_version="1.0.0",
        io_schema="atoms-in-file/1",
        providing_adapter="ast",
    )
    result = CodeFactChain(root=file_path).query(descriptor, {})
    if result is None or not isinstance(result.payload, dict):
        return False
    atoms = result.payload.get("atoms", [])
    return isinstance(atoms, list) and symbol in atoms


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


def validate_reuse_analysis_content(
    content: str, project_root: Path | None = None
) -> ReuseAnalysisResult:
    """Structurally validate the Reuse Analysis section. Pure when `project_root`
    is None; otherwise the impure content-grounding leg is active.

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
    - when `project_root` is given: any row whose `Existing Component | File`
      citation does NOT resolve through the CodeFactPort chain ->
      ungrounded-reuse-analysis (F-fix-reuse-analysis-content-grounding);
    - all component rows well formed (and, when checked, grounded) ->
      structurally-accepted (DDD-3 — NOT a claim that reuse-first was
      honoured; only that the table is well formed).

    Args:
        content: feature-delta.md body (UTF-8 text).
        project_root: base directory `File` citations resolve against. When
            None (the default, preserving the pure-function contract for
            existing callers), content-grounding is skipped.

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

    if project_root is not None:
        for row_no, row in enumerate(component_rows, start=1):
            cells = _parse_table_cells(row)
            if not _component_citation_is_grounded(cells[0], cells[1], project_root):
                return ReuseAnalysisResult(
                    verdict=VERDICT_UNGROUNDED_REUSE_ANALYSIS,
                    detail=(
                        f"row {row_no} cites {cells[0]!r} in {cells[1]!r} but "
                        f"no CodeFactPort tier resolves that symbol in that "
                        f"file (phantom component citation)"
                    ),
                )

    return ReuseAnalysisResult(
        verdict=VERDICT_STRUCTURALLY_ACCEPTED,
        detail=(
            f"Reuse Analysis is structurally accepted; "
            f"{len(component_rows)} component rows"
        ),
    )


# ---------------------------------------------------------------------------
# Pure core — Test Reuse & Consolidation Analysis structural validation (slice-03)
#
# A 1:1 mirror of the Reuse Analysis validator (DDD-2), reusing the shared table
# machinery (`_parse_table_cells`, `_is_separator_row`, `_plan_table_rows`,
# `_normalise_decision_token`) and the closed-verdict-token pattern. git-free,
# section-content only — the git-dependent blind-add cross-check is slice-04/05.
# ---------------------------------------------------------------------------


class SustainabilityResult(NamedTuple):
    """Outcome of the --require-sustainability content check.

    `verdict` is one of the closed token set (DDD-2, git-free subset); `detail` is a
    human-readable diagnostic naming the cause. Mirrors `ReuseAnalysisResult` shape.
    """

    verdict: str
    detail: str


def _sustainability_heading_indices(content: str) -> list[int]:
    """Return the line indices of every canonical sustainability heading. Pure."""
    return [
        idx
        for idx, line in enumerate(content.splitlines())
        if _SUSTAINABILITY_HEADING_RE.match(line.rstrip())
    ]


def _sustainability_body_lines(content: str) -> list[str]:
    """Return the non-blank, non-`|` lines under the first sustainability heading
    until the next `##` heading. Pure.

    These are the candidate exemption-marker lines (DDD-9). The body stops at the first
    table line, the first blank-after-content boundary, or the next `##` heading.
    """
    indices = _sustainability_heading_indices(content)
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


def _classify_sustainability_exemption(content: str) -> SustainabilityResult | None:
    """Detect a DDD-9 exemption marker under the canonical heading. Pure.

    Returns the methodology-exempt or no-new-tests verdict when the corresponding marker
    is present; None otherwise.
    """
    for line in _sustainability_body_lines(content):
        if _SUSTAINABILITY_MARKER_METHODOLOGY_EXEMPT_RE.match(line):
            return SustainabilityResult(
                verdict=VERDICT_METHODOLOGY_EXEMPT,
                detail="Test-Reuse-Analysis: methodology-exempt marker present (DDD-9)",
            )
        if _SUSTAINABILITY_MARKER_NO_NEW_TESTS_RE.match(line):
            return SustainabilityResult(
                verdict=VERDICT_NO_NEW_TESTS,
                detail="Test-Reuse-Analysis: no-new-tests marker present (DDD-9)",
            )
    return None


def _classify_sustainability_row(
    row_no: int, cells: list[str]
) -> SustainabilityResult | None:
    """Classify a single sustainability row. Pure.

    Returns a rejection verdict on the first defect found, or None when the row is well
    formed (Decision in {REUSE, EXTEND, CONSOLIDATE, CREATE_NEW}, with non-empty
    Justification on CREATE_NEW).
    """
    if len(cells) < len(SUSTAINABILITY_COLUMNS):
        return SustainabilityResult(
            verdict=VERDICT_MALFORMED_SUSTAINABILITY,
            detail=(
                f"row {row_no} has {len(cells)} cells; expected "
                f"{len(SUSTAINABILITY_COLUMNS)} ({list(SUSTAINABILITY_COLUMNS)})"
            ),
        )
    decision = _normalise_decision_token(cells[3])
    if decision not in _SUSTAINABILITY_DECISION_TOKENS:
        return SustainabilityResult(
            verdict=VERDICT_MALFORMED_SUSTAINABILITY,
            detail=(
                f"row {row_no} Decision {cells[3]!r} does not normalise into "
                f"{sorted(_SUSTAINABILITY_DECISION_TOKENS)} (DDD-3)"
            ),
        )
    if decision == "CREATE_NEW" and not cells[4].strip():
        return SustainabilityResult(
            verdict=VERDICT_UNJUSTIFIED_CREATE_NEW,
            detail=(f"row {row_no} is CREATE_NEW with an empty Justification (DDD-3)"),
        )
    return None


def validate_sustainability_content(content: str) -> SustainabilityResult:
    """Structurally validate the Test Reuse & Consolidation Analysis section. Pure.

    Closes the DDD-2 git-free verdict subset (1:1 mirror of
    `validate_reuse_analysis_content`):

    - no `## Test Reuse & Consolidation Analysis` heading + no exemption marker ->
      missing-sustainability-section;
    - exemption marker under the heading -> methodology-exempt / no-new-tests
      (DDD-9, accepted);
    - duplicate canonical heading -> malformed-sustainability-section;
    - table column header not the canonical five columns ->
      malformed-sustainability-section;
    - any row with Decision not in {REUSE, EXTEND, CONSOLIDATE, CREATE_NEW} after DDD-7
      normalization -> malformed-sustainability-section;
    - any CREATE_NEW row with an empty Justification -> unjustified-create-new (DDD-3);
    - all rows well formed -> structurally-accepted (DDD-3 — NOT a claim that
      reuse-first was honoured; only that the table is well formed).

    Args:
        content: feature-delta.md body (UTF-8 text).

    Returns:
        SustainabilityResult carrying the closed-set verdict token + a diagnostic.
    """
    heading_indices = _sustainability_heading_indices(content)
    if len(heading_indices) > 1:
        return SustainabilityResult(
            verdict=VERDICT_MALFORMED_SUSTAINABILITY,
            detail=(
                f"duplicate '{SUSTAINABILITY_HEADING}' heading at lines "
                f"{[idx + 1 for idx in heading_indices]} (DDD-3)"
            ),
        )

    marker_result = _classify_sustainability_exemption(content)
    if marker_result is not None:
        return marker_result

    rows = _plan_table_rows(content, _SUSTAINABILITY_HEADING_RE)
    if rows is None:
        return SustainabilityResult(
            verdict=VERDICT_MISSING_SUSTAINABILITY,
            detail=(
                f"no '{SUSTAINABILITY_HEADING}' section found "
                "(DDD-3 / nw-distill sustainability section)"
            ),
        )

    header_cells = _parse_table_cells(rows[0]) if rows else []
    if tuple(header_cells) != SUSTAINABILITY_COLUMNS:
        return SustainabilityResult(
            verdict=VERDICT_MALFORMED_SUSTAINABILITY,
            detail=(
                f"sustainability table columns {header_cells} do not match the "
                f"canonical five-column header {list(SUSTAINABILITY_COLUMNS)} (DDD-3)"
            ),
        )

    data_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    if not data_rows:
        return SustainabilityResult(
            verdict=VERDICT_MALFORMED_SUSTAINABILITY,
            detail="sustainability section has its header but zero rows",
        )

    for row_no, row in enumerate(data_rows, start=1):
        rejection = _classify_sustainability_row(row_no, _parse_table_cells(row))
        if rejection is not None:
            return rejection

    return SustainabilityResult(
        verdict=VERDICT_STRUCTURALLY_ACCEPTED,
        detail=(
            f"sustainability section is structurally accepted; {len(data_rows)} rows"
        ),
    )


def sustainability_decisions(content: str) -> list[str]:
    """The normalised Decision tokens of the sustainability section rows. Pure.

    Reuses the slice-03 table machinery (`_plan_table_rows`, `_is_separator_row`,
    `_parse_table_cells`, `_normalise_decision_token`). The metrics mode reads these to
    compute the C (adoption-ratio) cell and to detect a declared CONSOLIDATE/REUSE intent
    for the blind-add cross-check. An absent section / header-only section yields `[]`.
    """
    rows = _plan_table_rows(content, _SUSTAINABILITY_HEADING_RE)
    if rows is None:
        return []
    data_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    decisions: list[str] = []
    for row in data_rows:
        cells = _parse_table_cells(row)
        if len(cells) > 3:
            decisions.append(_normalise_decision_token(cells[3]))
    return decisions


# ---------------------------------------------------------------------------
# Pure core — registry-backed [REF]-section enforcement
# (algebra-projections-enforced slice-01; ADR-001 D1/D3, DESIGN DA-1/DA-2/DA-6)
#
# slice-01 DELIVER (IMPLEMENTED):
#   * read_wave_output_contract — stdlib narrow line-scan of
#     `nWave/waves/<wave>.yaml output_contract.ref_sections` (REUSES the
#     verify_wave_contract_coherence.py:64-69 idiom; NO PyYAML — WD-4).
#   * classify_registry_sections — pure direction-(a) classifier: a [REF] section
#     ∉ contract.ref_sections → the `undeclared-section` verdict naming the
#     offending section; all declared → `accepted`. (Direction (b)
#     mandatory∉delta is slice-02.)
#
# slice-02 DELIVER (IMPLEMENTED, ADD-not-mutate — `LOCKED_REF_SECTIONS` is
# untouched):
#   * missing_registry_sections — the registry-backed sibling of
#     `locked_sections_present`; reads the SAME presence universe
#     (`_present_section_set`) so the DELIVER-entry caller migration is byte-stable
#     (DA-3). Wired by verify_deliver_entry_contract.py via `_DELIVER_LOCKED_CONTRACT`.
# ---------------------------------------------------------------------------

# slice-01 closed verdict tokens (direction (a)); slice-02 adds the direction-(b)
# missing-mandatory token; slice-05 adds the rest.
VERDICT_REGISTRY_SECTIONS_ACCEPTED = "accepted"
VERDICT_UNDECLARED_SECTION = "undeclared-section"
VERDICT_MISSING_MANDATORY_SECTION = "missing-mandatory-section"

#: slice-05 fail-closed boundary (DESIGN DA-5 / DD-A5). When the registry the check
#: must read is unreadable, the boundary degrades into ONE of two typed verdicts —
#: never `accepted`, never a crash:
#:  * `unknown-wave` REJECT — the `<wave>` argument is NOT a canonical nWave wave
#:    (a section-check verdict in the same family as `undeclared-section`, NOT a
#:    §17 GateVerdict);
#:  * `indeterminate` degrade-LOUD — a canonical wave whose registry is
#:    absent/garbled. This REUSES the existing §17 `GateVerdict.INDETERMINATE`
#:    token verbatim (no sixth GateVerdict token; mirror of
#:    `verify_wave_contract_coherence._indeterminate`).
VERDICT_UNKNOWN_WAVE = "unknown-wave"
VERDICT_INDETERMINATE = GateVerdict.INDETERMINATE.value

#: The canonical nWave wave universe (SSOT: the `WaveName` Literal in
#: `documentation_density_event.py`). Membership is case-insensitive — the driving
#: surface passes a lowercase wave id (`discuss`), the SSOT spells them UPPERCASE.
#: A `<wave>` outside this set is the `unknown-wave` REJECT; a `<wave>` inside it
#: with an unreadable registry is the `indeterminate` degrade.
_CANONICAL_WAVE_NAMES: frozenset[str] = frozenset(get_args(WaveName))

#: A ``- id: <value>`` list entry inside ``output_contract.ref_sections``. The
#: value carries spaces ("Wave-Decision Reconciliation", "Persona ID"), so this
#: is NOT the gate_id token regex from verify_wave_contract_coherence.py — it
#: captures the full trimmed value (REUSED idiom, distinct token grammar, WD-4:
#: stdlib line-scan, NO PyYAML).
_REF_SECTION_ID_RE = re.compile(r"^\s*-\s*id:\s*(?P<id>.+?)\s*$")

#: A ``grade: <value>`` sibling line of a ref_sections entry.
_REF_SECTION_GRADE_RE = re.compile(r"^\s*grade:\s*(?P<grade>mandatory|optional)\s*$")

#: A ``greenfield_degradation: <value>`` sibling line of a ref_sections entry.
_REF_SECTION_DEGRADATION_RE = re.compile(
    r"^\s*greenfield_degradation:\s*(?P<value>.+?)\s*$"
)

#: A top-level YAML key (zero-indent ``key:``) — the boundary that ends the
#: ``output_contract`` block.
_TOP_LEVEL_KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+):\s*$")

#: A two-space-indented YAML key inside ``output_contract`` (``ref_sections:`` /
#: ``files:``) — the boundary that ends the ``ref_sections`` list.
_OUTPUT_CONTRACT_CHILD_KEY_RE = re.compile(r"^  (?P<key>[A-Za-z0-9_-]+):\s*$")


@dataclass(frozen=True)
class RefSection:
    """One `output_contract.ref_sections` entry (ADR-FLOW-006 D3). Pure value."""

    id: str
    grade: Literal["mandatory", "optional"]
    greenfield_degradation: str | None = None


@dataclass(frozen=True)
class WaveOutputContract:
    """A wave's parsed `output_contract.ref_sections` (ADR-001 D1). Pure value."""

    wave: str
    ref_sections: tuple[RefSection, ...]


@dataclass(frozen=True)
class RegistrySectionResult:
    """Closed-set verdict envelope for the registry-section cross-check. Pure value."""

    verdict: str
    detail: str


def _scan_ref_sections(text: str) -> tuple[RefSection, ...]:
    """Parse the `output_contract.ref_sections` list from registry text. Pure.

    A narrow stdlib line-scan (WD-4, no PyYAML): walk into the top-level
    `output_contract:` block, then into its `  ref_sections:` child, then collect
    each `- id:` entry with its `grade:` / optional `greenfield_degradation:`
    siblings until the list ends (a sibling child key like `  files:` or the next
    top-level key).
    """
    in_output_contract = False
    in_ref_sections = False
    sections: list[RefSection] = []
    current_id: str | None = None
    current_grade: str = "mandatory"
    current_degradation: str | None = None

    def flush() -> None:
        nonlocal current_id, current_grade, current_degradation
        if current_id is not None:
            sections.append(
                RefSection(
                    id=current_id,
                    grade="optional" if current_grade == "optional" else "mandatory",
                    greenfield_degradation=current_degradation,
                )
            )
        current_id = None
        current_grade = "mandatory"
        current_degradation = None

    for line in text.splitlines():
        top = _TOP_LEVEL_KEY_RE.match(line)
        if top is not None:
            flush()
            in_output_contract = top.group("key") == "output_contract"
            in_ref_sections = False
            continue
        if not in_output_contract:
            continue
        child = _OUTPUT_CONTRACT_CHILD_KEY_RE.match(line)
        if child is not None:
            flush()
            in_ref_sections = child.group("key") == "ref_sections"
            continue
        if not in_ref_sections:
            continue
        id_match = _REF_SECTION_ID_RE.match(line)
        if id_match is not None:
            flush()
            current_id = id_match.group("id")
            continue
        grade_match = _REF_SECTION_GRADE_RE.match(line)
        if grade_match is not None:
            current_grade = grade_match.group("grade")
            continue
        degradation_match = _REF_SECTION_DEGRADATION_RE.match(line)
        if degradation_match is not None:
            current_degradation = degradation_match.group("value")
    flush()
    return tuple(sections)


def read_wave_output_contract(wave: str, waves_dir: Path) -> WaveOutputContract | None:
    """Read `<waves_dir>/<wave>.yaml output_contract.ref_sections`.

    A stdlib narrow line-scan (no PyYAML, WD-4) returning the parsed contract, or
    None when the registry is absent / undecodable (the degrade-LOUD boundary
    keyed by slice-05's INDETERMINATE).
    """
    try:
        text = (waves_dir / f"{wave}.yaml").read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return None
    return WaveOutputContract(wave=wave, ref_sections=_scan_ref_sections(text))


def _carried_ref_sections(content: str) -> list[str]:
    """The `[REF]` section ids a feature-delta carries, in document order. Pure.

    Reads every `## Wave: <W> / [REF] <S>` heading via the existing
    `_WAVE_HEADING_RE` and collects the `<S>` of those whose type token is `REF`.
    """
    carried: list[str] = []
    for line in content.splitlines():
        match = _WAVE_HEADING_RE.match(line.rstrip())
        if match is not None and match.group("type") == "REF":
            carried.append(match.group("section").strip())
    return carried


def classify_registry_sections(
    content: str, contract: WaveOutputContract
) -> RegistrySectionResult:
    """Cross-check a feature-delta's [REF] sections against the registry. Pure.

    slice-01, direction (a): return `undeclared-section` (naming the offending
    section) for the first `## Wave: <W> / [REF] <S>` section whose `<S>` is not in
    `contract.ref_sections`; `accepted` when every carried section is declared by
    the live registry.
    """
    declared = {section.id for section in contract.ref_sections}
    for carried in _carried_ref_sections(content):
        if carried not in declared:
            return RegistrySectionResult(
                verdict=VERDICT_UNDECLARED_SECTION,
                detail=(
                    f"the feature-delta carries a [REF] section {carried!r} the "
                    f"{contract.wave!r} wave registry does not declare; declared "
                    f"sections are {sorted(declared)}"
                ),
            )
    return RegistrySectionResult(
        verdict=VERDICT_REGISTRY_SECTIONS_ACCEPTED,
        detail=(
            f"every [REF] section is declared by the {contract.wave!r} wave registry"
        ),
    )


def missing_registry_sections(content: str, contract: WaveOutputContract) -> list[str]:
    """Registry-backed sibling of `locked_sections_present`. Pure.

    Return the `grade: mandatory` `contract.ref_sections` ids ABSENT from the
    feature-delta, in contract order. A section carrying a `greenfield_degradation`
    literal is NOT a missing-mandatory failure even when its heading is absent
    (WD-5): the registry itself carries the honest-empty fallback, so the check
    must NOT block over its absence. `grade: optional` sections never fail on
    absence (DESIGN OQ-3).

    ADD-not-mutate (ADR-001 D1): `LOCKED_REF_SECTIONS` / `locked_sections_present`
    are untouched; this sibling reads the SAME presence universe
    (`_present_section_set`) so the DELIVER-entry caller migration is byte-stable
    (DA-3). When called with a contract whose `ref_sections` are the four
    `LOCKED_REF_SECTIONS` (all mandatory, none degradable), this returns exactly
    what `locked_sections_present` returns.
    """
    sections = _present_section_set(content)
    return [
        ref.id
        for ref in contract.ref_sections
        if ref.grade == "mandatory"
        and ref.greenfield_degradation is None
        and ref.id not in sections
    ]


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
    "usage: des validate-feature-delta "
    "[--require-slice-plan] [--require-feature-plan] [--require-reuse-analysis] "
    "[--require-sustainability] [--with-metrics] "
    "[--consolidate-on-add] [--add-only-baseline-loc <N>] "
    "[--existing-base-trend] [--prior-existing-base-ratio=<float>] "
    "[--corpus-root=<dir>] "
    "[--require-registry-sections <wave>] [--waves-dir <dir>] "
    "[--format=json] <path-to-feature-delta.md>"
)


class _ParsedArgs(NamedTuple):
    """Parsed CLI arguments."""

    path: str
    require_slice_plan: bool
    require_feature_plan: bool
    require_reuse_analysis: bool
    require_sustainability: bool
    with_metrics: bool
    consolidate_on_add: bool
    add_only_baseline_loc: int | None
    existing_base_trend: bool
    prior_existing_base_ratio: float | None
    corpus_root: str | None
    require_registry_sections: str | None
    waves_dir: str | None
    json_format: bool


def _parse_args(args: list[str]) -> _ParsedArgs | None:
    """Parse the CLI argument list. Returns None on malformed invocation.

    Accepts the optional flags `--require-slice-plan`, `--require-feature-plan`,
    `--require-reuse-analysis`, `--require-registry-sections <wave>`, and
    `--format=json` in any order, plus exactly one positional path argument. The
    plain-mode contract (a lone path argument) is preserved.

    `--require-registry-sections` consumes the NEXT token as its wave argument
    (algebra-projections-enforced slice-01, DESIGN DA-6); a trailing
    `--require-registry-sections` with no following wave token is malformed.

    `--waves-dir <dir>` (algebra-projections-enforced slice-05, DD-A2 — additive,
    mirrors the `verify-wave-contract-coherence --waves-dir` sibling) likewise
    consumes the NEXT token, overriding the default repo `nWave/waves` registry
    directory so the fail-closed boundary can be exercised against a hermetic tmp
    registry; a trailing `--waves-dir` with no following directory is malformed.
    """
    require_slice_plan = False
    require_feature_plan = False
    require_reuse_analysis = False
    require_sustainability = False
    with_metrics = False
    consolidate_on_add = False
    add_only_baseline_loc: int | None = None
    existing_base_trend = False
    prior_existing_base_ratio: float | None = None
    corpus_root: str | None = None
    require_registry_sections: str | None = None
    waves_dir: str | None = None
    json_format = False
    positionals: list[str] = []
    skip_next = False
    for idx, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--require-slice-plan":
            require_slice_plan = True
        elif arg == "--require-feature-plan":
            require_feature_plan = True
        elif arg == "--require-reuse-analysis":
            require_reuse_analysis = True
        elif arg == "--require-sustainability":
            require_sustainability = True
        elif arg == "--with-metrics":
            with_metrics = True
        elif arg == "--consolidate-on-add":
            consolidate_on_add = True
        elif arg.startswith("--add-only-baseline-loc="):
            try:
                add_only_baseline_loc = int(arg.split("=", 1)[1])
            except ValueError:
                return None
        elif arg == "--existing-base-trend":
            existing_base_trend = True
        elif arg.startswith("--prior-existing-base-ratio="):
            try:
                prior_existing_base_ratio = float(arg.split("=", 1)[1])
            except ValueError:
                return None
        elif arg.startswith("--corpus-root="):
            corpus_root = arg.split("=", 1)[1]
        elif arg == "--require-registry-sections":
            if idx + 1 >= len(args):
                return None
            require_registry_sections = args[idx + 1]
            skip_next = True
        elif arg == "--waves-dir":
            if idx + 1 >= len(args):
                return None
            waves_dir = args[idx + 1]
            skip_next = True
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
        require_feature_plan=require_feature_plan,
        require_reuse_analysis=require_reuse_analysis,
        require_sustainability=require_sustainability,
        with_metrics=with_metrics,
        consolidate_on_add=consolidate_on_add,
        add_only_baseline_loc=add_only_baseline_loc,
        existing_base_trend=existing_base_trend,
        prior_existing_base_ratio=prior_existing_base_ratio,
        corpus_root=corpus_root,
        require_registry_sections=require_registry_sections,
        waves_dir=waves_dir,
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


#: fix-validate-feature-delta-routes-to-doctor: the routing pointer added to
#: every `--require-*` REJECTION path. `des feature-delta-doctor <path>`
#: reports EVERY structural gap in ONE pass (per-gap what/why/how) instead of
#: the author fixing one rejection, re-running, hitting the next, N times
#: across N separate gate invocations. The specific rule/verdict violated
#: stays named as context -- this is an ADDED primary remedy, never a
#: replacement of it.
def _doctor_routing_hint(target: Path) -> str:
    """The primary-remedy pointer text naming `des feature-delta-doctor`. Pure."""
    return (
        f"run `des feature-delta-doctor {target}` for a one-pass report of "
        "every gap (not just this one)"
    )


def _routing_suffix(target: Path, *, accepted: bool) -> tuple[str, dict[str, str]]:
    """The (plain-text suffix, JSON extra-fields) pair for one verdict print. Pure.

    Empty on an ACCEPTED verdict (`accepted=True`) -- a well-formed feature-
    delta must never mention the doctor-routing remedy (no false steer on a
    clean delta). On REJECTION, returns the shared routing line -- the SAME
    line for every rejection verdict (malformed-wave-heading,
    unjustified-create-new, ungrounded-reuse-analysis, missing-*-section,
    etc.); never a per-verdict copy.
    """
    if accepted:
        return "", {}
    hint = _doctor_routing_hint(target)
    return f" -- {hint}", {"remedy": hint}


def _print_verdict_result(
    target: Path, verdict: str, detail: str, json_format: bool, *, accepted: bool
) -> None:
    """Print one (verdict, detail) result -- the shared print every
    `--require-*` mode funnels its terminal output through.

    On rejection (`accepted=False`), appends the `des feature-delta-doctor
    <path>` routing pointer as the PRIMARY remedy while keeping the specific
    `verdict` named as context (never replaced). On an accepted verdict,
    prints unchanged.
    """
    suffix, extra = _routing_suffix(target, accepted=accepted)
    if json_format:
        print(json.dumps({"verdict": verdict, "detail": detail, **extra}))
    else:
        print(f"{verdict}: {detail}{suffix}")


def _run_require_slice_plan(target: Path, json_format: bool) -> int:
    """Run the structural slice-plan check (slice-06).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on `accepted`, 1 on rejection.
    """
    content = target.read_text(encoding="utf-8")
    result = validate_slice_plan_content(content)
    accepted = result.verdict == VERDICT_ACCEPTED
    _print_verdict_result(
        target, result.verdict, result.detail, json_format, accepted=accepted
    )
    return 0 if accepted else 1


def _run_require_feature_plan(target: Path, json_format: bool) -> int:
    """Run the structural Feature Plan check (discuss-epic-mode slice-01).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on `accepted`, 1 on rejection.
    Mirrors `_run_require_slice_plan`.
    """
    content = target.read_text(encoding="utf-8")
    result = validate_feature_plan_content(content)
    accepted = result.verdict == VERDICT_ACCEPTED
    _print_verdict_result(
        target, result.verdict, result.detail, json_format, accepted=accepted
    )
    return 0 if accepted else 1


def _run_require_reuse_analysis(target: Path, json_format: bool) -> int:
    """Run the structural Reuse Analysis check (F-DESIGN-REUSE-FIRST-GATE).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on `structurally-accepted`,
    1 on rejection. Mirrors `_run_require_slice_plan` per DDD-1.

    Passes the current working directory as `project_root` so `Existing
    Component | File` citations are content-grounded THROUGH the
    CodeFactPort chain (F-fix-reuse-analysis-content-grounding) -- the same
    resolution base `_ground_sut` uses for `sut:` citations.

    On REJECTION the printed message routes the author to `des
    feature-delta-doctor <path>` as the primary remedy -- the one-pass tool
    that reports every structural gap at once -- while still naming the
    specific verdict violated as context
    (fix-validate-feature-delta-routes-to-doctor).
    """
    content = target.read_text(encoding="utf-8")
    result = validate_reuse_analysis_content(content, project_root=Path.cwd())
    accepted = result.verdict == VERDICT_STRUCTURALLY_ACCEPTED
    _print_verdict_result(
        target, result.verdict, result.detail, json_format, accepted=accepted
    )
    return 0 if accepted else 1


def _run_require_sustainability(target: Path, json_format: bool) -> int:
    """Run the structural Test Reuse & Consolidation Analysis check (slice-03, DDD-2).

    Emits a single JSON object carrying the closed-set `verdict` token (when
    `--format=json` is set) and returns exit 0 on an accepted verdict
    (structurally-accepted / methodology-exempt / no-new-tests), 1 on rejection.
    Mirrors `_run_require_reuse_analysis`. git-free section-content validation only.
    """
    content = target.read_text(encoding="utf-8")
    result = validate_sustainability_content(content)
    accepted_verdicts = {
        VERDICT_STRUCTURALLY_ACCEPTED,
        VERDICT_METHODOLOGY_EXEMPT,
        VERDICT_NO_NEW_TESTS,
    }
    accepted = result.verdict in accepted_verdicts
    _print_verdict_result(
        target, result.verdict, result.detail, json_format, accepted=accepted
    )
    return 0 if accepted else 1


#: The section-content verdicts the metrics mode treats as a structurally-accepted base
#: (the cross-check only runs once the section itself is well formed; a malformed/missing
#: section is rejected BEFORE the git diff, so a heading-only section is
#: `malformed-sustainability-section`, never a silent metrics emission).
_SUSTAINABILITY_ACCEPTED_VERDICTS = frozenset(
    {
        VERDICT_STRUCTURALLY_ACCEPTED,
        VERDICT_METHODOLOGY_EXEMPT,
        VERDICT_NO_NEW_TESTS,
    }
)


#: slice-07 (DDD-4/16C): the top-level verdict the gate emits when a run DECLARES
#: consolidate-on-add (supplies an add-only baseline) but its net test-LOC is NOT below
#: that baseline — the add-only masquerade the counter-gradient unmasks.
VERDICT_CONSOLIDATE_ON_ADD_NOT_REALIZED = "consolidate-on-add-not-realized"

#: slice-09 (DDD-16C/17C): the top-level verdict the gate emits when a run DECLARES
#: the existing-base trend (`--existing-base-trend`) but its existing-base near-duplicate-
#: step ratio is NOT below the prior committed ratio — the existing base regressed.
VERDICT_EXISTING_BASE_DUPLICATION_REGRESSED = "existing-base-duplication-regressed"


def _existing_base_corpus_census(corpus_root: str | None) -> dict[str, int] | None:
    """The near-duplicate-step-group / total-step-def census over the AST step-shape corpus.

    The impure leg behind the existing-base ratio: re-derives the step-shape fact THROUGH the
    CodeFactPort chain (the structural `ast` tier) over the corpus root, never an ad-hoc parse.
    Returns the census mapping when a usable step-shape fact came back; returns None — the LOUD
    "no step-shape fact" signal — when the corpus root is absent OR the chain reports no
    step definitions (empty / unparseable / non-Python corpus). DDD-17C degrade-LOUD: a None
    return drives the existing-base leg to INDETERMINATE, NEVER a fabricated `0.0` ratio.
    """
    if corpus_root is None:
        return None
    root = Path(corpus_root)
    if not root.exists():
        return None

    from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
    from des.ports.code_fact_port import (
        CAPABILITY_STEP_SHAPE_CORPUS,
        CapabilityDescriptor,
    )

    descriptor = CapabilityDescriptor(
        id=CAPABILITY_STEP_SHAPE_CORPUS,
        stability="stable",
        contract_version="1.0.0",
        io_schema="step-shape-corpus/1",
        providing_adapter="ast",
    )
    result = CodeFactChain(root=root).query(descriptor, {})
    if result is None or not isinstance(result.payload, dict):
        return None
    total = result.payload.get("total_step_definitions", 0)
    groups = result.payload.get("near_duplicate_groups", 0)
    if not isinstance(total, int) or not isinstance(groups, int) or total <= 0:
        return None
    return {"near_duplicate_groups": groups, "total_step_definitions": total}


def _classify_existing_base_trend_leg(
    *,
    section_verdict: str,
    corpus_root: str | None,
    prior_existing_base_ratio: float | None,
    metrics: dict[str, object],
    payload: dict[str, object],
) -> tuple[str, str, int]:
    """The slice-09 existing-base near-duplicate-step trend classification leg (DDD-16C/17C).

    Active ONLY when the `--existing-base-trend` MODE flag is present. Re-derives the existing-
    base ratio over the AST step-shape corpus (the impure CodeFactPort leg), classifies its
    trend against the prior committed ratio, mutates `metrics` / `payload` with the ratio cell
    + the `existing_base_trend` cross-check object, and returns the (verdict, detail, exit_code)
    the leg governs:

      * AST step-shape corpus unavailable  -> `indeterminate`, exit 1 (degrade-LOUD; NEVER a
        fabricated `0.0` ratio nor a fabricated downward trend);
      * no prior committed ratio supplied  -> `indeterminate`, exit 1 (the trend denominator
        is absent);
      * ratio < prior  -> `improved`, top verdict stays the section's accepted verdict, exit 0;
      * ratio >= prior -> `regressed`, top verdict `existing-base-duplication-regressed`, exit 1.
    """
    from des.domain.sustainability_metrics import (
        ExistingBaseTrendVerdict,
        classify_existing_base_trend,
        existing_base_duplication_ratio,
    )

    census = _existing_base_corpus_census(corpus_root)
    if census is None:
        payload["existing_base_trend"] = {
            "verdict": ExistingBaseTrendVerdict.INDETERMINATE.value,
            "reason": "the AST step-shape corpus is unavailable (no step-shape fact)",
        }
        return (
            section_verdict,
            (
                "the existing-base trend was requested but its ratio cannot be computed — "
                "the AST step-shape corpus is unavailable (no parseable step definitions); "
                "the check degrades LOUD to indeterminate and refuses to pass, never a "
                "fabricated 0.0 ratio nor a fabricated downward trend"
            ),
            1,
        )

    ratio = existing_base_duplication_ratio(
        census["near_duplicate_groups"], census["total_step_definitions"]
    )
    metrics["existing_base_duplication_ratio"] = ratio
    trend = classify_existing_base_trend(ratio, prior_existing_base_ratio)

    if trend is ExistingBaseTrendVerdict.INDETERMINATE:
        payload["existing_base_trend"] = {
            "verdict": trend.value,
            "reason": "no prior committed existing-base ratio was supplied",
        }
        return (
            section_verdict,
            (
                "the existing-base trend was requested but no prior committed ratio was "
                "supplied (--prior-existing-base-ratio); the prior committed value is the "
                "trend denominator, so the check degrades LOUD to indeterminate and refuses "
                "to pass — never a fabricated downward trend"
            ),
            1,
        )

    payload["existing_base_trend"] = {
        "verdict": trend.value,
        "ratio": ratio,
        "prior_committed_ratio": prior_existing_base_ratio,
    }
    if trend is ExistingBaseTrendVerdict.IMPROVED:
        return (
            section_verdict,
            (
                f"the existing-base near-duplicate-step ratio ({ratio}) is below the prior "
                f"committed ratio ({prior_existing_base_ratio}); the existing base improved "
                f"this run (the active counter-gradient bent the existing-base curve)"
            ),
            0,
        )
    return (
        VERDICT_EXISTING_BASE_DUPLICATION_REGRESSED,
        (
            f"the existing-base near-duplicate-step ratio ({ratio}) is not below the prior "
            f"committed ratio ({prior_existing_base_ratio}) — the existing base regressed; "
            f"the downward-trend gate (DDD-16C) rejects the run"
        ),
        1,
    )


def _classify_consolidate_on_add_leg(
    *,
    section_verdict: str,
    delta: TestLocDelta | GitDiffUnavailable,
    add_only_baseline_loc: int | None,
    metrics: dict[str, object],
    payload: dict[str, object],
) -> tuple[str, str, int]:
    """The slice-07 consolidate-on-add (add-AND-improve) classification leg.

    Active ONLY when the `--consolidate-on-add` MODE flag is present. Mutates `metrics` /
    `payload` with the consolidate-on-add cells + cross-check object and returns the
    (verdict, detail, exit_code) the leg governs:

      * git diff unavailable OR no add-only baseline supplied -> `indeterminate` (the gain's
        denominator is absent), degrade-LOUD, exit 1, NEVER the plain-trend accept;
      * gain < 0  -> `realized`, top verdict stays the section's accepted verdict, exit 0;
      * gain >= 0 -> `not-realized`, top verdict `consolidate-on-add-not-realized`, exit 1.
    """
    from des.domain.sustainability_metrics import (
        ConsolidateOnAddVerdict,
        GitDiffUnavailable,
        classify_consolidate_on_add,
        consolidate_on_add_gain,
    )

    if isinstance(delta, GitDiffUnavailable) or add_only_baseline_loc is None:
        reason = (
            "the git-diff supplied no run net test-LOC"
            if isinstance(delta, GitDiffUnavailable)
            else "no add-only baseline was supplied (--add-only-baseline-loc)"
        )
        payload["consolidate_on_add"] = {
            "verdict": ConsolidateOnAddVerdict.INDETERMINATE.value,
            "reason": reason,
        }
        return (
            section_verdict,
            (
                f"consolidate-on-add was requested but its gain cannot be computed "
                f"({reason}); the add-only baseline is the denominator, so the check "
                f"degrades LOUD to indeterminate and refuses to pass — never a fabricated "
                f"realized"
            ),
            1,
        )

    gain = consolidate_on_add_gain(delta.net, add_only_baseline_loc)
    coa = classify_consolidate_on_add(gain)
    metrics["consolidate_on_add_gain_loc"] = gain.loc
    payload["consolidate_on_add"] = {"verdict": coa.value, "gain_loc": gain.loc}
    if coa is ConsolidateOnAddVerdict.REALIZED:
        return (
            section_verdict,
            (
                f"the run's net test-LOC ({delta.net}) is below the add-only baseline "
                f"({add_only_baseline_loc}); the add-AND-improve is realized "
                f"(gain {gain.loc})"
            ),
            0,
        )
    return (
        VERDICT_CONSOLIDATE_ON_ADD_NOT_REALIZED,
        (
            f"the section declares consolidate-on-add but the run's net test-LOC "
            f"({delta.net}) is not below the add-only baseline "
            f"({add_only_baseline_loc}) — the add-AND-improve claim is unmasked as "
            f"an add-only masquerade (gain {gain.loc})"
        ),
        1,
    )


def _run_require_sustainability_with_metrics(
    target: Path,
    json_format: bool,
    consolidate_on_add: bool = False,
    add_only_baseline_loc: int | None = None,
    existing_base_trend: bool = False,
    prior_existing_base_ratio: float | None = None,
    corpus_root: str | None = None,
) -> int:
    """Run the BALANCED-DENOMINATOR metrics + blind-add cross-check (slice-04, DDD-4/5/10).

    EXTENDS the slice-03 content gate: validates the section FIRST (a malformed/missing
    section is rejected before the git diff — `malformed-sustainability-section` for a
    heading-only section), then attaches the A+C `metrics` evidence cells and the
    `blind_add` git-diff cross-check to the JSON verdict.

    Verdict + exit (DDD-5 advisory-LOUD, trend non-regression, no absolute cliff):
      * blind-add unmasked   -> top-level `blind-add-detected`, exit 1;
      * git-diff indeterminate -> keep the section verdict, exit 1 (degrade-LOUD;
        NEVER a fabricated pass — git is not a hard dependency, DDD-4);
      * consistent on trend  -> the section's accepted verdict, exit 0.

    slice-07 consolidate-on-add (add-AND-improve) leg — ACTIVE only when the explicit
    `--consolidate-on-add` MODE flag is present (DISTINCT from the `--add-only-baseline-loc`
    VALUE, the design-defect FIX). A plain `--with-metrics` run NEVER routes through this leg,
    so the slice-04 accept-on-trend path is byte-stable. When the mode is active the routing,
    over the (baseline-supplied?, gain) space, is:
      * baseline supplied, gain < 0  -> `consolidate_on_add.verdict="realized"`; the top
        verdict stays the section's accepted verdict, exit 0;
      * baseline supplied, gain >= 0 -> `consolidate_on_add.verdict="not-realized"`; top
        verdict `consolidate-on-add-not-realized`, exit 1 (the add-only masquerade);
      * NO baseline supplied         -> `consolidate_on_add.verdict="indeterminate"`,
        degrade-LOUD, exit 1 — the add-only baseline is the denominator of the gain; with no
        denominator the gate refuses to decide, NEVER falling back to the plain-trend accept
        (DDD-4 / DDD-10). Reuses the same INDETERMINATE handling when the git diff itself is
        unavailable (no run net-LOC to compare).
    The consolidate-on-add classification takes precedence over the blind-add leg for the top
    verdict when the mode is active (the run is declaring add-AND-improve).

    Effect isolation (DDD-10): the pure core (`adoption_ratio`, `classify_blind_add`,
    `consolidate_on_add_gain`) computes the cells; the git diff (unbounded-preservation
    read) is delegated to `GitTestLocDiffAdapter` against the feature-delta's own directory.
    """
    content = target.read_text(encoding="utf-8")
    section = validate_sustainability_content(content)
    if section.verdict not in _SUSTAINABILITY_ACCEPTED_VERDICTS:
        _print_verdict_result(
            target, section.verdict, section.detail, json_format, accepted=False
        )
        return 1

    from des.adapters.driven.git.git_test_loc_diff_adapter import GitTestLocDiffAdapter
    from des.domain.sustainability_metrics import (
        BlindAddVerdict,
        GitDiffUnavailable,
        adoption_ratio,
        classify_blind_add,
    )

    decisions = sustainability_decisions(content)
    delta = GitTestLocDiffAdapter().test_loc_delta(target.parent)
    blind_add = classify_blind_add(decisions, delta)

    metrics: dict[str, object] = {"adoption_ratio": adoption_ratio(decisions)}
    if isinstance(delta, GitDiffUnavailable):
        blind_add_payload: dict[str, object] = {
            "verdict": blind_add.value,
            "reason": delta.reason,
        }
    else:
        metrics["consolidation_delta_loc"] = delta.net
        blind_add_payload = {"verdict": blind_add.value, "net_test_loc": delta.net}

    if blind_add is BlindAddVerdict.BLIND_ADD:
        verdict, detail, exit_code = (
            VERDICT_BLIND_ADD_DETECTED,
            (
                "the section claims consolidation/reuse but the git diff shows a net "
                f"test-LOC increase ({blind_add_payload.get('net_test_loc')}) — "
                "the claim is unmasked as a blind add"
            ),
            1,
        )
    elif blind_add is BlindAddVerdict.INDETERMINATE:
        verdict, detail, exit_code = (
            section.verdict,
            (
                "the git-diff blind-add cross-check could not run "
                f"({blind_add_payload.get('reason')}); the check degrades LOUD to an "
                "indeterminate cross-check and refuses to pass — git is not a hard "
                "dependency, an absent diff is never a fabricated pass"
            ),
            1,
        )
    else:
        verdict, detail, exit_code = section.verdict, section.detail, 0

    payload: dict[str, object] = {
        "verdict": verdict,
        "detail": detail,
        "metrics": metrics,
        "blind_add": blind_add_payload,
    }

    if consolidate_on_add:
        # The coa classification takes PRECEDENCE over the blind-add leg for the top
        # verdict when the mode is active (the run is declaring add-AND-improve) — write
        # the leg's result back so it overrides any blind-add top verdict already set.
        verdict, detail, exit_code = _classify_consolidate_on_add_leg(
            section_verdict=section.verdict,
            delta=delta,
            add_only_baseline_loc=add_only_baseline_loc,
            metrics=metrics,
            payload=payload,
        )
        payload["verdict"] = verdict
        payload["detail"] = detail

    if existing_base_trend:
        # The existing-base near-duplicate-step trend leg (slice-09, DDD-16C/17C) — ACTIVE
        # only on the explicit `--existing-base-trend` MODE flag (DISTINCT from the
        # `--prior-existing-base-ratio` VALUE + from `--consolidate-on-add`). A plain
        # `--with-metrics` / `--consolidate-on-add` run NEVER routes through it, so the
        # slice-04/07 paths are byte-stable.
        verdict, detail, exit_code = _classify_existing_base_trend_leg(
            section_verdict=verdict,
            corpus_root=corpus_root,
            prior_existing_base_ratio=prior_existing_base_ratio,
            metrics=metrics,
            payload=payload,
        )
        payload["verdict"] = verdict
        payload["detail"] = detail

    suffix, extra = _routing_suffix(target, accepted=exit_code == 0)
    payload.update(extra)
    if json_format:
        print(json.dumps(payload))
    else:
        print(f"{verdict}: {detail}{suffix}")
    return exit_code


# src/des/cli/<this file> -> parents[3] = REPO_ROOT (the waves-dir anchor).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"


def _emit_boundary_verdict(target: Path, wave: str, json_format: bool) -> int:
    """Emit the slice-05 fail-closed boundary verdict for an unreadable registry.

    Discriminates by the canonical-wave universe (the `None` return alone cannot):
    a non-canonical `<wave>` is `unknown-wave` (REJECT); a canonical `<wave>` whose
    registry is unreadable is `indeterminate` (degrade-LOUD). Never `accepted`,
    never a crash. The JSON shape mirrors the happy-path envelope; the AT reads the
    structured `verdict` token, never a free-text substring.
    """
    if wave.upper() in _CANONICAL_WAVE_NAMES:
        verdict = VERDICT_INDETERMINATE
        detail = (
            f"the wave registry for the known wave {wave!r} is unreadable "
            f"(absent / garbled); the check refuses to decide and degrades LOUD to "
            f"indeterminate — a missing/garbled registry is never a silent green"
        )
    else:
        verdict = VERDICT_UNKNOWN_WAVE
        detail = (
            f"the wave {wave!r} is not a canonical nWave wave "
            f"({sorted(_CANONICAL_WAVE_NAMES)}); the registry never declared it — "
            f"a deterministic refusal, not a guess"
        )
    _print_verdict_result(target, verdict, detail, json_format, accepted=False)
    return 1


def _run_require_registry_sections(
    target: Path, wave: str, waves_dir: Path, json_format: bool
) -> int:
    """Run the registry-backed [REF]-section check (algebra-projections-enforced
    slice-01, ADR-001 D1/D3; slice-05 fail-closed boundary DA-5 / DD-A5).

    Wires the additive driving surface (`--require-registry-sections <wave>
    [--waves-dir <dir>]`) to the live-registry reader + the pure direction-(a)
    classifier: a feature-delta `## Wave: <W> / [REF] <S>` section whose `<S>` is
    not in the wave's `output_contract.ref_sections` is REJECTED
    (`undeclared-section`, naming the section); a feature-delta whose sections are
    all declared is ACCEPTED. The emitted JSON shape
    (`{"verdict": <token>, "detail": <str>}`) mirrors the sibling `--require-*`
    modes; the AT reads the structured `verdict` token.

    The fail-closed boundary (slice-05): when the registry is unreadable the check
    degrades into a TYPED verdict — never `accepted`, never a crash —
    discriminated by the canonical-wave universe (`_CANONICAL_WAVE_NAMES`), since a
    `None` return alone cannot tell an unknown wave from a known wave's missing
    registry:
      * `<wave>` ∉ canonical universe -> `unknown-wave` (deterministic REJECT);
      * `<wave>` ∈ canonical universe + unreadable registry -> `indeterminate`
        (degrade-LOUD; reuses the §17 `GateVerdict.INDETERMINATE` token).
    """
    content = target.read_text(encoding="utf-8")
    contract = read_wave_output_contract(wave, waves_dir)
    if contract is None:
        return _emit_boundary_verdict(target, wave, json_format)
    # DISTILL-DETECTED DESIGN-DEFECT (slice-02, NOT wired): direction (b)
    # (`missing_registry_sections`) CANNOT compose onto this shared
    # `--require-registry-sections <wave>` surface without regressing slice-01.
    # slice-01 ATs assert `accepted` for PARTIAL deltas (3-of-12 / 1-of-12
    # mandatory sections present); slice-02's direction-(b) AT asserts
    # `missing-mandatory-section` for a NEAR-COMPLETE delta (11-of-12). A single
    # bidirectional classifier on this one surface (DD-A4) uniformly rejects the
    # slice-01 partial deltas it must accept — the two AT sets contradict on the
    # SAME public surface with NO discriminating flag/signal. Wiring direction (b)
    # is BLOCKED on a DESIGN disposition (see distill/red-classification.md). Until
    # resolved, this surface stays direction-(a)-only (slice-01 byte-stable).
    result = classify_registry_sections(content, contract)
    accepted = result.verdict == VERDICT_REGISTRY_SECTIONS_ACCEPTED
    _print_verdict_result(
        target, result.verdict, result.detail, json_format, accepted=accepted
    )
    return 0 if accepted else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `des validate-feature-delta [flags] <path-to-feature-delta.md>`.

    Args:
        argv: optional argument list (defaults to `sys.argv[1:]`).

    Returns:
        0 on success, 1 on any malformed heading / malformed slice plan /
        malformed reuse analysis / malformed registry sections / I/O error.
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
    if parsed.require_feature_plan:
        return _run_require_feature_plan(target, parsed.json_format)
    if parsed.require_reuse_analysis:
        return _run_require_reuse_analysis(target, parsed.json_format)
    if parsed.require_sustainability:
        if parsed.with_metrics:
            return _run_require_sustainability_with_metrics(
                target,
                parsed.json_format,
                parsed.consolidate_on_add,
                parsed.add_only_baseline_loc,
                parsed.existing_base_trend,
                parsed.prior_existing_base_ratio,
                parsed.corpus_root,
            )
        return _run_require_sustainability(target, parsed.json_format)
    if parsed.require_registry_sections is not None:
        waves_dir = (
            Path(parsed.waves_dir) if parsed.waves_dir is not None else _WAVES_DIR
        )
        return _run_require_registry_sections(
            target,
            parsed.require_registry_sections,
            waves_dir,
            parsed.json_format,
        )
    return _run_plain(target)


if __name__ == "__main__":
    raise SystemExit(main())
