"""Shared in-process CLI driver for the corpus-migration-in-process refactor.

Reproduces ``subprocess.run([sys.executable, "-m", "des.cli.X", ...], cwd=...)``
semantics IN-PROCESS so the acceptance corpus stops forking a fresh interpreter
per scenario (the migration the ``corpus-migration-in-process`` Mikado graph
drives). It is the single reusable tool every migration batch calls.

The driver:

  * ``os.chdir(cwd)`` with a ``try/finally`` restore so a shared test process is
    never left in the target directory — restored EVEN on exception;
  * captures stdout AND stderr via ``io.StringIO`` + ``contextlib.redirect_*`` so
    the migrated step can assert on the same text the subprocess captured;
  * calls the production CLI EDGE ``main(argv) -> int`` (default
    ``des.cli.__main__.main`` — the dispatcher that takes ``argv`` and RETURNS an
    int, never ``sys.exit``/``SystemExit``), driving the EDGE, never a leaf;
  * maps a ``SystemExit`` raised by the EDGE onto its exit code (faithful to the
    process boundary a subprocess imposed) rather than propagating it, so EDGEs
    that DO call ``sys.exit`` on an argparse error migrate without surprise.

Returns ``(exit_code, stdout, stderr)`` — the in-process analogue of a
``CompletedProcess``'s ``(returncode, stdout, stderr)``.

Two faithful in-process paths share this machinery:

  * ``run_cli_in_process`` — for a CLI EDGE ``main(argv) -> int`` (the
    ``python -m des.cli.X <args>`` fork class);
  * ``run_hook_in_process`` — for a **stdin-protocol hook** whose no-argv handler
    reads its JSON event from ``sys.stdin`` (the Claude Code hook protocol fork
    class, e.g. ``subprocess.run([sys.executable, "-m", "des...hook"],
    input=<json>)``). It additionally save/restores ``sys.stdin`` (and optionally
    ``sys.argv``) around the call — shared-process safe.

HOW A SCRIPT EDGE IS LOADED, AND THE ONE CAVEAT IT CARRIES
----------------------------------------------------------

``run_script_in_process`` / ``run_python_snippet_in_process`` execute the script's
own source via ``exec(code, {"__name__": "__main__", ...})`` — they do NOT resolve
``main`` through ``importlib.util.spec_from_file_location``. That is a deliberate
choice, not an accident of implementation, and it buys structural immunity to a
trap the spec-based route carries: ``@dataclass`` resolves ``cls.__module__``
through ``sys.modules``, so a module executed while still ABSENT from the registry
makes the lookup return ``None`` and every dataclass in the script dies with
``AttributeError: 'NoneType' object has no attribute '__dict__'`` — surfacing as a
collection error that never names its cause. The spec route needs
``sys.modules[name] = module`` BEFORE ``exec_module``; this route needs nothing,
because ``sys.modules["__main__"]`` always exists. Immunity beats a remembered
precaution: there is no registration anyone can forget.

**THE CAVEAT** (read this before converting a script that pickles): because
``__name__`` is ``"__main__"``, classes the script defines get
``__module__ == "__main__"``, which resolves to PYTEST's main module rather than to
the script. That is harmless for ``dataclasses``, which only needs a module object
with a ``__dict__`` (verified: ``slots=True``, ``frozen=True`` and
``field(default_factory=...)`` all behave). It is WRONG for ``pickle``, for
``copy.deepcopy`` of such instances, and for anything else that round-trips a class
by module-qualified name — those will resolve against the wrong module or fail to
resolve at all. A script edge doing any of that needs its ``main`` imported as a
real module under its own name, not executed as ``__main__``.
"""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import sys
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from types import CodeType

from des.cli.__main__ import main as _des_dispatcher_main


