"""The plugin-populated runner registry -- name -> run-facet dispatch (C2).

ADR-RTR-001 D2/D6. Replaces the hardcoded ``if self.name == "pytest"`` dispatch
in ``RunnerAdapter.run`` (test_runner_port.py:89) with a registry a plugin
POPULATES: each ``LanguageAdapterPlugin.register_adapters(registry)`` writes its
concrete run-facet under the runner name ``TestRunnerPort.resolve`` returns. The
cargo run-facet registers under the EXISTING ``"cargo-test"`` token (D8 -- no
rename), so resolve -> registry-key -> plugin-registration agree by construction.

A run-facet is the ``run_*_scope(adapter, target_root, scoped_node_ids) ->
RunVerdict`` callable shape (``run_pytest_scope`` / ``run_cargo_scope``).

``GLOBAL_REGISTRY`` is the module-level registry the gate seeds + the port
consults. ``seed_runner_registry()`` is the D6 entry-points discovery: it
enumerates the ``nwave.lang.adapter`` entry-points group (``importlib.metadata``,
stdlib) and calls each discovered ``plugin.register_adapters(GLOBAL_REGISTRY)``.
It is a FUNCTION CALL (run from the gate preamble), NOT module-import-time, so the
bundle-scan "stdlib-only at import time" contract holds. Idempotent: re-seeding
re-registers the same token (a no-op overwrite).

stdlib only (``importlib.metadata`` + ``typing``).
"""

from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.test_runner_port import ListScope, RunnerAdapter, RunVerdict


class RunFacet(Protocol):
    """The concrete run-facet callable shape a plugin registers under a runner name.

    Mirrors ``run_pytest_scope`` / ``run_cargo_scope``: shell the target's own
    runner over the per-runner ``scoped_node_ids`` and map the outcome to a
    ``RunVerdict``. ``adapter`` is the ``RunnerAdapter`` ``RunnerAdapter.run`` passes
    (``self``) -- the concrete facets are typed to it, so the Protocol names it too.
    """

    def __call__(
        self,
        adapter: RunnerAdapter,
        target_root: Path,
        scoped_node_ids: tuple[str, ...],
    ) -> RunVerdict: ...


class ListFacet(Protocol):
    """The concrete enumerate-facet callable shape a plugin registers per runner.

    Mirrors ``list_pytest_scope`` / ``list_cargo_scope`` (ADR-FLOW-011 D5 -- the
    read counterpart of ``RunFacet``): enumerate the target's whole-tree test scope
    in the runner's own enumerate facet and return the ``ListScope`` node-id set the
    digest fingerprints. ``adapter`` is the ``RunnerAdapter`` ``RunnerAdapter.list_scope``
    passes (``self``).
    """

    def __call__(
        self,
        adapter: RunnerAdapter,
        target_root: Path,
    ) -> ListScope: ...


class RunnerRegistry:
    """A ``runner-name -> run-facet`` registry a plugin populates.

    ``register`` is what a plugin's ``register_adapters`` writes into; ``lookup``
    is what ``RunnerAdapter.run`` consults. An absent name returns ``None`` -- the
    port maps that to ``RunnerAdapterUnavailable`` (degrade-LOUD, never a silent
    pass).
    """

    def __init__(self) -> None:
        self._facets: dict[str, RunFacet] = {}
        self._list_facets: dict[str, ListFacet] = {}

    def register(self, name: str, run_facet: RunFacet) -> None:
        """Register ``run_facet`` under ``name`` (idempotent overwrite)."""
        self._facets[name] = run_facet

    def lookup(self, name: str) -> RunFacet | None:
        """Return the run-facet registered under ``name``, or ``None`` if absent."""
        return self._facets.get(name)

    def register_list(self, name: str, list_facet: ListFacet) -> None:
        """Register the enumerate-facet under ``name`` (idempotent overwrite, D5)."""
        self._list_facets[name] = list_facet

    def lookup_list(self, name: str) -> ListFacet | None:
        """Return the enumerate-facet registered under ``name``, or ``None``."""
        return self._list_facets.get(name)


GLOBAL_REGISTRY = RunnerRegistry()

_ENTRY_POINTS_GROUP = "nwave.lang.adapter"


def seed_runner_registry() -> None:
    """Populate ``GLOBAL_REGISTRY`` with the built-in + entry-point run-facets.

    Two sources, both seeded here (a function call from the gate preamble, NOT
    import-time, so the import surface stays stdlib-only -- the ``pytest``/plugin
    run-facet imports are LOCAL):

    * the ``pytest`` dogfood built-in (``run_pytest_scope``) -- always present in
      the nWave-dev tree, registered directly so the Python path resolves through
      the SAME registry dispatch as every other runner (no hardcoded branch).
    * D6 entry-points discovery: enumerate the ``nwave.lang.adapter`` group
      (stdlib ``importlib.metadata``), load each plugin class, and call
      ``register_adapters(GLOBAL_REGISTRY)`` (the cargo run-facet registers under
      ``"cargo-test"`` this way).

    Idempotent: re-seeding re-registers the same tokens (a no-op overwrite).
    """
    from des.adapters.driven.runner.cargo_runner import (
        list_cargo_scope,
        run_cargo_scope,
    )
    from des.adapters.driven.runner.go_runner import run_go_scope
    from des.adapters.driven.runner.pytest_runner import (
        list_pytest_scope,
        run_pytest_scope,
    )
    from des.adapters.driven.runner.vitest_runner import run_vitest_scope

    # In-tree built-in run-facets are DIRECT-registered (BUG C): the shared
    # ~/.claude/lib install is a sys.path INSERT, not a pip package, so the
    # entry-point discovery below is EMPTY there. cargo_runner lives in this tree
    # like pytest_runner, so register it directly -- same always-present guarantee
    # as pytest, zero-dependency on the install method. Entry-point discovery
    # stays ADDITIVE for EXTERNAL/paid language plugins.
    GLOBAL_REGISTRY.register("pytest", run_pytest_scope)
    GLOBAL_REGISTRY.register("cargo-test", run_cargo_scope)
    GLOBAL_REGISTRY.register("go-test", run_go_scope)
    GLOBAL_REGISTRY.register("vitest", run_vitest_scope)
    # The enumerate (list) facets (ADR-FLOW-011 D5 -- the digest's read counterpart):
    # only the pytest dogfood + cargo enumerate facets are built in this slice
    # (slice-03 wires go/vitest). pytest is registered as one row among equals so
    # `list_scope` dispatches uniformly, never a hardcoded pytest enumerate.
    GLOBAL_REGISTRY.register_list("pytest", list_pytest_scope)
    GLOBAL_REGISTRY.register_list("cargo-test", list_cargo_scope)
    for entry_point in metadata.entry_points(group=_ENTRY_POINTS_GROUP):
        plugin_cls = entry_point.load()
        plugin_cls().register_adapters(GLOBAL_REGISTRY)


__all__ = [
    "GLOBAL_REGISTRY",
    "ListFacet",
    "RunFacet",
    "RunnerRegistry",
    "seed_runner_registry",
]
