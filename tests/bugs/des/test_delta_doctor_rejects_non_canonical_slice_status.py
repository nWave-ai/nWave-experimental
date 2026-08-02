"""Regression: `des feature-delta-doctor` is silent on a non-canonical
Slice Plan `Status` cell (EDC-7/LSC-6 closed vocabulary UNENFORCED by any
gate, GDP-6 silent-wrong).

DEFECT (RCA confirmed line-by-line against this checkout): the Slice Plan
`Status` column carries a CLOSED vocabulary declared in
`nWave/skills/nw-discuss/SKILL.md` (EDC-7 line ~206; LSC-6 line ~233):
exactly `pending | in-flight | shipped`. LSC-6 explicitly names `done`,
`wip`, `blocked` as ILLEGAL and states the keystone validator does NOT
validate Status cells (DC-1) -- the vocabulary is enforced by a
human-followed PROCEDURE, by no gate.

Downstream consequence: `des commit-slice` calls `_sync_slice_plan_status`
(`src/des/cli/commit_slice.py:330`) after a real `SliceCommitVerified` to
flip the cell to `shipped`; `mark_slice_status_shipped`
(`src/des/cli/carpaccio_format.py:749`) refuses with a SILENT no-op on any
value that is not the literal `pending`
(`row.status.strip().lower() != "pending"` -- note: case-insensitive). So a
non-canonical token silently suppresses the sync, and only `des next`
notices later, reporting the SYMPTOM (ledger/plan disagree) not the CAUSE.

`des feature-delta-doctor` already parses every slice row via
`carpaccio_format.parse_slice_plan` (transitively, via
`slice_plan_header_deviation` today; a full `parse_slice_plan` call is the
fix's own obligation) yet reports `gap_count: 0` on such a document.

THE FIX BEING TESTED (not implemented here -- test authorship only): a new
doctor gap `non-canonical-slice-status`, plus a GDP-8 third state
`slice-status-could-not-verify` for the case where the Slice Plan table
cannot even be parsed into rows (a malformed row means the doctor cannot
read ANY status in that table -- reporting zero status gaps there would
itself be a silent-wrong, the same class of defect this AT exists to close).

Driving surface (Mandate 2/8, Layer 3 in-process default): the REAL `des
feature-delta-doctor <path> --format=json` CLI, driven in-process via the
shared `tests/common/in_process_cli.run_cli_in_process` -- mirrors the
established `tests/bugs/des/test_delta_doctor_slice_plan_columns.py` idiom.
Never imports `feature_delta_doctor.diagnose` directly -- the doctor's own
CLI dispatcher is the driving port.

RED today: `diagnose()` never validates a Slice Plan Status CELL's token
against the closed vocabulary at all -- so every scenario below reports
`gap_count: 0` (verified empirically against this exact checkout before
authoring this file).

covers: bugfix/slice-plan-status-token-edc-7-unenforced
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# Vocabulary + gap ids under test
# ---------------------------------------------------------------------------

#: The canonical 5-column Slice Plan header -- identical literal to
#: `test_delta_doctor_slice_plan_columns.py`'s own `_CANONICAL_HEADER` (SSOT:
#: this is the exact header every LOCKED_REF_SECTIONS-carrying feature-delta
#: in this repo already uses).
_CANONICAL_HEADER = "| Slice | Value statement | Status | Annotation | Justification |"

#: The gap id the fix introduces for a Status cell outside the closed
#: vocabulary (EDC-7/LSC-6): exactly `pending | in-flight | shipped`.
_GAP_ID = "non-canonical-slice-status"

#: The GDP-8 third state: the Slice Plan table EXISTS but cannot be parsed
#: into rows at all (e.g. a row with no `slice-NN` identifier cell) -- the
#: doctor cannot read ANY status in that table, so it must say so LOUDLY
#: instead of silently reporting zero status gaps.
_COULD_NOT_VERIFY_GAP_ID = "slice-status-could-not-verify"

#: The closed vocabulary itself (EDC-7) -- every canonical token, exactly.
_CANONICAL_STATUS_TOKENS = ("pending", "in-flight", "shipped")

#: Real offending forms, measured in this repo's own tree today (before the
#: two collateral-fixture corrections this same change made) plus the tokens
#: LSC-6 explicitly names illegal. Keyed by a short, stable parametrize id.
_OFFENDING_STATUSES = {
    "reporter-verbatim-example": "Shipped 0.2.0, race fixed 0.2.1",
    "done": "done",
    "wip": "wip",
    "blocked": "blocked",
    "planned": "planned",
    "designed": "designed",
    "delivered": "delivered",
    "not-started": "Not started",
    "active": "active",
    "deferred": "deferred",
    # Decorated -- this EXACT shape is what suppresses `mark_slice_status_
    # shipped`'s sync in production: `row.status.strip().lower() !=
    # "pending"` refuses any decorated/extended value as a silent no-op.
    "decorated-hash": "shipped `4c455714e`",
    "decorated-merged-note": (
        "shipped (merged `3cb9cd783`, 2026-07-20; SliceCommitVerified)"
    ),
    "decorated-bold-hash": "**SHIPPED** (`ae367402f`)",
}


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _feature_delta_with_slice_plan_rows(header_line: str, *rows: str) -> str:
    """A structurally-complete feature-delta (every LOCKED_REF_SECTIONS
    heading well-formed, Reuse Analysis + sustainability both exempted per
    DDD-9) whose Slice Plan table header is `header_line` and whose data
    rows are `rows`.

    Every section OTHER than the Slice Plan table is byte-identical to the
    empirically-verified zero-gap `CLEAN_FEATURE_DELTA` fixture in
    `tests/des/unit/cli/test_feature_delta_doctor.py` -- isolating the Slice
    Plan table as the ONLY variable so a gap (once implemented) can be
    attributed to it and nothing else.
    """
    body = "\n".join(rows)
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
        f"{body}\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _row(slice_id: str, status: str) -> str:
    """One canonical-shape Slice Plan data row with `status` as its Status
    cell -- Value statement / Annotation / Justification held constant so the
    Status token is the only variable."""
    return f"| {slice_id} | ships the walking skeleton | {status} |  | shipped |"


def _feature_delta_missing_slice_plan_section() -> str:
    """Every OTHER LOCKED_REF_SECTIONS heading present and well-formed, but
    NO `[REF] Slice Plan` section at all -- `missing-locked-section` already
    reports this; `non-canonical-slice-status` must never double-count it."""
    return (
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
        "\n"
        "Some architecture prose.\n"
        "\n"
        "## Wave: DESIGN / [REF] ADR Refs\n"
        "\n"
        "- ADR-001\n"
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


def _run_doctor(target: Path, tmp_path: Path) -> tuple[int, dict[str, object], str]:
    """Drive the REAL `des feature-delta-doctor <path> --format=json` CLI
    in-process; return `(exit_code, parsed_json_report, stderr)`."""
    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-delta-doctor", str(target), "--format=json"],
        cwd=tmp_path,
    )
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        return exit_code, json.loads(stripped), stderr
    raise AssertionError(
        f"no JSON report envelope on stdout -- exit_code={exit_code} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# (1) POSITIVE -- a non-canonical Status cell MUST produce a gap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "deviation_class,status_value",
    list(_OFFENDING_STATUSES.items()),
    ids=list(_OFFENDING_STATUSES.keys()),
)
def test_doctor_flags_non_canonical_slice_status(
    tmp_path: Path, deviation_class: str, status_value: str
) -> None:
    """A Slice Plan Status cell outside the closed EDC-7/LSC-6 vocabulary
    (`pending | in-flight | shipped`) MUST produce a `non-canonical-slice-
    status` gap naming the offending slice-id AND value (`what`), the closed
    vocabulary (`why`), and an actionable fix (`how`).

    RED today: `diagnose()` never validates a Status cell's token against
    the closed vocabulary at all, so the gap list is empty and `_GAP_ID` is
    never among the reported ids -- verified empirically before authoring.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            _CANONICAL_HEADER, _row("slice-01", status_value)
        ),
        encoding="utf-8",
    )

    exit_code, report, stderr = _run_doctor(target, tmp_path)
    gaps = report["gaps"]
    gap_ids = {gap["id"] for gap in gaps}

    assert exit_code == 1, (
        f"[{deviation_class}] expected exit 1 (gaps found) for status "
        f"{status_value!r}; got exit_code={exit_code} report={report} "
        f"stderr={stderr!r}"
    )
    assert _GAP_ID in gap_ids, (
        f"[{deviation_class}] status {status_value!r} is outside the closed "
        f"EDC-7/LSC-6 vocabulary {_CANONICAL_STATUS_TOKENS} -- the doctor "
        f"must report a {_GAP_ID!r} gap naming it (a non-canonical token "
        f"silently suppresses `mark_slice_status_shipped`'s sync in "
        f"production, per `row.status.strip().lower() != 'pending'`). Got "
        f"gap ids={gap_ids} (gaps={gaps})."
    )

    status_gap = next(gap for gap in gaps if gap["id"] == _GAP_ID)
    assert "slice-01" in status_gap.get("what", ""), (
        f"[{deviation_class}] the gap's 'what' must NAME the offending "
        f"slice-id 'slice-01'; got what={status_gap.get('what')!r}"
    )
    assert status_value in status_gap.get("what", ""), (
        f"[{deviation_class}] the gap's 'what' must NAME the offending "
        f"value {status_value!r} verbatim; got "
        f"what={status_gap.get('what')!r}"
    )
    why_lower = status_gap.get("why", "").lower()
    for token in _CANONICAL_STATUS_TOKENS:
        assert token in why_lower, (
            f"[{deviation_class}] the gap's 'why' must name the closed "
            f"vocabulary token {token!r} (all three: "
            f"{_CANONICAL_STATUS_TOKENS}); got why={status_gap.get('why')!r}"
        )
    assert status_gap.get("how", "").strip(), (
        f"[{deviation_class}] gap missing a non-empty, actionable 'how': {status_gap}"
    )


