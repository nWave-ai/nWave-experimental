"""des feature-delta-doctor -- one-pass structural gap aggregator (WS-2 / M2).

FR-11 traced a 7-sequential-rejection friction cascade: a contributor fixes
one gate rejection, resubmits, hits the NEXT gate's rejection, and so on --
one gap at a time. This doctor is the root fix: it reads a feature-delta.md
ONCE and reports every structural gap in ONE JSON payload -- missing
mandatory sections, malformed Wave headings, malformed/unjustified Reuse
Analysis rows -- each gap self-explaining what/why/how (the STANDING
every-failure-explains-what-why-how mandate).

Composes the EXISTING validators verbatim -- it does NOT re-implement their
classification logic:

- `validate_feature_delta_content` (malformed `## Wave:` headings)
- `locked_sections_present` (missing `LOCKED_REF_SECTIONS`)
- `validate_reuse_analysis_content` (malformed / unjustified Reuse Analysis
  rows), called WITHOUT `project_root` -- the content-grounding leg (which
  resolves citations through the CodeFactPort chain) is deliberately out of
  scope for this doctor's filesystem-only core.
- `feature_delta_source.dereference_adr_refs` (D6/DD-8) -- resolves declared
  `adr-refs` id tokens against the filesystem, read-only.

Target-machine agnosticism (CLAUDE.md standing mandate): this module is
FILESYSTEM-ONLY. It never shells out to `git` or any other external tool --
unlike `scripts/cli/check_reuse_first_design.py`'s `git diff` detector, which
is explicitly out of scope here.

CLI contract:

    des feature-delta-doctor <path> [--repo-root <root>] --format=json

Emits ``{"gap_count": N, "gaps": [{"id", "what", "why", "how"}, ...]}`` to
stdout. Exit 0 on zero gaps, exit 1 on >=1 gap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.carpaccio_format import (
    SLICE_PLAN_CANONICAL_COLUMNS,
    slice_plan_header_deviation,
)
from des.cli.feature_delta_schema import _section_body
from des.cli.validate_feature_delta import (
    _SUSTAINABILITY_ACCEPTED_VERDICTS,
    LOCKED_REF_SECTIONS,
    SUSTAINABILITY_HEADING,
    VERDICT_MALFORMED_REUSE_ANALYSIS,
    VERDICT_MALFORMED_WAVE_HEADING,
    VERDICT_METHODOLOGY_EXEMPT,
    VERDICT_MISSING_REUSE_ANALYSIS,
    VERDICT_NO_OVERLAP_DECLARED,
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNJUSTIFIED_CREATE_NEW,
    locked_sections_present,
    validate_feature_delta_content,
    validate_reuse_analysis_content,
    validate_sustainability_content,
)
from des.domain.feature_delta_source import (
    any_adr_ref_root_exists,
    dereference_adr_refs,
)


class Gap(TypedDict):
    """One self-explaining structural gap (what / why / how, STANDING mandate)."""

    id: str
    what: str
    why: str
    how: str


#: Synthetic gap id for a missing `LOCKED_REF_SECTIONS` entry -- there is no
#: existing verdict token for section-presence gaps (`locked_sections_present`
#: returns a bare name list, not a verdict), so the doctor names the class.
_MISSING_LOCKED_SECTION_ID = "missing-locked-section"

#: Reuse Analysis verdicts that are NOT gaps: either well-formed
#: (`structurally-accepted`) or an accepted DDD-9 exemption. `missing-reuse-
#: analysis` is deliberately excluded too -- `locked_sections_present` already
#: reports an absent "Reuse Analysis" heading, so re-reporting it here would
#: double-count one root cause under two gap ids.
_REUSE_ANALYSIS_NON_GAP_VERDICTS = frozenset(
    {
        VERDICT_STRUCTURALLY_ACCEPTED,
        VERDICT_METHODOLOGY_EXEMPT,
        VERDICT_NO_OVERLAP_DECLARED,
        VERDICT_MISSING_REUSE_ANALYSIS,
    }
)


def _wave_heading_gaps(content: str) -> list[Gap]:
    """Malformed `## Wave:` heading gaps, reusing `validate_feature_delta_content`."""
    result = validate_feature_delta_content(content)
    return [
        Gap(
            id=VERDICT_MALFORMED_WAVE_HEADING,
            what=(
                f"malformed Wave heading at line {offender.line}: '{offender.heading}'"
            ),
            why=offender.reason,
            how=(
                "Replace the malformed heading with the GENERATED one: `des "
                "feature-delta-schema inject --wave <wave>` emits the canonical "
                "'## Wave: <NAME> / [REF|WHY|HOW] <Section>' form -- paste it over "
                "the offending line rather than hand-correcting the punctuation."
            ),
        )
        for offender in result.offenders
    ]


def _missing_section_gaps(content: str) -> list[Gap]:
    """Missing mandatory-section gaps, reusing `locked_sections_present`."""
    gaps: list[Gap] = []
    for section_name in locked_sections_present(content):
        how = (
            "Add the canonical '## Reuse Analysis' heading."
            if section_name == "Reuse Analysis"
            else (
                "GENERATE the heading, do not retype it: `des feature-delta-schema "
                "inject --wave <wave>` emits every canonical "
                f"'## Wave: <NAME> / [REF] <Section>' heading -- copy the "
                f"'{section_name}' line VERBATIM into feature-delta.md and fill "
                "its body. Hand-typing the heading is how it ends up malformed."
            )
        )
        gaps.append(
            Gap(
                id=_MISSING_LOCKED_SECTION_ID,
                what=f"missing locked section: '{section_name}'",
                why=(
                    f"'{section_name}' is one of the mandatory LOCKED_REF_SECTIONS "
                    f"{list(LOCKED_REF_SECTIONS)} and no heading names it."
                ),
                how=how,
            )
        )
    return gaps


#: Principle-level rationale per Reuse Analysis gap verdict -- explains WHY the
#: rule exists, never merely restating the row-N condition already named in
#: `what` (DEFECT 2, Vera examine-reloop WS-2: `why` was a verbatim substring
#: of `what`, adding zero new information). Only verdicts reachable here (the
#: filesystem-only leg, `project_root=None`) need an entry; any future verdict
#: falls back to `result.detail`.
_REUSE_ANALYSIS_PRINCIPLE_WHY: dict[str, str] = {
    VERDICT_UNJUSTIFIED_CREATE_NEW: (
        "DDD-3 (Reuse-First Design) requires every CREATE_NEW row to carry a "
        "documented Justification -- an unexplained duplication decision is "
        "not reviewable or traceable, and skips the reuse-first accountability "
        "the rule exists to enforce."
    ),
    VERDICT_MALFORMED_REUSE_ANALYSIS: (
        "The Reuse Analysis table is the reviewable evidence of reuse-first "
        "diligence -- a malformed row or header cannot be checked by "
        "reviewers or tooling, defeating the section's accountability purpose."
    ),
}


def _reuse_analysis_gaps(content: str) -> list[Gap]:
    """Malformed/unjustified Reuse Analysis gaps, reusing
    `validate_reuse_analysis_content` (filesystem-only: no `project_root`)."""
    result = validate_reuse_analysis_content(content)
    if result.verdict in _REUSE_ANALYSIS_NON_GAP_VERDICTS:
        return []
    return [
        Gap(
            id=result.verdict,
            what=f"Reuse Analysis section is invalid: {result.detail}",
            why=_REUSE_ANALYSIS_PRINCIPLE_WHY.get(result.verdict, result.detail),
            how=(
                "Fix the Reuse Analysis row per the diagnostic above -- the "
                "canonical five-column header, a Decision in "
                "{EXTEND, CREATE_NEW}, and a non-empty Justification on "
                "CREATE_NEW."
            ),
        )
    ]


def _sustainability_gaps(content: str) -> list[Gap]:
    """Missing/malformed sustainability-section gaps, reusing
    `validate_sustainability_content` -- the SAME parser
    `des verify-readiness-pre-dispatch`'s `sustainability` invariant enforces
    (M1 shared-SSOT: `SUSTAINABILITY_HEADING` / `_SUSTAINABILITY_ACCEPTED_VERDICTS`
    imported verbatim from `des.cli.validate_feature_delta`, never re-literalled).

    A missing section, a malformed section (wrong columns / bad Decision /
    unjustified CREATE_NEW), or a duplicate heading all surface as ONE gap here
    -- the doctor's covered-section set must MATCH the readiness gate's."""
    result = validate_sustainability_content(content)
    if result.verdict in _SUSTAINABILITY_ACCEPTED_VERDICTS:
        return []
    return [
        Gap(
            id=result.verdict,
            what=(
                f"missing or malformed '{SUSTAINABILITY_HEADING}' section: "
                f"{result.detail}"
            ),
            why=(
                "the readiness gate's sustainability invariant "
                "(`des verify-readiness-pre-dispatch`) requires a well-formed "
                f"'{SUSTAINABILITY_HEADING}' section on every feature-delta; "
                "a missing or malformed section is REJECTED there."
            ),
            how=(
                f"Add the canonical '{SUSTAINABILITY_HEADING}' heading with "
                "the canonical five-column Test Reuse table (well-formed "
                "REUSE/EXTEND/CONSOLIDATE/CREATE_NEW rows, Justification "
                "required on CREATE_NEW), or a "
                "'Test-Reuse-Analysis: methodology-exempt' marker if no new "
                "tests were authored."
            ),
        )
    ]


#: Gap id for a Slice Plan header deviating from `SLICE_PLAN_CANONICAL_COLUMNS`
#: (fix-delta-doctor-validates-slice-plan-columns) -- an extra/missing/
#: reordered column shifts every downstream cell SILENTLY (the shared parser
#: `carpaccio_format._build_slice_rows` reads value/status/annotation/
#: justification POSITIONALLY, regardless of header text).
_MALFORMED_SLICE_PLAN_HEADER_ID = "malformed-slice-plan-header"

#: The canonical header row text, built FROM `SLICE_PLAN_CANONICAL_COLUMNS`
#: (M1: never a copied literal) -- the exact copy-paste fix an operator
#: applies to a malformed header.
_CANONICAL_SLICE_PLAN_HEADER = "| " + " | ".join(SLICE_PLAN_CANONICAL_COLUMNS) + " |"


def _slice_plan_header_gaps(content: str) -> list[Gap]:
    """`malformed-slice-plan-header` gap when the Slice Plan table header
    deviates from `SLICE_PLAN_CANONICAL_COLUMNS` -- reusing
    `carpaccio_format.slice_plan_header_deviation`, the SAME parser module
    that reads the Slice Plan table downstream (M1: one locus, no copy).

    Empirical anchor (2026-07-12): seven hand-authored feature-deltas
    carried `| Slice | Value statement | Class | Status | Annotation |`
    instead of the canonical header -- the shared parser shifted every cell
    SILENTLY and the DISTILL-exit mechanical seal refused opaquely while the
    doctor reported nothing (GDP-6 silent-wrong)."""
    malformed_header = slice_plan_header_deviation(content)
    if malformed_header is None:
        return []
    return [
        Gap(
            id=_MALFORMED_SLICE_PLAN_HEADER_ID,
            what=f"malformed Slice Plan header: '{malformed_header}'",
            why=(
                "the header deviates from the canonical Slice Plan columns; "
                "the shared parser (`carpaccio_format._build_slice_rows`) "
                "reads value/status/annotation/justification POSITIONALLY "
                "from the cells after the slice-id, regardless of what the "
                "header text says, so every downstream cell shifts SILENTLY "
                "-- the DISTILL-exit mechanical seal then reads the wrong "
                "cell as the annotation and refuses opaquely."
            ),
            how=f"Rewrite the Slice Plan header to: {_CANONICAL_SLICE_PLAN_HEADER}",
        )
    ]


#: `## Wave: DESIGN / [REF] ADR Refs` -- the `adr-refs` `RefList` section
#: (`feature_delta_schema.py`) DD-9 reads read-only, via the EXISTING generic
#: extractor (`_section_body`, M1: one locus, no second section parser).
_ADR_REFS_HEADING = "## Wave: DESIGN / [REF] ADR Refs"

#: A real, declared-but-nonexistent id -- write the missing ADR or drop the
#: reference. Distinct from `_ADR_REF_COULD_NOT_VERIFY_ID`: the two route the
#: operator to DIFFERENT actions.
_DANGLING_ADR_REF_ID = "dangling-adr-ref"

#: The resolved `repo_root` holds NONE of the 4 declared ADR root directories
#: -- the TREE cannot be checked at all, not any one id. Reporting zero gaps
#: here would be a GDP-6 silent-wrong.
_ADR_REF_COULD_NOT_VERIFY_ID = "adr-ref-could-not-verify"


def _dangling_adr_ref_gaps(content: str, repo_root: Path) -> list[Gap]:
    """`dangling-adr-ref` / `adr-ref-could-not-verify` gaps (DD-9, D6).

    Reuses the generic section-body extractor (`_section_body`) for the
    `adr-refs` section and `feature_delta_source.dereference_adr_refs` (DD-8)
    for per-id resolution -- this function adds no parsing logic of its own,
    only the AGGREGATE THIRD state `dereference_adr_refs` deliberately does
    not model (it answers per-id PRESENT/ABSENT only; "can the tree be
    checked at all" is a doctor-level, not a per-id, question)."""
    section_body = _section_body(content, _ADR_REFS_HEADING)
    if not section_body or not section_body.strip():
        return []

    if not any_adr_ref_root_exists(repo_root):
        return [
            Gap(
                id=_ADR_REF_COULD_NOT_VERIFY_ID,
                what=(
                    f"cannot verify any declared adr-refs id against repo_root="
                    f"{repo_root} -- none of the 4 declared ADR root "
                    "directories exist there"
                ),
                why=(
                    "the resolved repo_root holds NONE of the declared, closed "
                    "ADR root tuple (docs/product/architecture/, "
                    "docs/feature/<feature-id>/design/adrs/, "
                    "docs/architecture/adrs/, docs/adrs/) -- the TREE itself, "
                    "not any one id, cannot be checked; reporting zero gaps "
                    "here would silently agree every reference resolved "
                    "(GDP-6 silent-wrong)"
                ),
                how=(
                    "pass the correct tree: `des feature-delta-doctor <path> "
                    f"--repo-root <project-root>` (resolved to {repo_root} "
                    "this run). If that IS the correct tree, the 4 declared "
                    "ADR root directories are themselves missing and must be "
                    "created."
                ),
            )
        ]

    # feature_id is intentionally the empty string here: the doctor has no
    # single feature in scope (DD-9's signature carries no feature_id
    # parameter), so the feature-specific root
    # (docs/feature/{feature_id}/design/adrs/) degrades to a no-op path while
    # the other 3 declared roots resolve normally.
    records = dereference_adr_refs(section_body, repo_root=repo_root, feature_id="")
    return [
        Gap(
            id=_DANGLING_ADR_REF_ID,
            what=(
                f"declared adr-refs id {record.adr_id!r} names no file under "
                "any declared ADR root"
            ),
            why=(
                "D6: a declared 'adr-refs' reference must resolve to a real "
                f"file or be NAMED dangling -- never silently accepted; "
                f"{record.adr_id!r} matched no file under "
                "docs/product/architecture/, "
                "docs/feature/<feature-id>/design/adrs/, "
                "docs/architecture/adrs/, or docs/adrs/ under this repo_root."
            ),
            how=(
                f"write the missing ADR (e.g. "
                f"docs/product/architecture/{record.adr_id}-<title>.md), or "
                f"remove {record.adr_id!r} from the "
                f"'{_ADR_REFS_HEADING}' section if it was declared in error."
            ),
        )
        for record in records
        if record.resolved_path is None
    ]


def diagnose(content: str, *, repo_root: Path | None = None) -> list[Gap]:
    """Aggregate every structural gap for one feature-delta body in ONE pass.

    Pure function -- filesystem I/O lives only in `main`. Composes the
    existing validators; never re-implements their classification logic. The
    covered-section set MUST match `des verify-readiness-pre-dispatch`'s
    (LOCKED_REF_SECTIONS + sustainability) -- see
    fix-doctor-covers-sustainability-section.

    `repo_root` is KEYWORD-ONLY and DEFAULTED to None (DD-9) so the existing
    single-positional-argument call
    (`src/des/application/deliver_loop_projection.py:160`) keeps working
    unchanged. The `adr-refs` dangling/could-not-verify leg only runs when a
    caller EXPLICITLY names the tree to check it against -- with no
    `repo_root`, this function has no basis to distinguish "the tree really
    lacks the declared ADR roots" from "no tree was ever supplied", so it
    stays silent on that leg rather than guessing and false-positiving on
    every caller that predates DD-9 and never supplies one.
    """
    gaps: list[Gap] = [
        *_wave_heading_gaps(content),
        *_missing_section_gaps(content),
        *_reuse_analysis_gaps(content),
        *_sustainability_gaps(content),
        *_slice_plan_header_gaps(content),
    ]
    if repo_root is not None:
        gaps.extend(_dangling_adr_ref_gaps(content, repo_root))
    return gaps


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature-delta-doctor",
        description=(
            "One-pass structural gap aggregator for a feature-delta.md -- "
            "reports every gap (missing mandatory sections, malformed Wave "
            "headings, malformed/unjustified Reuse Analysis rows, dangling "
            "ADR refs) in ONE invocation instead of one gate rejection at a "
            "time."
        ),
    )
    parser.add_argument("path", help="Path to the feature-delta.md file.")
    add_repo_root_argument(
        parser,
        "--repo-root",
        default=None,
        help=(
            "Repo root the declared ADR root directories are resolved "
            "against (DD-9). When omitted, the dangling/could-not-verify "
            "adr-refs check is skipped entirely -- it has no tree to check "
            "against, and guessing one would false-positive on any "
            "feature-delta that predates this check."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only 'json' is supported).",
    )
    return parser


#: Deliberate, distinguishable exit for "bad input" (unreadable target path) --
#: distinct from 0 (zero gaps) and 1 (gaps found), so a caller can tell "the
#: tool could not run" apart from "the tool ran and found gaps" (DEFECT 1,
#: Vera examine-reloop WS-2: an uncaught `FileNotFoundError` used to leak a
#: raw Python traceback and exit 1 -- indistinguishable from "gaps found").
_EXIT_USAGE_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    """Run the doctor; return 0 on zero gaps, 1 on >=1 gap, 2 on unreadable input."""
    args = _build_parser().parse_args(argv)
    try:
        content = Path(args.path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(json.dumps({"error": f"feature-delta path not found: {args.path}"}))
        return _EXIT_USAGE_ERROR
    except (OSError, UnicodeDecodeError) as exc:
        print(json.dumps({"error": f"cannot read feature-delta at {args.path}: {exc}"}))
        return _EXIT_USAGE_ERROR
    repo_root = Path(args.repo_root) if args.repo_root else None
    gaps = diagnose(content, repo_root=repo_root)
    report = {"gap_count": len(gaps), "gaps": gaps}
    print(json.dumps(report))
    return 0 if not gaps else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
