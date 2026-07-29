"""The general spawn boundary — every child gets an explicit stdin and a bound.

CREATE_NEW (RCA ``docs/feature/fix-inherited-stdin-deadlocks-spawns/rca.md`` §7
"Where the locus must sit", §9.2, §10 "New: src/des/runtime/spawn.py — the
locus").

WHY-NEW-FILE: src/des/runtime/spawn.py
  CLOSEST-EXISTING: src/des/runtime/interpreter.py (``des_spawn``)
  EXTENSION-COST: ``des_spawn`` selects by CALLEE IDENTITY — "argv[0] is
    ``python_for(capability)``, env carries the des root" (``interpreter.py``
    :348-367). The hazard fixed here is not about the callee: the site that
    actually deadlocked (``shell_agent_invocation_adapter.py:44``) shells a
    THIRD-PARTY CLI and has no business going through an interpreter-resolution
    helper, so it could never be one of ``des_spawn``'s 17 call sites. Extending
    ``des_spawn`` would enforce the stdio/bounding property for 28% of the 60
    spawn sites — which is exactly how the deadlock shipped (RCA ROOT CAUSE A).
  PARALLEL-RATIONALE: the two boundaries have INCOMPATIBLE selection criteria and
    different lifecycles — ``des_spawn`` is a des-module composer that must keep
    resolving interpreters and PYTHONPATH, this is the process boundary one level
    LOWER that every spawn (des module, git, uv, a vendor CLI, a language runner)
    passes through. ``des_spawn`` now DELEGATES here rather than duplicating.

THE DEFECT THIS CLOSES. ``des refactor --pile`` deadlocked: four nested processes
all sleeping on pipes. NO spawn site in ``src/des/**`` passed ``stdin=`` (0 of
60); POSIX inherits fd 0 transitively, so the deepest grandchild read the
outermost parent's stdin and blocked, while that parent blocked draining the
capture pipes the blocked grandchild held open. 41 of 60 sites carried no
``timeout=``, so nothing on the path could escape. The lethal descriptor is one
that DELIVERS DATA AND NEVER REACHES EOF — measured; an empty never-closed pipe
is survivable, which is why a bound alone is not the fix and ``DEVNULL`` is.

THE THREE DUTIES no object in the tree owned (RCA §7):

1. ``stdin=subprocess.DEVNULL`` by default — applied ONLY when the caller passed
   neither ``stdin=`` nor ``input=``. The conditional is load-bearing, not
   defensive: ``subprocess.run`` RAISES ``ValueError: stdin and input arguments
   may not both be used``, so an unconditional default would crash the two sites
   that commit a message on the child's stdin (``commit_slice.py:1416``/``:1448``)
   — i.e. every slice commit. Exemption by CONSTRUCTION, never by an allowlist.
2. A wall-clock bound on every spawn, generous and env-overridable per tier
   (§8). A bound that kills a legitimate 45-minute suite converts a hang into a
   worse defect, so the default is the most generous tier the repo already runs
   on and each caller narrows it deliberately.
3. Process-group reaping on the timeout path, PER TIER (RCA risk #5: "keep
   reaping per-tier, not blanket") — ``reap_process_group=True``. MEASURED
   caveat that makes it a duty at all: on POSIX ``subprocess.run(timeout=)`` does
   ``kill()`` + ``wait()``, NOT ``communicate()`` — it raises promptly but
   ORPHANS grandchildren. A bound without a reap converts an infinite hang into a
   silent process leak, once per pile item, on a 4-core shared box. It is opt-in
   rather than default because reaping needs a new SESSION, and a new session
   also detaches the child from the terminal's foreground process group — an
   interactive command's Ctrl-C would stop reaching its own child. Same pattern,
   same rationale, as ``pytest_runner.run_pytest_reaped`` (``:125-186``).

And duty 4, from the standing what/why/how rule: a fired bound EXPLAINS ITSELF —
what timed out, why, and the env override to reach for — never a bare
``TimeoutExpired`` traceback or a naked non-zero exit.

THIN PASSTHROUGH (RCA risk #6). This only ever INJECTS defaults the caller
omitted; it never rewrites a kwarg the caller decided. Everything else is
forwarded to ``subprocess`` unchanged, and the return value is a plain
``subprocess.CompletedProcess``, so routing a site through here is a
behaviour-preserving move.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable


# --------------------------------------------------------------------------- #
# Active-process-group registry (duty 3, extended to the operator-abort path).
#
# ``_run_reaped`` already reaps its child's process group when ITS OWN wall
# clock fires or an exception unwinds THROUGH it. But a SIGTERM/SIGINT delivered
# to the PARENT process is neither of those: Python's default SIGTERM
# disposition terminates the process outright (no exception unwinds ``_run_
# reaped`` at all), and even a SIGINT raised in the main thread never unwinds a
# ``_run_reaped`` running in a WORKER thread (drain_batch). Both leave the
# reaped child -- deliberately spawned into its OWN session so the timeout reap
# could ``killpg`` it -- orphaned, because that same detachment means nothing
# else will ever signal it once the parent is gone.
#
# So a process-wide signal handler needs a way to reach every reaped child's
# process group from OUTSIDE the call frame that owns it. This registry is that
# seam: ``_run_reaped`` publishes its child's pgid for the lifetime of the
# ``Popen``, and ``reap_active_process_groups`` -- called by the entrypoint's
# signal handler -- SIGKILLs every one still live. The set is the minimum shared
# state that makes the child's group knowable to a handler; the reap itself
# reuses the same ``_reap_process_group`` the timeout path uses.
# --------------------------------------------------------------------------- #

_active_process_groups: set[int] = set()
_active_process_groups_lock = threading.Lock()


def _register_active_process_group(pgid: int) -> None:
    with _active_process_groups_lock:
        _active_process_groups.add(pgid)


def _forget_active_process_group(pgid: int) -> None:
    with _active_process_groups_lock:
        _active_process_groups.discard(pgid)


def reap_active_process_groups() -> None:
    """SIGKILL the process group of every currently-running reaped spawn.

    The seam a process-wide SIGINT/SIGTERM handler calls to make the timeout
    path's reap reach the operator-abort path too: without it, a signal to the
    parent orphans the very agent subtrees ``reap_process_group=True`` detached
    into their own sessions. Best-effort and idempotent -- a group that has
    already exited is the success case (``ProcessLookupError`` suppressed inside
    ``_reap_process_group``). A SNAPSHOT is taken under the lock and the kills
    run OUTSIDE it, so a syscall never runs while the lock is held and a
    concurrent ``_run_reaped`` finishing mid-reap cannot deadlock the handler.
    """
    with _active_process_groups_lock:
        pgids = list(_active_process_groups)
    for pgid in pgids:
        _reap_process_group(pgid)


AGENT_TIMEOUT_ENV = "NWAVE_REFACTOR_AGENT_TIMEOUT"
"""Operator-facing override for the AGENT tier — the HOW of a fired agent bound."""

_AGENT_TIMEOUT_DEFAULT_SECONDS = 3600.0
"""AGENT tier, RCA §8: derived from the actuator's own budget (``--max-turns 60``)
and the measured 25-minute-per-item reality. One hour, deliberately generous."""


GIT_TIMEOUT_ENV = "NWAVE_GIT_TIMEOUT"
"""Operator-facing override for the GIT tier -- the HOW of a fired git bound."""

_GIT_TIMEOUT_DEFAULT_SECONDS = 30.0
"""GIT tier: the read-only git seam (rev-parse, symbolic-ref, merge-base,
rev-list). These answer from LOCAL git state and never dial the network, so
seconds is the honest order of magnitude -- a probe still running after 30s is
blocked on an index.lock, a credential prompt, or a hung mount, not working.
Deliberately far tighter than the RUN default: a bound that inherits the
45-minute suite ceiling would let a lock-blocked probe stall a gate for most of
an hour, which is the hang this tier exists to bound."""


def git_timeout_seconds() -> float:
    """Wall-clock ceiling for one read-only git probe (GIT tier)."""
    try:
        return float(os.environ.get(GIT_TIMEOUT_ENV, _GIT_TIMEOUT_DEFAULT_SECONDS))
    except ValueError:
        return _GIT_TIMEOUT_DEFAULT_SECONDS


def agent_timeout_seconds() -> float:
    """Wall-clock ceiling for one headless-agent invocation (RCA §8, AGENT tier).

    Generous AND overridable on purpose: the charter negative "must NOT cut off
    work that is still visibly progressing" is only satisfiable if the operator
    has a lever, and a self-explaining timeout's HOW has to name one. A malformed
    override falls back to the default rather than crashing the drain.
    """
    try:
        return float(os.environ.get(AGENT_TIMEOUT_ENV, _AGENT_TIMEOUT_DEFAULT_SECONDS))
    except ValueError:
        return _AGENT_TIMEOUT_DEFAULT_SECONDS


def default_timeout_seconds() -> float:
    """The bound applied when a caller names no tier of its own.

    Deliberately the MOST GENEROUS tier the repo already runs on — the RUN
    ceiling (``run_timeout_seconds``, default 45 min, overridable via
    ``NWAVE_GATE_RUN_TIMEOUT``), whose own docstring cites "the empirical
    61-min-at-0%-CPU full-suite hang". Rationale (RCA §8): an omitted bound must
    become a ceiling that catches an infinite hang, NOT one that false-kills a
    legitimate long child — the longest thing spawned without an explicit bound
    today is a full test suite, so that is the number to inherit. Callers with a
    shorter tier pass their own ``timeout=``.

    Imported inside the call, not at module scope, to keep the SSOT single
    (``run_timeout_seconds`` lives in the run-facet adapter by existing
    convention) without creating the import cycle a module-level import would:
    ``pytest_runner`` imports ``des.runtime.interpreter``, which imports this
    module.
    """
    from des.adapters.driven.runner.pytest_runner import run_timeout_seconds

    return run_timeout_seconds()


class SpawnTimeout(subprocess.TimeoutExpired):
    """A fired wall-clock bound that explains itself.

    Subclasses ``subprocess.TimeoutExpired`` deliberately: every existing
    ``except subprocess.TimeoutExpired`` handler in the tree keeps working
    unchanged, so routing a site through the boundary cannot silently break its
    timeout handling. What is added is a ``__str__`` carrying WHAT / WHY / HOW —
    a bare ``TimeoutExpired`` carries what and why but no HOW, leaving the
    operator a number and no lever.
    """

    def __init__(
        self,
        cmd: Any,
        timeout: float,
        *,
        output: Any = None,
        stderr: Any = None,
        timeout_env: str | None = None,
    ) -> None:
        super().__init__(cmd, timeout, output=output, stderr=stderr)
        self.timeout_env = timeout_env

    @property
    def captured_text(self) -> str:
        """Whatever the killed child managed to emit, as text.

        ``TimeoutExpired.stdout`` is ``str | bytes | None`` depending on the
        spawn's capture mode; a caller reporting to an operator wants one type.
        The partial output is the evidence of WHERE the child got stuck, so it is
        normalised here rather than discarded at each call site.
        """
        captured = self.stdout
        if isinstance(captured, bytes):
            return captured.decode(errors="replace")
        return captured or ""

    def _how(self) -> str:
        if self.timeout_env:
            return (
                f"if the child was still doing real work, raise its bound with "
                f"{self.timeout_env}=<seconds> and re-run; if it was genuinely "
                f"stuck, the captured output on this exception is the evidence."
            )
        return (
            "if the child was still doing real work, pass a larger `timeout=` at "
            "the call site; if it was genuinely stuck, the captured output on this "
            "exception is the evidence."
        )

    def __str__(self) -> str:
        return (
            f"WHAT: the child process timed out — {_describe(self.cmd)} did not "
            f"finish within its {self.timeout:g}s wall-clock bound and was killed "
            f"together with its whole process group.\n"
            f"WHY: it was still running when the bound fired. Either it is "
            f"genuinely stuck (a child blocked on a descriptor nobody will ever "
            f"write to or close — the deadlock class this boundary exists to "
            f"bound), or the work legitimately needs longer than this tier allows.\n"
            f"HOW: {self._how()}"
        )


def spawn(
    argv: Any,
    *,
    timeout: float | None = None,
    timeout_env: str | None = None,
    reap_process_group: bool = False,
    **subprocess_kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a child process with an explicit stdin and an explicit bound.

    Drop-in for ``subprocess.run``: ``argv`` and every ``**subprocess_kwargs``
    (``cwd``, ``env``, ``shell``, ``capture_output``, ``text``, ``check``,
    ``input``, ``stdin``, ``stdout``, ``stderr``, ...) mean exactly what they mean
    there, the execution is ``subprocess.run``'s, and the return value is a plain
    ``CompletedProcess``. ONE default is INJECTED and never imposed over a
    caller's choice: ``stdin=subprocess.DEVNULL`` when the caller passed neither
    ``stdin=`` nor ``input=``. Cutting the OUTERMOST descriptor immunises the
    whole subtree, because stdin is inherited rather than re-derived.

    ``timeout=None`` means "no tier named" and resolves to
    ``default_timeout_seconds()`` — omission can no longer mean unbounded.
    ``timeout_env`` names the operator's override for the tier in play and is
    quoted in the HOW of a fired bound.

    ``reap_process_group`` is the PER-TIER opt-in for duty 3, deliberately not a
    blanket default (RCA risk #5: "keep reaping per-tier, not blanket"). Turning
    it on makes the child a session leader so a fired bound can ``killpg`` its
    whole subtree instead of orphaning grandchildren — the right trade for a tier
    that shells a third-party CLI subtree, and the WRONG one as a default,
    because a new session also detaches the child from the terminal's foreground
    process group: an interactive ``des`` command's Ctrl-C would stop reaching
    its own child. Tiers that spawn a first-party, leaf-shaped child keep the
    plain semantics; the agent tier opts in.

    Raises ``SpawnTimeout`` (a ``subprocess.TimeoutExpired``) when the bound
    fires.
    """
    bound = default_timeout_seconds() if timeout is None else timeout
    if "stdin" not in subprocess_kwargs and "input" not in subprocess_kwargs:
        subprocess_kwargs["stdin"] = subprocess.DEVNULL

    run: Callable[..., subprocess.CompletedProcess[Any]] = (
        _run_reaped if reap_process_group else subprocess.run
    )
    try:
        return run(argv, timeout=bound, **subprocess_kwargs)
    except subprocess.TimeoutExpired as expired:
        raise SpawnTimeout(
            argv,
            bound,
            output=expired.stdout,
            stderr=expired.stderr,
            timeout_env=timeout_env,
        ) from None


