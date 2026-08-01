"""Regression #53 — pytest-regression AT count over-counts a SHARED file.

Bug (recurring friction #53, bit twice today on `language-port-realization-gate`
slice-06): `count_pytest_regression_ats` (`src/des/cli/carpaccio_format.py`
L375-420) AST-counts EVERY module-level `test_*` function in the WHOLE
`regression_test_file` -- with no notion of which slice each function belongs
to. `check_carpaccio`'s assertion-1 size gate (`carpaccio_format.py` L620-628)
consumes that whole-file count UNCONDITIONALLY as the entering slice's
`at_count`:

    at_count = count_pytest_regression_ats(regression_test_file)   # L622
    ...
    return _check_slice_size_count(plan, entering_slice, slice_max, at_count, ...)

`carpaccio_slice_gate.py`'s assertion-5 verdict check (`_check_verdict_record`,
L610-622) has the identical shape (`at_count = count_pytest_regression_ats(...)`
feeding the `AT-{n}` id-set comparison) -- both call sites share the same
root-cause function; this AT targets assertion 1, the one that produced
today's spurious `CARPACCIO_SLICE_TOO_LARGE` and forced a needless `@coupled`
annotation.

Repro (today): a shared regression file already carries 10 ATs attested to a
PREDECESSOR slice (via an `ATReviewVerdict` ledger record). The entering
slice adds exactly 1 NEW test to that same file. `count_pytest_regression_ats`
returns 11 (10 + 1) -- the file's total -- so a ceiling of 7 rejects a slice
that in truth added only 1 AT.

Neither `count_pytest_regression_ats` nor `check_carpaccio`'s pytest-regression
branch reads the AT-completion ledger at all -- the predecessor's attested
`at_ids` are never consulted to discount the total. The fix (out of scope for
this AT -- TEST ONLY) must count what the ENTERING slice adds (or exclude
predecessor-attested `at_ids`), not the file's raw total.

Hermetic, fixture-based (no live-state coupling): drives the real
`des.cli.carpaccio_slice_gate.main` CLI entry point against a `tmp_path` repo,
mirroring `test_carpaccio_mechanical_seal.py`'s conventions (crafted ledger
records + a `RedObserved` seal in the P0.2 producer's own shape via its
`_seal_path` helper).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main
from des.cli.verify_red_green import _seal_path


_FEATURE_ID = "fix-53-carpaccio-shared-file-overcounting"


def _feature_delta(rows: list[tuple[str, str]]) -> str:
    """Build a `[REF] Slice Plan` table with one empty-annotation row per (slice_id, value)."""
    header = (
        "# Feature Delta: shared-file overcounting fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
    )
    body = "".join(
        f"| {slice_id} | {value} | pending | | |\n" for slice_id, value in rows
    )
    return header + body


def _make_repo(
    tmp_path: Path,
    *,
    plan_rows: list[tuple[str, str]],
    regression_rel: str,
    regression_src: str,
) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        _feature_delta(plan_rows), encoding="utf-8"
    )
    regression = repo / regression_rel
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(regression_src, encoding="utf-8")
    return repo


def _write_predecessor_verdict(
    repo: Path, *, slice_id: str, at_ids: list[str], content_hash: str = "n/a"
) -> None:
    """Simulate a PREDECESSOR slice's already-attested ATReviewVerdict record.

    Mirrors the real record shape (`des record-at-review-verdict` /
    `_latest_verdict_record` in `carpaccio_slice_gate.py`) -- one JSONL line,
    keyed by `slice_id`, in the SAME ledger file the entering slice's own
    verdict lookup will later scan. `content_hash` is irrelevant to this
    predecessor's own past clearance (already happened) and is never read by
    `count_pytest_regression_ats` for ANY slice -- that is exactly the
    defect this AT demonstrates.
    """
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "ATReviewVerdict",
        "schema_version": "1.0.0",
        "slice_id": slice_id,
        "verdict": "APPROVED",
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": at_ids,
        "at_content_hash": content_hash,
        "timestamp": "2026-07-03T00:00:00Z",
        "findings_summary": [],
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _write_red_seal(repo: Path, regression_rel: str) -> None:
    """Craft a fresh `RedObserved` seal (P0.2) for `regression_rel`, matching
    CURRENT file content -- so the entering slice can also clear assertion 5
    (mechanical-seal route) once assertion 1's over-counting is fixed. Not
    exercised by the RED assertion below (assertion 1 fails first, before
    assertion 5 ever runs) -- present so this AT does not newly break on
    assertion 5 the moment the counting fix lands.
    """
    test_file = (repo / regression_rel).resolve()
    seal = _seal_path(repo.resolve(), test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": regression_rel,
                "content_sha256": hashlib.sha256(test_file.read_bytes()).hexdigest(),
                "outcomes": {"t::test_a": "fail", "t::test_b": "fail"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_gate(
    repo: Path,
    entering_slice: str,
    regression_rel: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    exit_code = carpaccio_gate_main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            entering_slice,
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_rel,
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


# ---------------------------------------------------------------------------
# Fixture regression-file bodies
# ---------------------------------------------------------------------------

_PREDECESSOR_10_AT_IDS = [f"AT-{n}" for n in range(1, 11)]

_PREDECESSOR_10 = "".join(
    f"def test_predecessor_slice_02_at_{n:02d}():\n    assert True\n\n\n"
    for n in range(1, 11)
)

# The entering slice's OWN single new AT -- named with the `_rejects_` negative
# stem so it doubles as the P0.3 negative-AT the mechanical-seal route needs.
_SLICE_06_ONE_NEW_AT = "def test_slice_06_rejects_invalid_input():\n    assert True\n"

_PREDECESSOR_2 = "".join(
    f"def test_predecessor_slice_02_at_{n:02d}():\n    assert True\n\n\n"
    for n in range(1, 3)
)

# The entering slice's 16 genuinely NEW ATs (net-new > ceiling of 15 on its own).
_SLICE_07_SIXTEEN_NEW_ATS = "".join(
    f"def test_slice_07_new_at_{n:02d}():\n    assert True\n\n\n" for n in range(1, 17)
)


def test_slice_clears_when_only_net_new_ats_counted_against_ceiling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RED (right reason): slice-06 adds exactly 1 new AT (ceiling 15) to a
    shared file that already carries 10 ATs attested to predecessor slice-02.

    Wrong (today): `count_pytest_regression_ats` returns 11 (10 + 1, the
    file's raw total) -> `CARPACCIO_SLICE_TOO_LARGE`, forcing a spurious
    `@coupled` annotation on a slice that genuinely added only 1 AT.

    Right (fixed): the entering slice's AT count reflects what IT adds (1),
    which clears the ceiling of 15 without any `@coupled` escape -- exit 0,
    `SliceCleared`.
    """
    regression_rel = "tests/regression/test_shared_slice_ats.py"
    repo = _make_repo(
        tmp_path,
        plan_rows=[
            ("slice-02", "Predecessor slice already attested via the ledger"),
            ("slice-06", "Entering slice adds exactly one new AT to the shared file"),
        ],
        regression_rel=regression_rel,
        regression_src=_PREDECESSOR_10 + _SLICE_06_ONE_NEW_AT,
    )
    _write_predecessor_verdict(repo, slice_id="slice-02", at_ids=_PREDECESSOR_10_AT_IDS)
    _write_red_seal(repo, regression_rel)

    exit_code, payload = _run_gate(repo, "slice-06", regression_rel, capsys)

    assert exit_code == 0 and payload.get("event") == "SliceCleared", (
        "slice-06 adds exactly 1 new AT to the shared regression file (ceiling "
        f"15) but was rejected: exit_code={exit_code} payload={payload}. "
        "count_pytest_regression_ats (src/des/cli/carpaccio_format.py "
        "L375-420) AST-counts the file's WHOLE total (10 ATs already "
        "attested to predecessor slice-02 + 1 new = 11), not the net-new "
        "count the ENTERING slice actually adds; check_carpaccio's "
        "assertion-1 size gate (L620-628) consumes that inflated total "
        "unconditionally -- the ledger's predecessor at_ids are never "
        "consulted to discount it."
    )


