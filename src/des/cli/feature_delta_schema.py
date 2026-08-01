"""feature_delta_schema — the feature-delta section-schema algebra.

OSS realization of ADR-FLOW-007 / flow-v2-design.md §S: the feature-delta defined
EXPLICITLY as a typed 5-constructor `SectionType` algebra + a `consumed_by`-routed
section registry + THREE total pure projections.

The feature-delta is ONE typed value — a closed five-constructor sum
(`SectionType = KeyedBlock | Table | Prose | RefList | Composite`) plus an ordered
`FEATURE_DELTA_SCHEMA` registry mapping each `section_id` to its constructor and
the waves that consume it. The three consumers are TOTAL PURE projections derived
from that one value, so a section is authored once and consumed three ways with
zero drift (OUT is IN):

- P1 `gate_verify`     — fail-closed validation (PASS / FAIL(named) / INDETERMINATE)
- P2 `wave_injection`  — pure filter on `consumed_by`
- P3 `output_contract` — the write spec for a section

evolution-plan P1.4 adds a FOURTH consumer — P4 `project_for_role` — a role-scoped
markdown projection (`crafter | examiner | atd`) so an agent consumes a lean SLICE
of the one SSOT feature-delta instead of the whole document (~8x full-delta reads
per feature, measured). The Reuse Analysis rows are MANDATORY, NON-PROJECTABLE-AWAY
for the crafter role (Ale 2026-07-03: "il crafter spesso crea codice alternativo e
viola SSOT") — a crafter projection that would drop them is REFUSED loud rather than
silently shipped slim, because that is exactly the anti-SSOT-duplication guardrail
the crafter must see.

OSS invariant (F-D-09): `des.*` imports + stdlib only; NO `import yaml`; NO
sequencer/engine. The projections REUSE the shipped validators in
`des.cli.validate_feature_delta` — they do NOT re-implement Table validation.

CLI contract (driving port): `des feature-delta-schema
{describe,verify,inject,contract,project}`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from des.cli.validate_feature_delta import (
    _SLICE_PLAN_HEADING_RE,
    REUSE_ANALYSIS_COLUMNS,
    REUSE_ANALYSIS_HEADING,
    SLICE_PLAN_COLUMNS,
    SUSTAINABILITY_HEADING,
    VERDICT_ACCEPTED,
    VERDICT_MALFORMED_REUSE_ANALYSIS,
    VERDICT_MISSING_REUSE_ANALYSIS,
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNJUSTIFIED_CREATE_NEW,
    _is_separator_row,
    _parse_table_cells,
    _plan_table_rows,
    validate_reuse_analysis_content,
    validate_slice_plan_content,
)
from des.domain.gate_outcome import GateVerdict


__SCAFFOLD__ = False


# ---------------------------------------------------------------------------
# §S.1 — closed section-type algebra (5 constructors).
#
# `SectionType = KeyedBlock | Table | Prose | RefList | Composite`. The set is
# CLOSED; every registered section maps to EXACTLY ONE constructor
# (make-illegal-states-unrepresentable). The constructors are frozen dataclasses
# carrying their own shape data — `Table` its locked column header, `Composite`
# its ordered Table sub-blocks — so a section's verification contract lives IN
# the value, not in a branch on section identity.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionType:
    """Closed sum base — the five constructors below are its only members."""


@dataclass(frozen=True)
class KeyedBlock(SectionType):
    """A `key: value` block section (e.g. a manifest-style header)."""


@dataclass(frozen=True)
class Table(SectionType):
    """A GFM table whose header columns are byte-locked, in fixed order."""

    columns: tuple[str, ...]


@dataclass(frozen=True)
class Prose(SectionType):
    """A free-text prose section (no structural contract)."""


@dataclass(frozen=True)
class RefList(SectionType):
    """A bullet list of `- <key>: <ref>,...` reference lines."""


@dataclass(frozen=True)
class Composite(SectionType):
    """A recursive AND-of-sub-blocks — an ordered tuple of named Table sub-blocks.

    The convergence `architecture-and-contract-tests` section is the sole
    instance: two byte-locked Table sub-blocks (Contract-Tests, Architecture-
    Tests) whose columns must NOT change (cross-tier lock with SF).
    """

    sub_blocks: tuple[tuple[str, Table], ...]


def section_type_constructors() -> tuple[type, ...]:
    """Return the closed set of `SectionType` constructors (exactly five)."""
    return (KeyedBlock, Table, Prose, RefList, Composite)


# ---------------------------------------------------------------------------
# §S.3 — the section registry (routing-as-data).
#
# The registry is a value: an ordered tuple of `SectionEntry`, each carrying its
# `section_id`, the `section_type` constructor INSTANCE it maps to, its heading
# literal, and the `consumed_by` set of waves (kebab-lowercase ⊆ the eight
# waves). No projection branches on section identity — each reads the registry.
# ---------------------------------------------------------------------------

#: The eight waves a section's `consumed_by` may contain (§S.3, kebab-lowercase).
WAVES: frozenset[str] = frozenset(
    {
        "discover",
        "diverge",
        "discuss",
        "design",
        "devops",
        "distill",
        "deliver",
        "review",
    }
)


@dataclass(frozen=True)
class SectionEntry:
    """One registry row: a section's id, type, heading, and consuming waves."""

    section_id: str
    section_type: SectionType
    heading: str
    consumed_by: frozenset[str]


