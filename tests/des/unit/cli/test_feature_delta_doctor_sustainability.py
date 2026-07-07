"""Regression AT -- `des feature-delta-doctor` must cover the sustainability
section (fix-doctor-covers-sustainability-section).

DEFECT: the doctor (`src/des/cli/feature_delta_doctor.py`) checks the four
`LOCKED_REF_SECTIONS` (Architecture & Contract Tests, ADR Refs, Reuse Analysis,
Slice Plan) plus Wave-heading well-formedness plus Reuse Analysis row content --
but it NEVER calls `validate_sustainability_content` for the
`## Test Reuse & Consolidation Analysis` (sustainability) section that
`des verify-readiness-pre-dispatch`'s `sustainability` invariant enforces
(`_check_sustainability` -> `validate_sustainability_content`,
src/des/cli/verify_readiness_pre_dispatch.py:527). A feature-delta with every
LOCKED_REF section present but NO sustainability section today gets
`gap_count: 0` from the doctor -- a false "all clear" the readiness gate then
REJECTS (confirmed live on a real feature-delta).

Charter: docs/product/expectations/fix-doctor-covers-sustainability-section/
the-doctor-flags-the-missing-sustainability-section.md

Canonical heading/columns SSOT (M1 shared-SSOT -- the fix must reuse these, not
a parallel literal): `des.cli.validate_feature_delta.SUSTAINABILITY_HEADING` /
`SUSTAINABILITY_COLUMNS`.

Driving surface (P1-P4 in-process active-RED pattern, `nw-distill-red-
scaffolding`): the REAL `des feature-delta-doctor` CLI EDGE, driven IN-PROCESS
via `tests/common/in_process_cli.run_cli_in_process` against the production
dispatcher `des.cli.__main__.main` -- the in-process analogue of
`python -m des.cli.__main__ feature-delta-doctor <path> --format=json`
established by the sibling `test_feature_delta_doctor.py`. The subcommand IS
already registered (unlike that sibling file's WS-2 era), so this file's
RED-today failure is a genuine semantic `AssertionError` on `gap_count` /
gap content -- never an argparse `invalid choice`.

covers: fix-doctor-covers-sustainability-section
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from des.cli.validate_feature_delta import SUSTAINABILITY_HEADING
from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# Fixtures -- feature-delta content
# ---------------------------------------------------------------------------

#: Every LOCKED_REF_SECTIONS heading present and well-formed (Architecture &
#: Contract Tests, ADR Refs, Slice Plan via Wave heading, Reuse Analysis via the
#: bare canonical heading + DDD-9 `no-overlap` exemption marker) -- but NO
#: `## Test Reuse & Consolidation Analysis` (sustainability) section anywhere.
#: This is EXACTLY the shape `des verify-readiness-pre-dispatch`'s
#: `sustainability` invariant rejects (`missing-sustainability-section`) while
#: the doctor, today, reports `gap_count: 0` on it -- the defect this AT pins.
MISSING_SUSTAINABILITY_FEATURE_DELTA = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
    "\n"
    "Some architecture prose.\n"
    "\n"
    "## Wave: DESIGN / [REF] ADR Refs\n"
    "\n"
    "- ADR-001\n"
    "\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | ships the walking skeleton | done |  | shipped |\n"
    "\n"
    "## Reuse Analysis\n"
    "\n"
    "Reuse-Analysis: no-overlap\n"
)

#: The same LOCKED_REF shape PLUS a well-formed sustainability section
#: (canonical `SUSTAINABILITY_HEADING`, canonical five-column header, one
#: REUSE row with a non-empty Justification) -- a COMPLETE feature-delta the
#: readiness gate's sustainability invariant ACCEPTS (`structurally-accepted`).
COMPLETE_FEATURE_DELTA_WITH_SUSTAINABILITY = (
    MISSING_SUSTAINABILITY_FEATURE_DELTA + "\n" + SUSTAINABILITY_HEADING + "\n"
    "\n"
    "| Existing Test/DSL-Step | File | Overlap | Decision | Justification |\n"
    "|---|---|---|---|---|\n"
    "| test_doctor_reports_zero_gaps_for_a_clean_feature_delta "
    "| tests/des/unit/cli/test_feature_delta_doctor.py | doctor JSON shape "
    "| REUSE | same fixture pattern, no new coverage needed |\n"
)


# ---------------------------------------------------------------------------
# Driving-port helper -- in-process, faithful to the subprocess contract
# ---------------------------------------------------------------------------


def _run_doctor(target: Path) -> tuple[int, dict[str, Any], str]:
    """Invoke `des feature-delta-doctor <target> --format=json` IN-PROCESS.

    Faithful in-process analogue of
    `python -m des.cli.__main__ feature-delta-doctor <target> --format=json`,
    driving the production dispatcher `des.cli.__main__.main` directly
    (no interpreter fork). Returns `(exit_code, json_report_or_empty_dict,
    stderr)`.
    """
    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-delta-doctor", str(target), "--format=json"],
        cwd=target.parent,
    )
    try:
        payload: dict[str, Any] = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {}
    return exit_code, payload, stderr


def _sustainability_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter gaps that name the sustainability section, by `what` or `id`."""
    return [
        gap
        for gap in gaps
        if SUSTAINABILITY_HEADING in gap.get("what", "")
        or "sustainability" in gap.get("id", "").lower()
        or "sustainability" in gap.get("what", "").lower()
    ]


