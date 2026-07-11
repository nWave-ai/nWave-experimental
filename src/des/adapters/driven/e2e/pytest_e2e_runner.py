"""run_pytest_against_installed -- shared pytest-against-staged-prefix runner.

Feature `implement-language-adapter-facets`, slice-03 (feature-delta.md Slice
Plan row 3, components D3/D4). Extracted verbatim from
`des.cli.verify_environmental_e2e._run_e2e_against_installed` (DDD-02): ONE
implementation, shared by the CLI's own fallback path and by
`PythonEnvironmentalE2EAdapter.run_against_installed` (the registered-facet
routing path) -- no duplication (D4).

Real I/O: a real pytest subprocess against a real staged install prefix.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.runtime.interpreter import python_for


if TYPE_CHECKING:
    from pathlib import Path


def run_pytest_against_installed(
    e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
) -> None:
    """Run pytest on `e2e_path` with `PYTHONPATH=prefix`, writing JUnit XML."""
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(prefix),
        "HOME": str(work_dir),
    }
    subprocess.run(
        [
            python_for(None),
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