#: The convergence Composite's two byte-locked Table sub-blocks (§S.5). The
#: column tuples are byte-identical with SF — do NOT change.
_CONTRACT_TESTS_TABLE = Table(
    columns=(
        "Component/AT-target",
        "Contract-shape",
        "Universe",
        "Assertion-mechanism",
        "Consumed-by",
    )
)
_ARCHITECTURE_TESTS_TABLE = Table(
    columns=(
        "Invariant",
        "AST-query-or-probe",
        "Enforcement-layer",
        "Consumed-by",
    )
)

#: Definition-of-Done heading literal — reused by both the registry entry and the
#: P4 role-projection extractor (single seam, no per-consumer duplicate literal).
_DEFINITION_OF_DONE_HEADING = "## Wave: DISCUSS / [REF] Definition of Done"

#: DESIGN Decisions heading literal — same single-seam reuse as above.
_DESIGN_DECISIONS_HEADING = "## Wave: DESIGN / [REF] Decisions"


#: The ordered section registry — the ONE typed feature-delta value (§S.3). Every
#: entry maps to exactly one constructor instance; every `consumed_by` token is a
#: kebab-lowercase wave from `WAVES`.
FEATURE_DELTA_SCHEMA: tuple[SectionEntry, ...] = (
    SectionEntry(
        section_id="slice-plan",
        section_type=Table(columns=SLICE_PLAN_COLUMNS),
        heading="## Wave: DISCUSS / [REF] Slice Plan",
        consumed_by=frozenset({"discuss", "distill", "deliver"}),
    ),
    SectionEntry(
        section_id="reuse-analysis",
        section_type=Table(columns=REUSE_ANALYSIS_COLUMNS),
        heading="## Reuse Analysis",
        consumed_by=frozenset({"design", "distill", "deliver"}),
    ),
    SectionEntry(
        section_id="architecture-and-contract-tests",
        section_type=Composite(
            sub_blocks=(
                ("Contract-Tests", _CONTRACT_TESTS_TABLE),
                ("Architecture-Tests", _ARCHITECTURE_TESTS_TABLE),
            )
        ),
        heading="## Wave: DESIGN / [REF] Architecture & Contract Tests",
        consumed_by=frozenset({"design", "distill", "deliver", "review"}),
    ),
    SectionEntry(
        section_id="adr-refs",
        section_type=RefList(),
        heading="## Wave: DESIGN / [REF] ADR Refs",
        consumed_by=frozenset({"design", "deliver"}),
    ),
    # --- evolution-plan P1.4: three ADDITIVE entries backing the P4 role
    # projection. Each is a no-op in gate_verify (Table/Prose section_ids other
    # than "slice-plan"/"reuse-analysis" fall through `_verify_table` unchanged;
    # ADD-not-mutate, zero behavior change for P1-P3 or the existing test suite.
    SectionEntry(
        section_id="definition-of-done",
        section_type=Prose(),
        heading=_DEFINITION_OF_DONE_HEADING,
        consumed_by=frozenset({"discuss", "distill", "deliver"}),
    ),
    SectionEntry(
        section_id="design-decisions",
        section_type=Table(columns=("ID", "Decision", "Rationale")),
        heading=_DESIGN_DECISIONS_HEADING,
        consumed_by=frozenset({"design", "distill", "deliver"}),
    ),
    SectionEntry(
        section_id="test-reuse-analysis",
        section_type=Prose(),
        heading=SUSTAINABILITY_HEADING,
        consumed_by=frozenset({"distill", "deliver"}),
    ),
)


