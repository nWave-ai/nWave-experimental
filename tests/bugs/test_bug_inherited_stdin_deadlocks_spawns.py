"""Regression witness -- inherited stdin deadlocks nested `des` spawns.

DEFECT (RCA `docs/feature/fix-inherited-stdin-deadlocks-spawns/rca.md`, verdict
HYPOTHESIS CONFIRMED). ``des refactor --pile`` hangs forever. Four nested
processes, all sleeping on pipes:

    L1  des refactor --pile                     (src/des/cli/refactor.py:102)
    L2  /bin/sh -c '<agent_cmd>'                (shell_agent_invocation_adapter.py:44)
    L3  python scripts/refactor_agent.py ...
    L4  claude -p ...                           (scripts/refactor_agent.py:219)

NO spawn site in ``src/des/**`` passes ``stdin=`` (0 of 60). POSIX inherits fd 0
transitively, so L4 reads L1's stdin and blocks; L1 is simultaneously blocked in
``communicate()`` draining L2's ``capture_output`` pipes, which the blocked L4
holds open. 41 of 60 sites carry no ``timeout=``, so neither side is bounded.
Permanent deadlock, zero output, killed by hand.

THE SHAPE OF THE HOSTILE DESCRIPTOR MATTERS (RCA correction, measured). An EMPTY
never-closed pipe is survivable -- ``claude`` v2.1.217 self-recovers after a 3s
grace. The descriptor that blocks FOREVER is one that DELIVERS SOME DATA AND NEVER
REACHES EOF. Every fixture here is that shape: a pipe written to and never closed,
read by a grandchild doing ``sys.stdin.read()`` (read-until-EOF, the same shape as
``claude``'s stream reader and as ``hook_protocol.read_and_parse_stdin``). Build
the empty-pipe shape instead and you get a witness that passes for the wrong
reason.

THE TRAP THAT SILENTLY DEFEATS A NAIVE TEST. pytest's default fd-capture dup2s
``/dev/null`` onto fd 0, so a subprocess spawned from inside a pytest test already
sees ``FD0=/dev/null`` and reads ``''`` (RCA §4.2, measured). A test that simply
calls the production code in-process is IMMUNE BY ACCIDENT and would go green
against the broken code. Therefore every witness here spawns a DRIVER process
whose stdin is explicitly the read end of a hostile pipe, and has THAT driver
exercise the production object.

BOUNDEDNESS IS A TEST-DESIGN REQUIREMENT, NOT A COURTESY. A test that hangs is not
a witness, it is a second outage. ``_drive`` bounds every driver on a wall clock,
captures to TEMP FILES rather than pipes (a pipe held open by a hung grandchild
would block the reader -- the very bug under test; same reasoning as
``pytest_runner.run_pytest_reaped``), and reaps the driver's whole PROCESS GROUP on
every exit path so a RED run leaks nothing.

NO REPO SUITE IS INVOKED FROM A SUBPROCESS. Every target is synthetic and lives in
``tmp_path``; shelling into this repo's ~8000-test suite would re-create the very
recursive nesting under fix.

WHAT IS PINNED, AND WHY IT IS BEHAVIOUR AND NOT SHAPE. A test asserting that the
literal ``stdin=subprocess.DEVNULL`` appears in the source, or that the kwarg is
present at a call site, would pass against a ``stdin=`` wired to entirely the wrong
thing. Nothing here inspects source text. Each test drives a REAL production object
(``ShellAgentInvocationAdapter.invoke``, ``commit_slice._commit_with_placeholder``,
and the general spawn boundary the fix introduces) and asserts an OBSERVABLE: the
chain returned within a bound, the grandchild saw EOF, the message bytes reached
the child, no orphan survived, the failure explained itself.

THE ONE PINNED LOCUS. The general spawn boundary is pinned as
``des.runtime.spawn.spawn`` -- not an incidental implementation guess but the
locus the RCA specifies (§7 "Where the locus must sit", §9.2, and §10 "Files
affected / New: src/des/runtime/spawn.py -- the locus"). Its minimal contract as
pinned here: ``spawn(argv, *, timeout=..., **subprocess_kwargs)`` returning an
object with ``.returncode`` (and ``.stdout`` when capture is requested), applying
``stdin=DEVNULL`` ONLY when the caller passed neither ``stdin=`` nor ``input=``.

active-RED at HEAD. The A1 witness HANGS against current code and therefore fails
on its wall-clock bound with a semantic ``AssertionError``; the spawn-boundary
tests fail with a semantic ``AssertionError`` naming the absent locus (the import
is LAZY, inside the test body, so collection stays clean -- never an ImportError at
collection). The two cure-must-not-overshoot guards (``input=`` preservation,
legitimate long work) are GREEN at HEAD by design: their job is to fail if the CURE
regresses them, which is exactly what a naive unconditional ``stdin=DEVNULL``
default would do (``subprocess.run`` raises ``ValueError: stdin and input arguments
may not both be used``, crashing ``commit_slice.py:1416``/``:1448``).
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# Wall-clock bounds. Every one is well under the pytest-timeout floor (600s,
# pyproject.toml) so a failure is a FAILURE with a readable message, never a hang
# handed to the global hang-catcher.
# --------------------------------------------------------------------------- #

WITNESS_BOUND_SECONDS = 20.0
"""A1/A2b: the un-fixed chain hangs forever; the fixed chain completes in <1s."""

REAP_BOUND_SECONDS = 30.0
"""A4/A6: the agent tier is driven down to 5s via its env override, so a fixed
chain returns in ~5s; the un-fixed chain never returns."""

LONG_WORK_BOUND_SECONDS = 45.0
"""A5: the legitimate agent works for ~6s; anything near this bound means the cure
killed work it should not have."""

AGENT_TIMEOUT_ENV = "NWAVE_REFACTOR_AGENT_TIMEOUT"
"""Operator-facing override for the AGENT tier (RCA §8). Pinned because the
charter's 'must not cut off work that is still visibly progressing' negative is
only satisfiable if the bound is generous AND overridable, and because a
self-explaining timeout's HOW has to name it."""


