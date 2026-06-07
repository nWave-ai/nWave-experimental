"""Child-process worker for canonical contract-scope collection (ADR-001).

The contract gate derives its gate-scope digest from pytest's IN-PROCESS
collection API (``session.items``) rather than from parsing the collapse-prone
``-q`` collect STDOUT. But ``run_contract_gate.main`` / ``gate_scope_digest``
are also called DIRECTLY in-process by other tests inside a live pytest session
-- running ``pytest.main()`` there would nest a session inside a session and
corrupt both. So the in-process collection is hoisted into THIS short-lived
worker subprocess: ``pytest.main()`` always runs in a fresh child interpreter,
never nested, regardless of whether the gate caller is itself under pytest.

Protocol (single source of truth, mirrored in ``run_contract_gate``). The
worker is spawned by FILE PATH (``<python> <path-to-this-file> --repo ...``),
never as a ``des.cli`` import module -- an installed customer tree has no
``des`` package importable by an arbitrary interpreter::

    <python> _collect_scope_worker.py --repo <repo> [--path <p> ...]

* exit 0 + a single ``NWAVE_COLLECT_SCOPE:{json}`` line on stdout when the
  collection succeeded (pytest exit 0 or 5);
* exit 2 + a ``NWAVE_COLLECT_SCOPE_ERROR:{json}`` line on stdout when pytest's
  own collection failed (non-(0,5) exit).

The JSON payload carries the ADR-001 cardinalities from the SAME session:
``node_ids`` (the sorted canonical class-aware ``fspath::Class::...::method``
identity set -- see ``_identity_of``),
``collected_count`` (``len(session.items)`` at collection finish) and
``modify_count`` (``len(items)`` captured one lifecycle phase UPSTREAM, at
``pytest_collection_modifyitems``). The two-signal pair lets the parent detect
a lying tree that empties ``session.items`` in a ``tryfirst``
``pytest_collection_finish`` hook: such a tamper cannot reach back into the
already-completed ``modifyitems`` phase, so ``modify_count`` stays truthful
while ``collected_count`` reads zero. pytest's own collection chatter goes to
the worker's stderr and is discarded by the parent -- the parent reads ONLY
the marker line, so the gate's stdout stays a clean single digest line
(idempotence contract).

stdlib + pytest only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest


# The contract gate scope -- the exact pre-push marker expression. Kept in sync
# with run_contract_gate._CONTRACT_MARKER (the parent passes nothing that would
# let these drift: both name the same frozen pre-push contract).
_CONTRACT_MARKER = "unit or integration or acceptance"

_RESULT_PREFIX = "NWAVE_COLLECT_SCOPE:"
_ERROR_PREFIX = "NWAVE_COLLECT_SCOPE_ERROR:"

# The ``--run`` branch marker (the arch-invariant collect-AND-RUN path). DISTINCT
# from the ``--collect-only`` markers above: the run branch RUNS the contract set
# over a path subset and reports the run outcome (pytest exit + collected count),
# never node-ids. The collect-only path stays byte-for-byte intact -- its
# ``--collect-only`` idempotence + the parent's two-signal lying-tree guard
# depend on collect-only and MUST NOT also run.
_RUN_RESULT_PREFIX = "NWAVE_RUN_SCOPE:"


class _Collector:
    """Capture the collected scope across TWO collection-lifecycle phases.

    The contract gate's fail-closed guard needs two independent count signals
    from the same session (ADR-001 two-signal lying-tree detection):

    * ``modify_count`` -- ``len(items)`` at ``pytest_collection_modifyitems``,
      one lifecycle phase UPSTREAM of ``pytest_collection_finish``. This hook
      runs with ``trylast=True`` so it observes the fully-collected item list
      AFTER every other ``modifyitems`` plugin. A tamper that empties
      ``session.items`` in a ``tryfirst pytest_collection_finish`` hook fires
      strictly later, so it cannot forge this count back to zero.
    * ``collected_count`` -- ``len(session.items)`` at collection finish, plus
      the canonical identities. A lying tree drives this to zero.

    ``modify_count > 0`` while ``collected_count == 0`` is the unforgeable
    lying-tree signature the parent fails closed on.
    """

    def __init__(self) -> None:
        self.identities: list[str] = []
        self.collected_count: int = 0
        self.modify_count: int = 0
        self.crashing_module: str | None = None

    def pytest_collectreport(self, report: object) -> None:
        # KPI-3 named-module capture: record the FIRST failed collector's
        # nodeid (the repo-relative file path of the module whose import
        # raised). A collection crash names a module here while the gate's
        # error path otherwise carries only the bare pytest exit code.
        if self.crashing_module is not None:
            return
        if getattr(report, "failed", False):
            nodeid = getattr(report, "nodeid", None)
            if isinstance(nodeid, str) and nodeid:
                self.crashing_module = nodeid

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(
        self, session: object, config: object, items: list[object]
    ) -> None:
        self.modify_count = len(items)

    def pytest_collection_finish(self, session: object) -> None:
        items = list(getattr(session, "items", []))
        self.collected_count = len(items)
        config = getattr(session, "config", None)
        rootpath = Path(str(getattr(config, "rootpath", Path.cwd())))
        self.identities = [_identity_of(item, rootpath) for item in items]


def _identity_of(item: object, rootpath: Path) -> str:
    """Return the canonical repo-relative class-aware identity.

    The identity is ``f"{repo-relative-fspath}::{Class::...::method}"`` -- the
    full ``parent`` chain from the item up to (but excluding) the Module node,
    so sibling test classes in one file that share a method name stay distinct.
    Using the bare ``item.name`` collapses N classes-with-the-same-method into
    one identity, undercounting the canonical scope by N-1 (the gap this gate
    exists to catch). ``item.nodeid`` is NOT used: pytest-bdd / docstring-titled
    items render multi-line docstrings into the nodeid, which would manufacture
    massive false collisions in the other direction.
    """
    fspath = Path(str(getattr(item, "path", getattr(item, "fspath", ""))))
    try:
        relative = fspath.relative_to(rootpath)
    except ValueError:
        relative = fspath
    chain: list[str] = []
    node: object | None = item
    module_name = fspath.name
    while node is not None and getattr(node, "name", None) != module_name:
        name = getattr(node, "name", None)
        if name is not None:
            chain.append(str(name))
        node = getattr(node, "parent", None)
    chain.reverse()
    return f"{relative.as_posix()}::{'::'.join(chain)}"


def _run_scope(repo: str, paths: list[str]) -> int:
    """RUN the contract set over ``paths`` and emit the run-outcome marker line.

    The ``--run`` branch of the single pytest-argv seam (DDD-12): it drops
    ``--collect-only`` and RUNS ``pytest.main`` over the given path subset under
    the SAME ``-m "unit or integration or acceptance"`` contract marker and the
    same ``no:cacheprovider`` hygiene. It reports the run OUTCOME --
    ``{"pytest_exit_code": N, "collected_count": M}`` -- so the parent can map a
    RED arch run to a refusal AND a zero-collected arch set to the M-1 floor.

    The arch-invariant set is a self-contained AST scanner class (it reads
    ``src/des/**`` as text, asserts at run-time), so a forbidden import / inline
    spawn / seeded assertion surfaces ONLY here, at run-time -- the collect-only
    path is structurally blind to it.
    """
    collector = _Collector()
    pytest_argv = [
        "-m",
        _CONTRACT_MARKER,
        "-p",
        "no:cacheprovider",
        "--rootdir",
        repo,
        *(paths if paths else [repo]),
    ]
    exit_code = int(pytest.main(pytest_argv, plugins=[collector]))
    print(
        _RUN_RESULT_PREFIX
        + json.dumps(
            {
                "pytest_exit_code": exit_code,
                "collected_count": collector.collected_count,
            }
        ),
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Collect the contract scope in-process and emit the marker line."""
    parser = argparse.ArgumentParser(prog="des-collect-scope-worker")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.run:
        return _run_scope(args.repo, args.path)

    collector = _Collector()
    pytest_argv = [
        "-m",
        _CONTRACT_MARKER,
        "--collect-only",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        args.repo,
        *(args.path if args.path else [args.repo]),
    ]
    exit_code = int(pytest.main(pytest_argv, plugins=[collector]))
    if exit_code not in (0, 5):
        error_payload: dict[str, object] = {"pytest_exit_code": exit_code}
        if collector.crashing_module is not None:
            error_payload["crashing_module"] = collector.crashing_module
        print(
            _ERROR_PREFIX + json.dumps(error_payload),
            flush=True,
        )
        return 2
    print(
        _RESULT_PREFIX
        + json.dumps(
            {
                "node_ids": collector.identities,
                "collected_count": collector.collected_count,
                "modify_count": collector.modify_count,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