def _section_name(entry: SectionEntry) -> str:
    """The human-readable section name carried in a FAIL verdict.

    The portion of the heading literal after the schema `[TYPE]` token (or the
    whole heading text for a bare `##` heading). For the convergence section this
    yields `Architecture & Contract Tests`; for the slice plan, `Slice Plan`.
    """
    tail = entry.heading.split("]", 1)[-1].strip()
    return tail if tail else entry.heading.lstrip("# ").strip()


# ---------------------------------------------------------------------------
# §S.4 — the three total pure projections.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyVerdict:
    """The outcome of P1 gate_verify — a fail-closed verdict + diagnostic.

    `verdict` is a shipped `GateVerdict` (no new verdict introduced); `detail`
    names the offending section on FAIL / the cause on INDETERMINATE.
    """

    verdict: GateVerdict
    detail: str


def _verify_table(entry: SectionEntry, content: str) -> VerifyVerdict | None:
    """Validate one Table section, delegating to the shipped validators. Pure.

    Returns a FAIL `VerifyVerdict` naming the section on a column/structure
    violation, or `None` when the section is well formed (or absent — absence is
    not this projection's concern; a required-section check is a separate gate).
    The slice-plan and reuse-analysis tables reuse `validate_slice_plan_content`
    / `validate_reuse_analysis_content` verbatim (REUSE, no re-implementation).
    """
    if entry.section_id == "slice-plan":
        plan_result = validate_slice_plan_content(content)
        if plan_result.verdict != VERDICT_ACCEPTED and "Slice Plan" in content:
            return VerifyVerdict(
                GateVerdict.FAIL,
                f"{_section_name(entry)}: {plan_result.detail}",
            )
        return None
    if entry.section_id == "reuse-analysis":
        reuse_result = validate_reuse_analysis_content(content)
        if (
            reuse_result.verdict != VERDICT_STRUCTURALLY_ACCEPTED
            and "Reuse Analysis" in content
        ):
            return VerifyVerdict(
                GateVerdict.FAIL,
                f"{_section_name(entry)}: {reuse_result.detail}",
            )
        return None
    return None


def _sub_block_rows(content: str, sub_heading: str) -> list[str]:
    """Extract the GFM table rows beneath a `### <sub_heading>` heading. Pure."""
    lines = content.splitlines()
    start = None
    target = f"### {sub_heading}"
    for idx, line in enumerate(lines):
        if line.strip() == target:
            start = idx + 1
            break
    if start is None:
        return []
    rows: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#"):
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


def _verify_composite(entry: SectionEntry, content: str) -> VerifyVerdict | None:
    """Validate a Composite section's byte-locked Table sub-blocks. Pure.

    Each sub-block's header columns must equal the locked tuple in fixed order.
    A reordered or wrong-count header is a FAIL naming the composite section. The
    section is only checked when its heading is present (absence is out of scope).
    """
    if entry.heading not in content:
        return None
    assert isinstance(entry.section_type, Composite)
    for sub_heading, table in entry.section_type.sub_blocks:
        rows = _sub_block_rows(content, sub_heading)
        if not rows:
            return VerifyVerdict(
                GateVerdict.FAIL,
                f"{_section_name(entry)}: missing '{sub_heading}' sub-table",
            )
        header_cells = tuple(_parse_table_cells(rows[0]))
        if header_cells != table.columns:
            return VerifyVerdict(
                GateVerdict.FAIL,
                (
                    f"{_section_name(entry)}: {sub_heading} columns "
                    f"{list(header_cells)} do not match the byte-locked header "
                    f"{list(table.columns)}"
                ),
            )
    return None


