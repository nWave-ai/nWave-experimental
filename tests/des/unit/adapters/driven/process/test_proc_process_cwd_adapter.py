"""Unit tests for ProcProcessCwdAdapter's degrade-LOUD contract.

Mirrors `test_git_commit_tree_path_adapter.py`'s shape: mocked/monkeypatched
edge cases for the degrade paths, plus one real end-to-end test (a REAL
subprocess with a known cwd, found via a REAL `/proc` scan) so the mocked
cases can't silently drift from what `/proc` actually looks like.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from des.adapters.driven.process.proc_process_cwd_adapter import (
    ProcProcessCwdAdapter,
)
from des.ports.driven_ports.process_cwd_probe_port import Indeterminate


def test_proc_root_absent_degrades_to_indeterminate() -> None:
    adapter = ProcProcessCwdAdapter()
    with patch(
        "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
        Path("/definitely-not-proc-on-this-host"),
    ):
        result = adapter.pids_with_cwd_under(Path("/tmp"))
    assert isinstance(result, Indeterminate)
    assert "/proc" in result.reason


class _ScopedProcRoot:
    """A real `/proc` view narrowed to exactly the given PID(s).

    This dev box runs dozens of concurrent, unrelated processes (other
    Claude Code agent sessions, `systemd --user`, `(sd-pam)`, ...) -- a full
    unscoped `/proc` scan is genuinely noisy ambient state, not a fixture
    the SUT's behavior should depend on. Every `os.stat`/`os.readlink` call
    the adapter makes still hits the REAL `/proc/<pid>` entry (this is not a
    mock of the syscalls), so the test still exercises the real mechanism --
    it just controls WHICH PIDs are offered as candidates, exactly the way a
    real, quieter host would.
    """

    def __init__(self, *pids: int) -> None:
        self._entries = [Path(f"/proc/{pid}") for pid in pids]

    def is_dir(self) -> bool:
        return True

    def iterdir(self):
        return iter(self._entries)


def test_no_candidate_processes_is_a_definitive_empty_tuple(tmp_path: Path) -> None:
    """An UNPOPULATED directory (no process cwd'd there) is a positive
    "checked, found nothing" -- an empty tuple, never Indeterminate."""
    adapter = ProcProcessCwdAdapter()
    with patch(
        "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
        _ScopedProcRoot(),
    ):
        result = adapter.pids_with_cwd_under(tmp_path)
    assert result == ()


def test_real_process_with_cwd_inside_target_is_found(tmp_path: Path) -> None:
    """No mocking of `os.stat`/`os.readlink`: spawn a REAL subprocess rooted
    at `tmp_path`, then confirm the real `/proc` scan finds it -- the
    walking-skeleton positive case. Scoped to just this PID (see
    `_ScopedProcRoot`) so ambient box noise cannot mask the assertion."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=tmp_path,
    )
    try:
        deadline = time.monotonic() + 5
        result = ()
        while time.monotonic() < deadline:
            adapter = ProcProcessCwdAdapter()
            with patch(
                "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
                _ScopedProcRoot(proc.pid),
            ):
                result = adapter.pids_with_cwd_under(tmp_path)
            if result:
                break
            time.sleep(0.1)
        assert not isinstance(result, Indeterminate)
        assert any(m.pid == proc.pid for m in result)
    finally:
        proc.kill()
        proc.wait()


def test_process_exits_mid_scan_is_silently_skipped_not_indeterminate(
    tmp_path: Path,
) -> None:
    """After the real process above exits, its cwd link disappears -- a
    benign race, never escalated to Indeterminate."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        cwd=tmp_path,
    )
    proc.wait()
    adapter = ProcProcessCwdAdapter()
    with patch(
        "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
        _ScopedProcRoot(proc.pid),
    ):
        result = adapter.pids_with_cwd_under(tmp_path)
    assert result == ()


def test_known_non_dumpable_session_daemon_is_excluded_not_escalated(
    tmp_path: Path,
) -> None:
    """`systemd --user` / `(sd-pam)` are structurally non-dumpable (systemd
    hardening) and permission-denied on `cwd` for every unprivileged reader,
    same-user or not. Measured on this project's own dev box: they are
    ALWAYS present and ALWAYS unreadable -- without this exclusion the guard
    would refuse unconditionally on any systemd-user-session host. A same-
    user PID with any OTHER comm must still escalate (covered by the test
    above) -- only this named, bounded pair is excluded."""
    adapter = ProcProcessCwdAdapter()
    fake_stat = type("_S", (), {"st_uid": os.getuid()})()

    with (
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
            _ScopedProcRoot(999998),
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.stat",
            return_value=fake_stat,
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.readlink",
            side_effect=PermissionError("denied"),
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter._comm",
            return_value="(sd-pam)",
        ),
    ):
        result = adapter.pids_with_cwd_under(tmp_path)
    assert result == ()


def test_unreadable_cwd_link_on_a_same_owner_pid_escalates_to_indeterminate(
    tmp_path: Path,
) -> None:
    """A permission-denied cwd link on a SAME-OS-user PID might be hiding
    the live process this probe exists to find -- GDP-8 arity corollary: it
    must reach the aggregate as Indeterminate, never be silently dropped
    from an otherwise-empty result."""
    adapter = ProcProcessCwdAdapter()
    fake_stat = type("_S", (), {"st_uid": os.getuid()})()

    with (
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
            _ScopedProcRoot(999999),
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.stat",
            return_value=fake_stat,
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.readlink",
            side_effect=PermissionError("denied"),
        ),
    ):
        result = adapter.pids_with_cwd_under(tmp_path)
    assert isinstance(result, Indeterminate)
    assert "999999" in result.reason


def test_other_owner_pid_with_unreadable_cwd_is_excluded_not_escalated(
    tmp_path: Path,
) -> None:
    """A DIFFERENT-OS-user PID cannot be our own lane's process -- excluded
    from the candidate set entirely, never escalated to Indeterminate. This
    is the empirically-required calibration: this dev box carries ~50
    root/system-owned PIDs whose cwd link is permission-denied on every
    scan; escalating on those would make the guard refuse unconditionally."""
    adapter = ProcProcessCwdAdapter()
    fake_stat = type("_S", (), {"st_uid": os.getuid() + 1})()

    with (
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter._PROC_ROOT",
            _ScopedProcRoot(1),
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.stat",
            return_value=fake_stat,
        ),
        patch(
            "des.adapters.driven.process.proc_process_cwd_adapter.os.readlink",
            side_effect=PermissionError("denied"),
        ),
    ):
        result = adapter.pids_with_cwd_under(tmp_path)
    assert result == ()
