"""K4 camp2/camp3/camp4 diagnosis (2026-08-20): `probe_examiner_start_recipe`
failed deterministically with "supervisor did not restart the server within
30s" on three separate campaigns. Corpse evidence: `server.log` ends with
"supervisor: restarting at ..." and then nothing -- the restore+migrate
BLOCK never even reaches the point where it would print anything further.
Isolated reproduction (documented in the K4 lock-hunt report) proved the
exact mechanism: `_restart()` (embedded source inside
`prepare_examiner_fixture.supervisor_script`) ran its restore/migrate BLOCK
via a bare `subprocess.run(['bash', '-c', BLOCK], timeout=60)`. A SIGTERM
landing on the supervisor mid-restart unwinds through `_handle_sigterm`'s
`sys.exit(0)` (a `BaseException`), which `subprocess.run`'s own cleanup
answers with `Popen.kill()` -- SIGKILL to the DIRECT `bash` child ONLY. Any
grandchild BLOCK had already forked (`migrate`, most likely) survives as an
ORPHAN that still holds `hc.sqlite.lock`'s fd 9, inherited on fork BEFORE
the BLOCK's own `exec 9>&-` line ever runs -- the lock is held by the
*open file description*, shared across every process that inherited the
fd, not released just because the direct child died. Nothing is left alive
to ever release it, so the next restart's own `flock -x 9` (previously
unbounded) hung forever.

The fix gives `_restart()`'s spawned bash its own process group
(`start_new_session=True`) and kills the WHOLE group on any interruption
(`os.killpg`), so a SIGTERM takes every descendant down atomically -- never
just the group leader.

This test extracts the ACTUAL `_restart()` source `supervisor_script()`
renders -- never a hand-retyped reimplementation that could drift from
what really runs -- substitutes a Django-free BLOCK (acquire the lock,
then sleep well past the SIGTERM) so the test needs no real Django app,
and proves a third party can reacquire the lock immediately after the
SIGTERM.

Run: uv run pytest -q tests/scripts/analysis/test_k4_supervisor_restart_lock_orphan.py
"""

from __future__ import annotations

import re
import signal
import subprocess
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[3] / "scripts" / "analysis" / "k4"))

import prepare_examiner_fixture as pef


def _extract_restart_function_source(rendered: str) -> str:
    """Pull just `def _restart():` out of the generated supervisor
    script, up to the next top-level `def` -- the exact code under test,
    never a hand-retyped copy that could silently drift from production."""
    match = re.search(
        r"\ndef _restart\(\):.*?(?=\ndef _handle_sigterm)", rendered, re.S
    )
    assert match, (
        "supervisor_script() must define _restart() -- rendering shape changed"
    )
    return match.group(0)


def test_restart_process_group_cleanup_frees_an_orphaned_db_lock(tmp_path):
    rendered = pef.supervisor_script(port=8000, api_key="unused")
    restart_src = _extract_restart_function_source(rendered)

    lock_path = tmp_path / "hc.sqlite.lock"
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import os, signal, subprocess, sys, time\n"
        # `sleep 8` is deliberately NOT the last command -- a bare `bash -c
        # 'cmd; sleep N'` with sleep tail-position lets bash exec() straight
        # into sleep (same PID, no fork), which a direct-child SIGKILL would
        # then correctly reap even under the OLD, buggy code and mask the
        # defect. The real BLOCK never has migrate as its last command
        # either (`exec 9>&-` and `runserver` always follow) -- this
        # trailing `echo RELEASED` reproduces that same non-tail shape so
        # `sleep` is forced to fork as a genuine, orphan-able child.
        f"BLOCK = 'exec 9>{lock_path}; flock -x 9; echo ACQUIRED; sleep 8; echo RELEASED'\n"
        "\n"
        "def _handle_sigterm(signum, frame):\n"
        "    sys.exit(0)\n"
        "\n"
        "signal.signal(signal.SIGTERM, _handle_sigterm)\n"
        + restart_src
        + "\n_restart()\n"
    )

    proc = subprocess.Popen([sys.executable, str(driver)], cwd=tmp_path)
    try:
        time.sleep(1.5)  # let the substitute BLOCK acquire the lock, uncontended
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    # A third party must be able to reacquire the lock RIGHT AWAY -- if any
    # orphan from the interrupted restart still held it, this times out.
    result = subprocess.run(
        ["bash", "-c", f"exec 9>{lock_path}; flock -x -w 3 9 && echo FREE"],
        capture_output=True,
        text=True,
        timeout=6,
    )
    assert "FREE" in result.stdout, (
        "the DB lock is still held after _restart() was interrupted by "
        "SIGTERM -- an orphaned descendant of the killed restart survived "
        "the process-group cleanup and is still holding hc.sqlite.lock"
    )
