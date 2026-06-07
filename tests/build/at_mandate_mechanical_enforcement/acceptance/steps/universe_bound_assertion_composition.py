"""Composition-root service for the M8 universe-bound-assertion gate AT (slice-03).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.assert_state_delta.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading
a fixture file off disk.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.assert_state_delta import AssertStateDeltaVerdict, detect
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    GUARD_CLEAN_CORPUS,
    MISSING_GUARD_CORPUS,
    PRIVATE_LEAK_CORPUS,
    GuardCorpusKind,
    GuardOutcome,
)


_CORPUS_BY_KIND = {
    GuardCorpusKind.MISSING_GUARD: MISSING_GUARD_CORPUS,
    GuardCorpusKind.PRIVATE_LEAK: PRIVATE_LEAK_CORPUS,
    GuardCorpusKind.CLEAN: GUARD_CLEAN_CORPUS,
}


class UniverseBoundAssertionGate:
    """Drives the real M8 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: GuardCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus]

    def inspect(self, corpus: GuardCorpusKind) -> AssertStateDeltaVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus."""
        path = _CORPUS_BY_KIND[corpus]
        source = path.read_text(encoding="utf-8")
        return detect(source, adapter=self._adapter, path=str(path), filename=str(path))

    @staticmethod
    def outcome_of(verdict: AssertStateDeltaVerdict) -> GuardOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return GuardOutcome.FLAGGED if verdict.flagged else GuardOutcome.CLEAN


def build_gate() -> UniverseBoundAssertionGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return UniverseBoundAssertionGate()