@contextlib.contextmanager
def _swapped_environ(env: Mapping[str, str] | None):
    """Replace ``os.environ`` wholesale with ``env`` for the body, then restore.

    Faithful to ``subprocess.run(..., env=env)`` — which gives the child the
    EXACT ``env`` mapping (a full replacement, not a delta). In a shared test
    process the original environment is captured and restored in ``finally`` so
    later tests are never observers of the swap. A child process the production
    code spawns DURING the body inherits the swapped ``os.environ`` (faithful to
    the subprocess case: a fixture-controlled ``PATH`` makes the production
    dispatch resolve a FAKE tool, a narrowed ``PATH`` makes ``git`` unresolvable,
    etc.). When ``env`` is ``None`` the environment is left untouched.
    """
    if env is None:
        yield
        return
    prior = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(prior)


def run_cli_in_process(
    argv: list[str],
    *,
    cwd: str | Path,
    main: Callable[[list[str]], int] = _des_dispatcher_main,
    env: Mapping[str, str] | None = None,
    stdin_text: str | None = None,
    catch_all: bool = False,
) -> tuple[int, str, str]:
    """Run a CLI EDGE ``main(argv)`` in-process under ``cwd``, capturing output.

    Args:
        argv: the argument vector the EDGE's ``main`` receives — for the default
            dispatcher this is ``[subcommand, *subcommand_args]`` (the in-process
            analogue of ``python -m des.cli.__main__ <subcommand> ...``).
        cwd: the working directory the EDGE resolves paths relative to (the corpus
            forks ran with ``cwd=tmp_path``); restored on return AND on exception.
        main: the production CLI EDGE callable. Defaults to the ``des.cli.__main__``
            dispatcher (the most common corpus EDGE); pass another EDGE's ``main``
            for batches whose fork targets a different module.
        env: optional full environment mapping the subprocess fork passed via
            ``env=`` — swapped into ``os.environ`` for the call and restored after
            (faithful to the fork's hermetic env: fixture ``PATH``, ``NWAVE_FRESHNESS``,
            narrowed ``PATH`` for a git-absent substrate, …). ``None`` leaves the
            ambient environment untouched.
        stdin_text: optional text the fork piped to the EDGE on stdin (``input=``);
            replaces ``sys.stdin`` for the call and is restored after.
        catch_all: when ``True``, an arbitrary exception escaping the EDGE is mapped
            onto exit code 1 with its traceback appended to the captured stderr —
            faithful to a subprocess that CRASHES (non-zero exit, partial stdout/
            stderr preserved) rather than exiting cleanly. The default ``False``
            keeps the strict contract (only ``SystemExit`` is mapped) for read-only
            EDGEs that never crash.

    Returns:
        ``(exit_code, stdout, stderr)`` — reproducing the subprocess observable.
    """
    out, err = io.StringIO(), io.StringIO()
    prior_cwd = os.getcwd()
    prior_stdin = sys.stdin
    os.chdir(str(cwd))
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with _swapped_environ(env):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    exit_code = main(argv)
                except SystemExit as exc:  # faithful to the subprocess boundary
                    exit_code = _exit_code_of(exc)
                except BaseException:
                    if not catch_all:
                        raise
                    traceback.print_exc(file=err)
                    exit_code = 1
    finally:
        os.chdir(prior_cwd)
        sys.stdin = prior_stdin
    return int(exit_code or 0), out.getvalue(), err.getvalue()


_CODE_CACHE: dict[tuple[str, str], CodeType] = {}