# --------------------------------------------------------------------------- #
# Synthetic processes. None of these touch this repository; they exist only in
# tmp_path and model the L3/L4 shape of the real drain leg.
# --------------------------------------------------------------------------- #

_L4_READS_STDIN_UNTIL_EOF = '''\
"""L4 analogue -- the third-party agent CLI. Reads stdin to EOF, as `claude`'s
stream reader does once any byte has arrived."""
import pathlib
import sys

witness = pathlib.Path(sys.argv[1])
data = sys.stdin.read()  # blocks forever on a descriptor that never reaches EOF
witness.write_text(repr(data), encoding="utf-8")
print("L4-OBSERVED-EOF", flush=True)
'''

_L3_SPAWNS_L4 = '''\
"""L3 analogue -- scripts/refactor_agent.py. Spawns the agent CLI with no
`stdin=` and no `timeout=`, exactly as refactor_agent.py:219 does at HEAD."""
import subprocess
import sys

completed = subprocess.run([sys.executable, sys.argv[1], sys.argv[2]], check=False)
raise SystemExit(completed.returncode)
'''

_AGENT_LEAVES_A_GRANDCHILD_BEHIND = '''\
"""Agent that starts a grandchild in ITS OWN process group and then blocks.

The grandchild does NOT call setsid, so it keeps the agent's pgid -- a process
group reap reaches it, while `subprocess.run(timeout=)` (which does kill() +
wait() on the DIRECT child only, on POSIX) orphans it."""
import pathlib
import subprocess
import sys
import time

pidfile = pathlib.Path(sys.argv[1])
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
pidfile.write_text(str(grandchild.pid), encoding="utf-8")
time.sleep(300)
'''

_AGENT_DOING_LEGITIMATE_LONG_WORK = '''\
"""Agent that works visibly for several seconds and then finishes normally."""
import sys
import time

for step in range(6):
    print(f"working, step {step}", flush=True)
    time.sleep(1)
print("AGENT-COMPLETED-ITS-WORK", flush=True)
'''

_AGENT_THAT_NEVER_FINISHES = '''\
"""Agent that never finishes -- forces the bound to fire."""
import time

time.sleep(300)
'''


# --------------------------------------------------------------------------- #
# Drivers. Each runs in its OWN process so its stdin can be the hostile pipe and
# so the whole chain can be bounded and reaped from the outside.
# --------------------------------------------------------------------------- #

_DRIVER_INVOKES_AGENT_ADAPTER = '''\
"""L1 analogue -- drives the REAL ShellAgentInvocationAdapter.invoke."""
import json
import pathlib
import sys

from des.adapters.driven.refactor.shell_agent_invocation_adapter import (
    ShellAgentInvocationAdapter,
)

agent_cmd, prompt_path, worktree_path, report_path = sys.argv[1:5]
report = pathlib.Path(report_path)
try:
    result = ShellAgentInvocationAdapter().invoke(
        agent_cmd, pathlib.Path(prompt_path), pathlib.Path(worktree_path)
    )
    payload = {
        "outcome": "returned",
        "exit_code": result.exit_code,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }
except BaseException as exc:  # noqa: BLE001 -- the report IS the assertion surface
    payload = {
        "outcome": "raised",
        "type": type(exc).__name__,
        "message": str(exc),
    }
report.write_text(json.dumps(payload), encoding="utf-8")
'''

