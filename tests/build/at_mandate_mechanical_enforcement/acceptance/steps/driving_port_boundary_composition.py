"""Composition-root service for the M1 driving-port-boundary gate AT (slice-01).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.driving_port_boundary.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@subcutaneous``/``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading
a fixture file off disk.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.driving_port_boundary import BoundaryVerdict, detect
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    CLEAN_CORPUS,
    VIOLATION_CORPUS,
    BoundaryOutcome,
    CorpusKind,
)


_CORPUS_BY_KIND = {
    CorpusKind.PLANTED_VIOLATION: VIOLATION_CORPUS,
    CorpusKind.CLEAN: CLEAN_CORPUS,
}


class DrivingPortBoundaryGate:
    """Drives the real M1 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: CorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus]

    def inspect(self, corpus: CorpusKind) -> BoundaryVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus."""
        path = _CORPUS_BY_KIND[corpus]
        source = path.read_text(encoding="utf-8")
        return detect(source, adapter=self._adapter, filename=str(path))

    @staticmethod
    def outcome_of(verdict: BoundaryVerdict) -> BoundaryOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return BoundaryOutcome.FLAGGED if verdict.flagged else BoundaryOutcome.CLEAN


def build_gate() -> DrivingPortBoundaryGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return DrivingPortBoundaryGate()
