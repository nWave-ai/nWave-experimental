"""run_pytest_against_installed -- shared pytest-against-staged-prefix runner.

Extracted from `des.cli.verify_environmental_e2e._run_e2e_against_installed`:
the CLI's one real Python E2E execution path.

Real I/O: a real pytest subprocess against a real staged install prefix.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.runtime.test_execution import pytest_interpreter


if TYPE_CHECKING:
    from pathlib import Path


def run_pytest_against_installed(
    e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
) -> None:
    """Run pytest on `e2e_path` with `PYTHONPATH=prefix`, writing JUnit XML.

    The interpreter is resolved through ``pytest_interpreter()`` -- the
    allowlisted pytest run-facet boundary (gate-layer-test-runner-genericity
    slice-01: the python-hardcode lives behind the runner-adapter boundary,
    never an inline ``python_for`` in gate/adapter logic). The child runs
    ``-m pytest`` against the staged install prefix, so a pytest-capable
    interpreter is the genuine requirement -- an interpreter that cannot
    import pytest is refused at the boundary (F-21) rather than spawned and
    failing one frame later.
    """
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(prefix),
        "HOME": str(work_dir),
    }
    subprocess.run(
        [
            pytest_interpreter(),
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--override-ini=addopts=",
            "--rootdir",
            str(work_dir),
            str(e2e_path),
            f"--junit-xml={junit_path}",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(work_dir),
    )


__all__ = ["run_pytest_against_installed"]
