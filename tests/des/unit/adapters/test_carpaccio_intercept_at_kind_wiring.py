"""Regression: the PreToolUse carpaccio intercept honors the AT-kind of a dispatch.

Bug (`fix-carpaccio-intercept-honors-at-kind`): the intercept's real carpaccio
runner (`_real_carpaccio_runner._run`) spawns `des.cli.carpaccio_slice_gate` with only
`--feature-id`/`--entering-slice`/`--repo-root` -- NEVER `--at-kind`/`--regression-test-file`.
So a `/nw-bugfix` slice whose ATs are a plain-pytest regression file (the shipped
`at_kind=pytest-regression` gate mode) is FALSE-REJECTED at crafter dispatch
(`no-scenarios-for-slice`, exit 45), even though `des carpaccio-slice-gate --at-kind
pytest-regression --regression-test-file <f>` PASSES when called manually.

Approved fix (ADD-not-mutate, template-identical to the RC4-b `_real_readiness_runner`
`lane` closure already in the same file):
  * a `_parse_at_kind_from_prompt(prompt) -> (str, str | None)` parser + two markers
    (`DES-AT-KIND`, `DES-REGRESSION-TEST-FILE`); absent DES-AT-KIND => ("gherkin", None).
  * `_real_carpaccio_runner(project_root, at_kind="gherkin", regression_test_file=None)`
    closes over the extra args at BUILD time -> the `_run(feature_id, entering_slice)`
    Callable signature is UNCHANGED; byte-identical des_spawn when gherkin.
  * the dispatcher threads the parse into the builder (beside `_parse_lane_from_prompt`).

Markers (two, mirroring the DES-LANE pair to keep an embedded path unambiguous):
  <!-- DES-AT-KIND : pytest-regression -->
  <!-- DES-REGRESSION-TEST-FILE : tests/build/x/test_y.py -->

This regression test IS the bugfix's AT (single-slice `/nw-bugfix`, no DISTILL wave).
It drives the REAL production seams (`ci._parse_at_kind_from_prompt`,
`ci._real_carpaccio_runner`, `ci.evaluate_atdd_pure_dispatch`) -- no reimplementation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from des.adapters.drivers.hooks import carpaccio_intercept as ci


_REGRESSION_FILE = "tests/build/x/test_y.py"


def _spawn_args(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch des_spawn in the intercept module; return a dict recording positional args."""
    recorded: dict[str, tuple] = {}

    def fake_spawn(*args, **kwargs):
        recorded["args"] = args
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = '{"event": "CarpaccioSliceThin", "verdict": "cleared"}'
        return completed

    monkeypatch.setattr(ci, "des_spawn", fake_spawn)
    return recorded


def test_carpaccio_runner_threads_at_kind_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A carpaccio runner built WITH pytest-regression passes --at-kind / --regression-test-file.

    RED against current code: `_real_carpaccio_runner` accepts only `project_root`, so
    building it with `at_kind=`/`regression_test_file=` raises TypeError (missing kwarg).
    """
    recorded = _spawn_args(monkeypatch)
    runner = ci._real_carpaccio_runner(
        tmp_path,
        at_kind="pytest-regression",
        regression_test_file=_REGRESSION_FILE,
    )
    runner("synthetic-feature", "slice-01")
    args = list(recorded["args"])

    assert "--at-kind" in args and "pytest-regression" in args, (
        "a carpaccio runner built with at_kind='pytest-regression' must pass "
        f"`--at-kind pytest-regression` to the gate subprocess. des_spawn args={args}"
    )
    assert "--regression-test-file" in args and _REGRESSION_FILE in args, (
        "the runner must forward the regression-test file so the gate discovers the "
        f"pytest-regression AT instead of globbing for .feature scenarios. args={args}"
    )
    # Position lock: the at_kind args are spliced AFTER --repo-root, and each flag
    # is immediately followed by its value (the CLI's argv contract).
    assert args.index("--at-kind") > args.index("--repo-root"), (
        f"--at-kind must be spliced after --repo-root (CLI argv order). args={args}"
    )
    assert args[args.index("--at-kind") + 1] == "pytest-regression"
    assert args[args.index("--regression-test-file") + 1] == _REGRESSION_FILE


def test_carpaccio_runner_no_at_kind_is_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default carpaccio runner (gherkin) invokes the gate byte-identically -- no --at-kind.

    Zero-blast-radius lock (green before AND after the fix): a Gherkin dispatch stays
    exactly as today. If the fix ever leaked `--at-kind` onto the default path this fails.
    """
    recorded = _spawn_args(monkeypatch)
    runner = ci._real_carpaccio_runner(tmp_path)
    runner("synthetic-feature", "slice-01")
    args = list(recorded["args"])

    assert "--at-kind" not in args, (
        "the default (gherkin) carpaccio runner must invoke the gate byte-identically "
        f"-- no --at-kind arg (ADD-not-mutate). des_spawn args={args}"
    )
    assert "--regression-test-file" not in args, (
        f"the default runner must not pass --regression-test-file. args={args}"
    )


