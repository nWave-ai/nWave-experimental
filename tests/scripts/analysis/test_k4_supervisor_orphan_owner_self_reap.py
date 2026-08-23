"""K4 camp3 diagnosis (2026-08-20): a live-box audit found a `k4-supervisor.py`
started by an EARLIER, unrelated campaign (spawned ~12:43) still alive and
serving ~4 HOURS later (~16:30), `setsid`-detached, reparented to init, cwd
still inside that campaign's own workspace. `prepare_examiner_fixture.
_stop_supervisor_locked` (the ONE function every `stop_supervisor()` call
and `probe_examiner_start_recipe`'s own `finally` route through) never ran
for this supervisor -- the owning preflight process died WITHOUT unwinding
its `finally` block: `earlyoom` SIGKILL under multi-camp memory pressure, a
hard Ctrl-C, or any other ungraceful crash all bypass Python's own `finally`
the exact same way SIGKILL bypasses everything. `setsid`-detachment -- the
very property that lets this supervisor survive its LAUNCHING Bash tool
call (see `supervisor_script`'s own top-level docstring) -- also means the
kernel reparents it to init the instant its real parent is gone: nothing
with a live PID is left that could ever call `stop_supervisor` a second
time.

Isolated reproduction of the SAME fresh, uncontended box (2026-08-20, lane
probelive) proved `probe_examiner_start_recipe`'s own restart mechanism
(the SIGKILL-mid-restart hang commit `732023735` fixed) no longer hangs at
all -- two consecutive clean full-preflight runs, `start recipe: proven`,
teardown clean, zero leaked processes. The camp3 orphan is a SEPARATE
defect: not a hang IN the supervisor, but the supervisor OUTLIVING every
process that could ever ask it to stop.

The fix: `start_supervisor` now captures `owner_pid` (`os.getpid()` of the
process calling it -- the SAME process that will run `stop_supervisor` in
its own `finally` on the happy path) and `supervisor_script` embeds it as
`OWNER_PID`. The poll loop checks `_owner_alive()` every `POLL_SECONDS`
BEFORE any of its other health work; an owner that stops existing, by ANY
means, is treated exactly like an explicit SIGTERM -- same `_shutdown()`
call, same server teardown, no second, divergent path a future incident
could find diverges from the first.

This test extracts the ACTUAL rendered `supervisor_script()` source --
never a hand-retyped reimplementation that could drift from what really
runs -- substitutes a trivial, Django-free BLOCK (background a `sleep`,
record its PID) so the test needs no real Django app, points OWNER_PID at
a throwaway dummy process this test controls, kills that dummy WITHOUT
ever sending the supervisor a signal directly, and proves: (1) the
supervisor exits on its own within a few poll cycles: (2) its managed
"server" child is torn down with it, never leaked; (3) `supervisor.log`
names the reason, honestly, per GDP-3.

Run: uv run pytest -q tests/scripts/analysis/test_k4_supervisor_orphan_owner_self_reap.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[3] / "scripts" / "analysis" / "k4"))

import prepare_examiner_fixture as pef


def _rendered_with_fake_block(*, port: int, owner_pid: int) -> str:
    """The REAL `supervisor_script()` output, with only the `BLOCK`
    assignment swapped for a Django-free stand-in that backgrounds a
    `sleep` (the fake managed "server") and records its PID to
    `SERVER_PID_FILE_NAME` -- everything else (`_owner_alive`, `_shutdown`,
    `_run`'s poll loop) is the UNMODIFIED production source under test."""
    rendered = pef.supervisor_script(port=port, api_key="unused", owner_pid=owner_pid)
    fake_block = f"sleep 100 & echo $! > {pef.SERVER_PID_FILE_NAME}\n"
    # `repl` is a CALLABLE, not a literal string: `re.sub`/`re.subn` treat a
    # string `repl` as its own mini-template and reinterpret backslash
    # escapes (`\n`, `\g<...>`, ...) in it -- `repr(fake_block)` already
    # contains an escaped `\n` for the block's own trailing newline, which
    # `re` would silently unescape back into a REAL newline, corrupting the
    # single-line `BLOCK = '...'` assignment into an unterminated string
    # literal. A function return value is inserted verbatim, no reinterpretation.
    new_rendered, count = re.subn(
        r"^BLOCK = .*\n",
        lambda _match: f"BLOCK = {fake_block!r}\n",
        rendered,
        count=1,
        flags=re.M,
    )
    assert count == 1, (
        "supervisor_script() must define BLOCK -- rendering shape changed"
    )
    return new_rendered


def test_supervisor_self_terminates_when_its_owner_process_dies(tmp_path):
    # A throwaway dummy process stands in for the real K4 preflight
    # campaign process -- this test kills IT, never the supervisor, to
    # prove the supervisor notices on its own.
    owner_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"]
    )
    supervisor_proc: subprocess.Popen | None = None
    try:
        port = pef.free_port()
        rendered = _rendered_with_fake_block(port=port, owner_pid=owner_proc.pid)
        script_path = tmp_path / "k4-supervisor.py"
        script_path.write_text(rendered, encoding="utf-8")

        supervisor_proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        server_pid_file = tmp_path / pef.SERVER_PID_FILE_NAME
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not server_pid_file.is_file():
            time.sleep(0.2)
        assert server_pid_file.is_file(), (
            "the supervisor's own first _restart() never wrote "
            f"{pef.SERVER_PID_FILE_NAME} -- fake BLOCK substitution broke "
            "before this test could even set up its scenario"
        )
        managed_pid = int(server_pid_file.read_text(encoding="utf-8").strip())
        os.kill(managed_pid, 0)  # sanity: the fake managed server is really up

        owner_proc.kill()
        owner_proc.wait(timeout=5)

        # The supervisor must notice the owner is gone within a few
        # POLL_SECONDS=2 cycles and exit on its own -- no signal sent to it.
        supervisor_proc.wait(timeout=15)
        assert supervisor_proc.returncode == 0, (
            "the supervisor must exit via its own sys.exit(0) self-reap "
            f"path, not crash -- got returncode {supervisor_proc.returncode}"
        )

        # Its managed "server" child must be torn down too, never leaked.
        deadline = time.monotonic() + 5
        managed_gone = False
        while time.monotonic() < deadline:
            try:
                os.kill(managed_pid, 0)
            except ProcessLookupError:
                managed_gone = True
                break
            time.sleep(0.2)
        assert managed_gone, (
            f"managed server pid {managed_pid} survived the supervisor's "
            "own self-termination -- an orphan was left behind"
        )

        supervisor_log = (tmp_path / pef.SUPERVISOR_LOG_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert "owner pid" in supervisor_log and "gone" in supervisor_log, (
            "the self-reap path must name WHY it terminated in "
            f"{pef.SUPERVISOR_LOG_FILE_NAME}, not exit silently: "
            f"{supervisor_log!r}"
        )
    finally:
        if supervisor_proc is not None and supervisor_proc.poll() is None:
            supervisor_proc.kill()
            supervisor_proc.wait(timeout=5)
        if owner_proc.poll() is None:
            owner_proc.kill()
            owner_proc.wait(timeout=5)


def test_owner_alive_check_never_fires_while_the_owner_is_a_live_pid(tmp_path):
    """Negative control, same discipline the sibling lock-orphan test uses:
    a supervisor whose OWNER_PID stays alive for the whole test must never
    self-terminate -- proving the new poll-loop branch discriminates rather
    than firing unconditionally."""
    port = pef.free_port()
    rendered = _rendered_with_fake_block(port=port, owner_pid=os.getpid())
    script_path = tmp_path / "k4-supervisor.py"
    script_path.write_text(rendered, encoding="utf-8")

    supervisor_proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        # This test process (the real OWNER_PID) is alive throughout --
        # several poll cycles must pass with the supervisor still up.
        time.sleep(6)
        assert supervisor_proc.poll() is None, (
            "the supervisor self-terminated even though its OWNER_PID "
            "(this test process) never died -- _owner_alive() is firing "
            "on a false positive"
        )
    finally:
        supervisor_proc.kill()
        supervisor_proc.wait(timeout=5)
