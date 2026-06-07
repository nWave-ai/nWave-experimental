"""Composition-root service for the drift-guard conformance gate (slice-12).

Provenance: feature `at-mandate-mechanical-enforcement`, slice-12 (DISTILL,
per-slice JIT). The drift-guard hardening turns the registry/vocabulary
conformance this feature ships on the feature's OWN testarch substrate
(Earned-Trust self-application, ADR-TEST-002 D-C/D-E; feature-delta slice-plan
row 229).

Mandate-12 (criteria 2+3): the conformance business logic lives in the production
rule module ``des.testarch.rules.registry_conformance`` (the single source of
truth — RED scaffold until A_GREEN); this service is the thin composition root
that drives the two parametrized ``detect`` entrypoints and projects their
port-exposed verdicts onto the acceptance vocabulary. Step bodies invoke this
service and never inline logic.

Two corpora per facet (the ADR-TEST-002 D-E recall/precision golden-fixture shape,
the same as every Tier-S gate slices 01-09):

  * RECALL — drives the detectors against the FROZEN drifted snapshot
    (``fixtures/registry_conformance/violation_drifted_snapshot.py``) that permanently carries
    both drift facets. Stays GREEN forever — proves the gate CAN bite.
  * PRECISION — drives the detectors against the LIVE production surface, READ at
    runtime (criterion 4 — the live surface is READ, never transcribed): the actual
    ``PBT_FORBIDDEN_LAYERS`` + ``AUDITED_LAYERS`` classification sets, the actual
    reference-adapter producible-layer surface, the actual ``Capability`` enum +
    registry, and the actual ``PythonAstAdapter`` method-name surface. RED NOW (the
    live surface carries ``fs_acceptance`` + the dead caps), GREEN after A_GREEN
    cleans it. THIS is the scenario the drops flip RED→GREEN.

Driving port: the parametrized conformance-rule entrypoints
``detect_layer_value_coverage`` + ``detect_real_adapter_capability_conformance``
(``des.testarch.rules.registry_conformance``). The rules cross-check the supplied
vocabulary surfaces as plain data — importing the production surface here to READ
it for the precision corpus is the correct shape (ADR-TEST-002 D-A carve-out: the
no-``import ast`` constraint binds the Tier-S source-scanning rules, not this
self-conformance check of this package's own vocabulary).

Honest tagging: an in-process introspection of the testarch substrate — @component
(auto-``unit`` under ``tests/build/``), NEVER @wiring_e2e/@subprocess. No spawn, no
real I/O.

RED scaffold (Mandate-7 / ADR-025): the driven ``detect_*`` functions raise
``AssertionError`` (the RED token — NOT NotImplementedError, NOT ImportError) until
A_GREEN implements them.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import (
    _SEGMENT_TO_LAYER as REFERENCE_ADAPTER_SEGMENT_TO_LAYER,
)
from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.capabilities import build_registry
from des.testarch.rules.assert_state_delta import AUDITED_LAYERS
from des.testarch.rules.pbt_layer_mode import PBT_FORBIDDEN_LAYERS
from des.testarch.rules.registry_conformance import (
    CapabilityRealizationVerdict,
    LayerValueCoverageVerdict,
    detect_layer_value_coverage,
    detect_real_adapter_capability_conformance,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.registry_conformance.clean_conformant_snapshot import (
    CONFORMANT_ADAPTER_METHOD_NAMES,
    CONFORMANT_CLASSIFICATION_SETS,
    CONFORMANT_PRODUCIBLE_LAYERS,
    CONFORMANT_REGISTERED_CAPABILITIES,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.registry_conformance.violation_drifted_snapshot import (
    DRIFTED_ADAPTER_METHOD_NAMES,
    DRIFTED_CLASSIFICATION_SETS,
    DRIFTED_PRODUCIBLE_LAYERS,
    DRIFTED_REGISTERED_CAPABILITIES,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    ConformanceOutcomeKind,
)


class RegistryConformanceService:
    """Drives the parametrized testarch drift-guard conformance rules.

    Recall corpus = the frozen drifted snapshot; precision corpus = the live
    production surface read at runtime.
    """

    # --- RECALL (frozen drifted snapshot — green forever) ------------------

    def layer_value_coverage_of_drifted_snapshot(self) -> LayerValueCoverageVerdict:
        """Drive the Layer-value detector against the frozen drifted snapshot."""
        return detect_layer_value_coverage(
            DRIFTED_CLASSIFICATION_SETS, DRIFTED_PRODUCIBLE_LAYERS
        )

    def capability_conformance_of_drifted_snapshot(
        self,
    ) -> CapabilityRealizationVerdict:
        """Drive the capability detector against the frozen drifted snapshot."""
        return detect_real_adapter_capability_conformance(
            DRIFTED_REGISTERED_CAPABILITIES, DRIFTED_ADAPTER_METHOD_NAMES
        )

    # --- PRECISION (frozen conformant snapshot — clean golden complement) --

    def layer_value_coverage_of_clean_snapshot(self) -> LayerValueCoverageVerdict:
        """Drive the Layer-value detector against the frozen conformant snapshot."""
        return detect_layer_value_coverage(
            CONFORMANT_CLASSIFICATION_SETS, CONFORMANT_PRODUCIBLE_LAYERS
        )

    def capability_conformance_of_clean_snapshot(
        self,
    ) -> CapabilityRealizationVerdict:
        """Drive the capability detector against the frozen conformant snapshot."""
        return detect_real_adapter_capability_conformance(
            CONFORMANT_REGISTERED_CAPABILITIES, CONFORMANT_ADAPTER_METHOD_NAMES
        )

    # --- PRECISION (live production surface, read at runtime) --------------

    def layer_value_coverage_of_live_substrate(self) -> LayerValueCoverageVerdict:
        """Drive the Layer-value detector against the LIVE rule sets + adapter.

        Reads (never transcribes) the actual ``PBT_FORBIDDEN_LAYERS`` +
        ``AUDITED_LAYERS`` classification sets and the actual reference-adapter
        producible-layer surface.
        """
        return detect_layer_value_coverage(
            self._live_classification_sets(), self._live_producible_layers()
        )

    def capability_conformance_of_live_substrate(
        self,
    ) -> CapabilityRealizationVerdict:
        """Drive the capability detector against the LIVE registry + real adapter.

        Reads (never transcribes) the actual registered ``Capability`` values and
        the actual ``PythonAstAdapter`` method-name surface.
        """
        return detect_real_adapter_capability_conformance(
            self._live_registered_capabilities(), self._live_adapter_method_names()
        )

    # --- live-surface readers (criterion 4: READ, never transcribe) --------

    @staticmethod
    def _live_classification_sets() -> dict[str, frozenset[str]]:
        """The actual rule classification sets, read live from the rule modules."""
        return {
            "pbt_layer_mode.PBT_FORBIDDEN_LAYERS": frozenset(PBT_FORBIDDEN_LAYERS),
            "assert_state_delta.AUDITED_LAYERS": frozenset(AUDITED_LAYERS),
        }

    @staticmethod
    def _live_producible_layers() -> frozenset[str]:
        """The reference adapter's producible ``Layer`` values, read live."""
        return frozenset(
            layer.value for layer in REFERENCE_ADAPTER_SEGMENT_TO_LAYER.values()
        )

    @staticmethod
    def _live_registered_capabilities() -> frozenset[str]:
        """The registered ``Capability`` values, read live from the registry."""
        return frozenset(
            capability.value for capability in build_registry().required_capabilities()
        )

    @staticmethod
    def _live_adapter_method_names() -> frozenset[str]:
        """The real ``PythonAstAdapter`` callable method names, read live."""
        adapter = PythonAstAdapter()
        return frozenset(
            name for name in dir(adapter) if callable(getattr(adapter, name))
        )

    # --- verdict → outcome projection --------------------------------------

    @staticmethod
    def layer_outcome_of(
        verdict: LayerValueCoverageVerdict,
    ) -> ConformanceOutcomeKind:
        """Project the Layer-value verdict onto the port-exposed outcome enum."""
        return (
            ConformanceOutcomeKind.FLAGGED
            if verdict.flagged
            else ConformanceOutcomeKind.CONFORMANT
        )

    @staticmethod
    def capability_outcome_of(
        verdict: CapabilityRealizationVerdict,
    ) -> ConformanceOutcomeKind:
        """Project the capability verdict onto the port-exposed outcome enum."""
        return (
            ConformanceOutcomeKind.FLAGGED
            if verdict.flagged
            else ConformanceOutcomeKind.CONFORMANT
        )


def build_service() -> RegistryConformanceService:
    """Composition-root entry — the production object graph for the conformance AT."""
    return RegistryConformanceService()
