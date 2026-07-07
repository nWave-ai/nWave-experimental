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

Target-machine agnosticism (CLAUDE.md standing mandate): this module is
FILESYSTEM-ONLY. It never shells out to `git` or any other external tool --
unlike `scripts/cli/check_reuse_first_design.py`'s `git diff` detector, which
is explicitly out of scope here.

CLI contract:

    des feature-delta-doctor <path> --format=json

Emits ``{"gap_count": N, "gaps": [{"id", "what", "why", "how"}, ...]}`` to
stdout. Exit 0 on zero gaps, exit 1 on >=1 gap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

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
            how="Rewrite the heading as '## Wave: <NAME> / [REF|WHY|HOW] <Section>'.",
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
            else f"Add a '## Wave: <NAME> / [REF] {section_name}' heading."
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


def diagnose(content: str) -> list[Gap]:
    """Aggregate every structural gap for one feature-delta body in ONE pass.

    Pure function -- filesystem I/O lives only in `main`. Composes the four
    existing validators; never re-implements their classification logic. The
    covered-section set MUST match `des verify-readiness-pre-dispatch`'s
    (LOCKED_REF_SECTIONS + sustainability) -- see
    fix-doctor-covers-sustainability-section.
    """
    return [
        *_wave_heading_gaps(content),
        *_missing_section_gaps(content),
        *_reuse_analysis_gaps(content),
        *_sustainability_gaps(content),
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature-delta-doctor",
        description=(
            "One-pass structural gap aggregator for a feature-delta.md -- "
            "reports every gap (missing mandatory sections, malformed Wave "
            "headings, malformed/unjustified Reuse Analysis rows) in ONE "
            "invocation instead of one gate rejection at a time."
        ),
    )
    parser.add_argument("path", help="Path to the feature-delta.md file.")
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
    gaps = diagnose(content)
    report = {"gap_count": len(gaps), "gaps": gaps}
    print(json.dumps(report))
    return 0 if not gaps else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
