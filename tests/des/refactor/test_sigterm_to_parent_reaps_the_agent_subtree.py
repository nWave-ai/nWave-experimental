"""Regression witness -- SIGTERM to the `des refactor` parent must reap the
agent subtree AND clean up the in-flight item (slice-02, this feature's own
charter negative "no leftover process from the previous run may still be alive
once my prompt is back", for the operator-abort case specifically).

DEFECT. The sibling slice-01 fix bounds the agent leg and reaps its process
group on the TIMEOUT path (``des.runtime.spawn._run_reaped`` -> ``killpg`` when
its own wall clock fires). But a SIGTERM/SIGINT delivered to the PARENT
``des refactor`` process is a DIFFERENT path and is not covered:

* Python's default disposition for SIGTERM TERMINATES the process outright --
  no exception is raised, so neither ``_run_reaped``'s ``except BaseException``
  reap nor ``drain_one``'s ``except BaseException`` worktree/branch cleanup ever
  runs.
* The agent subtree was spawned with ``start_new_session=True`` (so the reap can
  ``killpg`` it on the timeout path), which ALSO detached it into its own
  session -- so once the parent dies, nothing else will ever signal that
  subtree. It is orphaned.

MEASURED (real CLI, RCA follow-up, 2026-07-23): a stub fixer that spawns a
detached grandchild and blocks was dispatched through the real drain; SIGTERM to
the top-level ``des refactor`` process returned control at once but left the
shell, the stub, and the grandchild all alive as orphans, PLUS the item's git
worktree and ``refactor-<id>`` branch stranded on disk.

The existing ``test_tests_red_and_exception_exits_clean_up_worktree.py`` names
this case explicitly as the deferred follow-up ("a driven port raising, or a
future SIGINT") -- this is that follow-up.

active-RED at HEAD. At HEAD no signal handler is installed, so SIGTERM kills the
driver instantly: the grandchild stays ALIVE, the worktree/branch stay on disk,
and no WHAT/WHY/HOW abort message is printed. Every assertion below therefore
fails against HEAD. The cure installs a SIGINT/SIGTERM handler in the
``des refactor`` entrypoint that reaps the active spawn process groups, runs the
same worktree/branch cleanup a mid-drain crash already does, prints a
self-explaining abort message, and exits non-zero.

WHY THIS IS BEHAVIOUR AND NOT SHAPE. Nothing here inspects source text or asserts
a kwarg is present. It drives the REAL ``des refactor`` entrypoint
(``des.cli.refactor.main``) in a signalable child process, sends it a REAL
SIGTERM, and asserts OBSERVABLES: a grandchild pid is dead, the git worktree is
gone, the branch is gone, and the operator got a message. A signal is only
witnessable across a process boundary, which is why the parent is a separate
process rather than an in-process call.

SAFETY. The whole scenario is hermetic: a ``tmp_path`` git repo built by the
slice-01 composition root, a stub agent under ``tmp_path``, and worktrees git
places beside that tmp repo. No repo suite is invoked; the real checkout this
test runs from is never touched. Every process the scenario starts (the driver's
own session, the agent's session, the grandchild) is reaped in ``finally`` on
every exit path so a RED run leaks nothing.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


MARKER_WAIT_SECONDS = 45.0
"""How long to wait for the drain to reach agent dispatch (worktree created,
venv faked, `before` test-run done, grandchild spawned) before signalling."""

ABORT_WAIT_SECONDS = 25.0
"""How long the fixed driver may take to reap, clean up, and exit after SIGTERM.
The un-fixed driver dies instantly; the fixed one runs git cleanup first."""


# --------------------------------------------------------------------------- #
# The stub agent -- the L3/L4 stand-in. Spawns a grandchild that stays in the
# agent's OWN process group (no setsid), records both pids, marks itself
# dispatched, then blocks. The grandchild is what a killpg of the agent's group
# reaps and a bare parent-death orphans.
# --------------------------------------------------------------------------- #

_STUB_AGENT = """\
import os
import pathlib
import subprocess
import sys
import time