_DRIVER_INVOKES_SPAWN_BOUNDARY = '''\
"""L1 analogue -- drives the general spawn boundary the fix introduces."""
import json
import pathlib
import sys

report = pathlib.Path(sys.argv[1])
child_script, witness_path = sys.argv[2], sys.argv[3]

try:
    from des.runtime.spawn import spawn
except Exception as exc:  # noqa: BLE001
    report.write_text(
        json.dumps({"outcome": "no-locus", "message": f"{type(exc).__name__}: {exc}"}),
        encoding="utf-8",
    )
    raise SystemExit(0)

try:
    completed = spawn([sys.executable, child_script, witness_path], timeout=15)
    report.write_text(
        json.dumps({"outcome": "returned", "exit_code": completed.returncode}),
        encoding="utf-8",
    )
except BaseException as exc:  # noqa: BLE001
    report.write_text(
        json.dumps({"outcome": "raised", "message": f"{type(exc).__name__}: {exc}"}),
        encoding="utf-8",
    )
'''


# --------------------------------------------------------------------------- #
# Bounded, reaping driver harness.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DriveOutcome:
    """What a bounded driver run produced."""

    completed: bool
    """False == the wall-clock bound fired, i.e. the chain hung."""
    returncode: int | None
    console: str
    elapsed: float


def _reap_group(pid: int) -> None:
    """SIGKILL the whole process group led by ``pid`` (best-effort, idempotent).

    The driver is spawned with ``start_new_session=True``, so its pgid == its pid
    and every descendant that did not itself call setsid keeps that pgid. Killing
    the GROUP -- not just the direct child -- is what stops a RED run from leaking
    the L2/L3/L4 processes it deliberately deadlocked.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pid, signal.SIGKILL)


def _write_script(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


def _drive(
    script: Path,
    args: list[str],
    *,
    bound: float,
    stdin_fd: int | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> DriveOutcome:
    """Run ``script`` as a bounded, group-reaped driver process.

    ``stdin_fd`` is handed to the child VERBATIM -- that is the whole point: it is
    how the hostile descriptor is injected past pytest's ``/dev/null`` fd-capture.
    Capture goes to a TEMP FILE, never a pipe: a grandchild that survives holding a
    pipe open would block the read and hang this harness, reproducing the defect
    inside the witness.
    """
    child_env = {**os.environ, **(env or {})}
    console = tempfile.TemporaryFile()
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script), *args],
            stdin=stdin_fd if stdin_fd is not None else subprocess.DEVNULL,
            stdout=console,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(cwd) if cwd is not None else None,
            env=child_env,
        )
        try:
            proc.wait(timeout=bound)
            completed = True
        except subprocess.TimeoutExpired:
            completed = False
        finally:
            _reap_group(proc.pid)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=10)
        console.seek(0)
        text = console.read().decode("utf-8", errors="replace")
        return DriveOutcome(
            completed=completed,
            returncode=proc.returncode if completed else None,
            console=text,
            elapsed=time.monotonic() - started,
        )
    finally:
        console.close()


@contextlib.contextmanager
def _hostile_stdin():
    """Yield the read end of a pipe carrying DATA that never reaches EOF.

    The measured lethal shape (RCA §2 / §VERDICT correction): an empty never-closed
    pipe is survivable, a pipe that delivered bytes and never EOFs is not. The write
    end is held open by THIS process for the whole scenario and closed only on exit,
    so nothing downstream can ever observe EOF while the witness is running.
    """
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"a byte of data that is never followed by EOF\n")
    try:
        yield read_fd
    finally:
        for fd in (read_fd, write_fd):
            with contextlib.suppress(OSError):
                os.close(fd)


def _read_report(report: Path, outcome: DriveOutcome, *, what: str) -> dict:
    """Load the driver's JSON report, or fail with a self-explaining message."""
    assert report.is_file(), (
        f"WHAT: {what} -- the driver produced no report at {report}.\n"
        f"WHY: the driver process did not reach its report write "
        f"(completed={outcome.completed}, rc={outcome.returncode}, "
        f"elapsed={outcome.elapsed:.1f}s).\n"
        f"HOW: read the driver console below and fix the harness or the "
        f"production path it drives.\n"
        f"--- driver console ---\n{outcome.console}"
    )
    return json.loads(report.read_text(encoding="utf-8"))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _spawn_boundary():
    """Resolve the general spawn boundary the fix introduces, LAZILY.

    Imported inside the test body -- never at module top -- so an absent locus is a
    semantic ``AssertionError`` at run time, not an ``ImportError`` at collection
    (active-RED, never BROKEN).
    """
    try:
        from des.runtime.spawn import spawn
    except ImportError as exc:
        raise AssertionError(
            "WHAT: the general spawn boundary `des.runtime.spawn.spawn` does not "
            f"exist ({exc}).\n"
            "WHY: no object in the tree owns the three duties every spawn needs -- "
            "(1) stdin defaulted to DEVNULL when the caller passed neither `stdin=` "
            "nor `input=`, (2) a wall-clock bound, (3) process-group reaping on the "
            "timeout path. Without that locus the hazard is enforced for 28% of the "
            "60 spawn sites (RCA ROOT CAUSE A).\n"
            "HOW: create `src/des/runtime/spawn.py` exposing `spawn(argv, *, "
            "timeout=..., **subprocess_kwargs)` per RCA §7 / §9.2 / §10, and have "
            "`des_spawn` (interpreter.py:342/374) delegate to it."
        ) from None
    assert callable(spawn), (
        "WHAT: `des.runtime.spawn.spawn` exists but is not callable.\n"
        "WHY: the spawn boundary must be the single callable every spawn routes "
        "through.\n"
        "HOW: expose `spawn(argv, *, timeout=..., **subprocess_kwargs)` per RCA §7."
    )
    return spawn


