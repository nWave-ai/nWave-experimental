"""Regression AT: the scoped `## Prefactoring Assessment` gate
(`validate_prefactoring_assessment_content`, `--require-prefactoring-assessment`).

CHANGE 2 of fix-slice-third-phase-commit-only (RCA by Rex, nw-troubleshooter):
CHANGE 1 retires the per-slice L1-L6 refactor mandate (see
`tests/des/unit/test_per_slice_third_phase_is_commit_only.py`) WITH a
substitute -- the mandatory per-feature Prefactoring Assessment, authored
upstream at DESIGN time, moves the refactor EARLIER instead of skipping it.
Before this change the substitute was prose-only, never gate-enforced; this
AT proves the gate is now REAL (mechanically enforced), covering the three
cases named in the crafter dispatch:

  1. Absent -- REJECT (`missing-prefactoring-assessment`).
  2. A `@prefactoring` slice recorded as doing the reshaping work -- ACCEPT
     (`prefactoring-assessment-accepted`).
  3. A justified NONE (what was examined + why the shape fits) -- ACCEPT
     (`prefactoring-assessment-accepted`).

Plus the scoping boundary (no `## Wave: DESIGN` section -> the gate does not
apply -- `prefactoring-not-required`) and the skip-requires-justification
floor (an UNMOTIVATED "NONE" with no reasoning -- REJECT,
`unmotivated-prefactoring-assessment`), both load-bearing for the "scoped"
and "skip-requires-justification" halves of the dispatch's design intent.

RED-for-right-reason (verified manually before authoring GREEN production
code, see crafter's commit message): `validate_prefactoring_assessment_content`
did not exist on `des.cli.validate_feature_delta` before this change -- these
tests failed with `ImportError`/`AttributeError` (MISSING_FUNCTIONALITY RED),
never a crash unrelated to the defect.

Pure-function core tests, mirroring `TestValidateFeatureDeltaContent`'s style
in `test_validate_feature_delta.py` (direct import, no CLI subprocess) --
proportionate for this bugfix's regression scope.
"""

from __future__ import annotations

from des.cli.validate_feature_delta import (
    VERDICT_MISSING_PREFACTORING_ASSESSMENT,
    VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED,
    VERDICT_PREFACTORING_NOT_REQUIRED,
    VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
    PrefactoringAssessmentResult,
    validate_prefactoring_assessment_content,
)


_DESIGN_HEADING = "## Wave: DESIGN / [REF] Architecture\n\nSome architecture text.\n"


def _design_delta(prefactoring_body: str | None) -> str:
    """A minimal feature-delta with a `## Wave: DESIGN` section, optionally
    followed by a `## Prefactoring Assessment` section carrying `body`.
    `prefactoring_body=None` omits the section entirely."""
    text = _DESIGN_HEADING
    if prefactoring_body is not None:
        text += f"\n## Prefactoring Assessment\n\n{prefactoring_body}\n"
    text += "\n## Wave: DISCUSS / [REF] Slice Plan\n\n| Slice |\n|-------|\n"
    return text


class TestPrefactoringAssessmentContent:
    """Pure-function core: `validate_prefactoring_assessment_content`."""

    def test_absent_section_is_rejected(self) -> None:
        """CASE 1 (dispatch): no `## Prefactoring Assessment` heading at all
        on a DESIGN-having feature-delta -- REJECT."""
        result = validate_prefactoring_assessment_content(_design_delta(None))

        assert isinstance(result, PrefactoringAssessmentResult)
        assert result.verdict == VERDICT_MISSING_PREFACTORING_ASSESSMENT, (
            f"expected {VERDICT_MISSING_PREFACTORING_ASSESSMENT!r} for an "
            f"absent section -- got {result.verdict!r} (detail={result.detail!r})"
        )

    def test_prefactoring_slice_recorded_is_accepted(self) -> None:
        """CASE 2 (dispatch): the assessment names a `@prefactoring` slice
        doing the reshaping work -- ACCEPT (Class-P)."""
        body = (
            "A dedicated `@prefactoring` slice-00 extends `FooPort` to accept "
            "the new parameter before slice-01 begins, avoiding a mid-feature "
            "shape change."
        )
        result = validate_prefactoring_assessment_content(_design_delta(body))

        assert result.verdict == VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED, (
            f"expected {VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED!r} for a "
            f"recorded @prefactoring slice -- got {result.verdict!r} "
            f"(detail={result.detail!r})"
        )

    def test_justified_none_is_accepted(self) -> None:
        """CASE 3 (dispatch): a NONE naming what was examined + why the
        existing shape fits -- ACCEPT (justified skip)."""
        body = (
            "**NONE -- justified.** This feature extends `git_run`/`git_text` "
            "at their EXISTING generic seams with no shape compromise; no "
            "component is bent into an unnatural shape to receive this "
            "feature -- there is no `@prefactoring` slice to author."
        )
        result = validate_prefactoring_assessment_content(_design_delta(body))

        assert result.verdict == VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED, (
            f"expected {VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED!r} for a "
            f"justified NONE -- got {result.verdict!r} (detail={result.detail!r})"
        )

    def test_unmotivated_none_is_rejected(self) -> None:
        """Skip-requires-justification floor: a bare 'NONE.' with no
        reasoning is NOT a justified skip -- REJECT."""
        result = validate_prefactoring_assessment_content(_design_delta("NONE."))

        assert result.verdict == VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT, (
            f"expected {VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT!r} for a "
            f"bare, unmotivated NONE -- got {result.verdict!r} "
            f"(detail={result.detail!r})"
        )

    def test_empty_section_is_rejected(self) -> None:
        """Skip-requires-justification floor: a heading with an empty body
        is likewise unmotivated -- REJECT."""
        result = validate_prefactoring_assessment_content(_design_delta(""))

        assert result.verdict == VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT, (
            f"expected {VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT!r} for an "
            f"empty section body -- got {result.verdict!r} "
            f"(detail={result.detail!r})"
        )

    def test_no_design_wave_scopes_the_gate_out(self) -> None:
        """Scoping boundary: a feature-delta with no `## Wave: DESIGN`
        section has nothing to assess -- the gate is a no-op ACCEPT
        (`prefactoring-not-required`), regardless of whether a
        `## Prefactoring Assessment` section is present or absent."""
        no_design_delta = "## Wave: DISCUSS / [REF] Slice Plan\n\n| Slice |\n|---|\n"

        result = validate_prefactoring_assessment_content(no_design_delta)

        assert result.verdict == VERDICT_PREFACTORING_NOT_REQUIRED, (
            f"expected {VERDICT_PREFACTORING_NOT_REQUIRED!r} for a "
            f"DESIGN-skipped feature-delta -- got {result.verdict!r} "
            f"(detail={result.detail!r})"
        )