def test_gate_rejects_when_entering_slice_genuinely_adds_more_than_ceiling_new_ats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative guard (GREEN before AND after the fix): a shared file must
    NOT be blanket-exempted from the ceiling.

    Predecessor slice-02 attested only 2 ATs; entering slice-07 adds 16
    genuinely NEW ATs to the SAME shared file -- net-new (16) alone exceeds
    the ceiling (15), so the slice must still be rejected. Passes today
    (2 + 16 = 18 > 15 on the raw total) AND must keep passing once the
    over-counting fix lands (net-new 16 > 15 on the corrected count) -- pins
    the boundary so a naive fix cannot blanket-exempt every shared-file
    slice from the size ceiling. Count raised 8 -> 16 (Ale, 2026-08-01)
    alongside the ceiling raise 7 -> 15, so the fixture still genuinely
    exceeds whatever ceiling is in effect.
    """
    regression_rel = "tests/regression/test_shared_slice_ats_2.py"
    repo = _make_repo(
        tmp_path,
        plan_rows=[
            ("slice-02", "Predecessor slice already attested via the ledger"),
            ("slice-07", "Entering slice adds sixteen new ATs to the shared file"),
        ],
        regression_rel=regression_rel,
        regression_src=_PREDECESSOR_2 + _SLICE_07_SIXTEEN_NEW_ATS,
    )
    _write_predecessor_verdict(repo, slice_id="slice-02", at_ids=["AT-1", "AT-2"])

    exit_code, payload = _run_gate(repo, "slice-07", regression_rel, capsys)

    assert exit_code == 44
    assert payload.get("event") == "CARPACCIO_SLICE_TOO_LARGE"
