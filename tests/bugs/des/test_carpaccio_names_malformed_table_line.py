"""Regression (#106-class applied to the table parser, GDP-3): a slice-plan
parse halted by a non-pipe line inside the table body must NAME the
malformation and its stop line, not bare-claim the slice has "no row" as if
it were genuinely absent.

Charter: docs/feature/fix-carpaccio-names-malformed-table-line/feature-delta.md

Found in ``src/des/cli/carpaccio_format.py``:

* ``_collect_table_rows`` (line ~301) collects a CONTIGUOUS block of pipe-rows
  after the ``[REF] Slice Plan`` heading and stops at the first non-pipe
  line -- silently DROPPING every row below the interruption, with no
  diagnostic.
* ``check_carpaccio`` (line ~754) then looks up the entering slice's row;
  when the row was truncated away (not genuinely absent), it still raises
  the bare ``"entering slice '<slice>' has no row in the slice plan"`` --
  indistinguishable from a slice that is truly missing from a well-formed
  table.

Empirical anchor (sister team, 2026-07-12): 8 lines of prose leaked into one
slice-plan cell made slices 14/15/16 invisible; the author chased the phantom
"no row" message while the rows were present further down the table.

The fix (crafter's job, NOT this test's): when the table-row scan halts on a
non-pipe line INSIDE the body while further pipe-rows exist below it, raise a
``MalformedInput`` diagnostic (reusing the module's existing
``_malformed_table`` helper shape) naming the stop line and the truncation
cause -- never letting the downstream "no row" lookup mis-report a
truncation as genuine absence. A genuinely-absent slice in a well-formed
table keeps today's honest "no row" wording (Control Pin 1); a well-formed
table parses byte-identically (Control Pin 2).

Driving surface: the RED case and Control Pin 1 drive the real
``des.cli.carpaccio_slice_gate.main()`` CLI in-process (Layer 3 composition,
``capsys``) -- same pattern as
``tests/bugs/des/test_carpaccio_at_review_rejection_self_explains_how.py``.
Control Pin 2 calls ``parse_slice_plan`` directly -- the shared parser SEAM
both the CLI gate and the designer-facing precheck delegate to; there is no
higher driving port for pinning "the parser itself is unchanged" than the
parser's own public entry point (mirrors the direct-seam-call precedent in
``tests/bugs/des/test_carpaccio_reason_surfaces_gate_what_why_how.py``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from des.cli.carpaccio_format import parse_slice_plan
from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main


_FEATURE_ID = "carpaccio-malformed-table-fixture"

_LINE_REF_RE = re.compile(r"\bline\s*\d+\b", re.IGNORECASE)


def _feature_delta_path(repo: Path, feature_id: str) -> Path:
    return repo / "docs" / "feature" / feature_id / "feature-delta.md"


def _write_delta(repo: Path, feature_id: str, slice_plan_table: str) -> None:
    delta_path = _feature_delta_path(repo, feature_id)
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        f"{slice_plan_table}",
        encoding="utf-8",
    )


def _run_gate(
    repo: Path, entering_slice: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des carpaccio-slice-gate`` CLI (``main()``) in-process."""
    exit_code = carpaccio_gate_main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            entering_slice,
            "--repo-root",
            str(repo),
        ]
    )
    stdout = capsys.readouterr().out
    payload: dict[str, object] = next(
        (
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ),
        {},
    )
    return exit_code, payload


# A well-formed 5-column table with slice-01 valid, then several PROSE lines
# (no leading/trailing pipe) leaking into the table body, then a VALID
# slice-02 row further down -- the truncation case: slice-02's row exists but
# sits below the interruption `_collect_table_rows` halts at.
_MULTI_LINE_PROSE_BLOCK = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | The walking skeleton ships the first observable outcome. "
    "| pending | @walking-skeleton | First slice. |\n"
    "This is a stray prose paragraph that leaked into the slice-plan table\n"
    "body instead of staying inside a single piped cell, spanning several\n"
    "lines without the leading and trailing pipes a GFM table row requires,\n"
    "so the row-per-line contiguous-block scan halts on this line even\n"
    "though more declared slice rows sit directly beneath it.\n"
    "| slice-02 | The second slice extends the skeleton with the next "
    "step. | pending | | Second slice. |\n"
)

_SINGLE_PROSE_LINE = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | The walking skeleton ships the first observable outcome. "
    "| pending | @walking-skeleton | First slice. |\n"
    "A single stray prose line interrupts the table body here.\n"
    "| slice-02 | The second slice extends the skeleton with the next "
    "step. | pending | | Second slice. |\n"
)

_INDENTED_CONTINUATION = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | The walking skeleton ships the first observable outcome. "
    "| pending | @walking-skeleton | First slice. |\n"
    "    an indented continuation line, not a table row, interrupts the\n"
    "    table body here before the next declared slice row.\n"
    "| slice-02 | The second slice extends the skeleton with the next "
    "step. | pending | | Second slice. |\n"
)

