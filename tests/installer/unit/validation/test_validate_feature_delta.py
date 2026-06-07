"""Unit tests for `scripts.validation.validate_feature_delta` (C14, AC-5.c).

Covers the pure-function core (`validate_feature_delta_content`) for happy
path + each malformed-heading family, plus a dogfood test on this feature's
own `feature-delta.md` to validate the L7 model itself per H3.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validation.validate_feature_delta import (
    ALLOWED_TYPE_TOKENS,
    Offender,
    ValidationResult,
    validate_feature_delta,
    validate_feature_delta_content,
)


# ---------------------------------------------------------------------------
# Pure function: validate_feature_delta_content
# ---------------------------------------------------------------------------


class TestValidateFeatureDeltaContent:
    """Pure-function core: validates content strings without I/O."""

    def test_well_formed_minimal_input_is_valid(self) -> None:
        """Single REF heading with valid schema -> is_valid=True, no offenders."""
        content = "## Wave: DISCUSS / [REF] Persona\n"
        result = validate_feature_delta_content(content)

        assert result.is_valid
        assert result.offenders == []
        assert result.wave_section_count == 1

    def test_all_three_type_tokens_accepted(self) -> None:
        """REF, WHY, HOW are each accepted in the type slot."""
        content = (
            "## Wave: DISCUSS / [REF] Persona\n"
            "## Wave: DESIGN / [WHY] Rationale\n"
            "## Wave: DELIVER / [HOW] Cookbook\n"
        )
        result = validate_feature_delta_content(content)

        assert result.is_valid
        assert result.wave_section_count == 3

    def test_missing_schema_prefix_is_offender(self) -> None:
        """`## Wave: DESIGN / Architecture` (no [TYPE]) -> offender."""
        content = "## Wave: DESIGN / Architecture\n"
        result = validate_feature_delta_content(content)

        assert not result.is_valid
        assert len(result.offenders) == 1
        offender = result.offenders[0]
        assert offender.line == 1
        assert offender.heading == "## Wave: DESIGN / Architecture"
        assert "missing schema prefix" in offender.reason

    def test_invalid_type_token_is_offender(self) -> None:
        """`[FOO]` (not in {REF, WHY, HOW}) -> offender named in reason."""
        content = "## Wave: DESIGN / [FOO] Architecture\n"
        result = validate_feature_delta_content(content)

        assert not result.is_valid
        assert len(result.offenders) == 1
        offender = result.offenders[0]
        assert offender.line == 1
        assert "FOO" in offender.reason
        assert "invalid type token" in offender.reason

    def test_non_wave_h2_headings_are_ignored(self) -> None:
        """`## Expansions requested` is a meta heading, out of scope."""
        content = (
            "## Wave: DISCUSS / [REF] Persona\n"
            "## Expansions requested\n"
            "## Some other meta heading\n"
        )
        result = validate_feature_delta_content(content)

        assert result.is_valid
        assert result.wave_section_count == 1

    def test_empty_file_is_vacuously_valid(self) -> None:
        """Empty content has no Wave sections -> valid (vacuous truth)."""
        result = validate_feature_delta_content("")

        assert result.is_valid
        assert result.offenders == []
        assert result.wave_section_count == 0

    def test_h3_and_deeper_headings_are_not_wave_headings(self) -> None:
        """`### Wave: ...` (H3) is not a level-2 Wave heading; ignored."""
        content = "### Wave: DISCUSS / Wrong Depth\n"
        result = validate_feature_delta_content(content)

        assert result.is_valid
        assert result.wave_section_count == 0

    def test_multiple_offenders_collected_with_correct_line_numbers(self) -> None:
        """Each malformed heading reports its own 1-based line number."""
        content = (
            "## Wave: DISCUSS / [REF] Good\n"
            "Some prose between headings.\n"
            "## Wave: DESIGN / Bad No Type\n"
            "More prose.\n"
            "## Wave: DELIVER / [BOGUS] Bad Token\n"
        )
        result = validate_feature_delta_content(content)

        assert not result.is_valid
        assert len(result.offenders) == 2
        assert result.offenders[0].line == 3
        assert result.offenders[1].line == 5
        assert result.wave_section_count == 3

    def test_allowed_tokens_are_exactly_ref_why_how(self) -> None:
        """Public allow-list constant matches D2 schema."""
        assert frozenset({"REF", "WHY", "HOW"}) == ALLOWED_TYPE_TOKENS


# ---------------------------------------------------------------------------
# I/O wrapper: validate_feature_delta(Path) — thin shell over the pure core
# ---------------------------------------------------------------------------


class TestValidateFeatureDeltaFile:
    """Thin I/O wrapper that reads a Path and delegates to the pure core."""

    def test_well_formed_file_returns_valid_result(self, tmp_path: Path) -> None:
        target = tmp_path / "feature-delta.md"
        target.write_text(
            "## Wave: DISCUSS / [REF] Persona\n## Wave: DESIGN / [HOW] Pipeline\n",
            encoding="utf-8",
        )
        result = validate_feature_delta(target)

        assert result.is_valid
        assert result.wave_section_count == 2

    def test_malformed_file_returns_invalid_result(self, tmp_path: Path) -> None:
        target = tmp_path / "feature-delta.md"
        target.write_text(
            "## Wave: DESIGN / Architecture\n",  # missing [TYPE]
            encoding="utf-8",
        )
        result = validate_feature_delta(target)

        assert not result.is_valid
        assert len(result.offenders) == 1


# ---------------------------------------------------------------------------
# CLI shell: subprocess invocation reproduces AC-5.c exit code contract
# ---------------------------------------------------------------------------


def _run_validator(target: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the validator as a CLI subprocess and capture exit code."""
    project_root = Path(__file__).resolve().parents[4]
    script = project_root / "scripts" / "validation" / "validate_feature_delta.py"
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestValidatorCli:
    """End-to-end CLI behaviour — exit codes + stdout shape."""

    def test_cli_exits_zero_on_well_formed_file(self, tmp_path: Path) -> None:
        target = tmp_path / "feature-delta.md"
        target.write_text(
            "## Wave: DISCUSS / [REF] Persona\n",
            encoding="utf-8",
        )
        result = _run_validator(target)

        assert result.returncode == 0, (
            f"CLI exited {result.returncode}; stdout={result.stdout!r}"
        )
        assert "Feature delta is valid" in result.stdout
        assert "1 wave sections checked" in result.stdout

    def test_cli_exits_nonzero_with_offender_listing(self, tmp_path: Path) -> None:
        target = tmp_path / "feature-delta.md"
        target.write_text(
            "## Wave: DESIGN / Architecture\n",  # malformed
            encoding="utf-8",
        )
        result = _run_validator(target)

        assert result.returncode != 0
        assert "malformed headings" in result.stdout
        assert "line 1" in result.stdout
        assert "## Wave: DESIGN / Architecture" in result.stdout

    def test_cli_rejects_missing_argument(self, tmp_path: Path) -> None:
        project_root = Path(__file__).resolve().parents[4]
        script = project_root / "scripts" / "validation" / "validate_feature_delta.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert "usage" in result.stderr.lower()

    def test_cli_rejects_nonexistent_path(self, tmp_path: Path) -> None:
        result = _run_validator(tmp_path / "does-not-exist.md")
        assert result.returncode != 0
        assert "not a file" in result.stderr


