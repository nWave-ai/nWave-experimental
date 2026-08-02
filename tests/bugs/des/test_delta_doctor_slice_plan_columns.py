"""Regression: `des feature-delta-doctor` is column-drift-blind on the Slice
Plan table header (GDP-6 silent-wrong).

Charter: docs/feature/fix-delta-doctor-validates-slice-plan-columns/
feature-delta.md.

DEFECT (empirical anchor, 2026-07-12): seven hand-authored feature-deltas
carried the header `| Slice | Value statement | Class | Status | Annotation |`
instead of the canonical `| Slice | Value statement | Status | Annotation |
Justification |`. The shared parser (`carpaccio_format._build_slice_rows`) is
column-COUNT-tolerant but header-BLIND -- it reads `value_statement` /
`status` / `annotation` / `justification` POSITIONALLY from the cells that
follow the `slice-NN` cell, regardless of what the header row's cell TEXT
says. A malformed header therefore shifts every downstream cell SILENTLY
(the `Class` value lands in `status`, the real `Status` lands in
`annotation`, the `@regression-test-file` annotation lands in the
never-regexed `justification` cell) -- and the DISTILL-exit mechanical seal,
which reads `justification` for the annotation, refuses opaquely. `des
feature-delta-doctor`, run on the SAME file, reported unrelated gaps and
NOTHING about the header drift that actually blocked the pipeline.

Driving surface (Mandate 2/8, Layer 3 in-process default): the REAL `des
feature-delta-doctor <path> --format=json` CLI, driven in-process via the
shared `tests/common/in_process_cli.run_cli_in_process` (the in-process
analogue of `python -m des.cli.__main__ feature-delta-doctor ...`) --
mirrors the established `tests/bugs/des/
test_verify_deliver_entry_contract_rejection_names_repair_tool.py` idiom.
Never imports `feature_delta_doctor.diagnose` directly -- the doctor's own
CLI dispatcher is the driving port.

RED today: the doctor's `diagnose()` composes zero Slice-Plan-header
validation -- `_wave_heading_gaps` / `_missing_section_gaps` /
`_reuse_analysis_gaps` / `_sustainability_gaps` never look at the Slice Plan
table at all -- so a malformed header produces ZERO gaps naming it.

covers: F-fix-delta-doctor-validates-slice-plan-columns / slice-01
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# Canonical vs malformed Slice Plan headers
# ---------------------------------------------------------------------------

#: The canonical 5-column header (SSOT: this is the exact literal every
#: LOCKED_REF_SECTIONS-carrying feature-delta in this repo already uses --
#: see e.g. `tests/des/unit/cli/test_feature_delta_doctor.py`'s
#: CLEAN_FEATURE_DELTA fixture, or the current feature's OWN
#: `docs/feature/fix-delta-doctor-validates-slice-plan-columns/
#: feature-delta.md` Slice Plan table).
_CANONICAL_HEADER = "| Slice | Value statement | Status | Annotation | Justification |"

#: The gap id the design (feature-delta.md, DESIGN / [REF] Design reference)
#: names for this class: "malformed-slice-plan-header".
_GAP_ID = "malformed-slice-plan-header"

#: Three genuinely-distinct header deviation classes.
_MALFORMED_HEADERS = {
    "extra-column-empirically-shipped": (
        # The EXACT broken form 7 hand-authored deltas carried (feature-delta
        # bug-observable): "Class" instead of the canonical trailing pair
        # Status/Annotation/Justification -- every cell after it shifts.
        "| Slice | Value statement | Class | Status | Annotation |"
    ),
    "reordered-columns": (
        # Status and Value statement swapped -- same column COUNT as
        # canonical, so `_build_slice_rows`'s tolerant count-based read
        # would never notice; only a header-TEXT check catches this.
        "| Slice | Status | Value statement | Annotation | Justification |"
    ),
    "missing-column": (
        # Status dropped entirely -- Annotation silently shifts into the
        # position `_build_slice_rows` reads as `status`.
        "| Slice | Value statement | Annotation | Justification |"
    ),
}


def _feature_delta_with_slice_plan_header(header_line: str) -> str:
    """A structurally-complete feature-delta (every LOCKED_REF_SECTIONS
    heading well-formed, Reuse Analysis + sustainability both exempted per
    DDD-9) whose Slice Plan table header is `header_line`.

    Every section OTHER than the Slice Plan header is byte-identical to the
    empirically-verified zero-gap `CLEAN_FEATURE_DELTA` fixture in
    `tests/des/unit/cli/test_feature_delta_doctor.py` -- isolating the
    header text as the ONLY variable so a gap (once implemented) can be
    attributed to the header drift and nothing else.
    """
    return (
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
        f"{header_line}\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | ships the walking skeleton | shipped |  | shipped |\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


# ---------------------------------------------------------------------------
# Driving-port helper
# ---------------------------------------------------------------------------


def _run_doctor(target: Path, tmp_path: Path) -> dict[str, object]:
    """Drive the REAL `des feature-delta-doctor <path> --format=json` CLI
    in-process; return the parsed JSON report envelope."""
    _exit_code, stdout, stderr = run_cli_in_process(
        ["feature-delta-doctor", str(target), "--format=json"],
        cwd=tmp_path,
    )
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        return json.loads(stripped)
    raise AssertionError(
        f"no JSON report envelope on stdout -- stdout={stdout!r} stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# (1) NEGATIVE witness -- a malformed header must ALWAYS get a gap naming it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "deviation_class,header_line",
    list(_MALFORMED_HEADERS.items()),
    ids=list(_MALFORMED_HEADERS.keys()),
)
def test_doctor_never_passes_a_malformed_slice_plan_header(
    tmp_path: Path, deviation_class: str, header_line: str
) -> None:
    """A Slice Plan header deviating from the canonical column set (extra
    column, reordered columns, missing column) MUST produce a gap naming
    the malformed header, WHY it breaks (cells shift silently, the
    downstream mechanical-seal parse fails), and HOW to fix it (the exact
    canonical header line) -- regardless of which deviation class it is.

    RED today: `diagnose()` never inspects the Slice Plan table at all, so
    the gap list is empty and `_GAP_ID` is never among the reported ids.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_header(header_line), encoding="utf-8"
    )

    report = _run_doctor(target, tmp_path)
    gaps = report["gaps"]
    gap_ids = {gap["id"] for gap in gaps}

    assert _GAP_ID in gap_ids, (
        f"[{deviation_class}] header {header_line!r} deviates from the "
        f"canonical {_CANONICAL_HEADER!r} -- the doctor must report a "
        f"{_GAP_ID!r} gap naming it (cells shift silently downstream: the "
        f"DISTILL-exit mechanical seal reads the wrong cell as the "
        f"annotation and refuses opaquely). Got gap ids={gap_ids} "
        f"(gaps={gaps})."
    )

    header_gap = next(gap for gap in gaps if gap["id"] == _GAP_ID)
    assert header_line in header_gap.get("what", ""), (
        f"[{deviation_class}] the gap's 'what' must NAME the malformed "
        f"header verbatim; got what={header_gap.get('what')!r}"
    )
    assert header_gap.get("why"), f"[{deviation_class}] gap missing 'why': {header_gap}"
    assert header_gap.get("how"), f"[{deviation_class}] gap missing 'how': {header_gap}"
    assert _CANONICAL_HEADER in header_gap.get("how", ""), (
        f"[{deviation_class}] the gap's 'how' must carry the EXACT "
        f"canonical header line so an operator can copy-paste the fix; "
        f"got how={header_gap.get('how')!r}"
    )


