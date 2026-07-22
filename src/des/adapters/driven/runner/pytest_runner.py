"""The pytest concrete run-adapter -- shells pytest over a scoped node-id set.

The only production-ready run-facet adapter in ``f-spine-runs-tests-not-git-hooks``
(DDD-7): it implements ``RunnerAdapter.run`` for the ``pytest`` dogfood runner by
shelling ``<python_for(pytest)> -m pytest <scoped node-ids>`` and mapping the
pytest exit code to a pass/fail ``RunVerdict``. This is the EFFECT half of the
read/run split (Principle 12): ``TestRunnerPort.resolve`` is pure (filesystem
inspection, return-only); the actual test execution is confined here, behind the
port.

The interpreter is resolved through ``python_for("pytest")`` (the F-21 boundary
contract): a candidate that cannot import pytest is rejected at the boundary
rather than spawned and failing one frame later.

Exit-code mapping (pytest's own contract):

* ``0``  -- all selected tests passed                  -> PASS
* ``5``  -- no tests were collected for the scope       -> PASS (an empty scope
            is not a failure; the no-real-AT case is the gate's NOT_APPLICABLE
            concern upstream, handled before this adapter is reached)
* any other exit (``1`` test failures, ``2`` interrupted, ``3`` internal error,
  ``4`` usage error)                                    -> FAIL

stdlib + the resolved interpreter only.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import os
import signal
import subprocess
import tempfile
from typing import IO, TYPE_CHECKING

from des.ports.test_runner_port import (
    AtDiscoveryResult,
    ListScope,
    RunnerAdapterUnavailable,
    RunVerdict,
)
from des.runtime.interpreter import python_for


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.test_runner_port import RunnerAdapter


# pytest exit codes that mean "the scope is GREEN": 0 = passed, 5 = nothing
# collected (an empty scope is not a red verdict).
_GREEN_EXIT_CODES = frozenset({0, 5})


def _signal_kill_reason(returncode: int) -> str | None:
    """``None`` for a normal exit; else the named signal/OOM-kill reason (GDP-3).

    Shared by all 4 runner leaf adapters (imported here per the existing
    ``run_timeout_seconds``-lives-in-pytest_runner convention, re-imported by
    cargo/vitest/go) so the host-OS signal vocabulary is modeled ONCE, mirroring
    ``run_contract_gate._describe_worker_kill`` (not imported directly: that
    function lives in the ``des.cli`` layer, which already imports FROM this
    adapter package -- importing it back here would be a layering cycle).

    Detects the two host-OS signal-kill conventions a subprocess exposes on
    completion: POSIX ``returncode < 0`` (the negated signal number) and the
    ``128 + signal`` shell convention (137 = SIGKILL/OOM, 143 = SIGTERM).
    """
    if returncode < 0:
        signal_num = -returncode
        return (
            f"signal {signal_num} (SIGKILL/OOM-kill)"
            if signal_num == 9
            else f"signal {signal_num}"
        )
    if returncode in (137, 143):
        return f"exit code {returncode} (OOM-kill / SIGTERM shell convention)"
    return None


def run_timeout_seconds() -> float:
    """SSOT wall-clock ceiling for the pytest-RUN subprocesses (this scoped runner,
    the arch RUN, and the feature-end full-suite leg -- all behind this run-facet).

    These RUN tests, so the ceiling is GENEROUS (default 45 min) and env-overridable
    via ``NWAVE_GATE_RUN_TIMEOUT`` -- it catches an infinite hang (a deadlocking test
    blocking the gate forever, the empirical 61-min-at-0%-CPU full-suite hang) WITHOUT
    false-killing a legitimate long run. A malformed override falls back to the default
    rather than crashing the gate. Defined here (the shared run-facet boundary) so the
    contract-gate and this adapter share ONE definition (no duplication).
    """
    try:
        return float(os.environ.get("NWAVE_GATE_RUN_TIMEOUT", "2700"))
    except ValueError:
        return 2700.0


def _reap_process_group(pid: int) -> None:
    """SIGKILL the whole process group led by ``pid`` (best-effort, idempotent).

    ``pid`` is the group leader (the pytest child was spawned with
    ``start_new_session=True``, so its pgid == its pid). Signalling the GROUP --
    not just the reaped leader -- is what tears down any grandchild the child
    started (a target repo's durable-postgres/redis/docker fixture): those
    grandchildren keep the leader's pgid even after the leader dies, so
    ``killpg`` reaches them. ``ProcessLookupError`` (the group is already empty)
    is the success case, swallowed.
    """
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


def _read_capture(handle: IO[bytes] | None, text: bool) -> str | bytes | None:
    """Rewind and read a capture temp file; ``None`` when capture was off."""
    if handle is None:
        return None
    handle.seek(0)
    raw = handle.read()
    return raw.decode(errors="replace") if text else raw


def run_pytest_reaped(
    argv: list[str],
    *,
    cwd: Path,
    timeout: float | None = None,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run pytest as a session leader, reaping its WHOLE process group on exit.

    The gate spawns pytest as a subprocess; the TARGET repo's conftest may spawn
    a durable daemon fixture (a pgserver/postgres cluster) as a GRANDCHILD. A
    plain ``subprocess.run`` leaves that grandchild orphaned when the pytest
    child is killed on timeout (``run`` SIGKILLs only the DIRECT child) or when a
    session-scoped fixture fails to tear it down -- ``atexit``/finalizers cannot
    help under SIGKILL, so ONLY this supervisor can guarantee the reap.

    ``start_new_session=True`` makes the child a process-group leader; the
    ``finally`` ``killpg`` signals the whole group on EVERY exit path (timeout,
    PASS, FAIL) so no grandchild survives the leg. ``subprocess.TimeoutExpired``
    still propagates unchanged so existing callers' timeout handling is intact.

    Capture goes to TEMP FILES, not pipes, and the direct child is awaited with
    ``proc.wait`` (never ``communicate``): a leaked daemon that inherits the
    child's stdio would hold a PIPE open and hang the gate forever (and a pipe
    can dead-lock on a full buffer) -- a regular file never blocks the writer nor
    the wait, so the group can be reaped promptly once the child itself exits.
    """
    out_handle: IO[bytes] | None = tempfile.TemporaryFile() if capture_output else None
    err_handle: IO[bytes] | None = tempfile.TemporaryFile() if capture_output else None
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
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
                raise subprocess.TimeoutExpired(
                    argv,
                    timeout if timeout is not None else 0.0,
                    output=_read_capture(out_handle, text),
                    stderr=_read_capture(err_handle, text),
                ) from None
        finally:
            _reap_process_group(proc.pid)
        return subprocess.CompletedProcess(
            argv,
            proc.returncode,
            _read_capture(out_handle, text),  # type: ignore[arg-type]
            _read_capture(err_handle, text),  # type: ignore[arg-type]
        )
    finally:
        for handle in (out_handle, err_handle):
            if handle is not None:
                handle.close()


def pytest_interpreter(repo_root: Path | None = None) -> str:
    """Resolve the python interpreter the pytest run-facet drives, behind the port.

    The SINGLE sanctioned resolution of a pytest-capable python interpreter for
    the gate/wave layer. Gate LOGIC that drives nWave's OWN pytest workers (the
    contract-scope collection worker, the arch-invariant run, the feature-end
    full-suite leg) MUST obtain its interpreter through THIS run-facet boundary
    rather than calling ``python_for("pytest")`` inline -- so the python-hardcode
    lives behind the runner-adapter boundary (this allowlisted run-facet), never
    in gate logic that a non-python target would reach (the genericità mandate;
    a non-python target resolves its own run-facet via the registry and never
    reaches this python facet).

    ``repo_root``, when given, steers resolution at the TARGET repo being run
    (defect #79) rather than the installed ``des`` package's own location --
    see ``run_pytest_scope``, the only caller that has a ``target_root`` to
    forward. Callers with no target repo of their own (the nwave-dev dogfood
    workers) omit it and keep today's behavior unchanged.

    Raises ``InterpreterUnavailable`` (F-21 boundary) when no candidate can
    import pytest -- the gate maps that to its existing INDETERMINATE/exit-2
    degrade-LOUD path, unchanged.

    ``repo_root=None`` calls ``python_for("pytest")`` with NO ``repo_root=``
    kwarg at all (not ``repo_root=None``) -- byte-identical to the pre-fix
    call shape, so an existing test double that monkeypatches ``python_for``
    with the pre-fix single-argument signature keeps working unchanged for
    every caller that has no target repo of its own.
    """
    if repo_root is None:
        return python_for("pytest")
    return python_for("pytest", repo_root=repo_root)


def run_pytest_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Run the scoped node-ids under pytest in ``target_root``; return PASS/FAIL.

    Shells ``<python_for(pytest)> -m pytest <node-ids>`` with ``cwd`` at the
    target root (so the node-ids resolve against the target's own tree), maps the
    exit code to a verdict, and names the runner the verdict was earned in
    (``adapter.name``) so the gate can prove it ran in the RESOLVED runner.
    """
    interpreter = pytest_interpreter(repo_root=target_root)
    try:
        completed = run_pytest_reaped(
            [interpreter, "-m", "pytest", "-p", "no:cacheprovider", *scoped_node_ids],
            capture_output=True,
            text=True,
            cwd=target_root,
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        # ZERO DEFECTS: a deadlocking scoped test must never block the runner
        # forever -- fail LOUD as a non-green verdict on the ceiling.
        return RunVerdict(passed=False, runner=adapter.name)
    kill_reason = _signal_kill_reason(completed.returncode)
    if kill_reason is not None:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the pytest run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )
    passed = completed.returncode in _GREEN_EXIT_CODES
    return RunVerdict(passed=passed, runner=adapter.name)


def list_pytest_scope(
    adapter: RunnerAdapter,
    target_root: Path,
) -> ListScope:
    """Enumerate the pytest target's whole-tree contract scope (the list facet).

    The pytest ENUMERATE facet (ADR-FLOW-011 D5 -- the read counterpart of
    ``run_pytest_scope``): delegates to the EXISTING single collection seam
    (``run_contract_gate._collect_node_ids``, DDD-12) so the pytest digest path is
    registry-dispatched like every other runner -- genericità: pytest is one row
    among equals in the enumerate registry, not a hardcoded special-case. The seam
    is imported LOCALLY on the effect path to avoid an import cycle (the gate module
    imports this adapter at module load for ``pytest_interpreter``).

    Returns the canonical class-aware ``fspath::Class::method`` node-id set the gate
    digests -- the SAME identities the in-process pytest digest path fingerprints.
    """
    from des.cli.run_contract_gate import _collect_node_ids

    return ListScope(
        node_ids=tuple(_collect_node_ids(target_root)), runner=adapter.name
    )


# ---------------------------------------------------------------------------
# pytest at-discovery facet (fix-rust-regression-at-kind-wiring) -- a
# hardened relocation of ``carpaccio_format.count_pytest_regression_ats`` /
# ``pytest_regression_content_hash``, widened to ALSO walk class-nested
# ``Test*.test_*`` methods (F-AT-DETECTION-IS-LANGUAGE-BOUND: the original
# walked ``tree.body`` only, never recursing into a class body).
# ---------------------------------------------------------------------------


def _collect_pytest_test_names(tree: ast.Module) -> list[str]:
    """Module-level ``test_*`` function names PLUS class-nested ``test_*``
    method names (one level deep -- ``class Test*: def test_*``), excluding
    any ``@pytest.fixture``/``@fixture``-decorated ``test_*``-named def.
    """
    from des.cli.carpaccio_format import _has_fixture_decorator

    names: list[str] = []
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test_")
            and not _has_fixture_decorator(node)
        ):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if (
                    isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
                    and member.name.startswith("test_")
                    and not _has_fixture_decorator(member)
                ):
                    names.append(member.name)
    return names


def discover_pytest_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``test_*`` AT identities a pytest regression file carries.

    Reads the raw bytes ONCE (both the AST scan and the content-hash seal
    the SAME bytes -- no read-time-of-check/read-time-of-use gap), counts
    module-level AND class-nested ``test_*``/``async def test_*`` functions,
    and returns their names as ``at_ids`` alongside a sha256 content seal.
    Degrade-LOUD (``RunnerAdapterUnavailable``, never a silent empty
    discovery) on an unreadable file, a parse failure, or zero discovered
    tests.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name, reason=f"cannot read {regression_test_file}: {exc}"
        ) from exc
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=f"cannot decode {regression_test_file} as UTF-8: {exc}",
        ) from exc
    try:
        tree = ast.parse(text, filename=str(regression_test_file))
    except SyntaxError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name, reason=f"cannot parse {regression_test_file}: {exc}"
        ) from exc
    at_ids = _collect_pytest_test_names(tree)
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero test_* functions found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = [
    "discover_pytest_ats",
    "list_pytest_scope",
    "pytest_interpreter",
    "run_pytest_reaped",
    "run_pytest_scope",
]
