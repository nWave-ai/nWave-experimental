"""Regression: `--at-kind pytest-regression` is blind to pytest-bdd `scenarios()`
bindings -- the exact form DISTILL authors for gherkin ATs (#64).

Charter: docs/product/expectations/fix-pytest-regression-recognizes-pytest-bdd/
at-kind-recognizes-gherkin-bound-files.md

RCA (confirmed): `count_pytest_regression_ats`
(`src/des/cli/carpaccio_format.py:553-598`) AST-counts module-level
`def test_*` / `async def test_*` functions in `--regression-test-file`. A
valid pytest-bdd binding file (`from pytest_bdd import scenarios` +
`scenarios("some.feature")`) has ZERO literal `def test_*` lines -- pytest-bdd
registers its tests dynamically at collection time, invisible to a static AST
walk. Today the zero-count branch (:594-597) raises `GateError(2,
MalformedInput, "zero test_* functions found at module level ...")` -- a
false "your file is broken/empty" that sends the maintainer chasing a
non-existent authoring mistake instead of pointing them at `--at-kind
gherkin`. `count_pytest_regression_ats` is the ONE shared fix-site: every
`--at-kind pytest-regression` command surface (`des carpaccio-slice-gate`
via `carpaccio_format.check_carpaccio` -> `count_net_new_pytest_regression_ats`
-> `count_pytest_regression_ats`; `des record-at-review-verdict` via
`at_review_verdict._slice_at_derivation` -> the same function) calls it, so
fixing this one function fixes every surface -- confirmed by
`mcp__tsunami__callers_of` on `count_pytest_regression_ats`.

Driving port: Layer-3 subprocess CLI boundary, TWO real `des` command
surfaces sharing `--at-kind pytest-regression` (the charter's "do not assume
only one"):

  * `des record-at-review-verdict --verdict NEEDS_REVISION` -- the LIGHTEST
    seam: a NEEDS_REVISION verdict skips `_verify_feature_slice_exists` and
    writes nothing, so `main()` reaches `_slice_at_derivation` ->
    `count_pytest_regression_ats` with NO feature-delta / ledger setup at
    all (`src/des/cli/at_review_verdict.py:565-591`).
  * `des carpaccio-slice-gate` -- the charter's PRIMARY named surface. Needs
    a minimal `Wave: DISCUSS / [REF] Slice Plan` feature-delta (one
    `slice-01` row, no
    `.feature` files so `scenarios=[]` and the mixed-mode guard never
    fires). `check_carpaccio` calls `count_net_new_pytest_regression_ats` ->
    `count_pytest_regression_ats` BEFORE `check_at_review` ever runs, so the
    two malformed fixtures (pytest-bdd, genuinely-empty) fail/pass this
    surface's assertion purely on the AST-count recognition, independent of
    any AT-review-ledger state. The genuine-pytest-regression fixture is
    only checked here for the NEGATIVE misclassification guard (never
    redirected to gherkin) -- its exit code is intentionally NOT asserted
    on this surface, since a missing `ATReviewVerdict` ledger record (an
    orthogonal, expected precondition of this gate) can legitimately
    reject it for a DIFFERENT, unrelated reason.

Fail-for-right-reason discipline: every fixture-1 assertion below fails
TODAY because the real `MalformedInput: zero test_* functions ...` message
is genuinely emitted by the real validator -- a business-verdict mismatch,
never an argparse/collection/import error. No real `pytest_bdd` package
import ever happens (the validator only `ast.parse`s the file); this suite
needs no `pytest_bdd` dependency.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_module_in_process


def _repo_root() -> Path:
    """`tests/bugs/des/<this file>` is 2 directories under the repo root."""
    return Path(__file__).resolve().parents[2]


def _env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH so `des.*` is importable in the
    subprocess; `NWAVE_FRESHNESS=skip` opts out of the unrelated startup
    freshness gate (this harness runs with `cwd=<tmp_path>`, a self-
    contained fixture project with no `.git/`).
    """
    env = dict(os.environ)
    src = str(_repo_root() / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


_FEATURE_ID = "fixture-at-kind-64"
_SLICE_ID = "slice-01"

_PYTEST_BDD_BODY = 'from pytest_bdd import scenarios\n\nscenarios("checkout.feature")\n'
_EMPTY_BODY = "# nothing here -- no scenarios() call, no test_* function\n"
_REAL_REGRESSION_BODY = "def test_something():\n    assert 1 == 1\n"

_MALFORMED_ZERO_TEST_MESSAGE = "zero test_* functions"
#: Substrings any of which the fix is free to emit when it recognizes a
#: pytest-bdd gherkin-bound file -- loosely coordinated with the crafter.
_GHERKIN_HINTS = ("gherkin", "pytest-bdd", "scenarios", "--at-kind gherkin")


# ---------------------------------------------------------------------------
# Surface 1 -- `des record-at-review-verdict --verdict NEEDS_REVISION`: the
# lightest seam onto `_slice_at_derivation` -> `count_pytest_regression_ats`.
# ---------------------------------------------------------------------------


def _run_record_at_review_verdict(
    repo_root: Path, regression_file: str
) -> tuple[int, str]:
    exit_code, out, err = run_module_in_process(
        *[
            "des",
            "record-at-review-verdict",
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--verdict",
            "NEEDS_REVISION",
            "--reviewer-agent-id",
            "quinn-regression-test",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_file,
            "--repo-root",
            str(repo_root),
        ],
        env=_env(),
        cwd=repo_root,
    )
    return exit_code, (out + err)


# ---------------------------------------------------------------------------
# Surface 2 -- `des carpaccio-slice-gate`: the charter's primary named
# surface. Needs a minimal `[REF] Slice Plan` feature-delta.
# ---------------------------------------------------------------------------


def _write_minimal_slice_plan(repo_root: Path) -> None:
    feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature-delta.md").write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {_SLICE_ID} | fixture slice for AT-kind regression #64 | pending | | |\n",
        encoding="utf-8",
    )


