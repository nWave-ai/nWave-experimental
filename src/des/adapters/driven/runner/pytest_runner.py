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

import os
import subprocess
from typing import TYPE_CHECKING

from des.ports.test_runner_port import ListScope, RunVerdict
from des.runtime.interpreter import python_for


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.test_runner_port import RunnerAdapter


# pytest exit codes that mean "the scope is GREEN": 0 = passed, 5 = nothing
# collected (an empty scope is not a red verdict).
_GREEN_EXIT_CODES = frozenset({0, 5})


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


def pytest_interpreter() -> str:
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

    Raises ``InterpreterUnavailable`` (F-21 boundary) when no candidate can
    import pytest -- the gate maps that to its existing INDETERMINATE/exit-2
    degrade-LOUD path, unchanged.
    """
    return python_for("pytest")


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
    interpreter = pytest_interpreter()
    try:
        completed = subprocess.run(
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


__all__ = ["list_pytest_scope", "pytest_interpreter", "run_pytest_scope"]