@pytest.mark.parametrize(
    "marker_block, expected",
    [
        pytest.param(
            f"<!-- DES-AT-KIND : pytest-regression -->\n"
            f"<!-- DES-REGRESSION-TEST-FILE : {_REGRESSION_FILE} -->\n",
            ("pytest-regression", _REGRESSION_FILE),
            id="spaced-markers",
        ),
        pytest.param(
            f"<!--DES-AT-KIND:pytest-regression-->\n"
            f"<!--DES-REGRESSION-TEST-FILE:{_REGRESSION_FILE}-->\n",
            ("pytest-regression", _REGRESSION_FILE),
            id="tight-whitespace-tolerance",
        ),
        pytest.param(
            "<!-- DES-MODE : atdd_pure -->\n<!-- DES-SLICE : slice-01 -->\n",
            ("gherkin", None),
            id="absent-defaults-to-gherkin-none",
        ),
    ],
)
def test_parse_at_kind_from_prompt(
    marker_block: str, expected: tuple[str, str | None]
) -> None:
    """`_parse_at_kind_from_prompt` extracts (at_kind, file); absent => (gherkin, None).

    RED against current code: `_parse_at_kind_from_prompt` does not exist yet
    (AttributeError on `ci._parse_at_kind_from_prompt`). Whitespace around the colon is
    tolerated exactly like `_parse_lane_from_prompt`.
    """
    prompt = "<!-- DES-MODE : atdd_pure -->\n" + marker_block
    assert ci._parse_at_kind_from_prompt(prompt) == expected


@pytest.mark.parametrize(
    "at_kind_markers, expected_at_kind, expected_file",
    [
        pytest.param(
            f"<!-- DES-AT-KIND : pytest-regression -->\n"
            f"<!-- DES-REGRESSION-TEST-FILE : {_REGRESSION_FILE} -->\n",
            "pytest-regression",
            _REGRESSION_FILE,
            id="markers-present-thread-pytest-regression",
        ),
        pytest.param("", "gherkin", None, id="markers-absent-thread-gherkin-none"),
    ],
)
def test_intercept_threads_at_kind_into_carpaccio_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    at_kind_markers: str,
    expected_at_kind: str,
    expected_file: str | None,
) -> None:
    """Dormant-seam lock: the intercept THREADS the parsed at_kind into the builder.

    The highest-value end-to-end assertion. The pieces are unit-tested above, but nothing
    pins the CONNECTION: if the `evaluate_atdd_pure_dispatch` line that feeds the parsed
    at_kind into `_real_carpaccio_runner` is missing/dropped, the unit tests stay green
    while a pytest-regression dispatch is still false-rejected (the dormant-seam class).

    RED against current code: the dispatcher builds `_real_carpaccio_runner(project_root)`
    with NO at_kind kwarg, so the capturing builder's default ('gherkin') is recorded even
    when the markers are present -> the `expected_at_kind == 'pytest-regression'` case
    fails. The markers-absent case is the regression pin (green before AND after).
    """
    captured: dict[str, object] = {}

    def _capturing_builder(project_root, at_kind="gherkin", regression_test_file=None):
        captured["at_kind"] = at_kind
        captured["regression_test_file"] = regression_test_file
        return lambda _fid, _slice: (0, '{"event": "CarpaccioSliceThin"}')

    monkeypatch.setattr(ci, "_real_carpaccio_runner", _capturing_builder)

    prompt = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        "<!-- DES-PROJECT-ID : synthetic-feature -->\n"
    ) + at_kind_markers
    try:
        ci.evaluate_atdd_pure_dispatch(
            prompt=prompt, feature_id="synthetic-feature", project_root=tmp_path
        )
    except Exception:
        # The carpaccio builder is called BEFORE the gate stack runs; a downstream
        # crash on the synthetic tmp tree does not unset the capture.
        pass

    assert captured.get("at_kind") == expected_at_kind, (
        "the intercept must thread the parsed DES-AT-KIND into the DEFAULT carpaccio "
        "runner builder -- if this stays 'gherkin' when markers are present, the "
        f"parse->builder connection was dropped (dormant seam). captured={captured}"
    )
    assert captured.get("regression_test_file") == expected_file, (
        f"the intercept must thread the regression-test file too. captured={captured}"
    )
