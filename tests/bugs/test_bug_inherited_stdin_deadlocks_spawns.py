"""Regression properties for the shared subprocess boundary.

The retired refactor-swarm and per-slice commit adapters no longer justify
adapter-specific tests.  The live invariant is smaller: a child must never
inherit a potentially non-terminating stdin unless its caller explicitly
supplies stdin or input bytes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from des.runtime.spawn import spawn


@pytest.mark.negative_at
def test_spawn_boundary_never_passes_inherited_stdin_to_its_child(
    tmp_path: Path,
) -> None:
    """A child cannot inherit a descriptor that has data but never reaches EOF."""
    witness = tmp_path / "stdin.txt"
    child = tmp_path / "child.py"
    child.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(repr(sys.stdin.read()))\n",
        encoding="utf-8",
    )
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import sys\n"
        "from des.runtime.spawn import spawn\n"
        "raise SystemExit(spawn([sys.executable, sys.argv[1], sys.argv[2]], "
        "timeout=5).returncode)\n",
        encoding="utf-8",
    )
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"data without EOF")
    repo_root = Path(__file__).resolve().parents[2]
    child_env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    process = subprocess.Popen(
        [sys.executable, str(driver), str(child), str(witness)],
        stdin=read_fd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=child_env,
    )
    try:
        process.wait(timeout=8)
        completed = True
    except subprocess.TimeoutExpired:
        completed = False
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert completed, "spawn inherited a hostile stdin and the child blocked"
    assert process.returncode == 0
    assert witness.read_text(encoding="utf-8") == "''"


@pytest.mark.negative_at
def test_spawn_boundary_preserves_caller_supplied_input() -> None:
    """The DEVNULL default never displaces caller-owned input bytes."""
    completed = spawn(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
        timeout=10,
        input="caller-owned-bytes",
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "caller-owned-bytes"


@pytest.mark.negative_at
def test_spawn_boundary_preserves_explicit_caller_stdin(tmp_path: Path) -> None:
    """An explicit stdin stream is passed through byte-for-byte."""
    source = tmp_path / "stdin.txt"
    source.write_text("caller-chosen-stream", encoding="utf-8")

    with source.open("rb") as handle:
        completed = spawn(
            [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
            timeout=10,
            stdin=handle,
            capture_output=True,
            text=True,
        )

    assert completed.returncode == 0
    assert completed.stdout == "caller-chosen-stream"