def _compiled(program: str, filename: str) -> CodeType:
    """Compile once per (source, filename); re-execute the CODE, never the module.

    This is the whole caching answer for the shared driver, and the distinction
    matters more than the milliseconds. Caching the compiled CODE object is free of
    semantic consequence: every call still executes into a FRESH namespace, so the
    per-call module-global isolation that makes an in-process call faithful to the
    process boundary it replaces is preserved exactly.

    Caching the MODULE (loading the edge once and re-calling its ``main``) would be
    the other reading of "cache it", and it is the wrong one here: a module loaded
    once retains its globals between calls, so a script mutating module-level state
    leaks it into the next test. That is a false-green vector of precisely the class
    filed as `in-process-conversion-can-hollow-out-an-isolation-test...` -- a
    conversion silently weakening an isolation property while everything stays green.

    The measurement says the trade is not even close. Re-execution costs 0.94-2.39ms
    per call across the seven converted scripts, against the 31.9ms fork it replaces
    -- so re-exec already captures ~94% of the available saving, and module-caching
    competes for the remaining ~1.6ms. The reason it is so cheap is structural: an
    ``import`` statement re-run hits ``sys.modules`` and costs nothing, so ONLY the
    script's own top-level statements re-execute, never its transitive import tree.
    Compilation was the real recurring cost, and that is what this cache removes.
    """
    key = (filename, program)
    code = _CODE_CACHE.get(key)
    if code is None:
        code = compile(program, filename, "exec")
        _CODE_CACHE[key] = code
    return code


