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
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import (
    ALLOWED_TYPE_TOKENS,
    VERDICT_INDETERMINATE,
    Offender,
    ValidationResult,
    next_h2_boundary,
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


# ---------------------------------------------------------------------------
# Regression: Reuse Analysis content-grounding
# (F-fix-reuse-analysis-content-grounding, WS-9, 2026-07-07)
#
# RCA: `--require-reuse-analysis` validates the Reuse Analysis table's SHAPE
# only (heading / columns / decision-token, `validate_reuse_analysis_content`
# above) but never grounds the `Existing Component | File` citation against
# the real file the row claims to reuse -- a row can cite a symbol that DOES
# NOT EXIST in the named file and the gate accepts it exactly like a real
# citation. The sibling `component-manifest.yaml` gate IS grep-grounded
# (`scripts/cli/validate_component_manifest.py:37 _ground_sut`); Reuse
# Analysis is not -- this is the asymmetry the fix closes.
#
# Fix direction (Ale 2026-07-07, tool-agnostic outcome, no bespoke grep):
# ground the citation THROUGH the `CodeFactPort` chain
# (`des.ports.code_fact_port` + `des.adapters.driven.codefact.code_fact_chain`)
# -- Tsunami-first, AST fallback, textsearch floor, degrade-LOUD. An
# unresolvable citation REFUSES the feature-delta with a NEW closed-set
# verdict token this AT pins as `ungrounded-reuse-analysis` (kebab-case,
# mirrors the existing `missing-reuse-analysis` / `malformed-reuse-analysis`
# family).
#
# `VERDICT_UNGROUNDED_REUSE_ANALYSIS` below is deliberately a PLAIN STRING
# LITERAL, NOT an import from `des.cli.validate_feature_delta` -- the constant
# does not exist yet. Importing a name that isn't there would raise
# `ImportError` at collection time (a BROKEN failure), not the semantic
# `AssertionError` active-RED requires (ADR-025 / nw-distill-red-scaffolding).
# AT-a below fails RED-for-the-right-reason today: the CLI answers
# `structurally-accepted` (shape-only), not the new token.
# ---------------------------------------------------------------------------

#: The new closed-set verdict token this AT pins for the content-grounding
#: fix. Chosen (not yet implemented) name; the crafter's fix must emit this
#: exact string on an unresolvable `Existing Component | File` citation.
VERDICT_UNGROUNDED_REUSE_ANALYSIS = "ungrounded-reuse-analysis"

#: A REAL, port-resolvable citation: `validate_reuse_analysis_content` is a
#: real module-level function DEFINED in this very file
#: (`src/des/cli/validate_feature_delta.py`, confirmed by direct Read
#: 2026-07-07) -- any CodeFactPort tier (Tsunami / AST / textsearch) resolves
#: it.
_REAL_SYMBOL = "validate_reuse_analysis_content"
_REAL_FILE = "src/des/cli/validate_feature_delta.py"

#: A symbol GUARANTEED ABSENT from `_REAL_FILE` -- no CodeFactPort tier can
#: resolve it; the file exists, the symbol inside it does not (the "phantom
#: component" class the RCA names).
_PHANTOM_SYMBOL = "PhantomReuseAnalysisComponentNeverDefined"


def _reuse_analysis_feature_delta(existing_component: str, file_cell: str) -> str:
    """Build a minimal well-formed-SHAPE Reuse Analysis section. Pure helper.

    `validate_reuse_analysis_content` (the pure core `--require-reuse-analysis`
    drives) parses the bare `## Reuse Analysis` section directly -- unlike
    `validate_slice_plan_content` it does NOT require a preceding Wave
    heading. One CREATE_NEW data row with a non-empty Justification keeps the
    row shape-valid (DDD-3) so ONLY the new content-grounding check can reject
    it -- isolating the regression from every pre-existing shape check.
    """
    return (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| `{existing_component}` | `{file_cell}` | none | CREATE_NEW | "
        "fixture row for the content-grounding regression AT |\n"
    )


def _run_require_reuse_analysis_json(
    target: Path, project_root: Path
) -> tuple[int, dict[str, object]]:
    """Invoke `des validate-feature-delta --require-reuse-analysis --format=json`.

    `cwd=project_root` pins the repo root as the resolution base for `File`
    citations (e.g. `src/des/cli/validate_feature_delta.py`) -- the SAME base
    `_ground_sut` uses for `sut:` citations
    (`scripts/cli/validate_component_manifest.py:34 _REPO_ROOT`), so a
    repo-relative `File` cell grounds identically to the sibling gate.
    """
    result = subprocess.run(
        _validator_argv("--require-reuse-analysis", "--format=json", str(target)),
        capture_output=True,
        text=True,
        timeout=30,
        env=_validator_env(),
        cwd=project_root,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


class TestReuseAnalysisContentGrounding:
    """Regression: `--require-reuse-analysis` must ground `Existing Component |
    File` citations, not just validate the table's shape (WS-9,
    F-fix-reuse-analysis-content-grounding).

    Driving port: Layer-3 subprocess CLI boundary (`des validate-feature-delta
    --require-reuse-analysis --format=json`) -- the real entry point the
    crafter's fix wires the CodeFactPort grounding onto, and the AC-5.c JSON
    verdict-token contract the AT reads (never a free-text stdout substring).

    @contract-shape:bounded-change (AT-a): a phantom `Existing Component |
    File` citation moves the verdict from `structurally-accepted` (today,
    shape-only) to `ungrounded-reuse-analysis` (the new content-grounded
    rejection).

    @contract-shape:unbounded-preservation (AT-b): any REAL, port-resolvable
    citation stays `structurally-accepted` -- the fix must not over-reject
    legitimate reuse rows.
    """

    # ------------------------------------------------------------------
    # AT-a (active-RED) -- phantom citation -> ungrounded-reuse-analysis
    #
    # CURRENT: the gate is shape-only and answers `structurally-accepted` for
    # ANY well-formed row regardless of whether the citation is real --
    # `validate_reuse_analysis_content` never touches the filesystem /
    # CodeFactPort (confirmed by direct Read of the function body, 2026-07-07).
    # ------------------------------------------------------------------
    def test_phantom_citation_is_rejected_as_ungrounded(self, tmp_path: Path) -> None:
        """A row citing a symbol absent from a real file is REFUSED.

        `PhantomReuseAnalysisComponentNeverDefined` does not exist anywhere in
        `src/des/cli/validate_feature_delta.py` (a real, existing file) -- no
        CodeFactPort tier can resolve it. The gate must REFUSE the
        feature-delta with the new `ungrounded-reuse-analysis` verdict and a
        non-zero exit.

        ACTIVE-RED: today's gate has no content-grounding step and answers
        `structurally-accepted` (shape-only) for this same fixture.
        """
        target = tmp_path / "feature-delta.md"
        target.write_text(
            _reuse_analysis_feature_delta(_PHANTOM_SYMBOL, _REAL_FILE),
            encoding="utf-8",
        )
        project_root = Path(__file__).resolve().parents[4]

        exit_code, payload = _run_require_reuse_analysis_json(target, project_root)

        assert payload.get("verdict") == VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
            f"Expected the new {VERDICT_UNGROUNDED_REUSE_ANALYSIS!r} verdict for "
            f"a phantom citation ({_PHANTOM_SYMBOL!r} is absent from "
            f"{_REAL_FILE}); got {payload.get('verdict')!r}. (No content-"
            f"grounding step exists yet -- this is the active-RED signal; the "
            f"gate is shape-only per validate_reuse_analysis_content, DDD-8.)"
        )
        assert exit_code != 0, (
            "A phantom / ungrounded citation must REFUSE the feature-delta "
            f"(non-zero exit); got exit_code={exit_code}."
        )

    # ------------------------------------------------------------------
    # AT-b (guard, may already pass) -- real citation -> stays accepted
    #
    # Locks the no-over-reject invariant: once grounding lands, a row citing a
    # symbol that genuinely exists in the named file must NOT be rejected.
    # ------------------------------------------------------------------
    def test_real_citation_stays_structurally_accepted(self, tmp_path: Path) -> None:
        """A row citing a REAL, port-resolvable symbol stays accepted.

        `validate_reuse_analysis_content` is a real module-level function
        DEFINED in `src/des/cli/validate_feature_delta.py` -- every
        CodeFactPort tier (Tsunami / AST / textsearch) resolves it. The
        grounding fix must NOT reject this row: over-rejecting a legitimate
        reuse citation is the exact regression this guard exists to catch.
        """
        target = tmp_path / "feature-delta.md"
        target.write_text(
            _reuse_analysis_feature_delta(_REAL_SYMBOL, _REAL_FILE),
            encoding="utf-8",
        )
        project_root = Path(__file__).resolve().parents[4]

        exit_code, payload = _run_require_reuse_analysis_json(target, project_root)

        assert payload.get("verdict") == "structurally-accepted", (
            f"A REAL, port-resolvable citation ({_REAL_SYMBOL!r} genuinely "
            f"defined in {_REAL_FILE}) must stay `structurally-accepted`; got "
            f"{payload.get('verdict')!r}. The content-grounding fix must not "
            f"over-reject a legitimate reuse row."
        )
        assert exit_code == 0, (
            f"A structurally-accepted, content-grounded citation must exit 0; "
            f"got exit_code={exit_code}."
        )

    # ------------------------------------------------------------------
    # AT-c (guard, passes today) -- the grounding fact is CodeFactPort-
    # derivable WITHOUT Tsunami (tool-agnostic per the fix direction).
    #
    # Drives the REAL `CodeFactChain` -- the composition the fix is directed
    # to ground through -- with `tsunami_present=False` forced (never mocked:
    # `TsunamiAdapter.probe()` returns exactly its constructor `present` flag,
    # verified by direct Read 2026-07-07), so the query is answered by the
    # AST / textsearch floor tiers alone. Proves the phantom-vs-real
    # distinction AT-a / AT-b need is derivable on a machine with NO Tsunami:
    # the floor alone tells the phantom symbol apart from the real one. This
    # is the enabling mechanism the fix wires the gate onto -- the genuine
    # port entrypoint (`CodeFactChain.query`), callable directly from a pytest
    # AT, per the RCA's "assert at the CLI boundary only if the port
    # entrypoint isn't callable" guidance.
    # ------------------------------------------------------------------
    def test_grounding_fact_resolves_via_codefactport_without_tsunami(self) -> None:
        from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
        from des.ports.code_fact_port import (
            CAPABILITY_ATOMS_IN_FILE,
            CapabilityDescriptor,
        )

        project_root = Path(__file__).resolve().parents[4]
        target_file = project_root / _REAL_FILE
        assert target_file.is_file(), (
            f"fixture assumption broken: {_REAL_FILE} must exist under the "
            f"repo root for this AT to mean anything; checked {target_file}"
        )

        chain = CodeFactChain(root=target_file, tsunami_present=False)
        descriptor = CapabilityDescriptor(
            id=CAPABILITY_ATOMS_IN_FILE,
            stability="stable",
            contract_version="1.0.0",
            io_schema="atoms-in-file/1",
            providing_adapter="ast",
        )

        result = chain.query(descriptor, {})

        assert result is not None, (
            "the atoms-in-file stable-core capability must always answer "
            "(the universal floor guarantees a non-empty answer on any "
            "Python-only target, ADR-LA-001 §5)"
        )
        assert result.confidence != "binding-resolved", (
            f"tsunami_present=False must force the floor tiers (ast/"
            f"textsearch), never the paid tier; got "
            f"confidence={result.confidence!r}"
        )
        atoms = (
            result.payload.get("atoms", []) if isinstance(result.payload, dict) else []
        )
        assert _REAL_SYMBOL in atoms, (
            f"the real symbol {_REAL_SYMBOL!r} must resolve as an atom of "
            f"{_REAL_FILE} via the Tsunami-absent floor chain; got "
            f"atoms={atoms!r}"
        )
        assert _PHANTOM_SYMBOL not in atoms, (
            f"the phantom symbol {_PHANTOM_SYMBOL!r} must NOT resolve as an "
            f"atom of {_REAL_FILE} -- it does not exist there; got "
            f"atoms={atoms!r}"
        )
        assert any(
            event.endswith("tsunami-absent") for event in chain.health_events()
        ), (
            "the chain must record a LOUD health-event when it skips the "
            "absent Tsunami tier (degrade-LOUD, never a silent skip); got "
            f"health_events={chain.health_events()!r}"
        )

    # ------------------------------------------------------------------
    # AT-d (active-RED, WS-9b hardening) -- a citation naming a REAL but
    # NON-PYTHON / unparseable file must degrade LOUD to the closed-set
    # verdict, never CRASH the CLI (Vera examine 2026-07-07, regression).
    #
    # RCA (empirically confirmed 2026-07-07): `_component_citation_is_grounded`
    # builds `CodeFactChain(root=file_path)` and queries
    # `CAPABILITY_ATOMS_IN_FILE`. With Tsunami absent (the default OSS case)
    # the chain falls to `AstAdapter`, whose `_iter_files` returns
    # `[self._root]` unconditionally when `root.is_file()` -- NO extension /
    # filetype check -- and `_parse` calls the delegated
    # `PythonAstAdapter.parse`, a bare `ast.parse(source, filename=filename)`
    # with NO `except SyntaxError`. Citing `pyproject.toml` (a REAL file at
    # the repo root, valid TOML, NOT valid Python syntax -- direct repro:
    # `ast.parse(open("pyproject.toml").read())` raises `SyntaxError: cannot
    # assign to expression here...` at line 3) propagates that SyntaxError,
    # uncaught, through `validate_reuse_analysis_content` ->
    # `_run_require_reuse_analysis` -> `main` -- crashing the CLI with a
    # Python traceback instead of a clean gate refusal.
    #
    # This is an AGNOSTICISM defect, not a one-off: `AstAdapter` always
    # speaks Python `ast` regardless of the cited file's real language, so a
    # TypeScript project's Reuse Analysis citing a `.ts` file hits the
    # identical crash class.
    #
    # ACTIVE-RED: today's gate has no parse-failure guard -- it crashes. The
    # fix must catch the unparseable-citation case and degrade LOUD to the
    # SAME `ungrounded-reuse-analysis` verdict AT-a already pins for a
    # phantom symbol -- an unresolvable-because-unparseable citation is the
    # SAME failure CLASS as a phantom citation from the gate's point of view.
    # ------------------------------------------------------------------
    def test_nonpython_citation_degrades_loud_instead_of_crashing(
        self, tmp_path: Path
    ) -> None:
        """A citation naming a real-but-non-Python file REFUSES cleanly, never crashes.

        `pyproject.toml` is a REAL file at the repo root (guaranteed present in
        every dev/CI checkout) that is NOT valid Python syntax. The gate must
        REFUSE (non-zero exit) and MUST NOT print an uncaught Python traceback
        -- the crash this AT originally pinned as the regression.

        RECONCILED (F-fix-delta-grounding-incapacity-is-indeterminate, Sister
        G-8): a non-Python file is a grounding INCAPACITY (no CodeFactPort tier
        can structurally analyze it), not a genuine absence -- the verdict is
        `VERDICT_INDETERMINATE`, never the phantom `ungrounded-reuse-analysis`
        token this AT pinned before the fix. The crash-free / non-zero-exit
        contract this AT exists to protect is unchanged.
        """
        project_root = Path(__file__).resolve().parents[4]
        non_python_file = project_root / "pyproject.toml"
        assert non_python_file.is_file(), (
            f"fixture assumption broken: {non_python_file} must exist at the "
            f"repo root for this AT to mean anything"
        )

        target = tmp_path / "feature-delta.md"
        target.write_text(
            _reuse_analysis_feature_delta("SomeComponent", "pyproject.toml"),
            encoding="utf-8",
        )

        result = subprocess.run(
            _validator_argv("--require-reuse-analysis", "--format=json", str(target)),
            capture_output=True,
            text=True,
            timeout=30,
            env=_validator_env(),
            cwd=project_root,
        )
        combined_output = result.stdout + result.stderr

        assert "Traceback (most recent call last)" not in combined_output, (
            "the gate must degrade LOUD to a closed-set verdict on an "
            "unparseable citation, never crash with an uncaught Python "
            f"traceback; got exit_code={result.returncode}, "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
        assert "SyntaxError" not in combined_output, (
            "the underlying SyntaxError from ast.parse on a non-Python "
            "citation must be caught and degraded, not leaked to the CLI "
            f"surface; got stderr={result.stderr!r}"
        )

        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        assert payload.get("verdict") == VERDICT_INDETERMINATE, (
            f"a citation naming a real-but-non-Python file (pyproject.toml is "
            f"not valid Python syntax) is a grounding INCAPACITY -- no "
            f"CodeFactPort tier can analyze it -- so it must degrade to "
            f"{VERDICT_INDETERMINATE!r}, never the phantom "
            f"{VERDICT_UNGROUNDED_REUSE_ANALYSIS!r} verdict; got "
            f"verdict={payload.get('verdict')!r} "
            f"(exit_code={result.returncode}, stdout={result.stdout!r})."
        )
        assert result.returncode != 0, (
            "an INDETERMINATE grounding outcome must still REFUSE the "
            f"feature-delta with a non-zero exit; got "
            f"exit_code={result.returncode}"
        )


# ---------------------------------------------------------------------------
# GDP-8 arity corollary — an ABSENT Slice Plan section and a PRESENT one that
# declares no parallel slice are two different facts and must not collapse
# into the same empty answer at the accessor boundary.
# ---------------------------------------------------------------------------
from des.cli.validate_feature_delta import read_declared_parallel_slice_ids


class TestDeclaredParallelSliceIdsArity:
    """`read_declared_parallel_slice_ids` keeps the third state reachable.

    `None` means "the document carries no Slice Plan heading at all" — a
    structural omission the consumer blocks on. `()` means "the section is
    there and declares zero parallel slices" — a valid monolithic feature.
    """

    def test_absent_slice_plan_heading_returns_none(self) -> None:
        content = "# feature-delta\n\nProse only; no Slice Plan section.\n"

        assert read_declared_parallel_slice_ids(content) is None

    def test_present_slice_plan_with_zero_data_rows_returns_empty_tuple(self) -> None:
        result = read_declared_parallel_slice_ids(_PREAMBLE + _HEADER)

        assert result == ()
        assert result is not None, (
            "a present-but-empty Slice Plan is a valid monolithic plan, not the "
            "absent-section omission — it must stay distinguishable from None"
        )

    def test_present_slice_plan_with_rows_returns_declared_parallel_ids(self) -> None:
        content = _make_plan(
            "| slice-01 | Ship the reader | pending |  | — |",
            "| slice-02 | Ship the writer | pending | depends-on slice-01 | First |",
            "| slice-03 | Ship the gate | pending | @coupled | — |",
        )

        assert read_declared_parallel_slice_ids(content) == ("slice-01", "slice-03")


# ---------------------------------------------------------------------------
# GDP-8 arity corollary, one granularity up — same collapse as
# TestDeclaredParallelSliceIdsArity above, now fixed for the Feature Plan
# sibling accessor (read-declared-parallel-feature-ids-collapses-absent-and-
# empty-feature-plan, techdebt.md).
# ---------------------------------------------------------------------------
from des.cli.validate_feature_delta import read_declared_parallel_feature_ids


_FEATURE_PREAMBLE = "## Wave: DISCUSS / [REF] Feature Plan\n\n"

_FEATURE_HEADER = (
    "| Feature | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
)


def _make_feature_plan(*annotation_rows: str) -> str:
    return _FEATURE_PREAMBLE + _FEATURE_HEADER + "\n".join(annotation_rows) + "\n"


class TestDeclaredParallelFeatureIdsArity:
    """`read_declared_parallel_feature_ids` keeps the third state reachable.

    `None` means "the epic-delta carries no Feature Plan heading at all" — a
    structural omission the consumer blocks on. `()` means "the section is
    there and declares zero parallel features" — a valid monolithic epic.
    """

    def test_absent_feature_plan_heading_returns_none(self) -> None:
        content = "# epic-delta\n\nProse only; no Feature Plan section.\n"

        assert read_declared_parallel_feature_ids(content) is None

    def test_present_feature_plan_with_zero_data_rows_returns_empty_tuple(
        self,
    ) -> None:
        result = read_declared_parallel_feature_ids(_FEATURE_PREAMBLE + _FEATURE_HEADER)

        assert result == ()
        assert result is not None, (
            "a present-but-empty Feature Plan is a valid monolithic epic, not "
            "the absent-section omission — it must stay distinguishable from "
            "None"
        )

    def test_present_feature_plan_with_rows_returns_declared_parallel_ids(
        self,
    ) -> None:
        content = _make_feature_plan(
            "| feature-01 | Ship the reader | pending |  | — |",
            "| feature-02 | Ship the writer | pending | depends-on feature-01 | First |",
            "| feature-03 | Ship the gate | pending | @coupled | — |",
        )

        assert read_declared_parallel_feature_ids(content) == (
            "feature-01",
            "feature-03",
        )


# ---------------------------------------------------------------------------
# GDP-8 arity corollary, third sibling in the same module -- same collapse as
# the two accessors above, now fixed for `read_slice_plan_dependencies`
# (read-slice-plan-dependencies-collapses-absent-and-empty-plan, techdebt.md).
# Its sole production consumer, `des plan` (delivery_plan.py), already blocks
# on the absent-heading case via `validate_slice_plan_content` BEFORE ever
# calling this accessor -- so today the collapse this fixes is latent, not
# reachable through that caller. Fixed anyway for API-contract consistency
# with its two siblings, and delivery_plan.py gets an explicit (currently
# unreachable) guard rather than trusting the upstream validator silently.
# ---------------------------------------------------------------------------
from des.cli.validate_feature_delta import read_slice_plan_dependencies


class TestSlicePlanDependenciesArity:
    """`read_slice_plan_dependencies` keeps the third state reachable.

    `None` means "the document carries no Slice Plan heading at all". `()`
    means "the section is there and declares zero rows" -- a valid, empty
    monolithic plan.
    """

    def test_absent_slice_plan_heading_returns_none(self) -> None:
        content = "# feature-delta\n\nProse only; no Slice Plan section.\n"

        assert read_slice_plan_dependencies(content) is None

    def test_present_slice_plan_with_zero_data_rows_returns_empty_tuple(self) -> None:
        result = read_slice_plan_dependencies(_PREAMBLE + _HEADER)

        assert result == ()
        assert result is not None, (
            "a present-but-empty Slice Plan is a valid monolithic plan, not the "
            "absent-section omission — it must stay distinguishable from None"
        )

    def test_present_slice_plan_with_rows_returns_the_dependency_graph(self) -> None:
        content = _make_plan(
            "| slice-01 | Ship the reader | pending |  | — |",
            "| slice-02 | Ship the writer | pending | depends-on slice-01 | First |",
        )

        assert read_slice_plan_dependencies(content) == (
            ("slice-01", ()),
            ("slice-02", ("slice-01",)),
        )

    def test_trailing_punctuation_on_the_dependency_token_does_not_corrupt_it(
        self,
    ) -> None:
        """A stray trailing comma/period on the ``depends-on`` token must not
        become part of the extracted prerequisite id
        (des-plan-dependency-extractor-silently-corrupts-token-on-trailing-punctuation,
        techdebt.md). Before the fix, ``\\S+`` greedily swallowed the comma, so
        the prerequisite read back as the literal string ``"slice-01,"`` --
        which then never matches the clean id ``"slice-01"`` in ``completed``,
        silently blocking the dependent slice forever with no error anywhere.
        """
        content = _make_plan(
            "| slice-01 | Ship the reader | pending |  | — |",
            "| slice-02 | Ship the writer | pending | depends-on slice-01, | First |",
        )

        assert read_slice_plan_dependencies(content) == (
            ("slice-01", ()),
            ("slice-02", ("slice-01",)),
        )


# ---------------------------------------------------------------------------
# Pure function: next_h2_boundary (D31b -- the shared section-boundary SSOT)
# ---------------------------------------------------------------------------


class TestNextH2Boundary:
    """`next_h2_boundary` is the ONE section-boundary scan in the tree, now
    shared by `check_reuse_first_design.py` and
    `check_design_dimension_coverage.py` (previously two independent copies).

    A mid-document boundary (a `##` line following the one the caller is
    scanning past) is the case a mutant that always returns `len(text)` slips
    past IF the only fixtures ever place the target section last in the
    document -- both gates' existing walking-skeleton suites do exactly that,
    so this class is the regression net that would have caught it (proved by
    planting that exact mutant and watching `test_a_boundary_mid_document_...`
    go red before restoring, per the D31b mikado node's mutation-proof rule).
    """

    def test_a_boundary_mid_document_stops_before_the_next_h2_heading(self) -> None:
        text = "## First\nbody line\n## Second\nother body\n"
        # start = end of "## First\n" -> the next "## " line is "## Second".
        start = text.index("body line")
        assert next_h2_boundary(text, start) == text.index("## Second")

    def test_no_further_h2_heading_runs_to_end_of_document(self) -> None:
        text = "## Only\nbody line with no further heading\n"
        start = text.index("body line")
        assert next_h2_boundary(text, start) == len(text)

    def test_a_third_level_heading_does_not_count_as_a_boundary(self) -> None:
        text = "## First\n### Not a boundary\nstill inside First\n## Second\n"
        start = text.index("### Not a boundary")
        assert next_h2_boundary(text, start) == text.index("## Second")
