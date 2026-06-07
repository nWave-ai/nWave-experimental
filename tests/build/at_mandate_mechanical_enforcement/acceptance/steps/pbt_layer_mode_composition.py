"""Composition-root service for the M9/9-v2 PBT-layer-mode gate AT (slice-04).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.pbt_layer_mode.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Each golden-fixture corpus is read off its real disk path, but classified at a
SYNTHETIC representative layer-path (slice-03 pattern), so the gate keys on the
intended layer (3+ forbidden vs 1-2 home) independent of where the fixture file
physically lives under ``acceptance/fixtures/``.

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading
a fixture file off disk.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.pbt_layer_mode import PbtLayerModeVerdict, detect
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    CLEAN_EXAMPLE_AT_LAYER_CORPUS,
    CLEAN_EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH,
    CLEAN_PBT_AT_LAYER_CORPUS,
    CLEAN_PBT_AT_LAYER_REPRESENTATIVE_PATH,
    GIVEN_AT_LAYER_CORPUS,
    GIVEN_AT_LAYER_REPRESENTATIVE_PATH,
    STATE_MACHINE_AT_LAYER_CORPUS,
    STATE_MACHINE_AT_LAYER_REPRESENTATIVE_PATH,
    PbtCorpusKind,
    PbtLayerOutcome,
)


# Each corpus kind → (real disk path of fixture content, synthetic layer-path).
_CORPUS_BY_KIND = {
    PbtCorpusKind.GIVEN_AT_LAYER_3PLUS: (
        GIVEN_AT_LAYER_CORPUS,
        GIVEN_AT_LAYER_REPRESENTATIVE_PATH,
    ),
    PbtCorpusKind.STATE_MACHINE_AT_LAYER_3PLUS: (
        STATE_MACHINE_AT_LAYER_CORPUS,
        STATE_MACHINE_AT_LAYER_REPRESENTATIVE_PATH,
    ),
    PbtCorpusKind.CLEAN_PBT_AT_LAYER_1_2: (
        CLEAN_PBT_AT_LAYER_CORPUS,
        CLEAN_PBT_AT_LAYER_REPRESENTATIVE_PATH,
    ),
    PbtCorpusKind.CLEAN_EXAMPLE_AT_LAYER_3PLUS: (
        CLEAN_EXAMPLE_AT_LAYER_CORPUS,
        CLEAN_EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH,
    ),
}


class PbtLayerModeGate:
    """Drives the real M9/9-v2 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: PbtCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus][0]

    def inspect(self, corpus: PbtCorpusKind) -> PbtLayerModeVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus.

        The fixture content is read off disk; the layer is fixed by the synthetic
        representative path so the gate audits the intended layer.
        """
        disk_path, layer_path = _CORPUS_BY_KIND[corpus]
        source = disk_path.read_text(encoding="utf-8")
        return detect(
            source, adapter=self._adapter, path=layer_path, filename=str(disk_path)
        )

    @staticmethod
    def outcome_of(verdict: PbtLayerModeVerdict) -> PbtLayerOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return PbtLayerOutcome.FLAGGED if verdict.flagged else PbtLayerOutcome.CLEAN


def build_gate() -> PbtLayerModeGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return PbtLayerModeGate()
