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


# ===========================================================================
# 3. POSITIVE + NEGATIVE-guard -- garbage non-UTF-8 bytes (Vera feature-end
#    hostile-examine probe 7): the file must be refused LOUD via a
#    structured MalformedInput diagnostic, NEVER via a raw uncaught
#    `UnicodeDecodeError` traceback escaping the CLI.
#
# DEFECT (probe 7): `des record-at-review-verdict --at-kind rust-regression
# --regression-test-file <binary/garbage non-UTF-8 .rs>` -> exit 1 + a RAW
# `UnicodeDecodeError` traceback. `_count_rust_regression_ats`
# (`src/des/cli/at_review_verdict.py:237-242`) wraps
# `regression_test_file.read_text(encoding="utf-8")` in `except OSError`
# only -- `UnicodeDecodeError` is a `ValueError` subclass, NOT an
# `OSError`, so it escapes uncaught. It propagates through
# `_slice_at_derivation` and out of `main()` entirely (`main()`'s own
# `try/except` at line ~404 catches only `GateError`), so the CLI crashes
# instead of emitting the `MalformedInput` `GateError` diagnostic the
# zero-#[test]-functions case already gets (`_malformed_rust_regression_
# file`, exit code 2). The charter's oracle demands a comprehensible
# structured message for an unreadable/garbage file, never a raw
# traceback.
#
# Driven in-process with `catch_all=True` -- the faithful in-process
# analogue of a subprocess CRASH (non-zero exit, traceback text preserved
# in captured stderr) rather than propagating the exception out of the test
# itself; this is how an uncaught `UnicodeDecodeError` surfaces without
# forking a real interpreter (`tests/common/in_process_cli.py`
# `run_cli_in_process(..., catch_all=True)`).
#
# RED-for-right-reason: today `_count_rust_regression_ats` never catches
# `UnicodeDecodeError`, so BOTH scenarios below fail with a genuine
# semantic `AssertionError` (exit_code == 1 with a real `Traceback` /
# `UnicodeDecodeError` string in stderr, not exit_code == 2 with a JSON
# diagnostic) -- never an import/collection error.
# ===========================================================================