def gate_verify(schema: tuple[SectionEntry, ...], content: str) -> VerifyVerdict:
    """P1 — fail-closed validation of `content` against `schema`. Total, pure.

    Walks the registry once, dispatching per `section_type`: Table sections
    delegate to the shipped validators; the Composite section checks its
    byte-locked sub-tables. Returns the first FAIL (naming the offending
    section), or PASS when every checked section is well formed. Never an
    authorizing-YES-on-error: an undecodable document yields INDETERMINATE via
    `gate_verify_bytes`, never a silent pass (Invariant 1/2).
    """
    for entry in schema:
        section_type = entry.section_type
        if isinstance(section_type, Composite):
            verdict = _verify_composite(entry, content)
        elif isinstance(section_type, Table):
            verdict = _verify_table(entry, content)
        else:  # KeyedBlock | Prose | RefList — no structural lock to enforce.
            verdict = None
        if verdict is not None:
            return verdict
    return VerifyVerdict(GateVerdict.PASS, "every checked section is well formed")


def gate_verify_bytes(schema: tuple[SectionEntry, ...], raw: bytes) -> VerifyVerdict:
    """P1 boundary — decode `raw` then `gate_verify`; INDETERMINATE on bad bytes.

    Degrade-LOUD: a document that cannot be decoded as UTF-8 is INDETERMINATE
    (a refusal-to-decide), never a fabricated PASS.
    """
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return VerifyVerdict(
            GateVerdict.INDETERMINATE,
            f"document could not be decoded as UTF-8: {exc}",
        )
    return gate_verify(schema, content)


def wave_injection(schema: tuple[SectionEntry, ...], wave: str) -> list[SectionEntry]:
    """P2 — pure filter: the entries whose `consumed_by` contains `wave`. Total.

    A pure registry filter — its output is a function of (schema, wave) ALONE
    (L2 section-independence: no dependency on any document body). Returns the
    empty list for a wave that consumes nothing (e.g. `discover`).
    """
    return [entry for entry in schema if wave in entry.consumed_by]


@dataclass(frozen=True)
class SectionWriteSpec:
    """The output contract (P3) for emitting a section — its heading + shape."""

    section_id: str
    heading: str
    section_type: SectionType


def output_contract(
    schema: tuple[SectionEntry, ...], section_id: str
) -> SectionWriteSpec | None:
    """P3 — the write spec for `section_id`. Pure.

    Returns the `SectionWriteSpec` (carrying the section's heading literal + its
    type) for the registered `section_id`, or `None` when no entry matches.
    P1 ∘ P3 is the OUT≡IN seal at document granularity.
    """
    for entry in schema:
        if entry.section_id == section_id:
            return SectionWriteSpec(
                section_id=entry.section_id,
                heading=entry.heading,
                section_type=entry.section_type,
            )
    return None


# ---------------------------------------------------------------------------
# §S.5 — P4 `project_for_role`: role-scoped markdown projections
# (evolution-plan P1.4). SSOT stays the ONE feature-delta.md; this is a pure
# READ projection, never a second authoring surface.
#
# Roles v1:
#   - crafter  — value statement + DoD rows + Reuse Analysis rows (MANDATORY,
#                cannot be projected away) + Design Decisions table.
#   - examiner — ONLY the value statement + spec-row refs (deliberately the
#                leanest — its ignorance of implementation detail is its value).
#   - atd      — value statement + DoD + Design Decisions + Test-Reuse section.
# ---------------------------------------------------------------------------

#: The closed role vocabulary (v1). An unrecognized role is a USAGE error at the
#: CLI shell (exit 1) — never silently defaulted to a role.
ROLES: frozenset[str] = frozenset({"crafter", "examiner", "atd"})

#: A `**Label**: value` preamble metadata line (e.g. `**Backlog**: ...`,
#: `**Design ADR**: ...`) — the "spec-row refs" the leanest (examiner) role
#: carries instead of any implementation section.
_SPEC_REF_LINE_RE = re.compile(r"^\*\*[A-Za-z][A-Za-z0-9 \-]*\*\*:\s*.+")


class ProjectionRefusal(Exception):
    """Raised by `project_for_role` when a required section is absent/malformed.

    Carries a structured (what, why, how) triple so the CLI shell prints a
    self-explaining refusal (every failure explains what/why/how — never a bare
    non-zero exit).
    """

    def __init__(self, what: str, why: str, how: str) -> None:
        super().__init__(what)
        self.what = what
        self.why = why
        self.how = how


@dataclass(frozen=True)
class RoleProjection:
    """The rendered P4 projection + its size accounting. Pure value."""

    role: str
    slice_id: str
    source: str
    markdown: str
    full_chars: int
    full_words: int
    projected_chars: int
    projected_words: int