def _run_carpaccio_slice_gate(repo_root: Path, regression_file: str) -> tuple[int, str]:
    _write_minimal_slice_plan(repo_root)
    exit_code, out, err = run_module_in_process(
        *[
            "des",
            "carpaccio-slice-gate",
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _SLICE_ID,
            "--repo-root",
            str(repo_root),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_file,
        ],
        env=_env(),
        cwd=repo_root,
    )
    return exit_code, (out + err)


_RunSurface = Callable[[Path, str], tuple[int, str]]

_SURFACES: list[tuple[str, _RunSurface]] = [
    ("record-at-review-verdict", _run_record_at_review_verdict),
    ("carpaccio-slice-gate", _run_carpaccio_slice_gate),
]


# ---------------------------------------------------------------------------
# Oracle 1 (POSITIVE + NEGATIVE) -- the pytest-bdd binding fixture must be
# recognized as gherkin-bound, never "zero test_* functions". ACTIVE-RED at
# HEAD on both surfaces.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("surface_name, run_surface", _SURFACES)
def test_pytest_bdd_binding_file_is_recognized_not_misreported_empty(
    tmp_path: Path, surface_name: str, run_surface: _RunSurface
) -> None:
    fixture = tmp_path / "test_checkout_steps.py"
    fixture.write_text(_PYTEST_BDD_BODY, encoding="utf-8")

    exit_code, output = run_surface(tmp_path, fixture.name)
    lower_output = output.lower()

    assert _MALFORMED_ZERO_TEST_MESSAGE not in lower_output, (
        f"[{surface_name}] a pytest-bdd scenarios()-binding file "
        f"({fixture.name}) was mis-reported as {_MALFORMED_ZERO_TEST_MESSAGE!r} "
        f"-- this is a VALID gherkin-bound AT file (pytest-bdd registers its "
        f"tests dynamically), not a broken/empty one. Full output:\n{output}"
    )
    assert any(hint in lower_output for hint in _GHERKIN_HINTS), (
        f"[{surface_name}] a pytest-bdd scenarios()-binding file must be "
        f"recognized as gherkin/pytest-bdd-bound and redirect the maintainer "
        f"to --at-kind gherkin -- none of {_GHERKIN_HINTS!r} appeared in the "
        f"output:\n{output}"
    )
    assert exit_code != 0, (
        f"[{surface_name}] a --at-kind pytest-regression file that is "
        f"actually gherkin-bound must still be REJECTED (redirect to "
        f"--at-kind gherkin), never a silent exit 0 -- got exit_code=0, "
        f"output:\n{output}"
    )


# ---------------------------------------------------------------------------
# Oracle 2 (NEGATIVE, over-correction guard) -- a genuinely empty/malformed
# file (no scenarios() call, no test_* function) must stay rejected, never
# blanket-accepted as gherkin.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface_name, run_surface", _SURFACES)
def test_genuinely_empty_file_stays_rejected_not_blanket_accepted_as_gherkin(
    tmp_path: Path, surface_name: str, run_surface: _RunSurface
) -> None:
    fixture = tmp_path / "test_empty.py"
    fixture.write_text(_EMPTY_BODY, encoding="utf-8")

    exit_code, output = run_surface(tmp_path, fixture.name)
    lower_output = output.lower()

    assert exit_code != 0, (
        f"[{surface_name}] a genuinely empty/malformed regression-test file "
        f"(no scenarios() call, no test_* function) must still be REJECTED "
        f"-- the fix must NOT blanket-accept every zero-test_*-function file "
        f"as gherkin; got exit_code=0, output:\n{output}"
    )
    assert "scenarios" not in lower_output and "pytest-bdd" not in lower_output, (
        f"[{surface_name}] a genuinely empty file carries no "
        f"pytest_bdd.scenarios() call -- it must never be misreported as "
        f"gherkin/pytest-bdd-bound; output:\n{output}"
    )


# ---------------------------------------------------------------------------
# Oracle 3 (NEGATIVE, misclassification guard) -- a genuine pytest-regression
# file (real def test_* functions, no pytest-bdd import) must never be
# redirected/misclassified as gherkin.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface_name, run_surface", _SURFACES)
def test_real_pytest_regression_file_is_not_redirected_to_gherkin(
    tmp_path: Path, surface_name: str, run_surface: _RunSurface
) -> None:
    fixture = tmp_path / "test_real_regression.py"
    fixture.write_text(_REAL_REGRESSION_BODY, encoding="utf-8")

    exit_code, output = run_surface(tmp_path, fixture.name)
    lower_output = output.lower()

    assert not any(hint in lower_output for hint in _GHERKIN_HINTS), (
        f"[{surface_name}] a genuine pytest-regression file (real "
        f"def test_* functions, no pytest-bdd import) must NEVER be "
        f"redirected/misclassified as gherkin-bound; output:\n{output}"
    )
    if surface_name == "record-at-review-verdict":
        # This surface's NEEDS_REVISION path has NO other precondition (no
        # ledger read, no feature-delta needed) -- a genuine regression file
        # must validate cleanly end to end (exit 0), unaffected by the fix.
        assert exit_code == 0, (
            f"[{surface_name}] a genuine pytest-regression fixture must be "
            f"accepted/validated normally -- got exit_code={exit_code}, "
            f"output:\n{output}"
        )