def _write_rust_fixture_with_garbage_bytes(path: Path) -> None:
    """A `.rs` fixture containing raw non-UTF-8 bytes -- unreadable /
    undecodable content, the Vera probe-7 hostile-examine input."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe garbage \x00")


def test_rust_regression_at_kind_refuses_undecodable_file_with_structured_diagnostic(
    tmp_path: Path,
) -> None:
    """A `--at-kind rust-regression` invocation over a `.rs` file containing
    raw non-UTF-8 bytes must be refused LOUD -- a `MalformedInput`-shaped
    JSON diagnostic on stdout naming the file, exit code 2 (mirroring the
    zero-#[test]-functions `GateError`), and NO ledger record -- never an
    uncaught `UnicodeDecodeError` propagating as a raw traceback.
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/garbage_bytes.rs"
    _write_rust_fixture_with_garbage_bytes(repo / rust_file_rel)

    exit_code, stdout, stderr = run_cli_in_process(
        [
            *_base_argv(feature_id=_FEATURE_ID, slice_id=_SLICE_ID, repo_root=repo),
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            rust_file_rel,
        ],
        cwd=repo,
        main=record_at_review_verdict_main,
        catch_all=True,
    )

    assert exit_code == 2, (
        "an undecodable .rs regression-test file must be refused as a "
        "MalformedInput GateError (exit 2), mirroring the zero-#[test]-"
        f"functions case -- got exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}. Today `_count_rust_regression_ats` only "
        "catches `OSError`, so `UnicodeDecodeError` escapes uncaught (see "
        "this test module's section-3 docstring)."
    )

    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, (
        "expected a JSON diagnostic line on stdout naming the undecodable "
        f".rs file -- got EMPTY stdout (exit_code={exit_code}, "
        f"stderr={stderr!r})"
    )
    diagnostic = json.loads(stdout_lines[-1])
    diagnostic_text = json.dumps(diagnostic).lower()
    assert "malformed" in diagnostic_text or "cannot read" in diagnostic_text, (
        "the loud diagnostic must name the malformed/unreadable-file "
        f"condition -- got diagnostic={diagnostic!r}"
    )

    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    assert records == [], (
        "an undecodable .rs regression-test file must NEVER produce an "
        f"ATReviewVerdict ledger record -- got {records!r}"
    )


@pytest.mark.negative_at
def test_rust_regression_at_kind_never_lets_a_raw_traceback_escape_on_garbage_bytes(
    tmp_path: Path,
) -> None:
    """Negative guard (the wrong outcome must NOT be produced): a raw,
    uncaught `UnicodeDecodeError` traceback must never reach the CLI's
    captured output -- the exact crash-class failure mode Vera's
    feature-end hostile examine (probe 7) exhibited must be structurally
    absent, not merely "usually doesn't happen".
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/garbage_bytes_negative.rs"
    _write_rust_fixture_with_garbage_bytes(repo / rust_file_rel)

    exit_code, stdout, stderr = run_cli_in_process(
        [
            *_base_argv(feature_id=_FEATURE_ID, slice_id=_SLICE_ID, repo_root=repo),
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            rust_file_rel,
        ],
        cwd=repo,
        main=record_at_review_verdict_main,
        catch_all=True,
    )

    assert "Traceback" not in stderr, (
        "a raw UnicodeDecodeError traceback must NEVER escape to the CLI's "
        f"stderr -- got stderr={stderr!r} (exit_code={exit_code}, "
        f"stdout={stdout!r})"
    )
    assert "UnicodeDecodeError" not in stderr, (
        "the raw exception class name must never leak to stderr as an "
        f"unhandled-crash artifact -- got stderr={stderr!r}"
    )
    assert exit_code != 1, (
        "exit_code == 1 is this CLI's uncaught-crash signature under the "
        "in-process catch_all mapping (faithful to a subprocess crash) -- "
        "a malformed regression-test file must be refused with a "
        "deliberate, structured exit code (2), never an accidental crash "
        f"code. Got exit_code={exit_code}, stderr={stderr!r}"
    )


# ===========================================================================
# 4. FALSE-POSITIVE (round 3, Vera's round-2 probe 3): the regex is
#    comment-blind -- a `#[test]` occurring inside a `//` line comment
#    (never a real Rust attribute) still satisfies `_RUST_TEST_FN_RE` when
#    it sits directly above a genuine (non-test) `fn` declaration, because
#    the regex is a pure lexical scan over raw source text with no
#    comment/string-literal awareness.
#
# MECHANISM (confirmed empirically this diagnosis session, both against the
# bare regex and against the full in-process CLI):
#   `_RUST_TEST_FN_RE` = `#\[test\]\s*(?:#\[[^\]]*\]\s*)*(?:pub\s+)?
#   (?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)` requires ONLY that the literal
#   substring "#[test]" appear ANYWHERE in the source, followed (modulo
#   whitespace / `#[...]` attributes / `pub`/`async`/`unsafe` modifiers) by
#   a `fn NAME` -- it never checks whether "#[test]" sits inside a
#   `//`/`/* */` comment or a string literal, nor whether it is a real
#   line-leading attribute on the very next item.
#
#   Vera's probe-3 verbal repro as literally transcribed (a bare 2-function
#   file with ZERO occurrences of the text "#[test]" anywhere) does **not**
#   reproduce against this source: `_RUST_TEST_FN_RE.findall(...)` returns
#   `[]` for that exact text and the CLI correctly refuses (exit 2,
#   `MalformedInput`) -- verified directly. The REAL, reproducing trigger
#   (confirmed both via the bare regex and via the full
#   `des.cli.at_review_verdict.main` in-process CLI call) is a stray
#   `// #[test]` LINE COMMENT sitting directly above an unrelated real
#   `fn` -- e.g. left over from a refactor, or illustrative example text.
#   This DOES fabricate an `at_id` for that `fn`: exit 0, ledger entry
#   written with `at_ids: ["helper"]`, for a file with NO real `#[test]`
#   attribute anywhere -- exactly the observable Vera's probe reported.
#
# Two hardening cases pin CORRECT behavior that must survive the fix
# (already GREEN today under `_RUST_TEST_FN_RE` -- guarded here against
# regressing while the comment-blindness defect above is repaired):
#   (a) a `#[cfg(test)]` (or any other NON-test) attribute directly
#       preceding a `fn` must NOT be counted -- `#[cfg(test)]` is not the
#       literal substring `#[test]`, so the regex already correctly
#       refuses this case.
#   (b) a real `#[test] fn a()` immediately followed by a bare `fn b()`
#       must yield `at_ids == ["a"]` only -- the bare `fn b()` (no
#       `#[test]` of its own) must never be swept in.
# ===========================================================================


def _write_rust_fixture_with_commented_test_marker_before_real_fn(path: Path) -> None:
    """The round-3 false-positive repro: NO real `#[test]` attribute
    anywhere -- only a `// #[test]` LINE COMMENT (never a real Rust
    attribute) sitting directly above a genuine non-test `fn`. Confirmed
    (this diagnosis session) to fabricate `at_ids == ["helper"]` under
    `_RUST_TEST_FN_RE` today.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// Regression fixture -- balance invariants, no real #[test] "
        "anywhere.\n\n"
        "pub fn calculate_balance(amount: f64) -> f64 { amount }\n\n"
        "// #[test]\n"
        "fn helper() {}\n",
        encoding="utf-8",
    )