#: A wave-tagged section heading `## Wave: <WAVE> / [REF] <core>` — the
#: authoring convention (lean-wave-documentation D2). Capturing group = the
#: bare section name so a wave-tagged heading and a bare one compare equal.
_WAVE_TAGGED_HEADING_RE = re.compile(
    r"^#{2,4}\s+Wave:\s+\w+\s+/\s+\[REF\]\s+(?P<core>.+?)\s*$"
)
#: A bare section heading `## <core>` — the form several gate literals use.
_BARE_HEADING_RE = re.compile(r"^#{2,4}\s+(?P<core>.+?)\s*$")


def _heading_core(heading: str) -> str:
    """The bare section name, with any `Wave: <W> / [REF]` prefix stripped."""
    stripped = heading.rstrip()
    m = _WAVE_TAGGED_HEADING_RE.match(stripped) or _BARE_HEADING_RE.match(stripped)
    return m.group("core") if m else stripped


def _heading_matches(line: str, heading_literal: str) -> bool:
    """True when `line` IS the section `heading_literal` names, in EITHER the
    bare (`## Reuse Analysis`) or the wave-tagged
    (`## Wave: DESIGN / [REF] Reuse Analysis`) form.

    heading-SSOT unification (velocity-fix, 2026-07-05): the authoring skills
    emit the wave-tagged `## Wave: <W> / [REF] <core>` form while several gate
    literals here are bare `## <core>` — two independent definitions of the
    same heading that drifted, so a correctly-authored section was rejected on
    grammar alone. This matcher accepts the two forms interchangeably
    (ADD-not-mutate: the exact bare literal still matches; the wave-tagged
    variant of the SAME core name now also matches) so the two sides can never
    disagree on heading grammar. Match is by core-name equality, so an
    unrelated section (`## Out of scope`) never matches `## Reuse Analysis`.
    """
    stripped = line.rstrip()
    if stripped == heading_literal:
        return True
    m = _WAVE_TAGGED_HEADING_RE.match(stripped) or _BARE_HEADING_RE.match(stripped)
    return m is not None and m.group("core") == _heading_core(heading_literal)


def _section_body(content: str, heading_literal: str) -> str | None:
    """The raw text block beneath `heading_literal`, up to the next `##`
    heading (exclusive). Pure. Generic section-body extractor — the ONE seam
    every role projection reuses (no per-role/per-section parser).

    Heading match accepts the bare and wave-tagged forms interchangeably
    (`_heading_matches`, heading-SSOT unification) so authoring convention and
    gate never disagree on grammar."""
    lines = content.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if _heading_matches(line, heading_literal):
            start = idx + 1
            break
    if start is None:
        return None
    body_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("##"):
            break
        body_lines.append(line)
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return "\n".join(body_lines)


def _slice_plan_row(content: str, slice_id: str) -> dict[str, str] | None:
    """The single Slice Plan row for `slice_id` as a column->cell dict. Pure.

    Reuses `_plan_table_rows` + `_parse_table_cells` + `_is_separator_row`
    (validate_feature_delta) — no parallel table parser.
    """
    rows = _plan_table_rows(content, _SLICE_PLAN_HEADING_RE)
    if not rows:
        return None
    header = _parse_table_cells(rows[0])
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        cells = _parse_table_cells(row)
        if cells and cells[0].strip().lower() == slice_id.strip().lower():
            return dict(zip(header, cells, strict=False))
    return None


def _dod_lines_for_slice(content: str, slice_id: str) -> list[str] | None:
    """The Definition-of-Done bullets scoped to `slice_id`. Pure.

    Filters the DoD section's bullet lines to those mentioning `slice_id`; when
    no bullet is slice-annotated (a feature-wide DoD), returns every bullet —
    never a silent empty projection when the section genuinely has content.
    Returns None only when the DoD section itself is absent.
    """
    body = _section_body(content, _DEFINITION_OF_DONE_HEADING)
    if body is None:
        return None
    bullets = [line for line in body.splitlines() if line.strip().startswith("-")]
    scoped = [line for line in bullets if slice_id.lower() in line.lower()]
    return scoped if scoped else bullets


def _spec_row_refs(content: str) -> list[str]:
    """The preamble `**Label**: value` metadata lines (before the first `##`
    heading). Pure. The examiner role's "spec-row refs" — pointers to the
    backlog/ADR/spec provenance, deliberately without any design/reuse detail.
    """
    refs: list[str] = []
    for line in content.splitlines():
        if line.startswith("##"):
            break
        stripped = line.strip()
        if _SPEC_REF_LINE_RE.match(stripped):
            refs.append(stripped)
    return refs