# ---------------------------------------------------------------------------
# (2) NEGATIVE / no-false-positive PIN -- the 3 canonical tokens never gap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("canonical_status", _CANONICAL_STATUS_TOKENS)
def test_canonical_slice_status_never_gets_non_canonical_status_gap(
    tmp_path: Path, canonical_status: str
) -> None:
    """NEGATIVE PIN: each of the 3 canonical tokens (`pending`, `in-flight`,
    `shipped`) produces NO `non-canonical-slice-status` gap.

    Trivially green today (the gap class does not exist yet at all); pins
    the negative space so the post-fix implementation cannot regress into
    flagging a genuinely canonical token.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            _CANONICAL_HEADER, _row("slice-01", canonical_status)
        ),
        encoding="utf-8",
    )

    _exit_code, report, _stderr = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert _GAP_ID not in gap_ids, (
        f"canonical status {canonical_status!r} must never trigger "
        f"{_GAP_ID!r} -- got gap ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (3) CASE INSENSITIVITY -- exactly as tolerant as `mark_slice_status_
# shipped`'s own `.strip().lower()` comparison, no more and no less
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cased_status",
    ["Pending", "SHIPPED", "In-Flight", "  shipped  "],
    ids=["Pending", "SHIPPED", "In-Flight", "padded-shipped"],
)
def test_canonical_slice_status_case_and_padding_insensitive_never_gaps(
    tmp_path: Path, cased_status: str
) -> None:
    """NEGATIVE PIN: `Pending`, `SHIPPED`, `In-Flight`, and a padded
    `  shipped  ` all produce NO `non-canonical-slice-status` gap -- matching
    `mark_slice_status_shipped`'s own `row.status.strip().lower()`
    comparison exactly (`carpaccio_format.py`). The check must be exactly as
    tolerant as the consumer it protects: no more (a decorated value must
    still gap, see test 1) and no less (bare case/padding variance must not).
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            _CANONICAL_HEADER, _row("slice-01", cased_status)
        ),
        encoding="utf-8",
    )

    _exit_code, report, _stderr = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert _GAP_ID not in gap_ids, (
        f"status {cased_status!r} differs from a canonical token only by "
        f"case/padding -- `mark_slice_status_shipped` itself tolerates this "
        f"via `.strip().lower()`, so the doctor must too. Got gap "
        f"ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (4) NO DOUBLE-COUNT -- header lacks the Status column entirely
# ---------------------------------------------------------------------------


def test_missing_status_column_header_gets_only_the_header_gap_never_the_status_gap(
    tmp_path: Path,
) -> None:
    """When the Slice Plan header omits `Status` entirely, the parser reads
    every status cell as `''`. That case is ALREADY reported as
    `malformed-slice-plan-header`; it must NOT additionally produce
    `non-canonical-slice-status` (measured: all empty-status-cell rows in
    this repo today are this case, zero are the case-5 blank-cell-with-
    column-present case below).
    """
    header = "| Slice | Value statement | Annotation | Justification |"
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            header, "| slice-01 | ships the walking skeleton |  | shipped |"
        ),
        encoding="utf-8",
    )

    exit_code, report, stderr = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert exit_code == 1, (
        f"expected exit 1 (the malformed-header gap alone); got "
        f"exit_code={exit_code} report={report} stderr={stderr!r}"
    )
    assert "malformed-slice-plan-header" in gap_ids, (
        f"expected the pre-existing malformed-slice-plan-header gap for a "
        f"header lacking Status; got gap ids={gap_ids} (gaps={report['gaps']})"
    )
    assert _GAP_ID not in gap_ids, (
        f"a header lacking the Status column altogether is ALREADY covered "
        f"by malformed-slice-plan-header -- reporting {_GAP_ID!r} too would "
        f"double-count the same root cause under two gap ids. Got gap "
        f"ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (5) Empty Status cell WITH the column present -- IS a gap (blank is not
# in the closed set)
# ---------------------------------------------------------------------------


def test_empty_status_cell_with_canonical_header_gets_non_canonical_status_gap(
    tmp_path: Path,
) -> None:
    """The header IS canonical (Status column present); the Status cell is
    blank. Blank is not a member of the closed vocabulary
    (`pending | in-flight | shipped`) -- this MUST gap, distinct from test 4
    where the column itself is absent."""
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(_CANONICAL_HEADER, _row("slice-01", "")),
        encoding="utf-8",
    )

    exit_code, report, stderr = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert exit_code == 1, (
        f"expected exit 1 (blank Status with the column present is a gap); "
        f"got exit_code={exit_code} report={report} stderr={stderr!r}"
    )
    assert _GAP_ID in gap_ids, (
        f"a blank Status cell with the Status column PRESENT is not in the "
        f"closed vocabulary {_CANONICAL_STATUS_TOKENS} -- expected "
        f"{_GAP_ID!r} among gap ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (6) NO DOUBLE-COUNT -- section absent entirely
# ---------------------------------------------------------------------------


def test_missing_slice_plan_section_never_gets_non_canonical_status_gap(
    tmp_path: Path,
) -> None:
    """A feature-delta with NO `[REF] Slice Plan` section produces NO
    `non-canonical-slice-status` gap -- `Slice Plan` is in
    `LOCKED_REF_SECTIONS`, so `missing-locked-section` already reports it."""
    target = tmp_path / "feature-delta.md"
    target.write_text(_feature_delta_missing_slice_plan_section(), encoding="utf-8")

    exit_code, report, stderr = _run_doctor(target, tmp_path)
    gap_ids = {gap["id"] for gap in report["gaps"]}

    assert exit_code == 1, (
        f"expected exit 1 (missing-locked-section alone); got "
        f"exit_code={exit_code} report={report} stderr={stderr!r}"
    )
    assert "missing-locked-section" in gap_ids, (
        f"expected the pre-existing missing-locked-section gap naming "
        f"'Slice Plan'; got gap ids={gap_ids} (gaps={report['gaps']})"
    )
    assert _GAP_ID not in gap_ids, (
        f"an ABSENT Slice Plan section is already covered by "
        f"missing-locked-section -- {_GAP_ID!r} must never double-count it. "
        f"Got gap ids={gap_ids} (gaps={report['gaps']})"
    )
    assert _COULD_NOT_VERIFY_GAP_ID not in gap_ids, (
        f"an ABSENT section is a DIFFERENT state from an unparsable table -- "
        f"{_COULD_NOT_VERIFY_GAP_ID!r} must never fire when the section "
        f"itself is simply missing. Got gap ids={gap_ids} "
        f"(gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (7) THIRD STATE -- the table exists but cannot be parsed into rows at all
# (GDP-8 arity corollary: the aggregate must hear "could not verify", never
# silence)
# ---------------------------------------------------------------------------


def test_unparsable_slice_plan_table_gets_could_not_verify_gap_not_silence(
    tmp_path: Path,
) -> None:
    """When the Slice Plan section EXISTS but the table is malformed such
    that `carpaccio_format.parse_slice_plan` raises `GateError` (here: a data
    row with no `slice-NN` identifier cell at all), the doctor MUST emit
    `slice-status-could-not-verify` naming why the statuses could not be
    read. Reporting zero status gaps there would be a GDP-6 silent-wrong --
    exactly what happens today (verified empirically: `parse_slice_plan`
    genuinely raises `GateError(2, {'event': 'MalformedInput', 'cause': 'the
    slice-plan table', 'error': \"slice-plan row has no 'slice-NN'
    identifier cell: ...\"})` on this exact input, and the doctor today
    reports `gap_count: 0` -- neither crashing nor naming the problem).
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            _CANONICAL_HEADER,
            "| no slice id here | more text | pending | | |",
        ),
        encoding="utf-8",
    )

    exit_code, report, stderr = _run_doctor(target, tmp_path)

    assert "Traceback (most recent call last)" not in (stderr + json.dumps(report)), (
        f"the doctor must never leak a raw Python traceback for an "
        f"unparsable Slice Plan table; got exit_code={exit_code} "
        f"report={report} stderr={stderr!r}"
    )
    gap_ids = {gap["id"] for gap in report["gaps"]}
    assert exit_code == 1, (
        f"expected exit 1 (the could-not-verify gap); got "
        f"exit_code={exit_code} report={report} stderr={stderr!r}"
    )
    assert _COULD_NOT_VERIFY_GAP_ID in gap_ids, (
        f"a Slice Plan table that cannot be parsed into rows at all (no "
        f"'slice-NN' identifier cell in the sole data row) MUST surface "
        f"{_COULD_NOT_VERIFY_GAP_ID!r} naming why the statuses could not be "
        f"read -- silently reporting zero status gaps here is the GDP-6 "
        f"defect this AT exists to close. Got gap ids={gap_ids} "
        f"(gaps={report['gaps']})"
    )
    could_not_verify_gap = next(
        gap for gap in report["gaps"] if gap["id"] == _COULD_NOT_VERIFY_GAP_ID
    )
    assert could_not_verify_gap.get("what", "").strip(), (
        f"could-not-verify gap missing 'what': {could_not_verify_gap}"
    )
    why_lower = could_not_verify_gap.get("why", "").strip().lower()
    assert why_lower, f"could-not-verify gap missing 'why': {could_not_verify_gap}"
    assert any(phrase in why_lower for phrase in ("could not", "cannot", "unable")), (
        f"'why' must explain the statuses COULD NOT be verified/read (one "
        f"of 'could not' / 'cannot' / 'unable'); got "
        f"why={could_not_verify_gap.get('why')!r}"
    )
    assert could_not_verify_gap.get("how", "").strip(), (
        f"could-not-verify gap missing a non-empty, actionable 'how': "
        f"{could_not_verify_gap}"
    )
    assert _GAP_ID not in gap_ids, (
        f"the table cannot be parsed into rows AT ALL -- no per-row "
        f"non-canonical-slice-status gap can legitimately exist alongside "
        f"the could-not-verify state (there are no readable rows to name). "
        f"Got gap ids={gap_ids} (gaps={report['gaps']})"
    )


# ---------------------------------------------------------------------------
# (8) PER-ROW granularity -- one gap PER offending row, each naming its OWN
# slice-id
# ---------------------------------------------------------------------------


def test_multiple_offending_rows_each_get_their_own_gap_never_lumped(
    tmp_path: Path,
) -> None:
    """A plan with several offending rows produces ONE gap PER offending
    row, each naming ITS OWN slice-id -- never one lumped gap covering
    several rows, and never a gap for the one canonical row in between."""
    target = tmp_path / "feature-delta.md"
    target.write_text(
        _feature_delta_with_slice_plan_rows(
            _CANONICAL_HEADER,
            _row("slice-01", "done"),
            _row("slice-02", "pending"),
            _row("slice-03", "wip"),
        ),
        encoding="utf-8",
    )

    exit_code, report, stderr = _run_doctor(target, tmp_path)
    assert exit_code == 1, (
        f"expected exit 1 (2 offending rows); got exit_code={exit_code} "
        f"report={report} stderr={stderr!r}"
    )

    status_gaps = [gap for gap in report["gaps"] if gap["id"] == _GAP_ID]
    assert len(status_gaps) == 2, (
        f"expected exactly 2 {_GAP_ID!r} gaps (slice-01 'done', slice-03 "
        f"'wip'; slice-02 'pending' is canonical, no gap) -- never one "
        f"lumped gap for multiple offending rows. Got {len(status_gaps)}: "
        f"{status_gaps}"
    )
    named_slice_ids = {
        slice_id
        for gap in status_gaps
        for slice_id in ("slice-01", "slice-02", "slice-03")
        if slice_id in gap.get("what", "")
    }
    assert "slice-01" in named_slice_ids, (
        f"expected one gap naming 'slice-01' (status 'done'); got "
        f"status_gaps={status_gaps}"
    )
    assert "slice-03" in named_slice_ids, (
        f"expected one gap naming 'slice-03' (status 'wip'); got "
        f"status_gaps={status_gaps}"
    )
    assert "slice-02" not in named_slice_ids, (
        f"'slice-02' carries the canonical status 'pending' -- no gap must "
        f"name it. Got status_gaps={status_gaps}"
    )


# ---------------------------------------------------------------------------
# (9) NO CRASH / NO TRACEBACK -- every offending input above produces a
# well-formed JSON envelope, never a Python traceback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,content",
    [
        (
            f"offending-status-{deviation_class}",
            _feature_delta_with_slice_plan_rows(
                _CANONICAL_HEADER, _row("slice-01", status_value)
            ),
        )
        for deviation_class, status_value in _OFFENDING_STATUSES.items()
    ]
    + [
        (
            "blank-status-cell",
            _feature_delta_with_slice_plan_rows(
                _CANONICAL_HEADER, _row("slice-01", "")
            ),
        ),
        (
            "unparsable-table",
            _feature_delta_with_slice_plan_rows(
                _CANONICAL_HEADER,
                "| no slice id here | more text | pending | | |",
            ),
        ),
    ],
    ids=lambda param: param if isinstance(param, str) else None,
)
def test_doctor_never_crashes_on_any_offending_slice_status_input(
    tmp_path: Path, label: str, content: str
) -> None:
    """NEGATIVE AT: every offending input this file exercises (a
    non-canonical status token in any of its forms, a blank Status cell, or
    an unparsable Slice Plan table) exits 1 with a well-formed JSON envelope
    on stdout -- never a Python traceback, never exit 2 (the doctor's own
    'bad input' usage-error code, reserved for an unreadable target path,
    never a content-level parse failure it must classify as a Gap)."""
    target = tmp_path / "feature-delta.md"
    target.write_text(content, encoding="utf-8")

    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-delta-doctor", str(target), "--format=json"],
        cwd=tmp_path,
    )

    combined = stdout + stderr
    assert "Traceback (most recent call last)" not in combined, (
        f"[{label}] the doctor must never leak a raw Python traceback; got "
        f"exit_code={exit_code} stdout={stdout!r} stderr={stderr!r}"
    )
    assert exit_code == 1, (
        f"[{label}] expected exit 1 (a genuine gap was found, not a usage "
        f"error) -- got exit_code={exit_code} stdout={stdout!r} "
        f"stderr={stderr!r}"
    )

    json_line = next(
        (
            line.strip()
            for line in reversed(stdout.splitlines())
            if line.strip().startswith("{")
        ),
        None,
    )
    assert json_line is not None, (
        f"[{label}] expected a parseable JSON report envelope on stdout; "
        f"got stdout={stdout!r} stderr={stderr!r}"
    )
    report = json.loads(json_line)  # must not raise
    assert report["gap_count"] == len(report["gaps"]) >= 1, (
        f"[{label}] expected >=1 gap and a consistent gap_count; got report={report}"
    )
