"""Composition-root service for the M2 technical-call-smell gate AT (slice-08).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.technical_call_smell.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Each golden-fixture corpus is read off its real disk path. The M2 rule keys on
the dotted callee of each call site in a pytest-bdd step body
(``functions_with_decorator`` + ``calls_in_function``, both already produced by
the production adapter) — NO new capability is added by this slice.

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading a
fixture file off disk. (The gate practising the honesty the suite enforces.)
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.technical_call_smell import (
    TechnicalCallSmellVerdict,
    detect,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    CLEAN_DOMAIN_CORPUS,
    TECHNICAL_ASSERTION_CORPUS,
    TECHNICAL_CALLS_CORPUS,
    TechnicalCallCorpusKind,
    TechnicalCallOutcome,
)


# Each corpus kind → the real disk path of its fixture content.
_CORPUS_BY_KIND = {
    TechnicalCallCorpusKind.TECHNICAL_CALLS: TECHNICAL_CALLS_CORPUS,
    TechnicalCallCorpusKind.TECHNICAL_ASSERTION: TECHNICAL_ASSERTION_CORPUS,
    TechnicalCallCorpusKind.CLEAN_DOMAIN: CLEAN_DOMAIN_CORPUS,
}


class TechnicalCallSmellGate:
    """Drives the real M2 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: TechnicalCallCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus]

    def inspect(self, corpus: TechnicalCallCorpusKind) -> TechnicalCallSmellVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus."""
        disk_path = _CORPUS_BY_KIND[corpus]
        source = disk_path.read_text(encoding="utf-8")
        return detect(source, adapter=self._adapter, filename=str(disk_path))

    @staticmethod
    def outcome_of(verdict: TechnicalCallSmellVerdict) -> TechnicalCallOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return (
            TechnicalCallOutcome.FLAGGED
            if verdict.flagged
            else TechnicalCallOutcome.CLEAN
        )


def build_gate() -> TechnicalCallSmellGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return TechnicalCallSmellGate()