def _run_reaped(
    argv: Any, *, timeout: float, **subprocess_kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    """``subprocess.run`` semantics, plus a process-group reap on the bound.

    Hand-rolled around ``Popen`` because ``subprocess.run`` cannot serve this
    duty: it exposes no handle on the child, and on POSIX its timeout path is
    ``kill()`` + ``wait()`` on the DIRECT child only (measured, RCA §8) — the
    grandchildren survive, and a bound without a reap converts an infinite hang
    into a silent process leak, once per pile item on a 4-core box. Owning the
    ``Popen`` is what makes the child's pid — and therefore its process group —
    knowable.

    ``capture_output`` / ``input`` / ``check`` are translated exactly as
    ``subprocess.run`` translates them, so a caller sees no semantic difference
    between the two engines beyond the reap itself.
    """
    stdin_input = subprocess_kwargs.pop("input", None)
    check = bool(subprocess_kwargs.pop("check", False))

    if stdin_input is not None:
        if "stdin" in subprocess_kwargs:
            raise ValueError("stdin and input arguments may not both be used.")
        subprocess_kwargs["stdin"] = subprocess.PIPE

    if subprocess_kwargs.pop("capture_output", False):
        if "stdout" in subprocess_kwargs or "stderr" in subprocess_kwargs:
            raise ValueError(
                "stdout and stderr arguments may not be used with capture_output."
            )
        subprocess_kwargs["stdout"] = subprocess.PIPE
        subprocess_kwargs["stderr"] = subprocess.PIPE

    subprocess_kwargs["start_new_session"] = True

    with subprocess.Popen(argv, **subprocess_kwargs) as child:
        # Published for the lifetime of the Popen so a process-wide signal
        # handler (reap_active_process_groups) can reach this group from outside
        # this call frame -- the parent-signal path the local except-blocks below
        # cannot cover (SIGTERM raises no exception here; a SIGINT in the main
        # thread never unwinds this frame when it runs in a worker thread).
        _register_active_process_group(child.pid)
        try:
            try:
                stdout, stderr = child.communicate(stdin_input, timeout=timeout)
            except subprocess.TimeoutExpired:
                stdout, stderr = _reap_and_drain(child)
                raise subprocess.TimeoutExpired(
                    argv, timeout, output=stdout, stderr=stderr
                ) from None
            except BaseException:
                # An abnormal exit (Ctrl-C, a signal) would otherwise leave the
                # whole group orphaned: the new session detached it from the
                # terminal's foreground group, so nothing else will ever signal
                # it.
                _reap_and_drain(child)
                raise
        finally:
            _forget_active_process_group(child.pid)

    completed = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


def _reap_and_drain(child: subprocess.Popen[Any]) -> tuple[Any, Any]:
    """SIGKILL the child's process group, then collect whatever it produced.

    Order matters: draining FIRST would block until every holder of the capture
    pipe closed it, and a surviving grandchild holding that pipe open is the very
    deadlock under repair. Once the group is dead the second ``communicate`` — the
    retry shape the stdlib documents for ``TimeoutExpired`` — returns at once.
    """
    _reap_process_group(child.pid)
    with contextlib.suppress(ValueError, OSError):
        return child.communicate()
    return None, None


def _reap_process_group(pid: int) -> None:
    """SIGKILL the whole process group led by ``pid`` (best-effort, idempotent).

    ``pid`` is the group leader (``_run_reaped`` spawns with
    ``start_new_session=True``, so its pgid == its pid) and every descendant that
    did not itself call ``setsid`` keeps that pgid — which is what makes the
    GROUP signal reach grandchildren that ``kill()`` on the direct child cannot.
    ``ProcessLookupError`` (the group is already empty) is the success case.

    The pattern, and its reasoning, are inherited from
    ``pytest_runner._reap_process_group`` (``:101-113``) rather than imported:
    that helper is private to the run-facet adapter, and importing an adapter
    from ``des.runtime`` would invert the layering and close an import cycle.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pid, signal.SIGKILL)


def _describe(cmd: Any) -> str:
    """Render a spawn's command for an operator-facing message."""
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(part) for part in cmd)
    return str(cmd)


__all__ = [
    "AGENT_TIMEOUT_ENV",
    "GIT_TIMEOUT_ENV",
    "SpawnTimeout",
    "agent_timeout_seconds",
    "default_timeout_seconds",
    "git_timeout_seconds",
    "reap_active_process_groups",
    "spawn",
]
