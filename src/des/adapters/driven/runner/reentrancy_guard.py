"""Re-entrancy guard -- repo-scoped env sentinel (C14, ADR-ULAR-004).

Guards against a language-adapter-routed contract-gate call recursing into
itself: once ``PythonContractGateAdapter``/``VitestContractGateAdapter`` are
entry-point-registered, a target repo's OWN test suite shelling out to the
SAME gate against itself would route through the just-registered adapter,
which spawns a full unfiltered suite over the SAME tree -- re-running the
triggering test -- unboundedly (the observed failure: 8 nested pytest
processes, 22 minutes, process killed).

The guard is a bare env-var sentinel (``NWAVE_LANG_ADAPTER_ROUTE_ACTIVE``),
value = the resolved, canonicalized repo path(s) currently being routed
(``os.pathsep``-joined when more than one is nested), not a bare boolean and
not a depth counter -- this is the load-bearing precision ADR-ULAR-004
chose: it refuses ONLY a true self-referential re-entry on the SAME target,
never a legitimate nested call against a DIFFERENT target (e.g. two
distinct fixture repos gated in the same process tree). ``subprocess.run``
inherits the parent's ``os.environ`` by default, so the sentinel is visible
to any descendant process (xdist workers, grandchild ``des`` invocations)
with zero propagation code.

LOUD-advisory contract (NOT this module's job): the 3 seams that will guard
their routing with this module (a LATER, deferred wiring slice) are
responsible for emitting ``health.gate.lang-adapter.reentrancy-skipped`` on
stderr when they fall through due to an active guard -- this module stays a
pure primitive, stdlib-only (``os``, ``contextlib``), no emission of its own.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_GUARD_ENV_VAR = "NWAVE_LANG_ADAPTER_ROUTE_ACTIVE"


def is_routing_active_for(repo: Path) -> bool:
    """True iff the sentinel marks routing active for ``repo``.

    Reads ``os.environ`` only (no mutation). The sentinel value is a
    ``os.pathsep``-joined set of resolved repo paths, so this checks
    membership of ``str(repo.resolve())`` -- absent env var, or a value
    that names a different resolved path, both read as inactive.
    """
    raw = os.environ.get(_GUARD_ENV_VAR)
    if raw is None:
        return False
    active_paths = raw.split(os.pathsep)
    return str(repo.resolve()) in active_paths


@contextmanager
def routing_active_for(repo: Path) -> Iterator[None]:
    """Mark routing active for ``repo`` for the duration of the block.

    Adds ``str(repo.resolve())`` to the sentinel's path set on entry and
    restores the EXACT prior env-var state (present-with-prior-value, or
    absent) on exit -- including when the guarded body raises -- so nesting
    a call for a different repo composes safely and a leaked sentinel can
    never permanently false-block a later, legitimate call.
    """
    prior = os.environ.get(_GUARD_ENV_VAR)
    resolved = str(repo.resolve())
    active_paths = prior.split(os.pathsep) if prior is not None else []
    if resolved not in active_paths:
        active_paths.append(resolved)
    os.environ[_GUARD_ENV_VAR] = os.pathsep.join(active_paths)
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(_GUARD_ENV_VAR, None)
        else:
            os.environ[_GUARD_ENV_VAR] = prior


__all__ = ["is_routing_active_for", "routing_active_for"]