def _write_rust_fixture_with_cfg_test_attribute_and_bare_fn(path: Path) -> None:
    """Hardening (a): a `#[cfg(test)]` (NON-test) attribute directly above a
    `fn`, plus an ordinary `pub fn` -- zero REAL `#[test]` functions. Must be
    refused exactly like the plain zero-tests case (already GREEN today)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// No #[test] functions -- only a #[cfg(test)] conditional "
        "attribute.\n\n"
        "#[cfg(test)]\n"
        "fn conditionally_compiled_helper() {}\n\n"
        "pub fn add(a: i32, b: i32) -> i32 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )


def _write_rust_fixture_with_one_real_test_and_one_bare_fn(path: Path) -> None:
    """Hardening (b): one genuine `#[test] fn a()` immediately followed by
    an unrelated bare `fn b()` (no attribute of its own). Must record
    `at_ids == ["a"]` only -- `b` must never be swept in (already GREEN
    today)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#[test]\nfn a() {\n    assert_eq!(1, 1);\n}\n\nfn b() {}\n",
        encoding="utf-8",
    )


def test_rust_regression_at_kind_rejects_a_commented_out_test_marker_before_a_real_fn(
    tmp_path: Path,
) -> None:
    """RED today (round-3 false positive): a `.rs` file with NO real
    `#[test]` attribute anywhere -- only a `// #[test]` line comment sitting
    above a genuine, non-test `fn` -- must be refused exactly like the
    plain zero-real-tests case (exit 2, `MalformedInput`, "zero #[test]
    functions", NO ledger entry). `_RUST_TEST_FN_RE` is comment-blind: it
    matches the literal text "#[test]" wherever it occurs, including inside
    a `//` comment, so today this file records successfully (exit 0) with a
    FABRICATED `at_ids == ["helper"]` -- `helper` carries no real `#[test]`
    attribute at all. This assertion fails for the right (semantic) reason
    today: the CLI runs to completion and returns 0 with a bogus verdict,
    it does not crash or error out.
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/commented_test_marker.rs"
    _write_rust_fixture_with_commented_test_marker_before_real_fn(repo / rust_file_rel)

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

    assert exit_code == 2, (
        "a .rs file with NO real #[test] attribute -- only a `// #[test]` "
        "comment above an unrelated fn -- must be refused (exit 2, "
        f"MalformedInput) -- got exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}. `_RUST_TEST_FN_RE` is comment-blind and "
        "fabricates at_ids=['helper'] today (see module docstring section "
        "4 above for the confirmed mismatch mechanism)."
    )

    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, (
        "expected a JSON MalformedInput diagnostic line on stdout -- got "
        f"EMPTY stdout (exit_code={exit_code}, stderr={stderr!r})"
    )
    diagnostic = json.loads(stdout_lines[-1])
    diagnostic_text = json.dumps(diagnostic).lower()
    assert "malformed" in diagnostic_text or "zero" in diagnostic_text, (
        "the loud diagnostic must name the malformed-input / zero-test-"
        f"functions condition -- got diagnostic={diagnostic!r}"
    )

    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    assert records == [], (
        "a .rs file with NO real #[test] attribute must NEVER produce an "
        f"ATReviewVerdict record, fabricated or otherwise -- got {records!r}"
    )


@pytest.mark.negative_at
def test_rust_regression_at_kind_never_records_a_fabricated_at_id_from_a_commented_test_marker(
    tmp_path: Path,
) -> None:
    """Negative guard (the WRONG outcome must NOT be produced): a `//
    #[test]` comment marker must never cause a fabricated `at_id` for the
    real `fn` beneath it to reach the ledger -- the exact false-positive
    Vera's round-2 probe 3 exhibited (`at_ids: ["helper"]` for a file with
    no real test) must be structurally absent, not merely "usually doesn't
    happen".
    """
    repo = tmp_path / "repo"
    rust_file_rel = "tests/rust/regression/commented_test_marker_negative.rs"
    _write_rust_fixture_with_commented_test_marker_before_real_fn(repo / rust_file_rel)

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

    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    assert records == [], (
        "a fabricated at_id ('helper', sourced from a commented-out "
        "// #[test] marker with no real attribute) must NEVER be written "
        f"to the ledger -- got {records!r} (exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r})"
    )
    assert not any("helper" in str(r.get("at_ids")) for r in records), (
        "the fabricated 'helper' at_id must never appear in any recorded "
        f"verdict -- got {records!r}"
    )


@pytest.mark.parametrize(
    "fixture_writer,rust_file_rel,expected_exit_code,expected_at_ids",
    [
        pytest.param(
            _write_rust_fixture_with_cfg_test_attribute_and_bare_fn,
            "tests/rust/regression/cfg_test_not_counted.rs",
            2,
            None,
            id="cfg_test_attribute_not_counted",
        ),
        pytest.param(
            _write_rust_fixture_with_one_real_test_and_one_bare_fn,
            "tests/rust/regression/one_real_test_one_bare_fn.rs",
            0,
            ["a"],
            id="bare_fn_after_real_test_excluded",
        ),
    ],
)
def test_rust_regression_at_kind_hardening_cases_already_pass_today(
    tmp_path: Path,
    fixture_writer,
    rust_file_rel: str,
    expected_exit_code: int,
    expected_at_ids: list[str] | None,
) -> None:
    """Hardening (a)+(b), already GREEN today -- pinned so the
    comment-blindness fix cannot regress either: (a) a `#[cfg(test)]` (any
    NON-test attribute) directly preceding a `fn` must never be counted as
    a real test; (b) a real `#[test] fn a()` immediately followed by a bare
    `fn b()` must record `at_ids == ["a"]` only.
    """
    repo = tmp_path / "repo"
    fixture_writer(repo / rust_file_rel)

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

    assert exit_code == expected_exit_code, (
        f"expected exit_code={expected_exit_code} -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    records = _read_verdict_records(repo, _FEATURE_ID, _SLICE_ID)
    if expected_at_ids is None:
        assert records == [], (
            f"expected NO ledger record for a refused input -- got {records!r}"
        )
    else:
        assert len(records) == 1, f"expected exactly one record -- got {records!r}"
        assert records[0].get("at_ids") == expected_at_ids, (
            f"expected at_ids={expected_at_ids!r} -- got "
            f"at_ids={records[0].get('at_ids')!r}"
        )