#: Reuse Analysis verdicts under which the section is either well formed or
#: honestly exempt — safe to include in a crafter projection. Any OTHER verdict
#: (malformed / unjustified-create-new / missing) is a refusal: the crafter
#: mandate is that these rows are NON-PROJECTABLE-AWAY, so a source that cannot
#: be honestly parsed must never ship a silently slimmed projection.
_REUSE_ANALYSIS_SAFE_VERDICTS = frozenset(
    {
        VERDICT_STRUCTURALLY_ACCEPTED,
        "methodology-exempt",
        "no-overlap-declared",
    }
)


def _mandatory_reuse_analysis_block(content: str, source: str) -> str:
    """The Reuse Analysis section body for the crafter role, or a loud refusal.

    REUSES `validate_reuse_analysis_content` verbatim (no re-implementation).
    Malformed, unjustified-create-new, or wholly absent Reuse Analysis all
    raise `ProjectionRefusal` — this section can NEVER be silently dropped or
    slimmed away for the crafter role (Ale 2026-07-03 SSOT-duplication guard).
    """
    result = validate_reuse_analysis_content(content)
    if result.verdict not in _REUSE_ANALYSIS_SAFE_VERDICTS:
        malformed = result.verdict in (
            VERDICT_MALFORMED_REUSE_ANALYSIS,
            VERDICT_UNJUSTIFIED_CREATE_NEW,
        )
        missing = result.verdict == VERDICT_MISSING_REUSE_ANALYSIS
        what = (
            "Reuse Analysis section is malformed and cannot be safely projected"
            if malformed
            else "Reuse Analysis section is absent"
            if missing
            else f"Reuse Analysis section verdict is {result.verdict!r}"
        )
        raise ProjectionRefusal(
            what=what,
            why=f"{result.detail} (source: {source})",
            how=(
                "add the '## Reuse Analysis' heading -- it is required either "
                "way, the parser only ever looks beneath it. Under it, put "
                "the DDD-8 five-column table, or a Reuse-Analysis: "
                "methodology-exempt/no-overlap marker (the marker alone, "
                "with no heading above it, is refused) -- before projecting "
                "for the crafter role, this section is MANDATORY and can "
                "never be projected away"
            ),
        )
    body = _section_body(content, REUSE_ANALYSIS_HEADING)
    return body if body else result.detail


def project_for_role(
    content: str, role: str, slice_id: str, source: str
) -> RoleProjection:
    """P4 — the role-scoped markdown projection. Pure (raises on refusal).

    `role` MUST already be validated against `ROLES` by the caller (the CLI
    shell treats an unknown role as a usage error, exit 1); this function
    still defends against a bad role via `ProjectionRefusal` so a direct
    caller (e.g. a test) gets the same loud what/why/how.
    """
    if role not in ROLES:
        raise ProjectionRefusal(
            what=f"unknown role {role!r}",
            why=f"role must be one of {sorted(ROLES)}",
            how="pass --role crafter|examiner|atd",
        )
    row = _slice_plan_row(content, slice_id)
    if row is None:
        raise ProjectionRefusal(
            what=f"slice {slice_id!r} not found in the Slice Plan",
            why=(
                "no row in '## Wave: DISCUSS / [REF] Slice Plan' matches this "
                f"slice id (source: {source})"
            ),
            how="pass --slice matching a real row in the delta's Slice Plan table",
        )
    value_statement = row.get("Value statement", "")
    sections = [f"## Value Statement ({slice_id})\n\n{value_statement}"]

    if role == "examiner":
        refs = _spec_row_refs(content)
        if refs:
            sections.append("## Spec Refs\n\n" + "\n".join(f"- {r}" for r in refs))
        return _render_projection(role, slice_id, source, content, sections)

    # crafter + atd both carry DoD + Design Decisions.
    dod = _dod_lines_for_slice(content, slice_id)
    if dod is None:
        raise ProjectionRefusal(
            what="Definition of Done section is absent",
            why=(
                f"no '{_DEFINITION_OF_DONE_HEADING}' heading found (source: {source})"
            ),
            how="author the DISCUSS Definition of Done section before projecting",
        )
    sections.append(
        f"## Definition of Done ({slice_id})\n\n" + "\n".join(dod)
        if dod
        else f"## Definition of Done ({slice_id})\n\n(none)"
    )

    decisions_body = _section_body(content, _DESIGN_DECISIONS_HEADING)
    if decisions_body:
        sections.append(f"## Design Decisions\n\n{decisions_body}")

    if role == "crafter":
        reuse_block = _mandatory_reuse_analysis_block(content, source)
        sections.append(f"## Reuse Analysis\n\n{reuse_block}")

    if role == "atd":
        test_reuse_body = _section_body(content, SUSTAINABILITY_HEADING)
        if test_reuse_body is None:
            raise ProjectionRefusal(
                what="Test Reuse & Consolidation Analysis section is absent",
                why=f"no '{SUSTAINABILITY_HEADING}' heading found (source: {source})",
                how="author the DISTILL Test Reuse & Consolidation Analysis section",
            )
        sections.append(f"## Test Reuse & Consolidation Analysis\n\n{test_reuse_body}")

    projection = _render_projection(role, slice_id, source, content, sections)
    if role == "crafter" and "Reuse Analysis" not in projection.markdown:
        # Self-check (never reached under the guard above; defends the
        # NON-PROJECTABLE-AWAY invariant against a future rendering bug).
        raise ProjectionRefusal(
            what="Reuse Analysis rows were dropped from the crafter projection",
            why="the rendered markdown does not carry a Reuse Analysis section",
            how="this is a projector bug — do not ship a slim crafter projection",
        )
    return projection


