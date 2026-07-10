"""Composition root -- resolve plugins, AST-stub-probe declared-covered ports (slice-02).

language-port-realization-gate, slice-02 (DELIVER, A_GREEN). Wires the real
world (``importlib.metadata`` entry-point discovery, ``inspect``/``ast``
source reading) to the slice-01 pure detector
``des.testarch.rules.registry_conformance.detect_port_realization_conformance``.

Pipeline, per plugin:

  1. Read the plugin's self-declared ``port_coverage`` mapping
     (``LanguageAdapterPlugin.port_coverage``).
  2. Call ``plugin.register_adapters(<capturing registry>)`` with a registry
     double duck-typed against ``LanguageAdapterRegistry``'s 3 new
     ``register_contract_gate`` / ``register_environmental_e2e`` /
     ``register_robustness_density`` methods (``runner_registry.py``) --
     capturing whichever facet instance each call receives, independent of
     the ``name`` (tool-token) argument the plugin passes.
  3. For every DECLARED-covered (``True``) port, AST-stub-probe the captured
     facet's backing method(s) for that port: a method is a pure stub iff
     ``inspect.getsource`` + ``ast.parse`` shows its body reduces to a single
     ``raise NotImplementedError(...)`` (optional leading docstring only). A
     port is stub-backed iff EVERY method its Protocol declares is,
     individually, a pure stub (or absent from the facet entirely).
  4. Feed the resulting ``{plugin_id: {port: declared}}`` +
     ``{plugin_id: {port: is_stub}}`` maps to
     ``detect_port_realization_conformance`` and return its verdict.

Effect-Isolation (Earned-Trust 3-layer): the probe is STATIC -- it reads
source only via ``inspect.getsource`` + ``ast.parse`` and NEVER invokes
``build()``/``install()``/the probed method itself, nor any
``plugin.probe()``.

Degrade-LOUD: an unresolvable (``OSError``/``TypeError`` from
``inspect.getsource``) or unparsable (``SyntaxError`` from ``ast.parse``)
method source raises ``PortRealizationProbeError`` with the plugin/port/
method context -- never a silent pass, never a raw traceback from the
underlying stdlib exception. Likewise, a declared-covered port outside this
slice's known 3-port catalog raises ``PortRealizationProbeError`` rather than
guessing at its backing-method surface.

Imports: ``ast``, ``inspect``, ``textwrap``, ``importlib.metadata`` (stdlib)
plus the slice-01 detector (``des.testarch.rules.registry_conformance``) and
the ``LanguageAdapterPlugin`` port type -- stdlib + des only, F-D-09 clean,
no third-party.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from importlib import metadata
from typing import TYPE_CHECKING

from des.testarch.rules.registry_conformance import (
    PortRealizationVerdict,
    detect_port_realization_conformance,
)


if TYPE_CHECKING:
    from collections.abc import Iterable

    from des.ports.language_adapter_plugin import LanguageAdapterPlugin


_ENTRY_POINTS_GROUP = "nwave.lang.adapter"

RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"

# The backing-method surface each port's Protocol declares (mirrors
# ContractGatePort / EnvironmentalE2EPort / RobustnessDensityPort under
# src/des/ports/driven_ports/). A port is stub-backed iff ALL of these
# methods, individually, are pure NotImplementedError stubs.
_PORT_METHOD_NAMES: dict[str, tuple[str, ...]] = {
    RUN_CONTRACT_GATE: ("collect_scope", "run_suite"),
    VERIFY_ENVIRONMENTAL_E2E: ("build", "install", "run_against_installed"),
    CHECK_ROBUSTNESS_DENSITY: ("covered_domain_ids",),
}


class PortRealizationProbeError(RuntimeError):
    """Raised when the AST stub-probe cannot resolve a backing method's classification.

    Covers: unreadable source (``OSError``/``TypeError`` from
    ``inspect.getsource``), unparsable source (``SyntaxError`` from
    ``ast.parse``), and a declared-covered port outside this slice's known
    port catalog. Degrade-LOUD -- never a silent pass, never a bare stdlib
    traceback.
    """


class _CapturingRegistry:
    """Capturing double duck-typed against ``LanguageAdapterRegistry``.

    Exposes exactly the 3 method names a ``LanguageAdapterPlugin.register_adapters``
    call uses to wire its new-port facets (``register_contract_gate`` /
    ``register_environmental_e2e`` / ``register_robustness_density``) and
    captures whichever facet instance each call receives, independent of the
    ``name`` (tool-token) argument.
    """

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}

    def register_contract_gate(self, name: str, facet: object) -> None:
        del name
        self.captured[RUN_CONTRACT_GATE] = facet

    def register_environmental_e2e(self, name: str, facet: object) -> None:
        del name
        self.captured[VERIFY_ENVIRONMENTAL_E2E] = facet

    def register_robustness_density(self, name: str, facet: object) -> None:
        del name
        self.captured[CHECK_ROBUSTNESS_DENSITY] = facet


def _is_pure_notimplementederror_stub(
    method: object, *, plugin_id: str, port: str, method_name: str
) -> bool:
    """STATIC AST probe -- reads ``method``'s source, NEVER invokes it.

    A pure stub is a body reducible to a single ``raise
    NotImplementedError(...)`` statement, with an optional leading docstring.
    """
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError) as exc:
        raise PortRealizationProbeError(
            f"cannot read source for {plugin_id}.{port}.{method_name}: {exc}"
        ) from exc

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError as exc:
        raise PortRealizationProbeError(
            f"cannot parse source for {plugin_id}.{port}.{method_name}: {exc}"
        ) from exc

    func_def = tree.body[0] if tree.body else None
    if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise PortRealizationProbeError(
            f"source for {plugin_id}.{port}.{method_name} is not a function "
            "definition -- cannot AST-stub-probe"
        )

    body = list(func_def.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    if len(body) != 1 or not isinstance(body[0], ast.Raise):
        return False

    exc_node = body[0].exc
    callee = exc_node.func if isinstance(exc_node, ast.Call) else exc_node
    return isinstance(callee, ast.Name) and callee.id == "NotImplementedError"


def _probe_port_is_stub(plugin_id: str, port: str, facet: object | None) -> bool:
    """Classify a declared-covered port's backing facet as stub-backed or not.

    A missing facet (declared ``True`` but never captured via
    ``register_adapters``) is treated as fully unrealized (stub-backed). A
    declared-covered port outside the known 3-port catalog degrades LOUD.
    """
    if facet is None:
        return True

    method_names = _PORT_METHOD_NAMES.get(port)
    if method_names is None:
        raise PortRealizationProbeError(
            f"unknown port {port!r} declared by plugin {plugin_id!r} -- no "
            "backing-method surface registered for the AST stub-probe"
        )

    facet_type = type(facet)
    is_stub_per_method = []
    for method_name in method_names:
        method = getattr(facet_type, method_name, None)
        if method is None:
            is_stub_per_method.append(True)
            continue
        is_stub_per_method.append(
            _is_pure_notimplementederror_stub(
                method, plugin_id=plugin_id, port=port, method_name=method_name
            )
        )
    return all(is_stub_per_method)


def _discover_registered_plugins() -> list[LanguageAdapterPlugin]:
    """Resolve the registered ``nwave.lang.adapter`` entry-points.

    Default resolver used only when the caller omits ``plugins``. Untested
    by this slice's AT (Slice Plan justification: the AT always supplies an
    explicit ``plugins`` iterable, bypassing entry-point discovery).
    """
    discovered: list[LanguageAdapterPlugin] = []
    for entry_point in metadata.entry_points(group=_ENTRY_POINTS_GROUP):
        plugin_cls = entry_point.load()
        discovered.append(plugin_cls())
    return discovered


def resolve_and_probe_port_realization(
    plugins: Iterable[LanguageAdapterPlugin] | None = None,
) -> PortRealizationVerdict:
    """Resolve plugins, AST-stub-probe declared-covered ports, return the verdict.

    ``plugins`` is an ``Iterable[LanguageAdapterPlugin]``; when omitted, the
    registered ``nwave.lang.adapter`` entry-points are resolved instead
    (untested by this slice's AT).

    Pure over its resolved ``plugins`` argument (a real installed
    environment's ``entry_points()`` read + each adapter's on-disk source
    are the only external reads; the probe never mutates or invokes
    anything).
    """
    resolved = list(plugins) if plugins is not None else _discover_registered_plugins()

    plugin_ports: dict[str, dict[str, bool]] = {}
    is_stub_by_plugin: dict[str, dict[str, bool]] = {}

    for plugin in resolved:
        plugin_id = plugin.target_language
        declared_ports = dict(plugin.port_coverage)
        plugin_ports[plugin_id] = declared_ports

        registry = _CapturingRegistry()
        plugin.register_adapters(registry)

        is_stub_map: dict[str, bool] = {}
        for port, declared in declared_ports.items():
            if not declared:
                continue
            facet = registry.captured.get(port)
            is_stub_map[port] = _probe_port_is_stub(plugin_id, port, facet)
        is_stub_by_plugin[plugin_id] = is_stub_map

    return detect_port_realization_conformance(plugin_ports, is_stub_by_plugin)


__all__ = [
    "PortRealizationProbeError",
    "resolve_and_probe_port_realization",
]
