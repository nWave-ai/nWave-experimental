"""Regression (B-1, sister-reported): `des record-at-review-verdict` has NO
`--at-kind` choice for a Rust `.rs` acceptance-test file.

DEFECT: `at_review_verdict.py`'s `--at-kind` argparse option
(`src/des/cli/at_review_verdict.py:287-298`) offers only
`{gherkin, pytest-regression}`. `pytest-regression` counts module-level
`test_*` functions via `ast.parse` (`carpaccio_format.count_pytest_regression_
ats`) -- feeding it a `.rs` file correctly, LOUDLY refuses (post-#80 fix) with
a `MalformedInput` `GateError` rather than silently producing an empty
verdict. But there is NO `rust-regression` (or equivalent) choice at all, so a
bugfix slice whose AT file is a Rust `.rs` file has NO path to obtain an
`ATReviewVerdict` -- `des carpaccio-slice-gate` (assertion 5) then refuses the
slice's `A_GREEN` entry with nothing the operator can do about it. This is the
gap `#80`'s silence-fix exposed: the degrade is now LOUD for the wrong-parser
case, but there is still no PRODUCER path for the right language.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero `src/` edits): add `--at-kind rust-regression` that counts `#[test]`
functions in the `.rs` file (the Rust mirror of the pytest-regression
module-level `test_*` counting), ideally routed through the per-language
runner-port seam (#81) rather than a second Python-side parser -- degrade-LOUD
if unresolvable. This AT asserts the OUTCOME (a Rust regression AT earns a
non-empty, content-real `ATReviewVerdict`; a Rust file with zero `#[test]`
functions is refused LOUD, never silently recorded), never the mechanism.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.at_review_verdict.main(argv)` CLI EDGE, driven in-process
via `tests.common.in_process_cli.run_cli_in_process` (the in-process analogue
of `python -m des.cli.at_review_verdict ...`) under an isolated `tmp_path`
repo -- never the real `.nwave/telemetry/`.

RED-for-right-reason (this docstring documents WHY, per the red-scaffolding
discipline): `--at-kind rust-regression` is not a recognized choice today, so
argparse rejects the invocation before any repo/ledger work happens (`exit
code 2`, a bare "invalid choice" usage line on stderr, EMPTY stdout -- no JSON
diagnostic line at all, unlike the `GateError` path a recognized-but-malformed
`--at-kind` value takes). Both scenarios below assert on observables that are
only true once the fix lands (an exit-0 recorded verdict for the positive
case; a JSON `MalformedInput`-shaped diagnostic on stdout for the negative
case) -- today both fail with a genuine semantic `AssertionError`, never an
import/collection error.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.at_review_verdict import main as record_at_review_verdict_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "b1-rust-regression-at-kind"
_SLICE_ID = "slice-01"
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _run_record_at_review_verdict(
    repo_root: Path, argv: list[str]
) -> tuple[int, str, str]:
    """Drive the REAL `des record-at-review-verdict` CLI EDGE in-process."""
    return run_cli_in_process(argv, cwd=repo_root, main=record_at_review_verdict_main)


def _base_argv(*, feature_id: str, slice_id: str, repo_root: Path) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        "APPROVED",
        "--reviewer-agent-id",
        "nw-acceptance-designer-reviewer",
        "--repo-root",
        str(repo_root),
    ]


def _read_verdict_records(
    repo_root: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    return AtCompletionLedger(feature_id, repo_root).read_records(
        event_type="ATReviewVerdict", slice_id=slice_id
    )


def _write_rust_fixture_with_two_tests(path: Path) -> None:
    """A controlled, pytest-independent Rust `.rs` file: two `#[test]` fns,
    realistic idiom (descriptive names under `#[test]`, NOT `test_`-prefixed
    -- mirrors the Rust community convention, distinct from pytest's)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// Regression fixture -- balance invariants.\n\n"
        "#[test]\n"
        "fn balance_reflects_deposit() {\n"
        "    assert_eq!(2 + 2, 4);\n"
        "}\n\n"
        "#[test]\n"
        "fn balance_rejects_negative_withdrawal() {\n"
        "    assert_eq!(1 + 1, 2);\n"
        "}\n",
        encoding="utf-8",
    )


