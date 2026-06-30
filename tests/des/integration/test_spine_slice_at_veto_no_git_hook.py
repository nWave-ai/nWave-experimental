"""AT-A5 (slice-04, DDD-5, Principle 13 self-application): the spine genuinely RUNS
the entering slice's ATs at commit-time and VETOES on RED with git test-hooks ABSENT.

Integration tier (git subprocess + temp repo, pre-push marker -- NOT arch-tier).
The directive's "be CERTAIN" warning: removing the git pre-push net before proving
the spine genuinely RUNS the tests (not merely collects) is the silent-hole risk.
This probe answers "what happens if the environment lies (no git test-hook
installed)?" by exercising the no-git-hook case with a genuinely RED slice AT and
asserting the spine slice executor VETOES.

DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the REAL in-tree executor
``python -m des.cli.run_slice_ats --repo-root <temp> --entering-slice <s>`` over a
temp git repo that has NO git test-hook installed (a bare ``git init``, no
pre-commit). observable = the process EXIT CODE (the veto: != 0 for a RED slice).

This is a GENUINE RUN test, not collect-only: the planted slice AT is RED (its
``then`` asserts a false statement), so a collect-only walk would PASS -- only a
real RUN can produce the veto. That distinction is the whole point of CRITICAL-1.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD ``des.cli.run_slice_ats`` does not
exist (``__main__.py`` registers no ``run-slice-ats`` row), so the subprocess
exits non-zero on module-absence -- which is NOT the same observable as "the spine
RAN the RED AT and vetoed". The assertion distinguishes them: it requires the
verdict JSON to name FAIL (the genuine veto), not merely a non-zero exit. At HEAD
no such JSON is emitted -> semantic AssertionError. GREEN once DELIVER ships the
executor that genuinely RUNS the RED slice AT and emits the FAIL verdict.
"""

from __future__ import annotations

# des:allow-module-form: this suite drives the registered `run-slice-ats`
# subcommand via `python -m des.cli.run_slice_ats` as its hermetic Layer-3 SUT
# (the in-tree executor, deliberately NOT the PATH binary) -- P3-sanctioned per
# the rescoped single-entry-point migration gate
# (docs/feature/single-entry-point/feature-delta.md slice-04, AT-07).
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("git_hooks")]

REPO_ROOT = Path(__file__).resolve().parents[3]

_EXECUTOR_MODULE = "des.cli.run_slice_ats"
_ENTERING_SLICE = "slice-probe"


def _plant_red_slice_at(repo: Path) -> None:
    """Plant a REAL RED ``@<slice>`` acceptance test (its ``then`` asserts false).

    A collect-only walk would PASS this; only a genuine RUN produces the veto --
    the CRITICAL-1 distinction.
    """
    slug = _ENTERING_SLICE.replace("-", "_")
    slice_dir = repo / "tests" / slug
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "__init__.py").write_text("", encoding="utf-8")
    (slice_dir / f"{slug}.feature").write_text(
        f"@feature-probe @{_ENTERING_SLICE}\n"
        "Feature: planted probe slice\n\n"
        f"  @{_ENTERING_SLICE}\n"
        "  Scenario: the planted slice behaves\n"
        "    Given a planted slice precondition\n"
        "    When the planted slice acts\n"
        "    Then the planted slice outcome holds\n",
        encoding="utf-8",
    )
    (slice_dir / f"test_{slug}.py").write_text(
        "from pytest_bdd import given, when, then, scenarios\n\n"
        f'scenarios("{slug}.feature")\n\n\n'
        '@given("a planted slice precondition")\n'
        "def _given():\n    pass\n\n\n"
        '@when("the planted slice acts")\n'
        "def _when():\n    pass\n\n\n"
        '@then("the planted slice outcome holds")\n'
        "def _then():\n    assert 0 == 1\n",
        encoding="utf-8",
    )


def _verdict_json(output: str) -> dict[str, object]:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and "verdict" in stripped:
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue
    return {}


def test_spine_vetoes_red_slice_at_with_no_git_hook(tmp_path: Path) -> None:
    """A RED slice AT at commit-time is genuinely RUN and VETOED with no git hook."""
    repo = tmp_path / "target"
    repo.mkdir()
    # A bare git repo with NO git test-hook installed -- the no-git-hook case.
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8"
    )
    assert (
        not (repo / ".git" / "hooks" / "pre-commit").exists()
        or not (repo / ".git" / "hooks" / "pre-commit")
        .read_text(encoding="utf-8")
        .strip()
    ), "the temp repo must have no active git test-hook"

    _plant_red_slice_at(repo)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            _EXECUTOR_MODULE,
            "--repo-root",
            str(repo),
            "--entering-slice",
            _ENTERING_SLICE,
        ],
        capture_output=True,
        text=True,
        cwd=repo,
        timeout=180,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    output = completed.stdout + completed.stderr

    # The genuine veto: the executor RAN the RED slice AT and reports FAIL.
    # A collect-only walk would have PASSED; a module-absent exit is non-zero but
    # emits no FAIL verdict -- the JSON discriminates the genuine RUN-veto from
    # mere absence (active-RED at HEAD).
    assert completed.returncode == 1, (
        "expected the spine slice executor to VETO the RED slice AT (exit 1) with "
        f"no git test-hook present; got exit {completed.returncode}. "
        f"stdout/stderr:\n{output}"
    )
    assert _verdict_json(output).get("verdict") == "FAIL", (
        "expected the verdict JSON to name FAIL -- proving the spine genuinely RAN "
        "the RED AT and vetoed (not a collect-only pass, not a bare module-absent "
        f"exit); got {_verdict_json(output)!r}. stdout/stderr:\n{output}"
    )