# --------------------------------------------------------------------------- #
# A1 -- THE WITNESS. Hangs against current HEAD.
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.negative_at
def test_agent_invocation_does_not_inherit_hostile_stdin(tmp_path: Path) -> None:
    """The real 4-level drain topology returns, and its deepest child sees EOF.

    Topology reproduced verbatim from the incident: a driver (L1) whose stdin is a
    hostile never-EOF pipe calls the REAL ``ShellAgentInvocationAdapter.invoke``,
    which shells (L2) into a synthetic agent (L3) that spawns a grandchild (L4)
    reading stdin to EOF -- the shape `claude` has.

    At HEAD no level passes ``stdin=``, POSIX inherits fd 0 transitively, L4 blocks
    forever, and L1 blocks in ``communicate()`` on the capture pipes L4 holds open.
    The chain never returns and this test fails on its wall-clock bound.

    Cutting stdin at the OUTERMOST boundary immunises the whole subtree, because
    stdin is inherited rather than re-derived (RCA §2, repro variant B: 0.22s, and
    L4 logged an empty read).
    """
    l4 = _write_script(tmp_path, "l4_agent_cli.py", _L4_READS_STDIN_UNTIL_EOF)
    l3 = _write_script(tmp_path, "l3_actuator.py", _L3_SPAWNS_L4)
    driver = _write_script(tmp_path, "l1_driver.py", _DRIVER_INVOKES_AGENT_ADAPTER)

    witness = tmp_path / "what_l4_read_from_stdin.txt"
    report = tmp_path / "invoke_report.json"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("refactor the thing\n", encoding="utf-8")

    agent_cmd = " ".join(
        shlex.quote(part) for part in [sys.executable, str(l3), str(l4), str(witness)]
    )

    with _hostile_stdin() as hostile_fd:
        outcome = _drive(
            driver,
            [agent_cmd, str(prompt), str(tmp_path), str(report)],
            bound=WITNESS_BOUND_SECONDS,
            stdin_fd=hostile_fd,
            cwd=tmp_path,
        )

    assert outcome.completed, (
        "WHAT: the agent-dispatch chain never returned -- it was still running "
        f"after {WITNESS_BOUND_SECONDS:.0f}s and had to be killed.\n"
        "WHY: no level of the chain sets `stdin=`, so the deepest child inherited "
        "the driver's stdin (a pipe carrying data that never EOFs) and blocked "
        "reading it, while the parent blocked in communicate() draining the "
        "capture pipes that blocked child holds open -- the deadly embrace of "
        "RCA ROOT CAUSE A. This is the production deadlock, reproduced.\n"
        "HOW: pass `stdin=subprocess.DEVNULL` at the outermost spawn boundary "
        "(shell_agent_invocation_adapter.py:44) -- inheritance means the outermost "
        "cut immunises the whole subtree -- and route every spawn through the "
        "general boundary `des.runtime.spawn.spawn` (RCA §9.1/§9.2).\n"
        f"--- driver console ---\n{outcome.console}"
    )

    payload = _read_report(report, outcome, what="the agent invocation")
    assert payload["outcome"] == "returned", (
        "WHAT: the agent invocation did not return a result.\n"
        f"WHY: it raised {payload.get('type')}: {payload.get('message')}.\n"
        "HOW: the invocation must complete and surface an AgentInvocationResult; "
        "see RCA §9.1."
    )

    assert witness.is_file(), (
        "WHAT: the deepest child never recorded what it read from stdin.\n"
        "WHY: it never got past its stdin read -- it is still blocked on an "
        "inherited descriptor, or it never started.\n"
        "HOW: cut stdin at the outermost spawn boundary (RCA §9.1).\n"
        f"--- invoke result ---\n{json.dumps(payload, indent=2)}"
    )
    observed = witness.read_text(encoding="utf-8")
    assert observed == "''", (
        "WHAT: the deepest child did NOT observe an immediate EOF on stdin -- it "
        f"read {observed}.\n"
        "WHY: it was handed a real, inherited descriptor instead of /dev/null. "
        "Any descriptor that can deliver bytes can also fail to EOF, which is the "
        "measured lethal shape (RCA VERDICT correction).\n"
        "HOW: the spawn boundary must default `stdin=subprocess.DEVNULL` whenever "
        "the caller passed neither `stdin=` nor `input=` (RCA §7 duty 1)."
    )