agent_pidfile, grandchild_pidfile, marker = sys.argv[1:4]
# This process IS the group leader: des.runtime.spawn._run_reaped spawned the
# shell that exec'd us with start_new_session=True, so our pgid == this pid.
pathlib.Path(agent_pidfile).write_text(str(os.getpid()), encoding="utf-8")
grandchild = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(600)"]
)
pathlib.Path(grandchild_pidfile).write_text(str(grandchild.pid), encoding="utf-8")
pathlib.Path(marker).write_text("dispatched", encoding="utf-8")
time.sleep(600)
"""


# --------------------------------------------------------------------------- #
# The driver -- the REAL `des refactor` parent process. Fakes ONLY the
# non-deterministic env-provisioning port (the exact port the composition root
# fakes for every in-process slice AT; Architecture of Reference), then calls
# the REAL des.cli.refactor.main so its signal handling, its service, and its
# spawn boundary are all the production ones.
# --------------------------------------------------------------------------- #

_DRIVER = """\
import pathlib
import sys

import des.adapters.driven.refactor.uv_env_provision_adapter as _uvmod


class _FakeProvision:
    def probe(self):
        return True

    def provision(self, worktree_path):
        return pathlib.Path(worktree_path) / ".venv" / "bin" / "python"


_uvmod.UvEnvProvisionAdapter = _FakeProvision

from des.cli.refactor import main