# ---------------------------------------------------------------------------
# POSITIVE AT -- missing sustainability section MUST be flagged
# ---------------------------------------------------------------------------


def test_doctor_flags_missing_sustainability_section(tmp_path: Path) -> None:
    """A feature-delta with every LOCKED_REF section present but MISSING the
    `## Test Reuse & Consolidation Analysis` section must be flagged by the
    doctor as a gap -- never `gap_count: 0`.

    FAILS TODAY (semantic AssertionError -- not a crash, not an argparse
    error): the doctor composes `_wave_heading_gaps` + `_missing_section_gaps`
    (LOCKED_REF_SECTIONS only) + `_reuse_analysis_gaps`; it never calls
    `validate_sustainability_content`, so `diagnose()` reports `gap_count: 0`
    on this exact fixture even though `des verify-readiness-pre-dispatch`'s
    `sustainability` invariant REJECTS it.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(MISSING_SUSTAINABILITY_FEATURE_DELTA, encoding="utf-8")

    exit_code, report, stderr = _run_doctor(target)

    assert report, f"expected a JSON report on stdout; stderr={stderr!r}"
    assert report.get("gap_count", 0) >= 1, (
        "expected >=1 gap for the missing sustainability section; the doctor "
        f"reported gap_count={report.get('gap_count')!r} on a feature-delta "
        "the readiness gate's sustainability invariant would REJECT -- a "
        f"false all-clear. full report={report}"
    )
    assert exit_code == 1, (
        f"expected exit 1 (gaps found); got {exit_code}. report={report}"
    )

    gaps = report["gaps"]
    sustainability_gaps = _sustainability_gaps(gaps)
    assert sustainability_gaps, (
        "expected a gap naming the missing sustainability section "
        f"({SUSTAINABILITY_HEADING!r}); got gaps={gaps}"
    )

    gap = sustainability_gaps[0]
    # Every failure self-explains WHAT / WHY / HOW (STANDING mandate).
    assert gap.get("what"), f"gap missing 'what': {gap}"
    assert gap.get("why"), f"gap missing 'why': {gap}"
    assert gap.get("how"), f"gap missing 'how': {gap}"

    assert (
        SUSTAINABILITY_HEADING in gap["what"] or "sustainability" in gap["what"].lower()
    ), f"'what' must name the sustainability section; got what={gap['what']!r}"
    assert "required" in gap["why"].lower() or "sustainab" in gap["why"].lower(), (
        f"'why' must explain the section is required; got why={gap['why']!r}"
    )
    how_lower = gap["how"].lower()
    assert (
        "test reuse & consolidation analysis" in how_lower
        or "methodology-exempt" in how_lower
    ), (
        "expected 'how' to point at the canonical heading or the "
        f"'Test-Reuse-Analysis: methodology-exempt' marker; got "
        f"how={gap['how']!r}"
    )


# ---------------------------------------------------------------------------
# NEGATIVE AT -- a COMPLETE delta must NOT be flagged (no false positive)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_complete_delta_is_not_flagged_for_sustainability(tmp_path: Path) -> None:
    """A COMPLETE feature-delta (every LOCKED_REF section + a well-formed
    sustainability section) must NOT be flagged for the sustainability gap.

    Green TODAY (the doctor does not check sustainability at all, so it
    trivially reports no such gap) and MUST STAY GREEN after the fix (the
    fix must not false-positive on a well-formed section).
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(COMPLETE_FEATURE_DELTA_WITH_SUSTAINABILITY, encoding="utf-8")

    exit_code, report, stderr = _run_doctor(target)

    assert report, f"expected a JSON report on stdout; stderr={stderr!r}"
    gaps = report.get("gaps", [])
    sustainability_gaps = _sustainability_gaps(gaps)
    assert not sustainability_gaps, (
        "expected NO sustainability gap on a complete feature-delta; got "
        f"sustainability_gaps={sustainability_gaps} (full gaps={gaps})"
    )
    assert exit_code == 0, (
        f"expected exit 0 (zero gaps) on a complete feature-delta; got "
        f"{exit_code}. report={report}"
    )
    assert report.get("gap_count") == 0, (
        f"expected gap_count == 0 on a complete feature-delta; got report={report}"
    )
