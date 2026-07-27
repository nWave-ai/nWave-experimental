"""Regression (defects.md: rust-regression-at-kind-semi-wired): the
``rust-regression`` ``--at-kind`` value must be VALID across the whole
atdd_pure cycle, not just at the producer end.

DEFECT (as investigated -- the pile row's literal claim about `verify-slice-
commit` already accepting it turned out stale, see resolution note in
`done.md`): before this fix, `des record-at-review-verdict` (`at_review_
verdict.py`) was the ONLY consumer that accepted the literal `--at-kind
rust-regression` -- it has its own local `#[test]`-regex counter
(`_count_rust_regression_ats`). Every OTHER consumer in the cycle had since
migrated to a unified `native-regression` AT-discovery facet (fix-rust-
regression-at-kind-wiring, routed through the runner-port seam covering
`.rs`/`.cs`/`.kt` via suffix) but had NEVER learned the OLDER
`rust-regression` literal as an alias of it:

  * `des carpaccio-slice-gate` (`carpaccio_slice_gate.py`) -- argparse
    ``choices`` omitted ``rust-regression`` entirely (only
    ``gherkin``/``pytest-regression``/``native-regression``) -- a Rust
    bugfix slice with an APPROVED `rust-regression` verdict record could
    never re-clear the SAME slice's `A_GREEN` entry gate under its own
    at-kind vocabulary.
  * `des verify-slice-commit` (`verify_slice_commit_completeness.py`,
    reused by `commit_slice.py`'s own parser) -- same omission.
  * the U1 PreToolUse carpaccio-intercept dispatch-guard hook
    (`carpaccio_intercept.py::_real_carpaccio_runner`) -- silently DROPPED
    the `--at-kind`/`--regression-test-file` forwarding for anything other
    than the literal `"pytest-regression"`, so a `rust-regression` (or even
    `native-regression`) dispatch fell through to the default gherkin gate
    call and false-refused with `no-scenarios-for-slice` (a GDP-6 silent-
    wrong -- fixed here to degrade LOUD-and-correct instead, by actually
    forwarding the flags).

Note on `des_crafter_dispatch_guard.py`: per
`tests/build/f_nonbypassable_attestation/test_arch_wave_dispatch_guard_home.py`
this is a HAND-PLACED PERSONAL hook (`~/.claude/hooks/`), no repo source --
it has NO at-kind concept at all (gates on the DES-MODE/DES-PHASE/DES-SLICE
marker triple only), so there is nothing to fix there for this defect; the
REPO-TRACKED dispatch-guard hook that actually forwards at-kind into the
gate subprocess is `carpaccio_intercept.py`, fixed above.

Fix: ``rust-regression`` is now an accepted CLI-facing ALIAS of
``native-regression`` in all three lagging consumers -- normalized
immediately after argparse, before any downstream handling, so it reuses the
SAME unified runner-port AT-discovery facet (no second parser/duplicated
logic, SSOT/DRY).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from des.adapters.drivers.hooks import carpaccio_intercept as ci
from des.cli import at_review_verdict, carpaccio_slice_gate, commit_slice
from des.cli import verify_slice_commit_completeness as vscc


_REGRESSION_FILE = "src/lib.rs"


def _accepts(parser: argparse.ArgumentParser, argv: list[str]) -> argparse.Namespace:
    try:
        return parser.parse_args(argv)
    except SystemExit as exc:
        pytest.fail(
            f"argparse rejected --at-kind rust-regression (exit {exc.code}) -- "
            f"'rust-regression' must be a valid --at-kind choice. argv={argv!r}"
        )


# ---------------------------------------------------------------------------
# 1. record-at-review-verdict -- baseline, was ALREADY accepting it (B-1)
# ---------------------------------------------------------------------------


def test_record_at_review_verdict_accepts_rust_regression() -> None:
    args = at_review_verdict._parse_args(
        [
            "--feature-id",
            "f",
            "--slice-id",
            "slice-01",
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "reviewer-1",
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            _REGRESSION_FILE,
        ]
    )
    assert args.at_kind == "rust-regression"


# ---------------------------------------------------------------------------
# 2. carpaccio-slice-gate -- was REJECTING it (defect's literal claim)
# ---------------------------------------------------------------------------


def test_carpaccio_slice_gate_accepts_rust_regression() -> None:
    argv = [
        "--feature-id",
        "f",
        "--entering-slice",
        "slice-01",
        "--at-kind",
        "rust-regression",
        "--regression-test-file",
        _REGRESSION_FILE,
    ]
    try:
        args = carpaccio_slice_gate._parse_args(argv)
    except SystemExit as exc:
        pytest.fail(
            f"des carpaccio-slice-gate rejected --at-kind rust-regression "
            f"(argparse exit {exc.code}) -- 'rust-regression' must be a "
            f"valid --at-kind choice. argv={argv!r}"
        )
    assert args.at_kind == "rust-regression"


def test_carpaccio_slice_gate_normalizes_rust_regression_past_argument_validation(
    tmp_path: Path,
) -> None:
    """`main()` must accept the alias and get PAST the at-kind validation
    branch -- reaching the (unrelated) missing-feature-delta failure
    (`SlicePlanSectionMissing`, exit 1) rather than an argparse invalid-
    choice `SystemExit(2)` or the `MalformedInput` `--regression-test-file`
    guard (which would fire if the alias were dropped instead of normalized).
    """
    exit_code = carpaccio_slice_gate.main(
        [
            "--feature-id",
            "rust-regression-fully-wired-probe",
            "--entering-slice",
            "slice-01",
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            _REGRESSION_FILE,
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 1, (
        "a `rust-regression` dispatch against a repo with no feature-delta must "
        "fail on the MISSING FEATURE-DELTA (SlicePlanSectionMissing, exit 1) -- "
        "proving the alias was accepted and normalized past the --at-kind "
        f"validation branch. Got exit_code={exit_code!r} (2 would mean the "
        "alias is still rejected/mishandled)."
    )


# ---------------------------------------------------------------------------
# 3. verify-slice-commit (both entry points) -- was REJECTING it
# ---------------------------------------------------------------------------


def test_verify_slice_commit_completeness_accepts_rust_regression() -> None:
    parser = vscc._build_parser()
    args = _accepts(
        parser,
        [
            "--repo",
            "/does/not/need/to/exist/for/parsing",
            "--commit",
            "HEAD",
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            _REGRESSION_FILE,
        ],
    )
    assert args.at_kind == "rust-regression"


def test_commit_slice_accepts_rust_regression() -> None:
    parser = commit_slice._build_parser()
    args = _accepts(
        parser,
        [
            "--repo",
            "/does/not/need/to/exist/for/parsing",
            "--all",
            "--feature-id",
            "f",
            "--slice-id",
            "slice-01",
            "--message",
            "fix(slice): rust regression",
            "--at-kind",
            "rust-regression",
            "--regression-test-file",
            _REGRESSION_FILE,
        ],
    )
    assert args.at_kind == "rust-regression"


# ---------------------------------------------------------------------------
# 4. the dispatch-guard hook (carpaccio_intercept.py -- the repo-tracked U1
#    PreToolUse gate; the personal ~/.claude/hooks/des_crafter_dispatch_
#    guard.py has no at-kind concept, see module docstring) -- was SILENTLY
#    DROPPING the forwarding for rust-regression (GDP-6 silent-wrong)
# ---------------------------------------------------------------------------


def test_carpaccio_intercept_forwards_rust_regression_to_the_gate_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: dict[str, tuple] = {}

    def fake_spawn(*args, **kwargs):
        recorded["args"] = args
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = '{"event": "CarpaccioSliceThin", "verdict": "cleared"}'
        return completed

    monkeypatch.setattr(ci, "des_spawn", fake_spawn)

    runner = ci._real_carpaccio_runner(
        tmp_path,
        at_kind="rust-regression",
        regression_test_file=_REGRESSION_FILE,
    )
    runner("synthetic-feature", "slice-01")
    args = list(recorded["args"])

    assert "--at-kind" in args and "rust-regression" in args, (
        "the dispatch-guard hook's carpaccio runner must forward "
        "`--at-kind rust-regression` to the carpaccio-slice-gate subprocess "
        f"instead of silently dropping it. des_spawn args={args}"
    )
    assert "--regression-test-file" in args and _REGRESSION_FILE in args, (
        f"the regression-test file must be forwarded too. args={args}"
    )


def test_carpaccio_intercept_parses_rust_regression_marker_from_prompt() -> None:
    """End-to-end from the dispatch prompt's DES-AT-KIND marker down to the
    parsed (at_kind, regression_test_file) pair the runner is built with.
    """
    prompt = (
        "<!-- DES-AT-KIND : rust-regression -->\n"
        f"<!-- DES-REGRESSION-TEST-FILE : {_REGRESSION_FILE} -->\n"
    )
    at_kind, regression_test_file = ci._parse_at_kind_from_prompt(prompt)
    assert at_kind == "rust-regression"
    assert regression_test_file == _REGRESSION_FILE
