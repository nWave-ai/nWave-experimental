"""Composition-root service for the per-plugin x per-capability conformance gate.

Provenance: feature ``language-adapter-registry-self-enforcement``, slice-01
(DISTILL, per-slice JIT; DDD-D3a plugin-axis ruling). The walking-skeleton vertical:
the slice-12 ``detect_real_adapter_capability_conformance`` detector GENERALIZED from
1-D (caps x one adapter) to the 2-D cross-product (caps x every registered plugin's
realized surface). slice-01 tests the PURE 2-D rule (C1) over INJECTED surfaces — it
does NOT read the live ``nwave.lang.adapter`` registry (that is C2, slice-03 /
DDD-D4a).

Mandate-12 (criteria 2+3): the 2-D conformance business logic lives in the production
rule module ``des.testarch.rules.registry_conformance`` (the single source of truth —
RED scaffold until A_GREEN); this service is the thin composition root that drives the
``detect_per_plugin_capability_conformance`` entrypoint over the three corpora and
projects its port-exposed verdict onto the acceptance vocabulary. Step bodies invoke
this service and never inline logic.

Three corpora (the DDD-D3a recall/precision golden-fixture shape, mirroring slice-12):

  * RECALL — the FROZEN unrealized-pair snapshot
    (``fixtures/per_plugin_capability/violation_unrealized_pair_snapshot.py``) that
    permanently carries a registered-but-unrealized ``(plugin, capability)`` pair.
    GREEN forever once the detector exists — proves the 2-D gate CAN bite.
  * PRECISION (frozen) — the FROZEN all-realized snapshot
    (``fixtures/per_plugin_capability/clean_all_realized_snapshot.py``) in which every
    plugin realizes every required capability. CONFORMANT — the fail-closed bar.
  * PRECISION-LIVE — the real ``PythonAstAdapter`` method-surface INJECTED as a
    single-element ``{"python": <realized capability-method names>}`` map (treated as
    the de-facto reference adapter, DDD-D3a — NOT asserted to be a registered plugin).
    The required-capability obligation set is READ live from the registry
    (``build_registry().required_capabilities()``). ``PythonAstAdapter`` realizes all 9
    required capabilities, so injected-as-a-realized-map it is CONFORMANT. RED NOW (the
    2-D detector is a scaffold), GREEN EXACTLY when A_GREEN implements C1. THIS is the
    falsifiable flip.

Driving port: the pure ``detect_per_plugin_capability_conformance`` entrypoint
(``des.testarch.rules.registry_conformance``). The rule cross-checks the supplied
surfaces as plain data — importing the production ``PythonAstAdapter`` + registry here
to READ them for the precision-live corpus is the correct shape (the ADR-TEST-002 D-A
no-``import ast`` constraint binds the Tier-S source-scanning rules, not this
in-memory conformance check of registered vocabulary).

Honest tagging: an in-process introspection of the testarch substrate — @component
(auto-``unit`` under ``tests/build/``), NEVER @wiring_e2e/@subprocess. No spawn, no
real I/O.

RED scaffold (Mandate-7 / ADR-025): the driven ``detect_per_plugin_capability_conformance``
function raises ``AssertionError`` (the RED token — NOT NotImplementedError, NOT
ImportError) until A_GREEN implements it.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.capabilities import build_registry
from des.testarch.rules.registry_conformance import (
    PerPluginCapabilityVerdict,
    detect_per_plugin_capability_conformance,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.per_plugin_capability.clean_all_realized_snapshot import (
    CONFORMANT_REALIZED_BY_PLUGIN,
    CONFORMANT_REQUIRED_CAPABILITIES,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.per_plugin_capability.violation_unrealized_pair_snapshot import (
    PLANTED_REALIZED_BY_PLUGIN,
    PLANTED_REQUIRED_CAPABILITIES,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.domain_types import (
    ConformanceOutcome,
)


# The injected reference-adapter plugin id for the precision-live corpus. NOT a
# registered ``nwave.lang.adapter`` plugin id — the de-facto reference realized map
# (DDD-D3a). The live-registry read is slice-03's concern (C2 / DDD-D4a).
_REFERENCE_ADAPTER_PLUGIN_ID = "python"


class PerPluginCapabilityConformanceService:
    """Drives the generalized 2-D per-plugin x per-capability conformance rule.

    Recall corpus = the frozen unrealized-pair snapshot; frozen precision corpus =
    the frozen all-realized snapshot; precision-live corpus = the real
    ``PythonAstAdapter`` method-surface injected as a single-element realized map.
    """

    # --- RECALL (frozen unrealized-pair snapshot — green forever) ----------

    def conformance_of_unrealized_pair_snapshot(self) -> PerPluginCapabilityVerdict:
        """Drive the 2-D detector against the frozen unrealized-pair snapshot."""
        return detect_per_plugin_capability_conformance(
            PLANTED_REQUIRED_CAPABILITIES, PLANTED_REALIZED_BY_PLUGIN
        )

    # --- PRECISION (frozen all-realized snapshot — clean golden complement) -

    def conformance_of_all_realized_snapshot(self) -> PerPluginCapabilityVerdict:
        """Drive the 2-D detector against the frozen all-realized snapshot."""
        return detect_per_plugin_capability_conformance(
            CONFORMANT_REQUIRED_CAPABILITIES, CONFORMANT_REALIZED_BY_PLUGIN
        )

    # --- PRECISION-LIVE (injected reference-adapter surface) ----------------

    def conformance_of_injected_reference_adapter(self) -> PerPluginCapabilityVerdict:
        """Drive the 2-D detector against the injected reference-adapter surface.

        The required-capability obligation set is read live from the registry; the
        plugin axis is the real ``PythonAstAdapter`` method-surface injected as a
        single-element realized map (DDD-D3a — de-facto reference adapter, NOT a
        registered-plugin assertion).
        """
        return detect_per_plugin_capability_conformance(
            self._live_required_capabilities(),
            {_REFERENCE_ADAPTER_PLUGIN_ID: self._reference_adapter_method_names()},
        )

    # --- live-surface readers (READ, never transcribe) ----------------------

    @staticmethod
    def _live_required_capabilities() -> frozenset[str]:
        """The registered ``Capability`` values, read live from the registry."""
        return frozenset(
            capability.value for capability in build_registry().required_capabilities()
        )

    @staticmethod
    def _reference_adapter_method_names() -> frozenset[str]:
        """The real ``PythonAstAdapter`` callable method names, read live."""
        adapter = PythonAstAdapter()
        return frozenset(
            name for name in dir(adapter) if callable(getattr(adapter, name))
        )

    # --- verdict -> outcome projection --------------------------------------

    @staticmethod
    def outcome_of(verdict: PerPluginCapabilityVerdict) -> ConformanceOutcome:
        """Project the 2-D verdict onto the port-exposed outcome enum."""
        return (
            ConformanceOutcome.FLAGGED
            if verdict.flagged
            else ConformanceOutcome.CONFORMANT
        )


def build_service() -> PerPluginCapabilityConformanceService:
    """Composition-root entry — the production object graph for the slice-01 AT."""
    return PerPluginCapabilityConformanceService()
