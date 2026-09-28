"""Bounded subprocess helpers for the project's existing pytest commands.

This is deliberately not a test-runner abstraction.  It contains the shared
process-lifecycle mechanics used by the Python command surfaces that already
run pytest: interpreter selection, a bounded timeout, and process-group
cleanup.  Project-specific commands remain the authority for what to run.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
from typing import IO, TYPE_CHECKING, Any

from des.runtime.interpreter import python_for


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def run_timeout_seconds() -> float:
    """Return the bounded timeout for an existing test subprocess."""
    try:
        return float(os.environ.get("NWAVE_GATE_RUN_TIMEOUT", "2700"))
    except ValueError:
        return 2700.0


def pytest_interpreter(repo_root: Path | None = None) -> str:
    """Resolve a pytest-capable interpreter for an existing project command."""
    if repo_root is None:
        return python_for("pytest")
    return python_for("pytest", repo_root=repo_root)


def _reap_process_group(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


def _read_capture(handle: IO[bytes] | None, text: bool) -> str | bytes | None:
    if handle is None:
        return None
    handle.seek(0)
    raw = handle.read()
    return raw.decode(errors="replace") if text else raw


# Every keyword here is a `subprocess.run` keyword with `subprocess.run`
# semantics, and this module's own first line says it is "deliberately not a
# test-runner abstraction". Reaching five arguments means folding
# capture_output, text, stdin, stdout and stderr into one record, which IS the
# abstraction the module declines to be, and it would make a pre-commit hook
# script import a DES-internal type in order to run a subprocess. Grouping the
# three streams alone only reaches seven, so there is no cheap partial win.
def run_pytest_reaped(  # noqa: PLR0913 - see the note above
    argv: list[str],
    *,
    cwd: Path,
    timeout: float | None = None,
    capture_output: bool = False,
    text: bool = False,
    env: Mapping[str, str] | None = None,
    stdin: Any = subprocess.DEVNULL,
    stdout: IO[bytes] | None = None,
    stderr: IO[bytes] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one caller-selected pytest command and reap its complete process group.

    The caller retains authority for argv, cwd and declared environment. This
    lifecycle seam supplies an explicit stdin boundary, captures partial output
    on timeout when requested, and kills then drains the owned process group.
    """
    if capture_output and (stdout is not None or stderr is not None):
        raise ValueError("capture_output cannot be combined with stdout or stderr")
    out_handle: IO[bytes] | None = (
        tempfile.TemporaryFile() if capture_output else stdout
    )
    err_handle: IO[bytes] | None = (
        tempfile.TemporaryFile() if capture_output else stderr
    )
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=None if env is None else dict(env),
            stdin=stdin,
            stdout=out_handle,
            stderr=err_handle,
            start_new_session=True,
        )
        try:
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _reap_process_group(proc.pid)
                proc.wait()
                output = _read_capture(out_handle, text) if capture_output else None
                captured_stderr = (
                    _read_capture(err_handle, text) if capture_output else None
                )
                raise subprocess.TimeoutExpired(
                    argv,
                    timeout if timeout is not None else 0.0,
                    output=output,
                    stderr=captured_stderr,
                ) from None
        finally:
            _reap_process_group(proc.pid)
        return subprocess.CompletedProcess(
            argv,
            proc.returncode,
            _read_capture(out_handle, text) if capture_output else None,  # type: ignore[arg-type]
            _read_capture(err_handle, text) if capture_output else None,  # type: ignore[arg-type]
        )
    finally:
        for handle in (out_handle, err_handle) if capture_output else ():
            if handle is not None:
                handle.close()


__all__ = ["pytest_interpreter", "run_pytest_reaped", "run_timeout_seconds"]
