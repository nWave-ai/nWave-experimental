"""Design-dimension coverage CLI -- slice-01 walking skeleton.

F-OSS-UPSTREAM-WAVE-GATE-PAIRS pair-1 (DESIGN-dimensions <-> DISTILL-pbt),
Mandate-12 + Pillar 3. Sibling spine-gate of ``check_reuse_first_design.py``.
Hosted in ``scripts/cli/`` because the gate has no DES-runtime coupling (OSS
nwave-dev hooks-only, Ale 2026-05-24 topology).

slice-01 (existence-join walking skeleton, P1 -- DIM-1, DIM-3, DIM-5): the
gate joins the feature-delta's DESIGN dimensions block against the AT corpus's
``# dimension: DIM-N`` carrier comments. Every DESIGN-declared dimension-ID
must be witnessed by >=1 carrier comment; an unwitnessed dimension is the
exact drift the gate-or-residue policy forbids (a DESIGN axis of behavior no
downstream property ever exercises).

Stdout token contract -- single line, machine-parseable::

    design_dimension_coverage feature=<id> dimensions=<n> witnessed=<m> verdict=<PASS|INDETERMINATE|MALFORMED>

Exit code contract:
    0 = PASS          -- >=1 declared dimension AND every declared dimension-ID
                         is witnessed by >=1 carrier comment (n >= 1, m == n)
    1 = INDETERMINATE -- >=1 declared dimension has zero witnessing carriers.
                         NON-HALTING soft refusal (OSS hooks-only ACL, DIM-5):
                         the DISTILL-exit hook EMITS the loud warning and ALLOWS
                         the DISTILL->DELIVER move; it NEVER blocks.
    2 = MALFORMED     -- no parseable DESIGN dimensions block (heading absent,
                         table absent, or zero data rows -> empty block is
                         MALFORMED, never a vacuous all-witnessed PASS) OR the
                         AT-corpus root path does not exist.

Heading SSOT (DESIGN default #1): the dimensions block lives under EITHER the
canonical ``## DESIGN Dimensions`` heading OR the carpaccio variant
``## Wave: DESIGN / [REF] Dimensions``. The parser anchors on both via a regex
mirroring the sibling reuse-first gate's ``_REUSE_ANALYSIS_HEADING_RE``.

Read-only contract (DIM-10 tree-safe half, @contract-shape:unbounded-
preservation): the gate reads the feature-delta + the AT corpus and writes
ONLY stdout/stderr + an exit code -- it mutates no file it inspects.

Driving-port-only (Mandate-13): the gate is exercised exclusively through its
``main(argv)`` CLI entry point. stdlib + the shared human-surface helper only;
no git invocation (slice-01 is a pure filesystem read).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary
from des.cli.validate_feature_delta import next_h2_boundary


_EXIT_PASS = 0
_EXIT_INDETERMINATE = 1
_EXIT_MALFORMED = 2


# Matches a Markdown level-2 heading whose text names a DESIGN Dimensions
# block -- either the canonical ``## DESIGN Dimensions`` or the carpaccio
# variant ``## Wave: DESIGN / [REF] Dimensions`` (heading SSOT, DESIGN
# default #1). Both contain the literal token "DESIGN" and the word
# "Dimensions".
_DESIGN_DIMENSIONS_HEADING_RE = re.compile(
    r"^##\s+(?=.*\bDESIGN\b)(?=.*\bDimensions\b).*$",
    re.MULTILINE,
)

# A column-1 cell is a dimension-ID iff it is exactly ``DIM-<token>``.
_DIMENSION_ID_RE = re.compile(r"^DIM-[A-Za-z0-9-]+$")

# AT-corpus carrier comment: ``# dimension: DIM-N`` (the syntactic existence
# witness). Tolerates surrounding whitespace and a leading ``#`` comment marker
# in either ``.feature`` (Gherkin ``#``) or ``.py`` (Python ``#``) files.
_CARRIER_COMMENT_RE = re.compile(r"#\s*dimension:\s*(DIM-[A-Za-z0-9-]+)\b")

# AT-corpus files the carrier-comment parser scopes (non-vacuity invariant (c):
# a carrier comment in a non-corpus file does NOT count -- only files under the
# --at-corpus-root with these suffixes are scanned).
_CORPUS_FILE_SUFFIXES = (".feature", ".py")


def _extract_design_dimensions_sections(feature_delta_text: str) -> list[str]:
    """Return every DESIGN Dimensions section body found in the feature-delta.

    Each section runs from its ``##`` heading line up to (exclusive) the next
    ``##`` heading or end-of-document. Section-BOUNDARY scanning routes
    through the unified ``next_h2_boundary`` (D31b) -- shared with the
    sibling reuse-first gate's own section extraction, so this module no
    longer carries its own independent boundary scan.
    """
    headings = list(_DESIGN_DIMENSIONS_HEADING_RE.finditer(feature_delta_text))
    sections: list[str] = []
    for heading_match in headings:
        section_start = heading_match.start()
        section_end = next_h2_boundary(feature_delta_text, heading_match.end())
        sections.append(feature_delta_text[section_start:section_end])
    return sections


def _table_data_rows(design_dimensions_sections: list[str]) -> list[list[str]]:
    """Return the trimmed cells of every GFM table data row in the sections.

    A data row is any line starting with ``|`` that is not the separator row
    (``|---|---|...``). The heading row is structurally a data row here but is
    filtered downstream by the column-1 dimension-ID match.
    """
    rows: list[list[str]] = []
    for section in design_dimensions_sections:
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and all(set(cell) <= {"-", ":"} for cell in cells if cell):
                # Separator row (``|---|:--|``) -- skip.
                continue
            rows.append(cells)
    return rows


def _declared_dimensions(
    design_dimensions_sections: list[str],
) -> list[tuple[str, str]]:
    """Collect ``(dimension-ID, summary)`` for every join-key table data row.

    Walks every GFM table data row; when column-1 matches ``DIM-<token>`` the
    row declares a dimension, and column-2 (the summary) is the operator's
    comprehension-key (the report resolves the ID to this text -- DIM-4). Rows
    whose column-1 is blank or non-``DIM`` are not declarations (DIM-7 column-1
    vacuity is detected separately via ``_has_vacuous_identifier_column``).
    """
    declared: list[tuple[str, str]] = []
    for cells in _table_data_rows(design_dimensions_sections):
        first_cell = cells[0]
        if not _DIMENSION_ID_RE.match(first_cell):
            continue
        summary = cells[1] if len(cells) > 1 else ""
        declared.append((first_cell, summary))
    return declared


def _has_vacuous_identifier_column(
    design_dimensions_sections: list[str],
) -> bool:
    """True when a block has data rows but NONE carry a ``DIM`` column-1.

    DIM-7: a block whose only rows carry a blank / non-``DIM`` column-1 is
    MALFORMED on a *distinct* ground from an absent block -- the parser found
    the dimensions table and its rows, but the join-key identifier column is
    vacuous. Distinguishes a present-but-unkeyed block from a truly empty /
    absent one (an empty block has zero data rows below the header).
    """
    data_rows = [
        cells
        for cells in _table_data_rows(design_dimensions_sections)
        if cells and cells[0].lower() != "dimension-id"
    ]
    if not data_rows:
        return False
    return all(not _DIMENSION_ID_RE.match(cells[0]) for cells in data_rows)


def _witnessed_dimension_ids(at_corpus_root: Path) -> set[str]:
    """Collect the set of dimension-IDs carried by AT-corpus comments.

    Scans every ``.feature`` / ``.py`` file under ``at_corpus_root`` for
    ``# dimension: DIM-N`` carrier comments and returns the set of witnessed
    dimension-IDs.
    """
    witnessed: set[str] = set()
    for path in sorted(at_corpus_root.rglob("*")):
        if path.suffix not in _CORPUS_FILE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        witnessed.update(_CARRIER_COMMENT_RE.findall(text))
    return witnessed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_design_dimension_coverage",
        description=(
            "Design-dimension coverage gate (slice-01 walking skeleton). "
            "Joins the feature-delta's DESIGN dimensions block against the "
            "AT corpus's carrier comments: every declared dimension must be "
            "witnessed by at least one property."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="Kebab-case feature identifier (e.g. design-dimension-coverage-demo).",
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="Repository root containing docs/feature/<feature-id>/.",
    )
    parser.add_argument(
        "--at-corpus-root",
        required=True,
        help=(
            "Acceptance-test corpus directory whose .feature/.py files carry "
            "the '# dimension: DIM-N' witness comments."
        ),
    )
    return parser


def _name_dimension(dimension_id: str, summary: str) -> str:
    """Resolve a flagged dimension-ID to its operator-facing report name.

    DIM-4 comprehension-key contract: the report names a flagged dimension by
    ``DIM-N (summary)`` so the acceptance designer reads WHICH behavior axis is
    uncovered, never the opaque ``DIM-N`` alone.
    """
    return f"{dimension_id} ({summary.strip()})"


def _malformed_reason(design_dimensions_sections: list[str]) -> str:
    """Name the specific MALFORMED ground for the operator report (DIM-7).

    A block present with data rows whose column-1 join key is vacuous is named
    distinctly from a truly absent block / corpus, so the report says WHY the
    gate is malformed rather than emitting an undifferentiated either/or.
    """
    if _has_vacuous_identifier_column(design_dimensions_sections):
        return (
            "its DESIGN dimensions block has data rows whose identifier "
            "column (column-1) carries no DIM-<token> join key -- a vacuous "
            "identifier column is malformed, never a silent zero-dimensions "
            "pass"
        )
    return "it has no parseable DESIGN dimensions block or its AT corpus is absent"


def _emit(
    feature_id: str,
    declared_count: int,
    witnessed_count: int,
    verdict: str,
) -> None:
    """Emit the single-line stdout token (the Gate Contract machine surface)."""
    print(
        f"design_dimension_coverage feature={feature_id} "
        f"dimensions={declared_count} witnessed={witnessed_count} "
        f"verdict={verdict}"
    )


def _emit_report_detail(detail: str) -> None:
    """Emit the operator-facing report detail line on stdout.

    The machine token (``_emit``) is the stable single-line contract; this
    second stdout line is the human comprehension surface the acceptance
    designer reads to know WHICH behavior axis is uncovered (DIM-4 summary
    resolution) or WHY a block is malformed (DIM-7 column-1 vacuity). It is on
    stdout (not the stderr human summary) so it is part of the captured report
    surface the gate's callers inspect.
    """
    print(f"design_dimension_coverage_detail {detail}")


def main(argv: list[str] | None = None) -> int:
    """Run the design-dimension coverage gate; return the verdict exit code."""
    args = _build_parser().parse_args(argv)
    feature_id = args.feature_id
    repo_root = Path(args.repo_root)
    at_corpus_root = Path(args.at_corpus_root)

    feature_delta_path = (
        repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    feature_delta_text = feature_delta_path.read_text(encoding="utf-8")
    design_sections = _extract_design_dimensions_sections(feature_delta_text)
    declared = _declared_dimensions(design_sections)
    declared_ids = [dimension_id for dimension_id, _ in declared]

    # MALFORMED: no parseable dimensions block (heading absent / table absent /
    # zero data rows -> empty block) OR the AT-corpus root path does not exist.
    # The report NAMES the specific malformation ground rather than emitting an
    # undifferentiated either/or (DIM-7): a block present with data rows whose
    # column-1 join key is vacuous is distinguished from an absent block/corpus.
    if not declared or not at_corpus_root.exists():
        _emit(feature_id, len(declared), 0, "MALFORMED")
        reason = _malformed_reason(design_sections)
        _emit_report_detail(f"malformed: {reason}")
        print_human_summary(
            Verdict.FAIL,
            f"design-dimension coverage malformed: feature {feature_id} {reason}",
        )
        return _EXIT_MALFORMED

    witnessed = _witnessed_dimension_ids(at_corpus_root)
    witnessed_declared = [name for name in declared_ids if name in witnessed]

    if len(witnessed_declared) == len(declared):
        _emit(feature_id, len(declared), len(witnessed_declared), "PASS")
        print_human_summary(
            Verdict.PASS,
            f"design-dimension coverage verified: every declared dimension "
            f"({len(declared)}) is witnessed by an AT-corpus property",
        )
        return _EXIT_PASS

    unwitnessed = [
        _name_dimension(dimension_id, summary)
        for dimension_id, summary in declared
        if dimension_id not in witnessed
    ]
    _emit(feature_id, len(declared), len(witnessed_declared), "INDETERMINATE")
    _emit_report_detail(
        f"unwitnessed dimension(s): {', '.join(unwitnessed)} -- "
        f"no witnessing property in the AT corpus"
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"design-dimension coverage indeterminate: {len(unwitnessed)} of "
        f"{len(declared)} declared dimension(s) ({', '.join(unwitnessed)}) "
        f"have no witnessing property -- non-halting soft refusal, the "
        f"DISTILL->DELIVER move proceeds",
    )
    return _EXIT_INDETERMINATE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
