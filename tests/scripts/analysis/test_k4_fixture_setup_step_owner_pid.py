"""Defect `il-supervisore-non-riavvia-il-server-dell-esaminatore-si-
autotermina-da-orfano` (measured 2026-08-23 in the clean K4 preflight run;
RCA'd and fixed 2026-08-24).

`pef.fixture_setup_step(port)` returns argv shaped `[sys.executable,
prepare_examiner_fixture.py, <port>]` -- `nwave_setup_steps`/`control_
setup_steps` run it as a SHORT-LIVED setup-step subprocess (`preflight.
py`'s `_run(step, cwd=workspace, env=env)`), which calls `prepare()` ->
`start_supervisor()` and then exits almost immediately, its one job done.
Before this fix, `start_supervisor` had no `owner_pid` parameter at all,
so `supervisor_script`'s own `resolved_owner_pid = owner_pid if owner_pid
is not None else os.getpid()` always fell back to THIS transient
subprocess's own PID -- a supervisor born during setup was bound, by
construction, to a process already gone within about a second, and self-
terminated as an "orphan" a couple of `POLL_SECONDS=2` cycles later.
Measured directly (2026-08-24, standalone reproduction): the supervisor's
own log carried exactly one line, `owner pid <setup-step pid> gone, self-
terminating`, within ~4s of the setup-step subprocess exiting -- the SAME
single-line signature the defect's evidence describes.

The fix threads `owner_pid` through `start_supervisor` -> `prepare` ->
`prepare_examiner_fixture.main()`, which reads it from
`K4_SUPERVISOR_OWNER_PID` -- the SAME `os.environ`/`_rendered_arm_env`
channel `K4_WALL_CLOCK_CEILING_MINUTES`/`K4_CAMPAIGN_START_EPOCH` already
use (`preflight.main()` sets it once, propagated to every setup-step
subprocess automatically). This test reproduces the REAL call path (a
genuine short-lived subprocess running `prepare_examiner_fixture.main()`,
never a hand-rolled reimplementation) with only the Django-dependent
`start_and_wait_block` swapped for a trivial, fast `sleep`-backed fake --
the SAME substitution technique
`test_k4_supervisor_orphan_owner_self_reap.py` already uses, for the same
reason (no real healthchecks clone needed to prove the OWNER_PID wiring).

Run: uv run pytest -q tests/scripts/analysis/test_k4_fixture_setup_step_owner_pid.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path


_K4_DIR = str(Path(__file__).parents[3] / "scripts" / "analysis" / "k4")
sys.path.insert(0, _K4_DIR)

import prepare_examiner_fixture as pef


_SETUP_STEP_WRAPPER = '''
"""Standalone reproduction of `fixture_setup_step`'s own subprocess entry
point (`prepare_examiner_fixture.main()`), with only the Django-dependent
pieces stubbed -- the OWNER_PID wiring under test is exercised through the
REAL, unmodified `main()` -> `prepare()` -> `start_supervisor()` call
chain."""
import sys

sys.path.insert(0, {k4_dir!r})
import prepare_examiner_fixture as pef

pef.start_and_wait_block = lambda port, api_key: (
    "sleep 100 & echo $! > " + pef.SERVER_PID_FILE_NAME + "\\n"
)
pef._ensure_venv = lambda workspace: sys.executable
pef._migrate = lambda venv_python, workspace: None
pef._seed = lambda venv_python, workspace, existing: "fake-api-key"
pef._snapshot_pristine_db = lambda workspace: None
pef._add_exclude_entries = lambda workspace: None

pef.main(sys.argv[1:])
'''


def _run_setup_step(
    tmp_path: Path, port: int, env: dict[str, str]
) -> subprocess.CompletedProcess:
    wrapper = tmp_path / "setup_step_wrapper.py"
    wrapper.write_text(
        _SETUP_STEP_WRAPPER.format(k4_dir=_K4_DIR),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(wrapper), str(port)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _wait_for(predicate, *, timeout: float, interval: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_setup_step_subprocess_binds_supervisor_to_the_env_owner_not_itself(tmp_path):
    """The fix's positive control: `K4_SUPERVISOR_OWNER_PID` set (as
    `preflight.main()` now does before spawning any setup step) -> the
    supervisor born inside the transient setup-step subprocess is owned
    by the DECLARED long-lived PID, survives well past the point the
    setup-step subprocess itself exited, and its log carries zero orphan
    self-termination lines."""
    owner_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        port = pef.free_port()
        env = dict(os.environ)
        env["K4_SUPERVISOR_OWNER_PID"] = str(owner_proc.pid)

        done = _run_setup_step(tmp_path, port, env)
        assert done.returncode == 0, (
            f"setup-step subprocess failed: stdout={done.stdout!r} stderr={done.stderr!r}"
        )

        script_text = (tmp_path / pef.SUPERVISOR_SCRIPT_NAME).read_text(
            encoding="utf-8"
        )
        match = re.search(r"^OWNER_PID = (\d+)$", script_text, re.M)
        assert match, "rendered k4-supervisor.py has no OWNER_PID line"
        assert int(match.group(1)) == owner_proc.pid, (
            "the supervisor's OWNER_PID must be the declared long-lived campaign "
            f"PID ({owner_proc.pid}), not the transient setup-step subprocess's "
            f"own PID -- got {match.group(1)}"
        )

        supervisor_pid = int(
            (tmp_path / pef.SUPERVISOR_PID_FILE_NAME).read_text().strip()
        )

        # Several POLL_SECONDS=2 cycles pass with the DECLARED owner alive
        # (the setup-step subprocess itself is long gone by now) -- the
        # supervisor must NOT self-terminate.
        time.sleep(6)
        try:
            os.kill(supervisor_pid, 0)
            supervisor_alive = True
        except OSError:
            supervisor_alive = False
        assert supervisor_alive, (
            "the supervisor self-terminated even though its declared "
            "K4_SUPERVISOR_OWNER_PID never died -- the fix did not take"
        )

        log_file = tmp_path / pef.SUPERVISOR_LOG_FILE_NAME
        log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
        assert "gone, self-terminating" not in log_text, (
            f"unexpected orphan self-termination line: {log_text!r}"
        )

        # Negative control, same discipline as the sibling orphan test:
        # once the DECLARED owner genuinely dies, the mechanism must still
        # notice and self-terminate -- proving this isn't merely disarmed.
        owner_proc.kill()
        owner_proc.wait(timeout=5)
        died = _wait_for(lambda: not _pid_alive(supervisor_pid), timeout=10)
        assert died, "the supervisor never self-terminated after its real owner died"
        log_text = log_file.read_text(encoding="utf-8")
        assert "gone, self-terminating" in log_text
        assert str(owner_proc.pid) in log_text
    finally:
        pef.stop_supervisor(tmp_path)
        if owner_proc.poll() is None:
            owner_proc.kill()
            owner_proc.wait(timeout=5)


def test_setup_step_subprocess_without_the_env_var_reproduces_the_pre_fix_orphan(
    tmp_path,
):
    """Documents the ORIGINAL defect as a standing regression canary:
    absent `K4_SUPERVISOR_OWNER_PID` (an older harness, or a bare manual
    invocation), `prepare()`'s default still resolves `owner_pid` to the
    CALLING process -- for `fixture_setup_step`'s own subprocess, that
    caller is itself, and it exits within about a second. The supervisor
    must notice and self-terminate as an orphan a few poll cycles later
    -- this is the failure mode `il-supervisore-non-riavvia-...-si-
    autotermina-da-orfano` measured in the wild, reproduced here on
    purpose so the mechanism (not the plumbing) is proven to still work
    exactly as `test_k4_supervisor_orphan_owner_self_reap.py` already
    proves for the general case."""
    port = pef.free_port()
    env = dict(os.environ)
    env.pop("K4_SUPERVISOR_OWNER_PID", None)

    done = _run_setup_step(tmp_path, port, env)
    assert done.returncode == 0, (
        f"setup-step subprocess failed: stdout={done.stdout!r} stderr={done.stderr!r}"
    )

    supervisor_pid = int((tmp_path / pef.SUPERVISOR_PID_FILE_NAME).read_text().strip())
    log_file = tmp_path / pef.SUPERVISOR_LOG_FILE_NAME
    try:
        died = _wait_for(lambda: not _pid_alive(supervisor_pid), timeout=10)
        assert died, (
            "expected the pre-fix default (no declared owner) to self-terminate "
            "the supervisor as an orphan -- if this now stays alive, the "
            "_owner_alive() mechanism itself regressed"
        )
        log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
        assert "gone, self-terminating" in log_text
    finally:
        pef.stop_supervisor(tmp_path)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
