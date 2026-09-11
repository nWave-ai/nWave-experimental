"""Public lifecycle probe for the reaped pytest subprocess boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from des.runtime.test_execution import run_pytest_reaped


def test_timeout_retains_partial_output_and_reaps_the_spawned_group(
    tmp_path: Path,
) -> None:
    child_pid = tmp_path / "child.pid"
    script = tmp_path / "slow.py"
    script.write_text(
        "import pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"pathlib.Path({str(child_pid)!r}).write_text(str(child.pid))\n"
        "print('partial-output', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        run_pytest_reaped(
            [sys.executable, str(script)],
            cwd=tmp_path,
            timeout=0.2,
            capture_output=True,
            text=True,
        )
    assert "partial-output" in raised.value.output
    pid = int(child_pid.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("a descendant survived the reaped timeout boundary")