def _render_projection(
    role: str, slice_id: str, source: str, full_content: str, sections: list[str]
) -> RoleProjection:
    """Assemble the header + sections into the final markdown. Pure."""
    body = "\n\n".join(sections) + "\n"
    full_chars = len(full_content)
    full_words = len(full_content.split())
    projected_chars = len(body)
    projected_words = len(body.split())
    ratio = projected_chars / full_chars if full_chars else 0.0
    header = (
        "# Feature-Delta Projection\n\n"
        f"**Role**: {role} · **Slice**: {slice_id} · **Source**: {source}\n"
        f"**Size**: projection={projected_chars} chars ({projected_words} words) "
        f"/ full={full_chars} chars ({full_words} words) / ratio={ratio:.4f}\n\n"
    )
    markdown = header + body
    return RoleProjection(
        role=role,
        slice_id=slice_id,
        source=source,
        markdown=markdown,
        full_chars=full_chars,
        full_words=full_words,
        projected_chars=len(markdown),
        projected_words=len(markdown.split()),
    )


# ---------------------------------------------------------------------------
# Thin CLI shell — the driving port. Verdicts to STDOUT; the pure functions
# above are the only logic. This is the sole side-effect boundary.
# ---------------------------------------------------------------------------

_USAGE = (
    "usage: des feature-delta-schema "
    "{describe [--types|--consumed-by] | verify <file> | "
    "inject --wave <wave> | contract <section_id> | "
    "project --role <crafter|examiner|atd> --slice <slice-id> <file>}"
)


def _cmd_describe(extra: list[str]) -> int:
    """`describe [--types|--consumed-by]` — dump the schema as one value."""
    if extra == ["--types"]:
        for ctor in section_type_constructors():
            print(ctor.__name__)
        return 0
    if extra == ["--consumed-by"]:
        for entry in FEATURE_DELTA_SCHEMA:
            tokens = ",".join(sorted(entry.consumed_by))
            print(f"{entry.section_id}: {tokens}")
        return 0
    if extra:
        print(_USAGE, file=sys.stderr)
        return 1
    for entry in FEATURE_DELTA_SCHEMA:
        print(
            f"{entry.section_id}\t{type(entry.section_type).__name__}\t"
            f"{','.join(sorted(entry.consumed_by))}"
        )
    return 0


def _cmd_verify(extra: list[str]) -> int:
    """`verify <file>` — P1 gate_verify; print verdict + exit fail-closed."""
    if len(extra) != 1:
        print(_USAGE, file=sys.stderr)
        return 1
    from pathlib import Path

    target = Path(extra[0])
    if not target.is_file():
        print(f"{GateVerdict.INDETERMINATE.name}: {target} is not a file")
        return 4
    result = gate_verify_bytes(FEATURE_DELTA_SCHEMA, target.read_bytes())
    print(f"{result.verdict.name}: {result.detail}")
    return 0 if result.verdict is GateVerdict.PASS else 1


