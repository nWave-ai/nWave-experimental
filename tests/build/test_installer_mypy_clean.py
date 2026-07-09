"""Build-tier quality-pin AT for issue #24 (ZERO DEFECTS installer mypy debt).

`scripts/install/install_utils.py` and `scripts/install/plugins/des_plugin.py`
carry pre-existing mypy type-debt despite the project's `[tool.mypy]
strict = true` config (pyproject.toml). ZERO DEFECTS: any file the project
type-checks must be mypy-clean, regardless of who introduced the debt or
when -- "pre-existing" is not an exemption.

This test RUNS mypy on the two files as a subprocess and asserts the REAL
result reports zero errors. RED today (HEAD carries ~20+ errors across the
two files -- see the assertion message for the live count); GREEN once the
crafter adds the missing type annotations.

`--explicit-package-bases` is REQUIRED: without it mypy hits a spurious
"base.py found twice under different module names" duplicate-module error
(an invocation artifact from `scripts/install/plugins/base.py` colliding
with another `base.py` on the implicit search path) that has nothing to do
with the real type-debt this test pins.

This is a subprocess spawn in TEST code, not `src/des/**` -- out of scope
for `test_no_inline_interpreter_spawn.py`'s ban (which targets `src/des`
only; the mypy binary is not a Python interpreter spawn either).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TARGET_FILES = [
    "scripts/install/install_utils.py",
    "scripts/install/plugins/des_plugin.py",
]


@pytest.mark.fast_gate
def test_installer_modules_are_mypy_clean() -> None:
    """Pins zero mypy errors on the two installer modules tracked by #24.

    Runs the real `mypy` CLI (no mock) against the project's own
    `[tool.mypy]` config and asserts on its actual stdout/exit code.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            *TARGET_FILES,
            "--explicit-package-bases",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    error_lines = [line for line in result.stdout.splitlines() if ": error:" in line]

    assert result.returncode == 0 and not error_lines, (
        "mypy reports type errors in installer modules that must be "
        "mypy-clean (ZERO DEFECTS, issue #24):\n  "
        + "\n  ".join(error_lines)
        + f"\n\nfull mypy output:\n{result.stdout}"
        + (f"\nstderr:\n{result.stderr}" if result.stderr else "")
    )
