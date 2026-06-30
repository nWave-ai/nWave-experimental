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

OSS invariant (F-D-09): `des.*` imports + stdlib only; NO `import yaml`; NO
sequencer/engine. The projections REUSE the shipped validators in
`des.cli.validate_feature_delta` — they do NOT re-implement Table validation.

CLI contract (driving port): `des feature-delta-schema {describe,verify,inject,contract}`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from des.cli.validate_feature_delta import (
    REUSE_ANALYSIS_COLUMNS,
    SLICE_PLAN_COLUMNS,
    VERDICT_ACCEPTED,
    VERDICT_STRUCTURALLY_ACCEPTED,
    _parse_table_cells,
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
        result = validate_slice_plan_content(content)
        if result.verdict != VERDICT_ACCEPTED and "Slice Plan" in content:
            return VerifyVerdict(
                GateVerdict.FAIL,
                f"{_section_name(entry)}: {result.detail}",
            )
        return None
    if entry.section_id == "reuse-analysis":
        result = validate_reuse_analysis_content(content)
        if (
            result.verdict != VERDICT_STRUCTURALLY_ACCEPTED
            and "Reuse Analysis" in content
        ):
            return VerifyVerdict(
                GateVerdict.FAIL,
                f"{_section_name(entry)}: {result.detail}",
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
# Thin CLI shell — the driving port. Verdicts to STDOUT; the pure functions
# above are the only logic. This is the sole side-effect boundary.
# ---------------------------------------------------------------------------

_USAGE = (
    "usage: des feature-delta-schema "
    "{describe [--types|--consumed-by] | verify <file> | "
    "inject --wave <wave> | contract <section_id>}"
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


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `des feature-delta-schema {describe,verify,inject,contract}`."""
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
    }
    handler = dispatch.get(subcommand)
    if handler is None:
        print(_USAGE, file=sys.stderr)
        return 1
    return handler(extra)


if __name__ == "__main__":
    raise SystemExit(main())