def _cmd_inject(extra: list[str]) -> int:
    """`inject --wave <wave>` — P2 wave_injection; print the projected rows."""
    if len(extra) != 2 or extra[0] != "--wave":
        print(_USAGE, file=sys.stderr)
        return 1
    wave = extra[1]
    if wave not in WAVES:
        print(
            f"error: unknown wave {wave!r}; expected one of {sorted(WAVES)}",
            file=sys.stderr,
        )
        return 1
    for entry in wave_injection(FEATURE_DELTA_SCHEMA, wave):
        print(f"{entry.section_id}\t{entry.heading}")
    return 0


def _cmd_contract(extra: list[str]) -> int:
    """`contract <section_id>` — P3 output_contract; print the write spec."""
    if len(extra) != 1:
        print(_USAGE, file=sys.stderr)
        return 1
    spec = output_contract(FEATURE_DELTA_SCHEMA, extra[0])
    if spec is None:
        print(f"error: no registered section {extra[0]!r}", file=sys.stderr)
        return 1
    print(f"{spec.section_id}\t{type(spec.section_type).__name__}")
    print(spec.heading)
    return 0


def _parse_project_args(extra: list[str]) -> tuple[str, str, str] | None:
    """Parse `--role <role> --slice <slice-id> <file>` in any flag order. Pure.

    Returns (role, slice_id, path) or None when the invocation is malformed
    (missing a flag, missing/extra positional).
    """
    role: str | None = None
    slice_id: str | None = None
    positional: list[str] = []
    idx = 0
    while idx < len(extra):
        token = extra[idx]
        if token == "--role" and idx + 1 < len(extra):
            role = extra[idx + 1]
            idx += 2
        elif token == "--slice" and idx + 1 < len(extra):
            slice_id = extra[idx + 1]
            idx += 2
        else:
            positional.append(token)
            idx += 1
    if role is None or slice_id is None or len(positional) != 1:
        return None
    return role, slice_id, positional[0]


def _cmd_project(extra: list[str]) -> int:
    """`project --role <role> --slice <slice-id> <file>` — P4 project_for_role.

    Usage errors (malformed flags, unknown role) exit 1. A well-formed
    invocation whose SOURCE content cannot honestly satisfy the role's
    contract (missing file, missing slice, missing/malformed mandatory
    section) degrades LOUD: exit 2 with what/why/how — never a silent slim
    projection.
    """
    parsed = _parse_project_args(extra)
    if parsed is None:
        print(_USAGE, file=sys.stderr)
        return 1
    role, slice_id, path_str = parsed
    if role not in ROLES:
        print(
            f"error: unknown role {role!r}; expected one of {sorted(ROLES)}",
            file=sys.stderr,
        )
        return 1

    from pathlib import Path

    target = Path(path_str)
    if not target.is_file():
        print(
            f"{GateVerdict.INDETERMINATE.name}: "
            f"what=feature-delta {target} not found; "
            "why=project reads a real feature-delta.md; "
            "how=pass a valid path to an existing feature-delta.md",
            file=sys.stderr,
        )
        return 2
    try:
        content = target.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        print(
            f"{GateVerdict.INDETERMINATE.name}: "
            f"what=undecodable document; why={exc}; "
            "how=save the feature-delta as UTF-8",
            file=sys.stderr,
        )
        return 2

    try:
        projection = project_for_role(content, role, slice_id, str(target))
    except ProjectionRefusal as refusal:
        print(
            f"{GateVerdict.INDETERMINATE.name}: "
            f"what={refusal.what}; why={refusal.why}; how={refusal.how}",
            file=sys.stderr,
        )
        return 2

    print(projection.markdown)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `des feature-delta-schema {describe,verify,inject,contract,
    project}`."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(_USAGE, file=sys.stderr)
        return 1
    subcommand, *extra = args
    dispatch = {
        "describe": _cmd_describe,
        "verify": _cmd_verify,
        "inject": _cmd_inject,
        "contract": _cmd_contract,
        "project": _cmd_project,
    }
    handler = dispatch.get(subcommand)
    if handler is None:
        print(_USAGE, file=sys.stderr)
        return 1
    return handler(extra)


if __name__ == "__main__":
    raise SystemExit(main())
