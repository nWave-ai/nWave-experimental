"""run_vitest_against_installed -- shared vitest-against-staged-prefix runner.

Feature `implement-language-adapter-facets`, slice-04 (feature-delta.md Slice
Plan row 4, component D8). The TS mirror of `pytest_e2e_runner.py`'s
`run_pytest_against_installed` (D3/D4). `vitest` is resolved via the SHARED
`resolve_tool` discovery scale (`VITEST_KNOWN_LOCATIONS`, the same scale
`VitestContractGateAdapter`/`run_vitest_scope` already use) -- never assumed
on a fixed PATH.

Real I/O: a real vitest subprocess against a real staged install prefix,
invoked with `run --reporter=junit --outputFile=<junit_path>` -- the ONE
mechanism by which a per-call-varying `junit_path` can reach a real vitest
run (no static `vitest.config.ts` reporter path is viable).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.adapters.driven.runner.vitest_runner import (
    VITEST_INSTALL_HINT,
    VITEST_KNOWN_LOCATIONS,
)
from des.ports.test_runner_port import RunnerAdapterUnavailable


if TYPE_CHECKING:
    from pathlib import Path


def run_vitest_against_installed(
    e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
) -> None:
    """Run vitest on `e2e_path` against the staged `prefix`, writing JUnit XML.

    Raises `RunnerAdapterUnavailable` when `vitest` cannot be resolved via
    the shared discovery scale (the LOUD INDETERMINATE channel, never a
    silent pass).
    """
    resolution = resolve_tool(
        "vitest",
        VITEST_KNOWN_LOCATIONS,
        base_dir=work_dir,
        install_hint=VITEST_INSTALL_HINT,
    )
    if resolution.path is None:
        raise RunnerAdapterUnavailable("vitest", reason=resolution.remediation)
    env = {
        "PATH": "/usr/bin:/bin",
        "NODE_PATH": str(prefix),
        "HOME": str(work_dir),
    }
    subprocess.run(
        [
            resolution.path,
            "run",
            "--reporter=junit",
            f"--outputFile={junit_path}",
            str(e2e_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(work_dir),
    )


__all__ = ["run_vitest_against_installed"]