raise SystemExit(main(sys.argv[1:]))
"""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_group(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pid, signal.SIGKILL)


def _kill_pid(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, signal.SIGKILL)


def _read_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    with contextlib.suppress(ValueError):
        return int(path.read_text(encoding="utf-8").strip())
    return None


def _wait_for_file(path: Path, *, bound: float) -> bool:
    deadline = time.monotonic() + bound
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.slow
@pytest.mark.negative_at
def test_sigterm_to_parent_reaps_the_agent_subtree(tmp_path: Path) -> None:
    """A SIGTERM to the `des refactor` parent kills the whole agent subtree and
    leaves the repository clean, with a self-explaining abort on stderr.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    scratch = tmp_path.parent / f"{tmp_path.name}-sigterm-scratch"
    scratch.mkdir()
    stub_agent = scratch / "stub_agent.py"
    stub_agent.write_text(_STUB_AGENT, encoding="utf-8")
    driver_script = scratch / "driver.py"
    driver_script.write_text(_DRIVER, encoding="utf-8")

    agent_pidfile = scratch / "agent.pid"
    grandchild_pidfile = scratch / "grandchild.pid"
    marker = scratch / "dispatched.marker"

    agent_cmd = " ".join(
        shlex.quote(part)
        for part in [
            sys.executable,
            str(stub_agent),
            str(agent_pidfile),
            str(grandchild_pidfile),
            str(marker),
        ]
    )

    console = tempfile.TemporaryFile()
    driver = subprocess.Popen(
        [
            sys.executable,
            str(driver_script),
            "--pile",
            str(composition.pile_path),
            "--agent-cmd",
            agent_cmd,
        ],
        cwd=str(composition.project_root),
        stdout=console,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ},
    )
    try:
        dispatched = _wait_for_file(marker, bound=MARKER_WAIT_SECONDS)
        console.seek(0)
        console_text = console.read().decode("utf-8", errors="replace")
        assert dispatched, (
            "WHAT: the drain never reached agent dispatch within "
            f"{MARKER_WAIT_SECONDS:.0f}s, so this test cannot witness a "
            "SIGTERM during a live agent.\n"
            "WHY: the driver refused, crashed, or stalled before dispatching "
            "the stub agent.\n"
            f"HOW: read the driver console below.\n--- driver console ---\n"
            f"{console_text}"
        )

        grandchild_pid = _read_pid(grandchild_pidfile)
        agent_pid = _read_pid(agent_pidfile)
        assert grandchild_pid is not None, (
            "WHAT: the stub agent never recorded its grandchild's pid.\n"
            "WHY: it did not get far enough to spawn one.\n"
            f"HOW: read the driver console.\n--- console ---\n{console_text}"
        )
        assert _pid_alive(grandchild_pid), (
            "WHAT: the grandchild is not alive at the moment SIGTERM is about "
            "to be sent -- the arrangement is void.\n"
            "WHY: it exited early, so this test cannot prove the reap.\n"
            "HOW: the stub agent must keep the grandchild alive until the "
            "parent is signalled."
        )

        os.kill(driver.pid, signal.SIGTERM)

        try:
            driver.wait(timeout=ABORT_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        console.seek(0)
        console_text = console.read().decode("utf-8", errors="replace")

        assert driver.returncode is not None, (
            "WHAT: the des refactor parent never returned after SIGTERM "
            f"(still running after {ABORT_WAIT_SECONDS:.0f}s).\n"
            "WHY: the abort handler hung -- reaping or cleanup blocked instead "
            "of completing.\n"
            f"HOW: the SIGTERM handler must reap, clean up, and exit "
            f"promptly.\n--- driver console ---\n{console_text}"
        )
        assert driver.returncode != 0, (
            "WHAT: the des refactor parent exited 0 after being aborted by "
            "SIGTERM.\n"
            "WHY: an operator-initiated abort is not a success -- exit 0 tells "
            "the next command in a script that the item was drained.\n"
            f"HOW: the abort handler must exit non-zero.\n--- console ---\n"
            f"{console_text}"
        )

        deadline = time.monotonic() + 5.0
        while _pid_alive(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _pid_alive(grandchild_pid), (
            f"WHAT: grandchild pid {grandchild_pid} is STILL ALIVE after the "
            "des refactor parent was aborted by SIGTERM and returned.\n"
            "WHY: Python's default SIGTERM disposition terminates the parent "
            "outright, so neither the spawn reap nor the drain cleanup runs, "
            "and the agent subtree -- detached into its own session so the "
            "timeout reap could killpg it -- is orphaned with nothing left to "
            "signal it.\n"
            "HOW: install a SIGINT/SIGTERM handler in the des refactor "
            "entrypoint that calls des.runtime.spawn.reap_active_process_groups"
            "() before exiting, so the in-flight agent's process group is "
            "SIGKILLed with the parent (RCA §7 duty 3, extended to the "
            "operator-abort path)."
        )

        assert "TD-001" not in composition.worktree_list(), (
            "WHAT: git worktree list still shows a dangling registration for "
            "TD-001 after the SIGTERM abort.\n"
            "WHY: the parent died before its worktree/branch cleanup could "
            "run.\n"
            "HOW: the abort handler must run the same worktree/branch cleanup a "
            "mid-drain crash already does (mirroring _refused_after_cleanup / "
            "_cleanup_worktree_and_branch), via the drain service's in-flight "
            "tracker."
        )
        assert not composition.branch_exists("refactor-TD-001"), (
            "WHAT: the refactor-TD-001 branch still exists after the SIGTERM "
            "abort.\n"
            "WHY: the parent died before deleting the in-flight item's "
            "branch.\n"
            "HOW: the abort handler must delete the in-flight branch, exactly "
            "as a tests-red or mid-drain-crash cleanup already does."
        )

        lowered = console_text.lower()
        assert "what:" in lowered and "why:" in lowered and "how:" in lowered, (
            "WHAT: the SIGTERM abort produced no WHAT/WHY/HOW explanation.\n"
            "WHY: an operator-initiated abort that prints nothing (or a bare "
            "traceback) leaves the maintainer unable to tell what state the "
            "run is in or what to do next -- the charter negative 'a bare "
            "non-zero exit code with no human-readable explanation'.\n"
            f"HOW: print a WHAT/WHY/HOW abort message to stderr before "
            f"exiting.\n--- driver console ---\n{console_text}"
        )
        assert "re-run" in lowered, (
            "WHAT: the abort message never tells the operator the concrete "
            "next step.\n"
            "WHY: the charter requires that however a run ends, the last thing "
            "on screen says what to do next; nothing was merged, so the "
            "actionable HOW is to re-run.\n"
            f"HOW: name the re-run in the abort message.\n--- console ---\n"
            f"{console_text}"
        )
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(os.getpgid(driver.pid), signal.SIGKILL)
        agent_pid = _read_pid(agent_pidfile)
        if agent_pid is not None:
            _kill_group(agent_pid)
        grandchild_pid = _read_pid(grandchild_pidfile)
        if grandchild_pid is not None:
            _kill_pid(grandchild_pid)
        with contextlib.suppress(subprocess.TimeoutExpired):
            driver.wait(timeout=5)
        console.close()