# ---------------------------------------------------------------------------
# (2) No-false-positive pin -- the canonical header never gets this gap
# ---------------------------------------------------------------------------


def test_canonical_slice_plan_header_never_gets_malformed_header_gap(
    tmp_path: Path,
) -> None:
    """PIN (green today AND after the fix, for different reasons): a
    feature-delta whose Slice Plan header IS the canonical
    `| Slice | Value statement | Status | Annotation | Justification |`
    never gets a `malformed-slice-plan-header` gap.

    Trivially green TODAY because the gap class does not exist yet at all
    (zero gaps reported for ANY header). This test PINS the negative space
    so the post-fix implementation cannot regress into flagging the
    canonical header as malformed.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_header(_CANONICAL_HEADER), encoding="utf-8"
    )

    report = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert _GAP_ID not in gap_ids, (
        f"the canonical header {_CANONICAL_HEADER!r} must never trigger "
        f"'{_GAP_ID}' -- got gap ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (3) SSOT pin -- the 'how' must carry the canonical columns in ORDER,
# sourced from the SAME schema the parser uses (M1: one locus).
#
# `_build_slice_rows` (src/des/cli/carpaccio_format.py) has no exported
# canonical-columns constant today. Per the design ("if the parser has no
# exported canonical-columns constant today, EXPORT one there and consume it
# in both places -- one locus, never a copy"), this AT expresses the SSOT
# obligation as: IF a canonical-columns constant is exported from
# `carpaccio_format`, the 'how' message's canonical header must be built
# FROM it (never a copied literal) -- ELSE the obligation degrades to
# pinning the 'how' message's exact column ORDER, and the one-locus property
# itself is enforced by design review, not this AT (see the module
# docstring in feature_delta_doctor.py once slice-01 lands).
# ---------------------------------------------------------------------------


def test_malformed_header_how_names_exact_canonical_columns_in_order(
    tmp_path: Path,
) -> None:
    """The gap's 'how' must name the 5 canonical columns in the EXACT
    canonical order (Slice, Value statement, Status, Annotation,
    Justification) -- never a scrambled or partial list.

    If `carpaccio_format` exports a canonical-columns constant by the time
    this AT is exercised, the expected header is built FROM it (SSOT: one
    locus, never a copied literal); otherwise the exact canonical literal
    above is used, and the one-locus property is a design-review obligation
    the crafter must satisfy per the design reference, not a fact this
    filesystem-only AT can itself verify.
    """
    try:
        from des.cli.carpaccio_format import (  # type: ignore[attr-defined]
            SLICE_PLAN_CANONICAL_COLUMNS,
        )

        expected_header = "| " + " | ".join(SLICE_PLAN_CANONICAL_COLUMNS) + " |"
    except ImportError:
        expected_header = _CANONICAL_HEADER

    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_header(
            _MALFORMED_HEADERS["extra-column-empirically-shipped"]
        ),
        encoding="utf-8",
    )

    report = _run_doctor(target, tmp_path)
    gaps = [gap for gap in report["gaps"] if gap["id"] == _GAP_ID]
    assert len(gaps) == 1, (
        f"expected exactly one {_GAP_ID!r} gap; got {gaps} (report={report})"
    )
    how = gaps[0].get("how", "")
    assert expected_header in how, (
        f"the gap's 'how' must carry the canonical header "
        f"{expected_header!r} verbatim, columns in order; got how={how!r}"
    )
