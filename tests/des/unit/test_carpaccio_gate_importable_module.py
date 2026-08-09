"""F-11 regression: the carpaccio gate is an importable `des.cli.` module.

Friction-log F-11 (docs/analysis/atdd-pure-dogfooding-friction-2026-05-20.md).
The installed U1 PreToolUse hook resolved the carpaccio gate CLI via a
repo-layout-coupled `Path(__file__).resolve().parents[5]/scripts/cli/...`
path. In the INSTALLED layout (`~/.claude/lib/python/des/...`) that path
points at `~/.claude/lib/scripts/cli/carpaccio_slice_gate.py` -- which does
not exist, because `scripts/cli/` is not shipped to `~/.claude/`. The hook
rejected EVERY atdd_pure dispatch with `exit 2 "no gate output"`.

Approach A fix: the gate becomes an importable `des.cli.carpaccio_slice_gate`
module shipped with the `des` package, invokable layout-independently via
`python -m des.cli.carpaccio_slice_gate` -- exactly as U2 invokes
`python -m des.cli.verify_slice_commit_completeness`.

Layer: classic-TDD unit tests on the module move + the intercept path fix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from des.adapters.drivers.hooks import carpaccio_intercept


_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_carpaccio_gate_is_an_importable_des_cli_module() -> None:
    """The gate ships with the `des` package as `des.cli.carpaccio_slice_gate`.

    The import resolves -- the gate logic lives inside the shipped `des`
    package, not under the un-shipped `scripts/cli/` tree.
    """
    from des.cli import carpaccio_slice_gate as module

    assert callable(module.main)


def test_carpaccio_gate_runs_as_a_python_m_module() -> None:
    """`python -m des.cli.carpaccio_slice_gate` runs layout-independently.

    Invoked against a non-existent feature it must fail with the gate's own
    exit 1 + a structured JSON `event` -- proving the module entry point is
    reached, not an interpreter `No module named` error.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli.carpaccio_slice_gate",
            "--feature-id",
            "nonexistent-feature-f11-probe",
            "--entering-slice",
            "slice-01",
            "--repo-root",
            str(_REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # The module entry point was reached: a gate verdict, not an import error.
    assert "No module named" not in completed.stderr, completed.stderr
    assert completed.returncode == 1, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["event"] == "SlicePlanSectionMissing"


def test_intercept_resolves_gate_without_repo_relative_scripts_path() -> None:
    """`carpaccio_intercept` no longer depends on a `parents[N]/scripts/` path.

    The pre-F-11 intercept built `_CARPACCIO_CLI` from
    `Path(__file__).resolve().parents[5]/scripts/cli/...` -- a repo-layout
    coupling that breaks in the installed `~/.claude/lib/` layout. The fixed
    intercept invokes the gate as `python -m des.cli.carpaccio_slice_gate`,
    so no module-level `scripts`-relative path constant exists.
    """
    # The runner invokes the gate as an importable module, not a scripts path.
    assert carpaccio_intercept._CARPACCIO_GATE_MODULE == "des.cli.carpaccio_slice_gate"
    # No repo-relative scripts/cli path constant remains on the module.
    assert not hasattr(carpaccio_intercept, "_CARPACCIO_CLI")
    # The runner is built as a `project_root`-bound factory (so it can pass
    # `--repo-root`) -- not a bare module-level function.
    runner = carpaccio_intercept._real_carpaccio_runner(Path("/tmp"))
    assert callable(runner)
