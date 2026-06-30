"""Unit tests for `des.cli.validate_feature_delta` (C14, AC-5.c).

Covers the pure-function core (`validate_feature_delta_content`) for happy
path + each malformed-heading family, plus a dogfood test on this feature's
own `feature-delta.md` to validate the L7 model itself per H3.
"""

from __future__ import annotations

# des:allow-module-form: this suite drives the registered `validate-feature-delta`
# subcommand via `python -m des.cli.validate_feature_delta` as its hermetic
# Layer-3 SUT -- P3-sanctioned per the rescoped single-entry-point migration gate
# (docs/feature/single-entry-point/feature-delta.md slice-04, AT-07).
import os
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import (
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


def _validator_argv(*args: str) -> list[str]:
    """Build the `python -m des.cli.validate_feature_delta` argv."""
    return [sys.executable, "-m", "des.cli.validate_feature_delta", *args]


def _validator_env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH so `des.*` is importable in the subprocess."""
    project_root = Path(__file__).resolve().parents[4]
    env = dict(os.environ)
    src = str(project_root / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    return env


def _run_validator(target: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the validator as a CLI subprocess and capture exit code."""
    return subprocess.run(
        _validator_argv(str(target)),
        capture_output=True,
        text=True,
        timeout=30,
        env=_validator_env(),
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
        result = subprocess.run(
            _validator_argv(),
            capture_output=True,
            text=True,
            timeout=30,
            env=_validator_env(),
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
        # Identify the placeholder by its heading CONTENT, not by line number —
        # the line shifts whenever the doc is edited (e.g. decision-F removed the
        # DISCUSS Driving Ports section), so a hard-coded line is brittle.
        non_placeholder_offenders = [
            offender
            for offender in result.offenders
            if "populated by crafter" not in offender.heading
        ]
        assert non_placeholder_offenders == [], (
            "All wave headings except the documented DELIVER placeholder "
            "(`## Wave: DELIVER *(populated by crafter …)*`) must satisfy the "
            f"validator the feature ships with. Unexpected offenders: {non_placeholder_offenders!r}"
        )
        # Sanity: the DELIVER placeholder IS reported as the documented known gap
        # (identified by content, not line — robust to line shifts).
        placeholder_offenders = [
            offender
            for offender in result.offenders
            if "populated by crafter" in offender.heading
        ]
        assert placeholder_offenders or not result.offenders, (
            "Expected the DELIVER placeholder (populated by crafter) to be the "
            f"only offender; got offenders={result.offenders!r}"
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


# ---------------------------------------------------------------------------
# slice-06 cohesion-MECC gate (nwave-flow-v2-enforcement)
#
# These three tests drive `validate_slice_plan_content` — the same driving
# port used by `--require-slice-plan --format=json` — and pin the new
# `rejected-infra-only` verdict (§22.0 MECC floor).
#
# AT-1 is active-RED: the validator currently returns `accepted` on an
# all-@infrastructure plan (grep-verified 2026-06-09 — `_classify_slice_cohesion`
# does not exist yet). DELIVER adds the function and the verdict token; AT-1
# then goes GREEN.
#
# AT-2 and AT-3 are preservation-GREEN: they assert that the MECC does NOT
# fire on value-bearing plans, so DELIVER cannot introduce a false-positive.
# They PASS on master and must stay GREEN after the change.
# ---------------------------------------------------------------------------
from des.cli.validate_feature_delta import (
    VERDICT_ACCEPTED,
    validate_slice_plan_content,
)


#: Well-formed feature-delta preamble required by `validate_slice_plan_content`
#: (it runs heading-form validation first; all scenario fixtures add a valid
#: DISCUSS/[REF] heading so the heading check does not shadow the cohesion check).
_PREAMBLE = "## Wave: DISCUSS / [REF] Slice Plan\n\n"

#: The five-column header row + separator that every fixture needs.
_HEADER = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
)


def _make_plan(*annotation_rows: str) -> str:
    """Build minimal feature-delta content for the cohesion check.

    Each element of `annotation_rows` is the full pipe-delimited data row
    (e.g. ``"| slice-01 | Deploy infra | pending | @infrastructure | — |"``).
    """
    rows = "\n".join(annotation_rows)
    return f"{_PREAMBLE}{_HEADER}{rows}\n"


class TestCohesionMECC:
    """slice-06 (nwave-flow-v2-enforcement): the MECC floor for infra-only plans.

    Contract shape: pure-function (validate_slice_plan_content is return-only,
    zero I/O, zero mutation).  The driving port is the in-process
    `validate_slice_plan_content` call — same surface the `--require-slice-plan
    --format=json` CLI drives (Layer 3 composition).

    @contract-shape:bounded-change (AT-1): adding _classify_slice_cohesion
    changes the verdict token for all-@infrastructure content from `accepted`
    to `rejected-infra-only`; the detail string conveys the reason; the
    SlicePlanResult VO shape is unchanged.

    @contract-shape:unbounded-preservation (AT-2, AT-3): any value-bearing
    plan — regardless of how many @infrastructure rows it also contains —
    must remain `accepted` after the change.
    """

    # ------------------------------------------------------------------
    # AT-1 (active-RED) — all-@infrastructure plan → rejected-infra-only
    #
    # Currently returns `accepted` (no _classify_slice_cohesion exists).
    # DELIVER adds the function; this assertion then passes.
    # ------------------------------------------------------------------
    def test_all_infrastructure_slice_plan_is_rejected(self) -> None:
        """An all-@infrastructure plan is rejected by the MECC floor.

        Every data row carries `@infrastructure` in the Annotation column.
        The MECC veto returns `rejected-infra-only` (non-zero exit contract)
        instead of the previous `accepted`.

        ACTIVE-RED: `validate_slice_plan_content` currently returns `accepted`
        on this input — `_classify_slice_cohesion` has not been implemented yet.
        """
        content = _make_plan(
            "| slice-01 | Deploy shared infra | shipped | @infrastructure | CI runner setup |",
            "| slice-02 | Configure pipeline  | pending | @infrastructure | Pipeline wiring |",
        )

        result = validate_slice_plan_content(content)

        assert result.verdict == "rejected-infra-only", (
            f"Expected `rejected-infra-only` for an all-@infrastructure plan "
            f"but got {result.verdict!r}. "
            f"(_classify_slice_cohesion not yet implemented — this is the active-RED signal.)"
        )
        # AT-review L2: pin a domain substring so a wrong-reason detail can't pass.
        assert "infrastructure" in result.detail.lower(), (
            f"detail must name the infra-only cohesion reason; got {result.detail!r}"
        )

    # ------------------------------------------------------------------
    # AT-2 (preservation-GREEN) — empty Annotation → accepted (no false-positive)
    #
    # A plan with at least one value-bearing row (empty Annotation) must
    # stay `accepted` after DELIVER adds the cohesion check.
    # ------------------------------------------------------------------
    def test_value_bearing_slice_plan_is_not_rejected(self) -> None:
        """A plan with a value-bearing (empty Annotation) row stays accepted.

        The MECC fires ONLY on the all-@infrastructure case.  A single
        plain value-bearing slice is sufficient to make the gate step aside.

        PRESERVATION-GREEN: passes on master (accepted) and must stay green
        after DELIVER's change.
        """
        content = _make_plan(
            "| slice-01 | Operator sees live status | pending |  | Core user-visible value |",
        )

        result = validate_slice_plan_content(content)

        assert result.verdict == VERDICT_ACCEPTED, (
            f"A value-bearing plan (empty Annotation) must remain `accepted`; "
            f"got {result.verdict!r}. The cohesion gate must not produce a false-positive."
        )

    # ------------------------------------------------------------------
    # AT-3 (preservation-GREEN) — mixed plan → accepted (boundary case)
    #
    # At least one value-bearing row in an otherwise infra-heavy plan is
    # sufficient; the MECC only vetoes the ALL-infra structural case.
    # ------------------------------------------------------------------
    def test_mixed_plan_with_one_value_bearing_row_is_accepted(self) -> None:
        """A mixed plan (some @infrastructure + ≥1 value-bearing) stays accepted.

        The MECC is conservative: it vetoes only when EVERY row is
        @infrastructure.  One empty or @walking-skeleton Annotation is enough
        for the gate to step aside and return `accepted`.

        PRESERVATION-GREEN: passes on master and must stay green after DELIVER.
        """
        content = _make_plan(
            "| slice-01 | Deploy shared infra | shipped | @infrastructure | CI setup only |",
            "| slice-02 | Operator sees live status | pending |  | Core user value |",
            "| slice-03 | Bootstrap observability | pending | @infrastructure | Infra wiring |",
        )

        result = validate_slice_plan_content(content)

        assert result.verdict == VERDICT_ACCEPTED, (
            f"A mixed plan with ≥1 value-bearing row must remain `accepted`; "
            f"got {result.verdict!r}. The MECC veto must only fire on the all-infra case."
        )
