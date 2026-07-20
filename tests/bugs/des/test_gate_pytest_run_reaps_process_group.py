"""Regression: the gate's pytest RUN legs must reap the WHOLE process group.

Bug (bugfix-feature-end-postgres-leak): ``des feature-end``'s whole-tree
contract-gate leg shells pytest as a subprocess. When the TARGET repo's own
conftest spawns a durable daemon fixture (a pgserver/postgres cluster, redis,
docker), that daemon is a GRANDCHILD of the gate. The pre-fix spawn used a plain
``subprocess.run`` with no process group, so:

* on TIMEOUT, ``subprocess.run`` SIGKILLs only the DIRECT pytest child -- the
  postgres grandchild reparents to init and orphans (still running 20+ min after
  the gate returned, from earlier retries);
* even on a NORMAL exit, a session-scoped fixture that failed to tear its daemon
  down leaves it orphaned -- ``atexit``/finalizers cannot help under SIGKILL, so
  ONLY the supervisor (the gate) can guarantee the reap.

The fix: spawn pytest as a session/group leader (``start_new_session=True``) and
signal the WHOLE group on exit -- timeout, PASS, or FAIL -- so no grandchild
survives the leg. These tests model the grandchild with a plain python sleeper
(target-machine-agnostic: only python, no ``sleep`` binary, no postgres).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from des.adapters.driven.runner.pytest_runner import run_pytest_reaped


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


# A "pytest child" that spawns a long-lived grandchild (the stand-in for the
# target's postgres cluster), prints its pid, then behaves per the scenario.
_CHILD_SPAWNS_GRANDCHILD = (
    "import subprocess, sys, time;"
    "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)']);"
    "print(gc.pid, flush=True);"
    "time.sleep(float(sys.argv[1]))"
)


def _grandchild_pid_from(stdout: str) -> int:
    return int(stdout.strip().splitlines()[0])


def test_reaped_run_kills_orphaned_grandchild_on_timeout(tmp_path):
    """On timeout the whole group dies -- the grandchild does NOT orphan."""
    argv = [sys.executable, "-c", _CHILD_SPAWNS_GRANDCHILD, "300"]  # child sleeps long
    with pytest.raises(subprocess.TimeoutExpired) as excinfo:
        run_pytest_reaped(argv, cwd=tmp_path, timeout=3, capture_output=True, text=True)
    stdout = excinfo.value.stdout
    output = stdout.decode() if isinstance(stdout, bytes) else (stdout or "")
    gc_pid = _grandchild_pid_from(output)
    assert _wait_dead(gc_pid), (
        f"grandchild {gc_pid} still alive after the timed-out run returned -- "
        "the process group was not reaped (postgres would orphan here)"
    )


def test_reaped_run_kills_lingering_grandchild_on_normal_exit(tmp_path):
    """Even when the child exits 0, a lingering grandchild is reaped by the group."""
    argv = [sys.executable, "-c", _CHILD_SPAWNS_GRANDCHILD, "0.2"]  # child exits fast
    completed = run_pytest_reaped(
        argv, cwd=tmp_path, timeout=30, capture_output=True, text=True
    )
    assert completed.returncode == 0
    gc_pid = _grandchild_pid_from(completed.stdout)
    assert _wait_dead(gc_pid), (
        f"grandchild {gc_pid} survived a normal (exit-0) run -- a session-scoped "
        "daemon fixture that failed to tear down would leak past the gate"
    )