def _write_rust_fixture_with_zero_tests(path: Path) -> None:
    """A controlled Rust `.rs` file with ZERO `#[test]` functions -- ordinary
    (non-test) source only, the malformed-input case for the negative AT."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// No #[test] functions in this file at all.\n\n"
        "pub fn add(a: i32, b: i32) -> i32 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )


# ===========================================================================
# 1. POSITIVE -- active-RED today
# ===========================================================================


def test_records_a_rust_regression_at_review_verdict_with_two_test_functions(
    tmp_path: Path,
) -> None:
    """A `--at-kind rust-regression` invocation over a controlled `.rs`
    fixture with two `#[test]` functions must record an `ATReviewVerdict`
    whose `at_ids` are non-empty (one per reviewed Rust test function) and
    whose `at_content_hash` seals REAL file content -- never the hash of an
    empty string.
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/balance_invariants.rs"
    _write_rust_fixture_with_two_tests(repo / rust_file_rel)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        [
            *_base_argv(feature_id=_FEATURE_ID, slice_id=_SLICE_ID, repo_root=repo),
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            rust_file_rel,
        ],
    )

    assert exit_code == 0, (
        "a rust-regression AT-review verdict over a real 2-test .rs fixture "
        "must record successfully (exit 0) -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}. "
        "'--at-kind rust-regression' does not exist yet on `des record-at-"
        "review-verdict` (src/des/cli/at_review_verdict.py) -- see this "
        "test module's docstring for the fix direction."
    )

    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    assert len(records) == 1, (
        "expected exactly one ATReviewVerdict record for the entering "
        f"slice -- got {records!r}"
    )
    record = records[0]

    at_ids = record.get("at_ids")
    assert isinstance(at_ids, list) and len(at_ids) == 2, (
        "the recorded verdict's at_ids must be non-empty and count the two "
        f"reviewed Rust #[test] functions -- got at_ids={at_ids!r}"
    )

    at_content_hash = record.get("at_content_hash")
    assert isinstance(at_content_hash, str) and at_content_hash, (
        f"at_content_hash must be a real, non-empty seal -- got {at_content_hash!r}"
    )
    assert at_content_hash != _EMPTY_SHA256, (
        "at_content_hash must be the hash of the REAL .rs file content, "
        f"never SHA256(''): got {at_content_hash!r}"
    )


# ===========================================================================
# 2. NEGATIVE -- zero #[test] functions must refuse LOUD, never silently
#    record an empty verdict (the #80 class, asserted absent for Rust too).
# ===========================================================================


@pytest.mark.negative_at
def test_rust_regression_at_kind_rejects_a_rust_file_with_zero_test_functions(
    tmp_path: Path,
) -> None:
    """A `.rs` fixture with ZERO `#[test]` functions must NEVER yield a
    silent-empty verdict (`at_ids: []` + `at_content_hash` of an empty
    string) -- it must be refused LOUD via a diagnostic on stdout, and no
    `ATReviewVerdict` record may ever reach the ledger.
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/no_tests_here.rs"
    _write_rust_fixture_with_zero_tests(repo / rust_file_rel)

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        [
            *_base_argv(feature_id=_FEATURE_ID, slice_id=_SLICE_ID, repo_root=repo),
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            rust_file_rel,
        ],
    )

    assert exit_code != 0, (
        "a rust-regression AT-review over a .rs file with ZERO #[test] "
        f"functions must be refused (non-zero exit) -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )

    # The refusal must be LOUD -- a parseable JSON diagnostic line on stdout
    # naming the malformed condition (mirroring the pytest-regression
    # MalformedInput GateError shape). Today `--at-kind rust-regression` is
    # not a recognized choice at all, so argparse rejects the invocation
    # BEFORE any file is ever read -- stdout is EMPTY (the "invalid choice"
    # usage text goes to stderr only), so this assertion fails for the right
    # (semantic) reason today.
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, (
        "expected a JSON diagnostic line on stdout naming the malformed "
        "Rust regression-test file (zero #[test] functions) -- got EMPTY "
        f"stdout (exit_code={exit_code}, stderr={stderr!r}). "
        "'--at-kind rust-regression' does not exist yet, so argparse's "
        "invalid-choice error never reaches file-content validation."
    )
    diagnostic = json.loads(stdout_lines[-1])
    diagnostic_text = json.dumps(diagnostic).lower()
    assert "malformed" in diagnostic_text or "zero" in diagnostic_text, (
        "the loud diagnostic must name the malformed-input / zero-test-"
        f"functions condition -- got diagnostic={diagnostic!r}"
    )

    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    assert records == [], (
        "a Rust file with zero #[test] functions must NEVER produce a "
        f"silent-empty ATReviewVerdict record -- got {records!r}"
    )