_INTERRUPTION_FORMS = {
    "multi_line_prose_block": _MULTI_LINE_PROSE_BLOCK,
    "single_prose_line": _SINGLE_PROSE_LINE,
    "indented_continuation": _INDENTED_CONTINUATION,
}

# A well-formed 5-column table with exactly slice-01 and slice-02 -- no
# interruption. Used both for the genuinely-absent-slice control pin
# (entering slice-99, which truly has no row) and the well-formed-unchanged
# control pin (parsing slice-01/slice-02 directly).
_WELL_FORMED_TABLE = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | The walking skeleton ships the first observable outcome. "
    "| pending | @walking-skeleton | First slice. |\n"
    "| slice-02 | The second slice extends the skeleton with the next "
    "step. | pending | | Second slice. |\n"
)


@pytest.mark.parametrize(
    "interruption_form",
    sorted(_INTERRUPTION_FORMS),
    ids=sorted(_INTERRUPTION_FORMS),
)
def test_truncated_table_names_the_malformation_not_bare_no_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], interruption_form: str
) -> None:
    """POSITIVE AT (active-RED today, the bug): a slice-plan table body
    interrupted by a non-pipe line BEFORE a further valid slice row must
    surface a diagnostic naming the malformation ("malform...") and a stop
    line ("line N"), never the bare "has no row in the slice plan" phrasing
    that reads as genuine absence.

    FAILS today: ``_collect_table_rows`` silently truncates at the
    interruption, ``slice-02``'s row is dropped, and ``check_carpaccio``
    raises the bare ``entering slice 'slice-02' has no row in the slice
    plan`` -- containing neither "malform" nor a "line N" reference.
    Semantic AssertionError, not a collection/import error.
    """
    repo = tmp_path / "repo"
    _write_delta(repo, _FEATURE_ID, _INTERRUPTION_FORMS[interruption_form])

    exit_code, payload = _run_gate(repo, "slice-02", capsys)

    assert exit_code != 0, f"a truncated table must still fail the gate: {payload!r}"
    payload_text = json.dumps(payload)

    assert "malform" in payload_text.lower(), (
        "the diagnostic must name the malformation (a 'malform...'-class "
        f"message) -- got: {payload!r}"
    )
    assert _LINE_REF_RE.search(payload_text), (
        "the diagnostic must name the stop LINE (a 'line N' reference) -- "
        f"got: {payload!r}"
    )
    bare_no_row = "entering slice 'slice-02' has no row in the slice plan"
    assert payload.get("error") != bare_no_row, (
        "the diagnostic must not bare-claim 'no row' as if the slice were "
        "genuinely absent -- the row IS present, just below an "
        f"interruption the parser stopped at: {payload!r}"
    )


@pytest.mark.negative_at
def test_genuinely_absent_slice_in_well_formed_table_keeps_the_honest_no_row_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control pin -- GREEN today AND after the fix): a
    WELL-FORMED table that simply does not declare the entering slice must
    keep today's honest "no row" message -- this IS the correct diagnosis
    when the table parses cleanly and the slice is truly missing. Protects
    the honest-absence path from being over-eagerly reclassified as
    malformed.
    """
    repo = tmp_path / "repo"
    _write_delta(repo, _FEATURE_ID, _WELL_FORMED_TABLE)

    exit_code, payload = _run_gate(repo, "slice-99", capsys)

    assert exit_code == 44, f"a genuinely-absent slice keeps exit 44: {payload!r}"
    assert payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE", payload
    assert (
        payload.get("error") == "entering slice 'slice-99' has no row in the slice plan"
    ), (
        "a genuinely-absent slice in a WELL-FORMED table must keep today's "
        f"honest bare 'no row' message, unchanged: {payload!r}"
    )
    assert "malform" not in json.dumps(payload).lower(), (
        "a well-formed table's genuine-absence path must never be "
        f"reclassified as malformed: {payload!r}"
    )


@pytest.mark.negative_at
def test_well_formed_table_parses_unchanged(tmp_path: Path) -> None:
    """NEGATIVE AT (control pin -- GREEN today AND after the fix): a
    well-formed, uninterrupted slice-plan table parses BOTH declared slices
    with their full value statements, with no new noise -- pins that the
    truncation-aware fix does not perturb the normal parse path.
    """
    delta_text = (
        "# Feature Delta: well-formed control pin\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        f"{_WELL_FORMED_TABLE}"
    )

    plan = parse_slice_plan(delta_text)

    assert [row.slice_id for row in plan.rows] == ["slice-01", "slice-02"], (
        f"a well-formed table must parse both slices, in order: {plan.rows!r}"
    )
    row1 = plan.row_for("slice-01")
    assert row1 is not None
    assert "first observable outcome" in row1.value_statement
    row2 = plan.row_for("slice-02")
    assert row2 is not None
    assert "next step" in row2.value_statement
