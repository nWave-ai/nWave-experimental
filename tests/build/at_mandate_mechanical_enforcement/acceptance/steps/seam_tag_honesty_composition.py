"""Composition-root service for the CM-I seam-tag-honesty gate AT (slice-05).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoint
``des.testarch.rules.seam_tag_honesty.detect`` through the production
``PythonAstAdapter`` — the driving port the gate is authored against
(ADR-TEST-002 D-C; feature-delta Driving Ports).

Each golden-fixture corpus is read off its real disk path. The CM-I rule keys on
the test's marker tags vs the spawn shape of its body — both STRUCTURAL facts
the adapter supplies; the layer is NOT consulted (CM-I is tag-vs-spawn, not
layer-driven).

Honest tagging: this is an in-process pure-AST query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading a
fixture file off disk. (The gate practising the honesty it enforces.)
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.seam_tag_honesty import SeamTagHonestyVerdict, detect
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    DISHONEST_CORPUS,
    SEAM_HONEST_CORPUS,
    SeamCorpusKind,
    SeamHonestyOutcome,
)


# Each corpus kind → the real disk path of its fixture content.
_CORPUS_BY_KIND = {
    SeamCorpusKind.DISHONEST_WIRING_E2E: DISHONEST_CORPUS,
    SeamCorpusKind.HONEST_TAGS: SEAM_HONEST_CORPUS,
}


class SeamTagHonestyGate:
    """Drives the real CM-I rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: SeamCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        return _CORPUS_BY_KIND[corpus]

    def inspect(self, corpus: SeamCorpusKind) -> SeamTagHonestyVerdict:
        """Run the real ``detect`` rule over the named golden-fixture corpus."""
        disk_path = _CORPUS_BY_KIND[corpus]
        source = disk_path.read_text(encoding="utf-8")
        return detect(source, adapter=self._adapter, filename=str(disk_path))

    @staticmethod
    def outcome_of(verdict: SeamTagHonestyVerdict) -> SeamHonestyOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return (
            SeamHonestyOutcome.FLAGGED if verdict.flagged else SeamHonestyOutcome.HONEST
        )


def build_gate() -> SeamTagHonestyGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return SeamTagHonestyGate()
