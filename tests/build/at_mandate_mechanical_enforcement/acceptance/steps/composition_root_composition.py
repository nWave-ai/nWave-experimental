"""Composition-root service for the P3 composition-root gate AT (slice-09).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.composition_root.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Each golden-fixture corpus is read off its real disk path. The P3 rule keys on
the collaborator-constructing assignments of each step body
(``assignments_constructing_type``) cross-checked against the presence/absence of
a composition-root entry call (``calls_in_function``). ``calls_in_function`` is
already produced by the production adapter (slice-03);
``assignments_constructing_type`` is an enum-registered capability
(``capabilities.py``) NOT yet realized on the adapter — DELIVER's A_GREEN realizes
it + adds the ``ConstructInfo`` port type. NO new capability is added by this
slice (cap 10 pre-exists in the enum + cap-table).

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading a
fixture file off disk. (The gate practising the honesty the suite enforces.)
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.composition_root import (
    CompositionRootVerdict,
    detect,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    COMPOSITION_ROOT_CLEAN_CORPUS,
    HAND_WIRED_CORPUS,
    CompositionCorpusKind,
    CompositionOutcome,
)


# Each corpus kind → the real disk path of its fixture content.
_CORPUS_BY_KIND = {
    CompositionCorpusKind.HAND_WIRED_SUT: HAND_WIRED_CORPUS,
    CompositionCorpusKind.COMPOSITION_ROOT: COMPOSITION_ROOT_CLEAN_CORPUS,
}


class CompositionRootGate:
    """Drives the real P3 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: CompositionCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus]

    def inspect(self, corpus: CompositionCorpusKind) -> CompositionRootVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus."""
        disk_path = _CORPUS_BY_KIND[corpus]
        source = disk_path.read_text(encoding="utf-8")
        return detect(source, adapter=self._adapter, filename=str(disk_path))

    @staticmethod
    def outcome_of(verdict: CompositionRootVerdict) -> CompositionOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return (
            CompositionOutcome.FLAGGED if verdict.flagged else CompositionOutcome.CLEAN
        )


def build_gate() -> CompositionRootGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return CompositionRootGate()
