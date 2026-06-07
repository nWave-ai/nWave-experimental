"""Composition-root service for the dispatcher registration-contract AT
(slice-06).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.registration_contract.check_registry`` — the driving port
the gate is authored against (feature-delta slice-plan row 223, DDD-6).

The registry corpus is selected by a typed ``RegistryCorpusKind``:

  * DROPPED_OR_BROKEN → the slice-06 planted-violation golden fixture;
  * FULLY_WIRED       → the slice-06 clean golden fixture;
  * LIVE              → the LIVE ``des.cli.__main__._REGISTRY`` read at runtime
    (DDD-6 — count-agnostic, auto-extending; NEVER the drifting
    SUBCOMMAND_TABLE mirror).

Honest tagging: this is an in-process ``importlib`` resolution of the registry's
rows. It is ``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond importing
the registered modules. (The gate practising the honesty it enforces.)
"""

from __future__ import annotations

from des.testarch.rules.registration_contract import (
    RegistrationVerdict,
    check_registry,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.registration_contract.clean_registry import (
    CLEAN_REGISTRY,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.fixtures.registration_contract.violation_registry import (
    VIOLATION_REGISTRY,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    RegistrationOutcome,
    RegistryCorpusKind,
)


def _live_registry() -> tuple:
    """The LIVE dispatcher registry, read at runtime (DDD-6).

    Read off ``des.cli.__main__._REGISTRY`` — the SSOT the dispatcher fans out
    over — NOT the drifting SUBCOMMAND_TABLE mirror. Reading live keeps the gate
    count-agnostic: it covers whatever rows the dispatcher currently exposes.
    """
    from des.cli.__main__ import _REGISTRY

    return _REGISTRY


# Each corpus kind → the registry the gate is asked to check.
_REGISTRY_BY_KIND = {
    RegistryCorpusKind.DROPPED_OR_BROKEN: VIOLATION_REGISTRY,
    RegistryCorpusKind.FULLY_WIRED: CLEAN_REGISTRY,
}


class RegistrationContractGate:
    """Drives the real registration-contract rule over a named registry corpus."""

    def registry_for(self, corpus: RegistryCorpusKind) -> tuple:
        """The registry rows of the named corpus (port-observable)."""
        if corpus is RegistryCorpusKind.LIVE:
            return _live_registry()
        return _REGISTRY_BY_KIND[corpus]

    def inspect(self, corpus: RegistryCorpusKind) -> RegistrationVerdict:
        """Run the real ``check_registry`` rule over the named registry corpus."""
        return check_registry(self.registry_for(corpus))

    @staticmethod
    def outcome_of(verdict: RegistrationVerdict) -> RegistrationOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return (
            RegistrationOutcome.CONFORMANT
            if verdict.conformant
            else RegistrationOutcome.FLAGGED
        )


def build_gate() -> RegistrationContractGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return RegistrationContractGate()
