"""Plugin-discovery resolve-and-probe helper (C2) -- RED scaffold (created by DISTILL).

language-adapter-registry-self-enforcement slice-03 (DDD-D4a / DDD-D7). The
composition-root read the live-registry conformance gate needs: resolve each
``nwave.lang.adapter`` entry point to its ``LanguageAdapterPlugin`` class, probe the
realized capability-method surface, and read ``target_language`` / ``port_coverage``.

This read does NOT exist anywhere yet (DDD-D7 / Reuse R5): ``doctor.py``'s
``_discover_registered_plugins`` returns only entry-point NAMES; it neither resolves-to-
class nor probes the realized capability surface. C2 BUILDS this read -- it is the single
resolve-and-probe implementation both the conformance gate (slice-03) and a future
doctor.py rewire would consume. doctor.py is left UNTOUCHED this feature (DDD-D7 option
ii, preserves the slice-01 ``_build_report`` AT).

HEXAGONAL SPLIT (DDD-D6): this module is the COMPOSITION ROOT for live discovery. It
owns the ``importlib.metadata`` read + plugin import/resolution + the structural
realized-surface probe (the ``CapabilityRegistry._adapter_covers`` shape). The pure 2-D
detector (``detect_per_plugin_capability_conformance`` in ``registry_conformance``) only
ever sees fully-resolved plain-data arguments -- it cannot itself degrade.

LOUD DEGRADATION (DDD-D5): when an entry point's target cannot be imported / resolved,
this helper raises a distinct ``DiscoveryResolutionError`` (NOT a fabricated empty
result, NOT a silent skip) -- the conformance-gate CLI shell maps that to the exit-3
INDETERMINATE loud lane. Resolution failure is a LOUD signal, never silent green.

PURE-PYTHON + ``importlib.metadata`` ONLY (D4): no git, no external CLI, no ``import
ast``. Target-machine-agnostic.

RED scaffold (Mandate-7 / ADR-025): the resolve-and-probe entrypoint raises
``AssertionError`` (the RED token -- NOT NotImplementedError, NOT ImportError) until
A_GREEN implements it. The ``DiscoveryResolutionError`` type is fully defined so the
exit-3 step can name the loud signal class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from importlib.metadata import EntryPoint


_ENTRY_POINT_GROUP = "nwave.lang.adapter"


class DiscoveryResolutionError(Exception):
    """A registered entry point could not be resolved-and-probed (DDD-D5 loud signal).

    Raised by :func:`resolve_and_probe_realized_surface` when an entry point's target
    module/class cannot be imported or instantiated. The conformance-gate CLI shell maps
    this to the exit-3 INDETERMINATE loud lane -- a DISTINCT loud failure, never a
    fabricated empty discovery set and never a silent green.

    ``plugin_id`` -- the name of the entry point that failed to resolve.
    ``reason`` -- a human-readable description of the underlying import/resolution failure.
    """

    def __init__(self, plugin_id: str, reason: str) -> None:
        self.plugin_id = plugin_id
        self.reason = reason
        super().__init__(
            f"language-adapter registry discovery is indeterminate: entry point "
            f"{plugin_id!r} could not be resolved ({reason})"
        )


@dataclass(frozen=True)
class DiscoveredPlugin:
    """A resolved-and-probed registered language-adapter plugin (port-exposed observable).

    ``plugin_id`` -- the entry-point name (the registered plugin id).
    ``target_language`` -- the plugin's declared ``target_language``.
    ``realized_capabilities`` -- the capability-method names the plugin realizes (the
                    structural ``CapabilityRegistry._adapter_covers`` probe result).
    ``covered_ports`` -- the plugin's declared ``port_coverage`` keys.
    """

    plugin_id: str
    target_language: str
    realized_capabilities: frozenset[str]
    covered_ports: frozenset[str]


def resolve_and_probe_realized_surface(
    required_capabilities: Iterable[str],
    entry_points_source: Iterable[EntryPoint],
) -> Mapping[str, frozenset[str]]:
    """Resolve each entry point to its plugin and probe its realized-capability surface.

    Returns a ``{plugin_id: realized_capability_method_names}`` mapping -- exactly the
    ``realized_by_plugin`` shape the pure 2-D detector
    ``detect_per_plugin_capability_conformance`` consumes. The composition root supplies
    ``entry_points_source`` (the real ``entry_points(group="nwave.lang.adapter")`` for the
    live gate; an injected iterable for the test's unresolvable / clean corpora) so this
    helper is parameterized over its discovery source (DDD-D6) -- it never hard-reads the
    process-global registry.

    For each entry point: ``.load()`` the target class, instantiate it, and probe which
    of ``required_capabilities`` the instance realizes (structural -- a capability is
    realized iff the instance exposes a callable method named for that capability value,
    the ``CapabilityRegistry._adapter_covers`` shape).

    LOUD DEGRADATION (DDD-D5): if any entry point's ``.load()`` or instantiation raises,
    this function raises :class:`DiscoveryResolutionError` -- never a fabricated empty
    mapping, never a silent skip.

    """
    required = frozenset(required_capabilities)
    realized_by_plugin: dict[str, frozenset[str]] = {}
    for entry_point in entry_points_source:
        plugin = _resolve_plugin(entry_point)
        realized_by_plugin[entry_point.name] = frozenset(
            capability
            for capability in required
            if _instance_realizes(plugin, capability)
        )
    return realized_by_plugin


def _resolve_plugin(entry_point: EntryPoint) -> object:
    """Load the entry point's target class and instantiate it (DDD-D5 loud on failure)."""
    try:
        plugin_class = entry_point.load()
        return plugin_class()
    except Exception as exc:
        raise DiscoveryResolutionError(entry_point.name, str(exc)) from exc


def _instance_realizes(plugin: object, capability: str) -> bool:
    """A capability is realized iff the instance exposes a callable method named for it."""
    return callable(getattr(plugin, capability, None))