# --------------------------------------------------------------------------- #
# A2a -- the cure must not clobber a caller that supplies stdin bytes.
#        Drives REAL production code; locus-independent.
# --------------------------------------------------------------------------- #


def _init_disposable_repo(repo: Path) -> None:
    """A throwaway git repo with one staged file. `git -C` explicit-target form
    only -- this must never be able to touch the real checkout."""
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True, timeout=60
    )
    for key, value in (
        ("user.name", "Regression Witness"),
        ("user.email", "witness@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(repo / ".no-hooks")),
    ):
        subprocess.run(
            ["git", "-C", str(repo), "config", key, value], check=True, timeout=60
        )
    (repo / "thing.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "thing.txt"], check=True, timeout=60)


@pytest.mark.negative_at
def test_commit_message_on_stdin_is_not_clobbered_by_the_stdin_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spawn that supplies its own message bytes still delivers them.

    Guards the cure, not the defect. ``subprocess.run`` RAISES
    ``ValueError: stdin and input arguments may not both be used``, so an
    UNCONDITIONAL ``stdin=subprocess.DEVNULL`` default would crash the two sites
    that commit a message on stdin (``commit_slice.py:1416`` and ``:1448``) -- i.e.
    every slice commit. The default must apply ONLY when the caller passed neither
    ``stdin=`` nor ``input=`` (RCA §6, risk #1).

    Charter negative served: "any `des` command that legitimately asks me a question
    must STILL ask it and STILL accept what I type".

    GREEN at HEAD by design; it fails if the CURE regresses it.
    """
    from des.cli.commit_slice import _commit_with_placeholder

    repo = tmp_path / "disposable"
    repo.mkdir()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    _init_disposable_repo(repo)

    message = "fix(witness): a multi-line message\n\nwith a body line"
    _commit_with_placeholder(repo, message, no_verify=True)

    recorded = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout

    assert "fix(witness): a multi-line message" in recorded, (
        "WHAT: the commit message supplied on the child's stdin never reached git.\n"
        "WHY: the stdin default was applied unconditionally, displacing the "
        "caller's `input=` bytes (or raising `ValueError: stdin and input arguments "
        "may not both be used`).\n"
        "HOW: apply the DEVNULL default only when the caller passed neither "
        "`stdin=` nor `input=` (RCA §6 / §7 duty 1); `commit_slice.py:1416` and "
        "`:1448` must be exempt by construction, never by an allowlist.\n"
        f"--- recorded message ---\n{recorded}"
    )
    assert "with a body line" in recorded, (
        "WHAT: only part of the message reached git.\n"
        "WHY: the stdin bytes were truncated or partially displaced.\n"
        "HOW: the boundary must forward `input=` verbatim (RCA risk #6 -- inject "
        "defaults, never rewrite a caller's kwarg)."
    )


# --------------------------------------------------------------------------- #
# A2b / A3 -- the spawn boundary's three-way conditional, driven behaviourally.
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.negative_at
def test_spawn_boundary_never_passes_inherited_stdin_to_its_child(
    tmp_path: Path,
) -> None:
    """With neither `stdin=` nor `input=`, the child must observe EOF at once.

    Driven from a driver process whose stdin is the hostile never-EOF pipe, because
    pytest's fd-capture would otherwise hand the child ``/dev/null`` for free and
    the test would pass without the fix existing (RCA §4.2).
    """
    _spawn_boundary()  # RED here, with a self-explaining message, until the locus exists

    child = _write_script(tmp_path, "reader.py", _L4_READS_STDIN_UNTIL_EOF)
    driver = _write_script(tmp_path, "driver.py", _DRIVER_INVOKES_SPAWN_BOUNDARY)
    witness = tmp_path / "what_the_child_read.txt"
    report = tmp_path / "spawn_report.json"

    with _hostile_stdin() as hostile_fd:
        outcome = _drive(
            driver,
            [str(report), str(child), str(witness)],
            bound=WITNESS_BOUND_SECONDS,
            stdin_fd=hostile_fd,
            cwd=tmp_path,
        )

    assert outcome.completed, (
        "WHAT: a spawn through the general boundary never returned "
        f"(bound {WITNESS_BOUND_SECONDS:.0f}s).\n"
        "WHY: the child inherited the driver's never-EOF stdin and blocked.\n"
        "HOW: default `stdin=subprocess.DEVNULL` in the boundary when the caller "
        "passed neither `stdin=` nor `input=` (RCA §7 duty 1).\n"
        f"--- driver console ---\n{outcome.console}"
    )
    payload = _read_report(report, outcome, what="the spawn boundary")
    assert payload["outcome"] == "returned", (
        "WHAT: the spawn boundary did not return a completed process.\n"
        f"WHY: {payload.get('message')}\n"
        "HOW: see RCA §7 for the boundary's contract."
    )
    observed = witness.read_text(encoding="utf-8") if witness.is_file() else "<absent>"
    assert observed == "''", (
        "WHAT: the child spawned through the boundary did not observe an immediate "
        f"EOF -- it read {observed}.\n"
        "WHY: the boundary forwarded an inherited descriptor instead of "
        "defaulting it to /dev/null.\n"
        "HOW: RCA §7 duty 1 -- default `stdin=subprocess.DEVNULL` unless the caller "
        "specified `stdin=` or `input=`."
    )


@pytest.mark.negative_at
def test_spawn_boundary_does_not_clobber_caller_supplied_input(
    tmp_path: Path,
) -> None:
    """`input=` bytes must reach the child, not be displaced by the default."""
    spawn = _spawn_boundary()

    echo = _write_script(
        tmp_path,
        "echo_stdin.py",
        "import sys\nsys.stdout.write(sys.stdin.read())\n",
    )
    completed = spawn(
        [sys.executable, str(echo)],
        timeout=30,
        input="marker-bytes-42",
        text=True,
        capture_output=True,
    )
    assert completed.stdout == "marker-bytes-42", (
        "WHAT: the caller's `input=` bytes did not reach the child "
        f"(child echoed {completed.stdout!r}).\n"
        "WHY: the boundary applied its stdin default on top of a caller-supplied "
        "`input=` -- the naive implementation `subprocess.run` rejects outright "
        "with `ValueError: stdin and input arguments may not both be used`.\n"
        "HOW: apply the default ONLY when neither `stdin=` nor `input=` was passed "
        "(RCA §6, §7 duty 1)."
    )


@pytest.mark.negative_at
def test_spawn_boundary_does_not_override_an_explicit_caller_stdin(
    tmp_path: Path,
) -> None:
    """An explicit `stdin=` is honoured, never silently replaced by the default."""
    spawn = _spawn_boundary()

    echo = _write_script(
        tmp_path,
        "echo_stdin.py",
        "import sys\nsys.stdout.write(sys.stdin.read())\n",
    )
    source = tmp_path / "caller_stdin.txt"
    source.write_text("bytes-the-caller-chose", encoding="utf-8")

    with source.open("rb") as handle:
        completed = spawn(
            [sys.executable, str(echo)],
            timeout=30,
            stdin=handle,
            text=True,
            capture_output=True,
        )
    assert completed.stdout == "bytes-the-caller-chose", (
        "WHAT: the caller's explicit `stdin=` was not honoured "
        f"(child echoed {completed.stdout!r}).\n"
        "WHY: the boundary overwrote a kwarg the caller had already decided.\n"
        "HOW: the boundary INJECTS defaults and never rewrites a caller's kwarg "
        "(RCA risk #6 -- keep it a thin passthrough)."
    )


# --------------------------------------------------------------------------- #
# A4 -- a bound without reaping is a silent process leak, not a fix.
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.negative_at
def test_no_orphan_grandchild_survives_the_agent_bound(tmp_path: Path) -> None:
    """When the bound fires, nothing the spawn started is still alive.

    Measured caveat that changes the design (RCA §8): on POSIX
    ``subprocess.run(timeout=)`` calls ``kill()`` then ``wait()``, NOT
    ``communicate()`` -- it raises promptly but ORPHANS grandchildren. A timeout
    without process-group reaping converts an infinite hang into a silent process
    leak, once per pile item, on a 4-core shared box.

    Charter negative served: "no leftover process from the previous run may still
    be alive once my prompt is back".
    """
    agent = _write_script(tmp_path, "agent.py", _AGENT_LEAVES_A_GRANDCHILD_BEHIND)
    driver = _write_script(tmp_path, "driver.py", _DRIVER_INVOKES_AGENT_ADAPTER)
    pidfile = tmp_path / "grandchild.pid"
    report = tmp_path / "invoke_report.json"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("refactor the thing\n", encoding="utf-8")

    agent_cmd = " ".join(
        shlex.quote(part) for part in [sys.executable, str(agent), str(pidfile)]
    )

    outcome = _drive(
        driver,
        [agent_cmd, str(prompt), str(tmp_path), str(report)],
        bound=REAP_BOUND_SECONDS,
        env={AGENT_TIMEOUT_ENV: "5"},
        cwd=tmp_path,
    )

    grandchild_pid: int | None = None
    if pidfile.is_file():
        with contextlib.suppress(ValueError):
            grandchild_pid = int(pidfile.read_text(encoding="utf-8").strip())

    try:
        assert outcome.completed, (
            "WHAT: the agent invocation never returned, even with "
            f"{AGENT_TIMEOUT_ENV}=5 "
            f"(still running after {REAP_BOUND_SECONDS:.0f}s).\n"
            "WHY: the spawn carries no wall-clock bound at all -- 41 of 60 sites "
            "in src/des are unbounded, including this one (RCA §1 evidence "
            "table).\n"
            "HOW: give every spawn a tiered, env-overridable bound; the AGENT tier "
            f"defaults to 3600s and is overridable via {AGENT_TIMEOUT_ENV} "
            "(RCA §8).\n"
            f"--- driver console ---\n{outcome.console}"
        )
        assert grandchild_pid is not None, (
            "WHAT: the synthetic agent never recorded its grandchild's pid.\n"
            "WHY: the chain did not get far enough to start one, so this test "
            "cannot witness the reap.\n"
            f"HOW: inspect the driver console.\n--- console ---\n{outcome.console}"
        )

        deadline = time.monotonic() + 5.0
        while _pid_alive(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.1)

        assert not _pid_alive(grandchild_pid), (
            f"WHAT: grandchild pid {grandchild_pid} is STILL ALIVE after the "
            "agent bound fired and control came back.\n"
            "WHY: `subprocess.run(timeout=)` SIGKILLs only the DIRECT child on "
            "POSIX (kill() + wait(), never communicate()), so every grandchild is "
            "orphaned -- the bound converted an infinite hang into a silent "
            "process leak (RCA §8 measured caveat, risk #4).\n"
            "HOW: spawn with `start_new_session=True` and `os.killpg` the whole "
            "group on every exit path -- the pattern already implemented at "
            "`pytest_runner.run_pytest_reaped` (RCA §7 duty 3)."
        )
    finally:
        if grandchild_pid is not None and _pid_alive(grandchild_pid):
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.kill(grandchild_pid, signal.SIGKILL)


# --------------------------------------------------------------------------- #
# A5 -- the cure must not kill work that is still progressing.
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.negative_at
def test_bound_does_not_kill_legitimate_long_running_work(tmp_path: Path) -> None:
    """An agent that works for seconds, well inside its tier, still finishes.

    "A bound that kills a legitimate 45-minute suite converts a hang into a worse
    defect" (RCA §8). Charter negative served: "the command must NOT cut off work
    that is still visibly progressing."

    GREEN at HEAD by design (nothing is bounded there); it fails if the CURE
    overshoots -- a single global short bound, or an unoverridable one.
    """
    agent = _write_script(tmp_path, "agent.py", _AGENT_DOING_LEGITIMATE_LONG_WORK)
    driver = _write_script(tmp_path, "driver.py", _DRIVER_INVOKES_AGENT_ADAPTER)
    report = tmp_path / "invoke_report.json"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("refactor the thing\n", encoding="utf-8")

    agent_cmd = " ".join(shlex.quote(part) for part in [sys.executable, str(agent)])

    outcome = _drive(
        driver,
        [agent_cmd, str(prompt), str(tmp_path), str(report)],
        bound=LONG_WORK_BOUND_SECONDS,
        env={AGENT_TIMEOUT_ENV: "120"},
        cwd=tmp_path,
    )

    assert outcome.completed, (
        "WHAT: a legitimate ~6s agent run never returned within "
        f"{LONG_WORK_BOUND_SECONDS:.0f}s.\n"
        "WHY: the chain hung, or the bound machinery itself blocked.\n"
        f"HOW: inspect the driver console.\n--- console ---\n{outcome.console}"
    )
    payload = _read_report(report, outcome, what="the legitimate agent run")
    assert payload["outcome"] == "returned", (
        "WHAT: legitimate long-running work was TERMINATED instead of completing.\n"
        f"WHY: {payload.get('type')}: {payload.get('message')} -- the bound applied "
        f"was tighter than the work, or {AGENT_TIMEOUT_ENV}=120 was ignored.\n"
        "HOW: use the tiered, env-overridable bounds of RCA §8 (AGENT tier 3600s), "
        "never one global number."
    )
    assert payload["exit_code"] == 0, (
        "WHAT: the legitimate agent run did not exit cleanly "
        f"(exit_code={payload['exit_code']}).\n"
        "WHY: it was signalled by the supervising bound while still progressing.\n"
        "HOW: RCA §8 -- do not use one number; keep the long tiers long and "
        "overridable."
    )
    assert "AGENT-COMPLETED-ITS-WORK" in payload["stdout"], (
        "WHAT: the agent's own completion marker never surfaced.\n"
        "WHY: the work was cut off before it finished, or its output was "
        "discarded.\n"
        f"HOW: RCA §8.\n--- captured stdout ---\n{payload['stdout']}"
    )


# --------------------------------------------------------------------------- #
# A6 -- when the bound does fire, it must explain itself.
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.negative_at
def test_agent_timeout_never_surfaces_as_a_bare_traceback(tmp_path: Path) -> None:
    """A fired bound names WHAT timed out, WHY, and HOW to proceed.

    Charter negative served: "the command must NOT end with a raw stack trace, or a
    bare non-zero exit code with no human-readable explanation of what failed and
    what to do about it." A bare ``subprocess.TimeoutExpired`` carries WHAT and WHY
    but no HOW -- the operator is left with a number and no lever. The HOW here is
    the env override the RCA specifies (§8), which is also the lever the "must not
    cut off progressing work" negative depends on.
    """
    agent = _write_script(tmp_path, "agent.py", _AGENT_THAT_NEVER_FINISHES)
    driver = _write_script(tmp_path, "driver.py", _DRIVER_INVOKES_AGENT_ADAPTER)
    report = tmp_path / "invoke_report.json"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("refactor the thing\n", encoding="utf-8")

    agent_cmd = " ".join(shlex.quote(part) for part in [sys.executable, str(agent)])

    outcome = _drive(
        driver,
        [agent_cmd, str(prompt), str(tmp_path), str(report)],
        bound=REAP_BOUND_SECONDS,
        env={AGENT_TIMEOUT_ENV: "5"},
        cwd=tmp_path,
    )

    assert outcome.completed, (
        "WHAT: an agent that never finishes was never stopped -- the invocation "
        f"was still running after {REAP_BOUND_SECONDS:.0f}s with "
        f"{AGENT_TIMEOUT_ENV}=5.\n"
        "WHY: the spawn is unbounded, so there is nothing to explain itself with; "
        "the operator gets silence instead of a message (RCA ROOT CAUSE C).\n"
        f"HOW: bound the spawn per RCA §8 and honour {AGENT_TIMEOUT_ENV}.\n"
        f"--- driver console ---\n{outcome.console}"
    )

    payload = _read_report(report, outcome, what="the timed-out agent invocation")
    explanation = "\n".join(
        str(payload.get(key, "")) for key in ("message", "stdout", "stderr")
    )

    assert not explanation.lstrip().startswith("Traceback"), (
        "WHAT: the timeout surfaced as a raw stack trace.\n"
        "WHY: the exception escaped unwrapped.\n"
        "HOW: wrap it in the WHAT/WHY/HOW shape the repo requires of every "
        f"failure.\n--- surfaced ---\n{explanation}"
    )
    lowered = explanation.lower()
    assert "time" in lowered and ("timed out" in lowered or "timeout" in lowered), (
        "WHAT: the surfaced failure does not say that a bound fired.\n"
        f"WHY: the operator cannot tell a timeout from a crash.\n"
        f"HOW: name WHAT timed out and WHY.\n--- surfaced ---\n{explanation}"
    )
    assert "5" in explanation, (
        "WHAT: the surfaced failure does not name the bound that fired.\n"
        "WHY: without the number the operator cannot judge whether the bound was "
        "wrong or the work was genuinely stuck.\n"
        f"HOW: include the applied bound in the message.\n"
        f"--- surfaced ---\n{explanation}"
    )
    assert AGENT_TIMEOUT_ENV in explanation, (
        "WHAT: the surfaced failure does not tell the operator what to DO next -- "
        f"it never names {AGENT_TIMEOUT_ENV}.\n"
        "WHY: a bare non-zero exit with no remediation is exactly the charter "
        "negative ('a bare non-zero exit code with no human-readable explanation "
        "of what failed and what to do about it'), and it leaves the operator no "
        "lever when the bound is wrong rather than the work.\n"
        f"HOW: every failure states WHAT/WHY/HOW, and the HOW here is the env "
        f"override {AGENT_TIMEOUT_ENV} (RCA §8).\n"
        f"--- surfaced ---\n{explanation}"
    )
