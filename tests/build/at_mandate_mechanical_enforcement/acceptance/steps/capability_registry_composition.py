"""Composition-root service for the capability-registry SSOT AT (slice-02).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL registry entrypoint
``des.testarch.capabilities.build_registry`` — the driving port the registry is
authored against (ADR-TEST-002 D-C; feature-delta Driving Ports). The reference
language adapter it checks is the production ``PythonAstAdapter``; the planted-gap
adapter is the slice-02 golden fixture.

Honest tagging: this is an in-process query of the registry catalog. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.capabilities import (
    Capability,
    ConformanceVerdict,
    build_registry,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.capability_registry.clean_complete_adapter import (
    CompleteFixtureAdapter,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.capability_registry.violation_missing_capability_adapter import (
    MissingCapabilityFixtureAdapter,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    CONSUMED_SO_FAR,
    ConformanceOutcome,
)


class CapabilityRegistryService:
    """Drives the real capability-registry SSOT + conformance check."""

    def __init__(self) -> None:
        self._registry = build_registry()

    def required_capabilities(self) -> frozenset[Capability]:
        """The complete capability contract the registry enumerates (port-observable)."""
        return self._registry.required_capabilities()

    def consumed_capabilities(self) -> frozenset[Capability]:
        """The capabilities the gates authored so far actually consume."""
        return CONSUMED_SO_FAR

    def check_reference_adapter(self) -> ConformanceVerdict:
        """Check the production Python adapter against the consumed-so-far subset."""
        return self._registry.check_conformance(
            PythonAstAdapter(), required=CONSUMED_SO_FAR
        )

    def check_complete_adapter(self) -> ConformanceVerdict:
        """Check the complete golden-fixture adapter against the full contract."""
        return self._registry.check_conformance(
            CompleteFixtureAdapter(), required=self.required_capabilities()
        )

    def check_missing_capability_adapter(self) -> ConformanceVerdict:
        """Check the planted-gap adapter against the full contract (recall half)."""
        return self._registry.check_conformance(
            MissingCapabilityFixtureAdapter(), required=self.required_capabilities()
        )

    @staticmethod
    def outcome_of(verdict: ConformanceVerdict) -> ConformanceOutcome:
        """Project the conformance verdict onto the port-exposed outcome enum."""
        return (
            ConformanceOutcome.CONFORMANT
            if verdict.conformant
            else ConformanceOutcome.NON_CONFORMANT
        )


def build_service() -> CapabilityRegistryService:
    """Composition-root entry — the production object graph for the registry AT."""
    return CapabilityRegistryService()