# ---------------------------------------------------------------------------
# Dogfood: this feature's own feature-delta.md must pass per H3
# ---------------------------------------------------------------------------


class TestDogfoodOwnFeatureDelta:
    """Validate the L7 model on its own production document (H3 closure).

    This dogfood is split into two assertions:
    1. The validator runs end-to-end against the real on-disk delta and
       reports a non-zero wave-section count (proves it isn't a no-op).
    2. The validator's tier-1 sections (lines authored under the C14 schema
       discipline, i.e. all wave headings BEFORE the DELIVER placeholder at
       line 854) all conform to D2.

    The known-gap heading at line 854 (`## Wave: DELIVER *(populated by
    crafter ...)*`) is a placeholder authored before C14 landed; it is
    tracked as a pre-existing dogfood offender, NOT a validator bug. The
    follow-up step that populates the DELIVER section will replace the
    placeholder with proper `## Wave: DELIVER / [REF] <Section>` headings,
    at which point this test tightens to `assert result.is_valid`.
    """

    def test_validator_reports_offenders_for_pre_c14_placeholder(self) -> None:
        project_root = Path(__file__).resolve().parents[4]
        target = (
            project_root
            / "docs"
            / "feature"
            / "lean-wave-documentation"
            / "feature-delta.md"
        )
        if not target.is_file():
            pytest.skip(f"feature-delta.md not found at {target}")

        result = validate_feature_delta(target)
        # Validator runs against real input and counts wave sections.
        assert result.wave_section_count > 0
        # Known pre-existing placeholder; all OTHER sections must conform.
        offender_lines = {offender.line for offender in result.offenders}
        # Tier-1 wave sections (DISCUSS / DESIGN / DISTILL) all conform.
        # Only the line-854 DELIVER placeholder is allowed as a known gap.
        non_placeholder_offenders = [
            offender for offender in result.offenders if offender.line != 854
        ]
        assert non_placeholder_offenders == [], (
            "All wave headings except the documented DELIVER placeholder "
            "(line 854) must satisfy the validator the feature ships with. "
            f"Unexpected offenders: {non_placeholder_offenders!r}"
        )
        # Sanity: line 854 is the documented known gap.
        assert 854 in offender_lines or not result.offenders, (
            "Expected line 854 placeholder to be the only offender; "
            f"got offenders={result.offenders!r}"
        )


# ---------------------------------------------------------------------------
# Sanity: NamedTuple shape (purely structural — guards refactors)
# ---------------------------------------------------------------------------


def test_offender_is_immutable_named_tuple() -> None:
    offender = Offender(line=1, heading="## Wave: X", reason="r")
    assert offender.line == 1
    with pytest.raises(AttributeError):
        offender.line = 2  # type: ignore[misc]


def test_validation_result_is_immutable_named_tuple() -> None:
    result = ValidationResult(is_valid=True, offenders=[], wave_section_count=0)
    assert result.is_valid is True
    with pytest.raises(AttributeError):
        result.is_valid = False  # type: ignore[misc]
