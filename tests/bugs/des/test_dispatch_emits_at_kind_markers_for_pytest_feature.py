"""Regression: `des dispatch` must be able to declare a pytest-regression AT
for ANY lane (including no/feature lane), emitting `DES-AT-KIND` +
`DES-REGRESSION-TEST-FILE` markers in the generated prompt.

DEFECT (GDP-4/GDP-5, the producing-tool routes-the-HOW rule): the marker
block `_build_prompt` assembles in `src/des/cli/dispatch.py` (~lines 159-171)
emits DES-VALIDATION / DES-PROJECT-ID / DES-MODE / DES-PHASE / DES-SLICE /
DES-WAVE, and -- only when `--lane` is given -- DES-LANE (+
DES-LANE-JUSTIFICATION for the bugfix lane). It NEVER emits a `DES-AT-KIND`
or `DES-REGRESSION-TEST-FILE` marker, and `des dispatch` has no `--at-kind` /
`--regression-test-file` option to request them.

Consequence: `carpaccio_intercept._parse_at_kind_from_prompt`
(carpaccio_intercept.py:307-331) reads `<!-- DES-AT-KIND : pytest-regression
-->` + `<!-- DES-REGRESSION-TEST-FILE : <path> -->` from the dispatch prompt
to run the carpaccio entry gate in pytest-regression mode. Because `des
dispatch` never emits them, a FEATURE slice whose acceptance test is a plain
pytest file (not gherkin) is BLOCKED at the carpaccio entry gate
(`no-scenarios-for-slice`), forcing the operator to hand-add the markers
instead of the producing tool (`des dispatch`) generating a gate-valid
dispatch by construction.

The fix (crafter's job, NOT implemented by this AT): `des dispatch` gains
`--at-kind {gherkin,pytest-regression}` (default `gherkin`, byte-identical
output for existing callers) + `--regression-test-file <path>`. When
`--at-kind pytest-regression` is given with `--regression-test-file`, the
generated prompt's marker block ALSO carries:

    <!-- DES-AT-KIND : pytest-regression -->
    <!-- DES-REGRESSION-TEST-FILE : <path> -->

Driving surface (Mandate 16 -- driving-port-only, default IN-PROCESS): the
REAL `des dispatch` CLI, driven in-process via
`tests/common/in_process_cli.run_cli_in_process` (the in-process analogue of
`python -m des.cli.__main__ dispatch ...`) against THIS checkout's real
`nWave/dispatch/atdd_pure.yaml` + `vendors.yaml` SSOT -- no mocking of the
prompt builder.

RED-for-right-reason (this docstring documents WHY, per the red-scaffolding
discipline): `--at-kind` is not a recognized `des dispatch` option today, so
argparse rejects the invocation (exit 2, usage error on stderr, EMPTY
stdout) rather than raising an uncaught exception. The positive assertions
below read the captured stdout and assert the marker text is present -- this
FAILS today because stdout is empty (argparse never reached prompt
assembly), a clear semantic `AssertionError` naming the absent marker, never
a crash/import/collection error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_dispatch(argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=_REPO_ROOT)


def _base_argv(*, project_id: str, slice_id: str) -> list[str]:
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        "--phase",
        "A_GREEN",
        "--repo-root",
        str(_REPO_ROOT),
    ]


@pytest.mark.parametrize(
    ("project_id", "slice_id", "regression_test_file"),
    [
        ("demo-feature", "slice-01", "tests/foo/test_bar.py"),
        ("another-feature", "slice-02", "tests/bugs/des/test_other_defect.py"),
    ],
)
def test_dispatch_emits_at_kind_and_regression_test_file_markers_for_pytest_regression(
    project_id: str, slice_id: str, regression_test_file: str
) -> None:
    """POSITIVE (the bug, active-RED today): a feature-lane dispatch (no
    `--lane`) declaring `--at-kind pytest-regression` +
    `--regression-test-file <path>` must emit BOTH the `DES-AT-KIND` and the
    `DES-REGRESSION-TEST-FILE` markers in the generated prompt, so the
    carpaccio-intercept hook can select its pytest-regression entry-gate path
    instead of rejecting a plain-pytest slice AT with
    `no-scenarios-for-slice`.
    """
    _exit_code, stdout, stderr = _run_dispatch(
        [
            *_base_argv(project_id=project_id, slice_id=slice_id),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_test_file,
        ]
    )

    assert "DES-AT-KIND : pytest-regression" in stdout, (
        "expected the generated `des dispatch` prompt to contain the "
        "'DES-AT-KIND : pytest-regression' marker so "
        "carpaccio_intercept._parse_at_kind_from_prompt can run the "
        f"pytest-regression entry-gate path -- got stdout={stdout!r} "
        f"(exit_code={_exit_code}, stderr={stderr!r}). `--at-kind` does not "
        "exist yet on `des dispatch` (src/des/cli/dispatch.py) -- see this "
        "test module's docstring for the fix direction."
    )
    assert f"DES-REGRESSION-TEST-FILE : {regression_test_file}" in stdout, (
        "expected the generated `des dispatch` prompt to contain the exact "
        f"'DES-REGRESSION-TEST-FILE : {regression_test_file}' marker (the "
        "same path passed via --regression-test-file, carried verbatim) -- "
        f"got stdout={stdout!r} (exit_code={_exit_code}, stderr={stderr!r})."
    )


@pytest.mark.parametrize(
    "regression_test_file",
    [
        "tests/foo/test_bar.py",
        "tests/bugs/des/test_a_totally_different_path.py",
        "tests/x/nested/dir/test_y.py",
    ],
)
def test_regression_test_file_marker_carries_the_exact_path_passed(
    regression_test_file: str,
) -> None:
    """POSITIVE (active-RED today): the emitted `DES-REGRESSION-TEST-FILE`
    marker must carry the EXACT path given via `--regression-test-file` --
    not a normalized, truncated, or reformatted variant. Parametrized over
    distinct paths (flat / dash-named / nested) to pin exact-echo, not
    substring-coincidence.
    """
    _exit_code, stdout, stderr = _run_dispatch(
        [
            *_base_argv(project_id="demo-feature", slice_id="slice-01"),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_test_file,
        ]
    )

    expected_marker = f"DES-REGRESSION-TEST-FILE : {regression_test_file}"
    assert expected_marker in stdout, (
        f"expected the exact marker {expected_marker!r} in the generated "
        f"prompt -- got stdout={stdout!r} (exit_code={_exit_code}, "
        f"stderr={stderr!r}). The marker is absent today because `des "
        "dispatch` has no `--at-kind`/`--regression-test-file` option yet."
    )


@pytest.mark.negative_at
def test_dispatch_does_not_emit_at_kind_marker_by_default() -> None:
    """NEGATIVE AT (control -- GREEN today and must stay GREEN after the
    fix): a default `des dispatch` invocation (no `--at-kind`, no `--lane`;
    plain feature-lane dispatch) must NEVER contain a `DES-AT-KIND` or
    `DES-REGRESSION-TEST-FILE` marker in its generated prompt -- the fix
    adds the markers ONLY when `--at-kind pytest-regression` is explicitly
    requested. The default (implicit `at_kind=gherkin`) must stay
    byte-identical to today's legacy marker block (DES-VALIDATION /
    DES-PROJECT-ID / DES-MODE / DES-PHASE / DES-SLICE / DES-WAVE [+ DES-LANE
    / DES-LANE-JUSTIFICATION when `--lane` is given]).
    """
    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(project_id="demo-feature", slice_id="slice-01")
    )

    assert exit_code == 0, (
        "a plain feature-lane `des dispatch` (no --at-kind) must succeed "
        f"today -- got exit_code={exit_code}, stderr={stderr!r}"
    )
    assert "DES-AT-KIND" not in stdout, (
        "a default dispatch (no --at-kind requested) must never emit a "
        f"DES-AT-KIND marker -- got stdout={stdout!r}"
    )
    assert "DES-REGRESSION-TEST-FILE" not in stdout, (
        "a default dispatch (no --regression-test-file requested) must "
        f"never emit a DES-REGRESSION-TEST-FILE marker -- got "
        f"stdout={stdout!r}"
    )