def run_python_snippet_in_process(
    program: str,
    *,
    cwd: str | Path,
    env: Mapping[str, str] | None = None,
    argv: list[str] | None = None,
    filename: str = "<in-process-probe>",
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    """Run a ``python -c <program>`` / ``python <script>`` fork IN-PROCESS.

    The faithful in-process analogue of
    ``subprocess.run([sys.executable, "-c", program], env=env, cwd=cwd)`` (and of
    ``[sys.executable, str(script), *args]`` — pass the script's source as
    ``program``, ``filename=str(script)``, ``argv=[str(script), *args]``). The
    IDENTICAL program string runs in THIS interpreter under a swapped ``os.environ``
    + ``cwd`` instead of forking a fresh one — so a hermetic-env probe (fixture
    ``PATH`` resolving a FAKE runner, neutralised toolchain vars) keeps its exact
    isolation, and the production EDGE the snippet imports + calls is driven for
    real. ``PYTHONPATH`` tweaks in the fork's ``env`` are simply inert in-process
    (``des`` is already importable), never harmful.

    Faithful to ``python -c`` exit semantics: the program runs with
    ``__name__ == "__main__"``; a ``SystemExit`` maps onto its code; any OTHER
    exception is mapped onto exit code 1 with its traceback printed to the captured
    stderr (exactly what a forked interpreter does — traceback to fd 2, exit 1).
    ``cwd``, ``sys.argv`` and ``sys.stdin`` are saved and restored in ``finally`` —
    shared-process safe even on exception.

    Returns:
        ``(exit_code, stdout, stderr)`` — the in-process analogue of the
        subprocess ``CompletedProcess``'s ``(returncode, stdout, stderr)``.
    """
    out, err = io.StringIO(), io.StringIO()
    prior_cwd = os.getcwd()
    prior_argv = sys.argv
    prior_stdin = sys.stdin
    os.chdir(str(cwd))
    sys.argv = list(argv) if argv is not None else [filename]
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    namespace: dict[str, object] = {"__name__": "__main__", "__file__": filename}
    try:
        with _swapped_environ(env):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    exec(_compiled(program, filename), namespace)
                    exit_code = 0
                except SystemExit as exc:  # faithful to `python -c` exit code
                    exit_code = _exit_code_of(exc)
                except BaseException:
                    traceback.print_exc(file=err)
                    exit_code = 1
    finally:
        os.chdir(prior_cwd)
        sys.argv = prior_argv
        sys.stdin = prior_stdin
    return int(exit_code or 0), out.getvalue(), err.getvalue()


def run_module_in_process(
    module: str,
    *args: str,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    """Run a ``python -m <module> <args>`` fork IN-PROCESS, capturing output.

    The faithful in-process analogue of
    ``subprocess.run([sys.executable, "-m", module, *args], cwd=...)``: ``runpy``
    executes the module under ``__name__ == "__main__"`` in a FRESH namespace, so a
    module whose CLI body lives under an ``if __name__ == "__main__":`` guard runs
    exactly as it did in the child, and module-level state cannot leak between
    calls. ``sys.argv`` is the argv the fork passed.

    Faithful to ``python -m`` exit semantics: ``SystemExit`` maps onto its code; any
    other exception maps onto exit code 1 with its traceback on the captured stderr.
    ``cwd``, ``sys.argv`` and ``sys.stdin`` are restored in ``finally``.

    Returns:
        ``(exit_code, stdout, stderr)`` — the in-process analogue of the subprocess
        ``CompletedProcess``'s ``(returncode, stdout, stderr)``.
    """
    out, err = io.StringIO(), io.StringIO()
    prior_cwd = os.getcwd()
    prior_argv = sys.argv
    prior_stdin = sys.stdin
    if cwd is not None:
        os.chdir(str(cwd))
    sys.argv = [f"-m {module}", *args]
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with _swapped_environ(env):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    runpy.run_module(module, run_name="__main__", alter_sys=True)
                    exit_code = 0
                except SystemExit as exc:  # faithful to `python -m` exit code
                    exit_code = _exit_code_of(exc)
                except BaseException:
                    traceback.print_exc(file=err)
                    exit_code = 1
    finally:
        os.chdir(prior_cwd)
        sys.argv = prior_argv
        sys.stdin = prior_stdin
    return int(exit_code or 0), out.getvalue(), err.getvalue()


_SCRIPT_SOURCE_CACHE: dict[str, str] = {}


def run_script_in_process(
    script: str | Path,
    *args: str,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    """Run a standalone ``scripts/**.py`` EDGE in-process, capturing output.

    The faithful in-process analogue of the most common corpus fork shape,
    ``subprocess.run([sys.executable, str(script), *args], cwd=...)``: the script's
    OWN source runs in THIS interpreter with ``__name__ == "__main__"``, its real
    path as ``__file__`` (so ``Path(__file__).resolve().parents[N]`` anchors resolve
    exactly as they did under the fork) and ``sys.argv == [str(script), *args]``.

    A fresh module namespace per call reproduces the process boundary's global
    isolation, so a script mutating its own module-level state cannot leak into the
    next call. The source is read once per path and cached — the repeated cost is a
    ``compile`` + ``exec``, not an interpreter startup.

    Returns:
        ``(exit_code, stdout, stderr)`` — the in-process analogue of the subprocess
        ``CompletedProcess``'s ``(returncode, stdout, stderr)``.
    """
    path = str(Path(script).resolve())
    source = _SCRIPT_SOURCE_CACHE.get(path)
    if source is None:
        source = Path(path).read_text(encoding="utf-8")
        _SCRIPT_SOURCE_CACHE[path] = source
    return run_python_snippet_in_process(
        source,
        cwd=cwd if cwd is not None else os.getcwd(),
        env=env,
        argv=[path, *args],
        filename=path,
        stdin_text=stdin_text,
    )


def run_hook_in_process(
    handler: Callable[[], int],
    *,
    stdin_text: str,
    cwd: str | Path,
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a stdin-protocol hook handler IN-PROCESS under ``cwd``, feeding stdin.

    The faithful in-process analogue of the JSON-hook-protocol subprocess fork
    ``subprocess.run([sys.executable, "-m", "des...hook"], input=<json>, cwd=...)``
    (or ``[sys.executable, "-c", "from <h> import handle; sys.exit(handle())"]``):
    the hook's handler is **no-argv** and reads the event from ``sys.stdin`` (the
    Claude Code hook protocol), so this driver replaces ``sys.stdin`` with the
    SAME payload the subprocess piped in and calls the handler directly. Faithful
    to the process boundary — the handler reads the identical bytes from the
    identical ``sys.stdin`` contract — without forking a fresh interpreter.

    Use this ONLY for hooks whose handler reads ``sys.stdin`` and is callable
    in-process without an installed-artifact import-time side effect (e.g. a
    freshness gate firing at module import against the installed artifact — that
    class stays a faithful subprocess and is NOT a node-C target).

    ``sys.stdin`` (and ``sys.argv`` when ``argv`` is given) plus ``cwd`` are saved
    and restored in ``finally`` so a shared test process is never left mutated —
    restored EVEN on exception. A ``SystemExit`` raised by the handler (e.g. a
    ``__main__`` entry that does ``raise SystemExit(handle())``) is mapped onto its
    exit code, faithful to the subprocess return-code boundary.

    ``sys.__stderr__`` is ALSO redirected to the SAME captured-stderr sink and
    restored (node-C-v2). Some hooks write their LOUD terminal diagnostic to
    ``sys.__stderr__`` — the interpreter's ORIGINAL stderr — PRECISELY to escape
    their own internal ``contextlib.redirect_stderr`` (e.g. the SubagentStop
    watchdog terminals in ``subagent_stop_handler.py`` print the
    terminating-INDETERMINATE warning via ``file=sys.__stderr__``). A subprocess
    captured that channel on fd 2 alongside ordinary stderr, so the returned
    ``stderr`` includes it here too — behaviour-identical for any assertion that
    reads the loud diagnostic.

    Args:
        handler: the hook's no-argv handler callable returning an int exit code
            (e.g. ``handle_user_prompt_submit`` / ``handle_pre_tool_use``). This is
            the production EDGE the subprocess invoked, driven directly.
        stdin_text: the exact text the subprocess piped to the hook on stdin (the
            ``input=`` payload — typically the JSON hook event).
        cwd: the working directory the hook resolves paths relative to (the corpus
            forks ran with ``cwd=project_root``); restored on return AND exception.
        argv: optional ``sys.argv`` the hook reads (most stdin hooks ignore argv;
            pass a shim only for hooks that consult it). Restored on return.
        env: optional full environment mapping the subprocess fork passed via
            ``env=`` — swapped into ``os.environ`` for the call and restored after
            (faithful to the fork's hermetic env: a sandbox ``HOME`` so hook-side
            signal/log writes stay inside the tmp root, ``NWAVE_FRESHNESS=skip``,
            fixture ``PYTHONPATH``, …). ``None`` leaves the ambient environment
            untouched. The import-time freshness gate already fired when this
            shared interpreter first imported the hook module, so a freshness var
            is inert here; ``HOME`` (read by ``Path.home()`` / ``expanduser``) is
            the env semantic that actually matters in-process and IS honoured.

    Returns:
        ``(exit_code, stdout, stderr)`` — the in-process analogue of the
        subprocess ``CompletedProcess``'s ``(returncode, stdout, stderr)``.
    """
    out, err = io.StringIO(), io.StringIO()
    prior_cwd = os.getcwd()
    prior_stdin = sys.stdin
    prior_argv = sys.argv
    prior_dunder_stderr = sys.__stderr__
    os.chdir(str(cwd))
    sys.stdin = io.StringIO(stdin_text)
    if argv is not None:
        sys.argv = list(argv)
    try:
        with _swapped_environ(env):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                # Point sys.__stderr__ at the SAME sink as sys.stderr so a hook's
                # loud diagnostic written via `file=sys.__stderr__` (to escape its
                # own redirect_stderr) is captured too — the subprocess caught it
                # on fd 2. Restored in finally; the shared sink preserves interleave.
                sys.__stderr__ = err  # type: ignore[misc]
                try:
                    exit_code = handler()
                except SystemExit as exc:  # faithful to the subprocess return-code
                    exit_code = _exit_code_of(exc)
    finally:
        os.chdir(prior_cwd)
        sys.stdin = prior_stdin
        sys.argv = prior_argv
        sys.__stderr__ = prior_dunder_stderr  # type: ignore[misc]
    return int(exit_code or 0), out.getvalue(), err.getvalue()


def _exit_code_of(exc: SystemExit) -> int:
    """Map a ``SystemExit`` payload onto a conventional integer exit code."""
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1  # a string/other SystemExit payload -> conventional failure code
